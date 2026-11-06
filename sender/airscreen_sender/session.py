"""One streaming session: capture (+audio) -> FFmpeg -> encrypted TCP, with automatic reconnection."""
from __future__ import annotations

import dataclasses
from collections import deque
import threading
import time
from typing import Callable

from .audio.pipeline import AudioError, AudioPipeline
from .audio.speaker_mute import SpeakerMute
from .capture.dxcam_capture import DesktopCapture
from .config.settings import Config
from .diagnostics import preflight
from .encoding.ffmpeg_encoder import FfmpegEncoder
from .negotiate import negotiate
from .networking.tcp_sender import AuthError, PairingRequired, TcpSender
from .networking.trust_store import TrustStore


class Transient(Exception):
    """Network-level failure worth retrying."""


class StreamSession:
    def __init__(self, cfg: Config, on_status: Callable[[str], None] = lambda s: None,
                 store: TrustStore | None = None, pairing_code: str | None = None) -> None:
        self.cfg = cfg.validate()
        from .config.settings import resolve_ffmpeg
        self.cfg.ffmpeg_path = resolve_ffmpeg(self.cfg.ffmpeg_path)
        self._status = on_status
        self.store = store or TrustStore()
        self.pairing_code = pairing_code
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.stats: dict[str, float] = {}
        self.error: str | None = None
        self.pairing_required: PairingRequired | None = None
        self._audio: AudioPipeline | None = None
        self.muted = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="stream", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=15)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def set_muted(self, muted: bool) -> None:
        self.muted = muted
        if self._audio:
            self._audio.muted = muted

    # --- outer loop: retry transient failures ---
    def _run(self) -> None:
        attempt = 0
        try:
            while not self._stop.is_set():
                started = time.monotonic()
                try:
                    self._stream_once()
                    break
                except PairingRequired as e:
                    self.pairing_required = e
                    self.error = str(e)
                    self._status(f"{e}. Enter the code shown on the TV.")
                    break
                except AuthError as e:
                    self.error = f"Authentication failed: {e}"
                    self._status(self.error)
                    break
                except Transient as e:
                    if not self.cfg.reconnect:
                        self.error = str(e)
                        self._status(f"Error: {e}")
                        break
                    attempt = 0 if time.monotonic() - started > 10 else attempt + 1
                    delay = min(1.0 * 2 ** min(attempt, 3), 5.0)
                    self._status(f"{e}. Reconnecting in {delay:.0f}s...")
                    self.stats = {}
                    self._stop.wait(delay)
                except Exception as e:
                    self.error = str(e)
                    self._status(f"Error: {e}")
                    break
        finally:
            if not self.error and not self.pairing_required:
                self._status("Disconnected")

    def _stream_once(self) -> None:
        cfg = self.cfg
        capture = encoder = net = audio = None
        speakers = None
        try:
            self._status("Checking encoder...")
            if cfg.encoder == "h264_nvenc":
                chk = preflight.check_nvenc(cfg.ffmpeg_path)
                if not chk.ok:
                    raise RuntimeError(f"NVENC unavailable: {chk.detail}")
            # Connect first (cheap to fail/retry), then start the heavy pipelines.
            self._status(f"Connecting to {cfg.receiver_ip}:{cfg.receiver_port}...")
            capture = DesktopCapture(cfg.monitor, cfg.cursor)
            audio_info = None
            if cfg.audio:
                try:
                    audio = AudioPipeline(cfg.ffmpeg_path, lambda p: net and net.submit_audio(p), cfg.audio_bitrate_kbps)
                    audio_info = audio.start()
                    audio.muted = self.muted
                    self._audio = audio
                except AudioError as e:
                    self._status(f"Audio disabled: {e}")
                    if audio:
                        audio.stop()
                    audio = None

            if audio_info and cfg.mute_pc_audio:
                speakers = SpeakerMute()
                if speakers.engage():
                    self._status("PC speakers muted: sound plays on the TV")
                else:
                    speakers = None

            try:
                net = TcpSender(cfg.receiver_ip, cfg.receiver_port, self.store, self.pairing_code)
            except (PairingRequired, AuthError):
                raise
            except OSError as e:
                raise Transient(f"Cannot reach receiver ({e})") from e

            if cfg.auto_quality:
                ch = negotiate(net.caps, capture.width, capture.height)
                cfg = dataclasses.replace(cfg, width=ch.width, height=ch.height, fps=ch.fps, bitrate_kbps=ch.bitrate_kbps)
                if cfg.force_width and cfg.force_height:
                    cfg = dataclasses.replace(cfg, width=cfg.force_width, height=cfg.force_height)
                if cfg.force_fps:
                    cfg = dataclasses.replace(cfg, fps=cfg.force_fps)
                if cfg.force_bitrate_kbps:
                    cfg = dataclasses.replace(cfg, bitrate_kbps=cfg.force_bitrate_kbps)
                for note in ch.notes:
                    self._status(f"Note: {note}")
            out_w, out_h = (cfg.width, cfg.height) if cfg.width else (capture.width, capture.height)
            net.begin(out_w, out_h, cfg.fps, audio_info)
            cap_times: deque = deque(maxlen=64)
            enc_ms: list = []

            def on_access_unit(au: bytes, key: bool) -> None:
                if cap_times and len(enc_ms) < 500:      # 1 AU per input frame, in order (no B-frames)
                    enc_ms.append((time.monotonic() - cap_times.popleft()) * 1000)
                net.submit_video(au, key)

            encoder = FfmpegEncoder(cfg, capture.width, capture.height, on_access_unit)
            encoder.start()
            self._status(f"Streaming to {net.receiver_name}: {out_w}x{out_h} @ {cfg.fps} fps, "
                         f"{cfg.bitrate_kbps / 1000:.0f} Mbit/s{' + audio' if audio_info else ''}"
                         f" ({'auto' if self.cfg.auto_quality else 'manual'}, {cfg.encoder})")

            interval = 1.0 / cfg.fps
            next_t = time.monotonic()
            last_report, last_bytes, last_frames = next_t, 0, 0
            while not self._stop.is_set():
                if net.error:
                    raise Transient(f"Connection lost ({net.error})")
                frame = capture.grab()
                cap_times.append(time.monotonic())
                encoder.write_frame(frame)
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
                        "audio_packets": audio.packets if audio else 0,
                        "enc_ms": sum(enc_ms) / len(enc_ms) if enc_ms else 0.0,
                        "enc_ms_max": max(enc_ms) if enc_ms else 0.0,
                        "net_ms": sum(net.net_ms) / len(net.net_ms) if net.net_ms else 0.0,
                        "net_ms_max": max(net.net_ms) if net.net_ms else 0.0,
                    }
                    enc_ms.clear(); net.net_ms.clear()
                    last_report, last_bytes, last_frames = now, net.sent_bytes, encoder.frames_in
        finally:
            if speakers:
                speakers.restore()          # always give the PC its sound back
            self._audio = None
            if audio:
                audio.stop()
            if encoder:
                encoder.stop()
            if net:
                net.close()
            if capture:
                capture.close()
