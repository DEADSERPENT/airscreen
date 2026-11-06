"""One streaming session: capture -> FFmpeg/NVENC -> TCP. Start/stop controlled from CLI or GUI."""
from __future__ import annotations

import threading
import time
from typing import Callable

from .capture.dxcam_capture import DesktopCapture
from .config.settings import Config
from .diagnostics import preflight
from .encoding.ffmpeg_encoder import FfmpegEncoder
from .networking.tcp_sender import TcpSender


class StreamSession:
    def __init__(self, cfg: Config, on_status: Callable[[str], None] = lambda s: None) -> None:
        self.cfg = cfg.validate()
        self._status = on_status
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.stats: dict[str, float] = {}
        self.error: str | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="stream", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run(self) -> None:
        cfg = self.cfg
        capture = encoder = net = None
        try:
            self._status("Checking encoder...")
            if cfg.encoder == "h264_nvenc":
                chk = preflight.check_nvenc(cfg.ffmpeg_path)
                if not chk.ok:
                    raise RuntimeError(f"NVENC unavailable: {chk.detail}")
            self._status("Starting capture...")
            capture = DesktopCapture(cfg.monitor)
            self._status(f"Connecting to {cfg.receiver_ip}:{cfg.receiver_port}...")
            out_w, out_h = (cfg.width, cfg.height) if cfg.width else (capture.width, capture.height)
            net = TcpSender(cfg.receiver_ip, cfg.receiver_port, out_w, out_h, cfg.fps)
            encoder = FfmpegEncoder(cfg, capture.width, capture.height, net.submit)
            encoder.start()
            self._status(f"Streaming {out_w}x{out_h} @ {cfg.fps} fps ({cfg.encoder})")

            interval = 1.0 / cfg.fps
            next_t = time.monotonic()
            last_report, last_bytes, last_frames = next_t, 0, 0
            while not self._stop.is_set():
                if net.error:
                    raise RuntimeError(f"connection lost: {net.error}")
                encoder.write_frame(capture.grab())
                next_t += interval
                delay = next_t - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_t = time.monotonic()  # fell behind; don't try to catch up with a burst
                now = time.monotonic()
                if now - last_report >= 1.0:
                    dt = now - last_report
                    self.stats = {
                        "fps_in": (encoder.frames_in - last_frames) / dt,
                        "mbps": (net.sent_bytes - last_bytes) * 8 / dt / 1e6,
                        "dropped": net.dropped,
                        "capture_errors": capture.errors,
                    }
                    last_report, last_bytes, last_frames = now, net.sent_bytes, encoder.frames_in
        except Exception as e:
            self.error = str(e)
            self._status(f"Error: {e}")
        finally:
            if encoder:
                encoder.stop()
            if net:
                net.close()
            if capture:
                capture.close()
            if not self.error:
                self._status("Disconnected")
