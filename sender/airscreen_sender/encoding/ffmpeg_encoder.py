"""FFmpeg subprocess encoder: raw BGRA frames in on stdin, Annex B H.264 access units out."""
from __future__ import annotations

import subprocess
import threading
from collections import deque
from typing import Callable

from ..config.settings import Config
from .annexb import AccessUnitSplitter


def build_command(cfg: Config, src_w: int, src_h: int) -> list[str]:
    out_w, out_h = (cfg.width, cfg.height) if cfg.width else (src_w, src_h)
    vf = []
    if (out_w, out_h) != (src_w, src_h):
        vf.append(f"scale={out_w}:{out_h}:flags=fast_bilinear")
    vf.append("format=nv12")
    cmd = [
        cfg.ffmpeg_path, "-hide_banner", "-loglevel", "warning", "-nostats",
        "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{src_w}x{src_h}", "-framerate", str(cfg.fps),
        "-i", "pipe:0",
        "-vf", ",".join(vf),
        "-c:v", cfg.encoder,
    ]
    if cfg.encoder == "h264_nvenc":
        cmd += [
            "-preset", "p3", "-tune", "ull", "-profile:v", "high", "-rc", "cbr",
            "-b:v", f"{cfg.bitrate_kbps}k", "-maxrate", f"{cfg.bitrate_kbps}k",
            "-bufsize", f"{cfg.bitrate_kbps // cfg.fps * 2}k",  # ~2 frames: low latency
            "-bf", "0", "-g", str(cfg.fps), "-forced-idr", "1", "-aud", "1", "-zerolatency", "1",
        ]
    else:  # libx264, only reachable with allow_cpu_fallback
        cmd += [
            "-preset", "ultrafast", "-tune", "zerolatency", "-profile:v", "high",
            "-b:v", f"{cfg.bitrate_kbps}k", "-maxrate", f"{cfg.bitrate_kbps}k",
            "-bufsize", f"{cfg.bitrate_kbps // cfg.fps * 2}k", "-g", str(cfg.fps), "-bf", "0",
            "-x264-params", "aud=1",
        ]
    # Repeat SPS/PPS in front of every keyframe so a receiver can join/recover at any IDR.
    cmd += ["-bsf:v", "dump_extra=freq=keyframe", "-f", "h264", "pipe:1"]
    return cmd


class FfmpegEncoder:
    def __init__(self, cfg: Config, src_w: int, src_h: int, on_access_unit: Callable[[bytes, bool], None]) -> None:
        self.cmd = build_command(cfg, src_w, src_h)
        self.out_size = (cfg.width, cfg.height) if cfg.width else (src_w, src_h)
        self._on_au = on_access_unit
        self._proc: subprocess.Popen | None = None
        self._stderr_tail: deque[str] = deque(maxlen=20)
        self._threads: list[threading.Thread] = []
        self.frames_in = 0
        self.access_units_out = 0
        self.bytes_out = 0

    def start(self) -> None:
        self._proc = subprocess.Popen(
            self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for target in (self._read_stdout, self._read_stderr):
            t = threading.Thread(target=target, daemon=True)
            t.start()
            self._threads.append(t)

    def write_frame(self, frame) -> None:
        """Blocks if FFmpeg is behind (natural backpressure). Raises on encoder death."""
        if self._proc is None or self._proc.poll() is not None:
            raise RuntimeError(f"encoder exited: {self.error_summary()}")
        try:
            self._proc.stdin.write(memoryview(frame).cast("B"))
        except (BrokenPipeError, OSError) as e:
            raise RuntimeError(f"encoder pipe closed: {self.error_summary()}") from e
        self.frames_in += 1

    def _read_stdout(self) -> None:
        splitter = AccessUnitSplitter()
        stdout = self._proc.stdout
        while True:
            chunk = stdout.read(65536)
            if not chunk:
                break
            for au, key in splitter.feed(chunk):
                self.access_units_out += 1
                self.bytes_out += len(au)
                self._on_au(au, key)

    def _read_stderr(self) -> None:
        for line in iter(self._proc.stderr.readline, b""):
            self._stderr_tail.append(line.decode(errors="replace").rstrip())

    def error_summary(self) -> str:
        return " | ".join(self._stderr_tail) or "no output from ffmpeg"

    def stop(self) -> None:
        p = self._proc
        if p is None:
            return
        try:
            p.stdin.close()
        except OSError:
            pass
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
        for t in self._threads:
            t.join(timeout=2)
        self._proc = None
