"""System audio: WASAPI loopback -> FFmpeg libopus (20 ms packets) -> callback per Opus packet.

WASAPI loopback delivers nothing while the PC is silent, so the feeder pads with zeros to keep a
continuous timeline (otherwise the encoder - and the TV's audio clock - would stall).
"""
from __future__ import annotations

import base64
import subprocess
import threading
import time
from collections import deque
from typing import Callable

from .ogg import OggPacketParser, parse_opus_head


class AudioError(RuntimeError):
    pass


class AudioPipeline:
    def __init__(self, ffmpeg: str, on_packet: Callable[[bytes], None], bitrate_kbps: int = 128) -> None:
        self._ffmpeg = ffmpeg
        self._on_packet = on_packet
        self._bitrate = bitrate_kbps
        self.muted = False
        self._running = False
        self._pcm: deque[bytes] = deque()
        self._pcm_lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._pa = None
        self._stream = None
        self._threads: list[threading.Thread] = []
        self._head_ready = threading.Event()
        self.info: dict | None = None  # filled once the encoder emits OpusHead
        self.packets = 0

    def start(self) -> dict:
        """Start capturing/encoding. Returns the audio description for HELLO."""
        try:
            import pyaudiowpatch as pa
            self._pa = pa.PyAudio()
            dev = self._pa.get_default_wasapi_loopback()
        except Exception as e:
            raise AudioError(f"no WASAPI loopback device: {e}") from e
        rate, channels = int(dev["defaultSampleRate"]), int(dev["maxInputChannels"])
        self._rate, self._channels = rate, channels

        cmd = [self._ffmpeg, "-hide_banner", "-loglevel", "error", "-nostats",
               "-f", "s16le", "-ar", str(rate), "-ac", str(channels), "-i", "pipe:0",
               "-ar", "48000", "-ac", "2", "-c:a", "libopus", "-b:a", f"{self._bitrate}k",
               "-application", "lowdelay", "-frame_duration", "20", "-vbr", "off",
               "-page_duration", "20000", "-flush_packets", "1", "-f", "ogg", "pipe:1"]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      bufsize=0, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self._running = True
        for fn in (self._read_opus, self._feed):
            t = threading.Thread(target=fn, daemon=True)
            t.start()
            self._threads.append(t)

        def callback(in_data, frame_count, time_info, status):
            with self._pcm_lock:
                self._pcm.append(in_data)
                while len(self._pcm) > 200:  # bounded: ~2 s at 10 ms buffers
                    self._pcm.popleft()
            return (None, pa.paContinue)

        self._stream = self._pa.open(format=pa.paInt16, channels=channels, rate=rate, input=True,
                                     input_device_index=dev["index"], frames_per_buffer=rate // 100,
                                     stream_callback=callback)
        if not self._head_ready.wait(timeout=5):
            raise AudioError("audio encoder produced no header: " + self._stderr_text())
        return self.info  # type: ignore[return-value]

    def _stderr_text(self) -> str:
        try:
            self._proc.kill()
            return self._proc.stderr.read().decode(errors="replace")[-300:]
        except Exception:
            return "unknown error"

    def _feed(self) -> None:
        bpf = 2 * self._channels
        start = time.monotonic()
        written = 0
        while self._running:
            time.sleep(0.01)
            with self._pcm_lock:
                data = b"".join(self._pcm)
                self._pcm.clear()
            expected = int((time.monotonic() - start) * self._rate)  # frames the timeline calls for
            if self.muted:
                data = b"\x00" * (max(0, expected - written) * bpf)
            else:
                short = expected - (written + len(data) // bpf)
                if short > self._rate // 50:  # >20 ms behind (silent PC): pad with silence
                    data += b"\x00" * (short * bpf)
            if not data:
                continue
            try:
                self._proc.stdin.write(data)
            except (OSError, ValueError):
                return
            written += len(data) // bpf

    def _read_opus(self) -> None:
        parser = OggPacketParser()
        seen = 0
        while True:
            chunk = self._proc.stdout.read(4096)
            if not chunk:
                return
            for pkt in parser.feed(chunk):
                seen += 1
                if seen == 1:  # OpusHead
                    h = parse_opus_head(pkt)
                    self.info = {"codec": "opus", "rate": h["rate"], "channels": h["channels"],
                                 "head": base64.b64encode(pkt).decode()}
                    self._head_ready.set()
                elif seen == 2:  # OpusTags
                    continue
                elif self._running:
                    self.packets += 1
                    self._on_packet(pkt)

    def stop(self) -> None:
        self._running = False
        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
            if self._pa:
                self._pa.terminate()
        except Exception:
            pass
        if self._proc:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        for t in self._threads:
            t.join(timeout=1)
