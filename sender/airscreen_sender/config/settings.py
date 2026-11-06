"""Sender configuration: JSON-loadable, validated, never silently clamped."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, fields
from pathlib import Path


class ConfigError(ValueError):
    pass


def resolve_ffmpeg(configured: str = "ffmpeg") -> str:
    """Find ffmpeg: explicit path, next to the app (installed build), PATH, then common locations."""
    import shutil
    import sys
    if configured and configured != "ffmpeg" and Path(configured).exists():
        return configured
    here = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    for cand in (here / "ffmpeg.exe", here / "ffmpeg" / "ffmpeg.exe"):
        if cand.exists():
            return str(cand)
    found = shutil.which("ffmpeg")
    if found:
        return found
    for cand in (Path("C:/ffmpeg/ffmpeg.exe"), Path("C:/ffmpeg/bin/ffmpeg.exe")):
        if cand.exists():
            return str(cand)
    return configured


@dataclass
class Config:
    receiver_ip: str = ""
    receiver_port: int = 5000
    monitor: int = 0            # output index on the capture device
    auto_quality: bool = True   # negotiate the best resolution/fps/bitrate with the receiver
    width: int = 1920           # encoded size; 0 = same as source
    height: int = 1080
    fps: int = 30
    bitrate_kbps: int = 12000
    force_width: int = 0        # per-field overrides on top of auto quality (0 = let auto decide)
    force_height: int = 0
    force_fps: int = 0
    force_bitrate_kbps: int = 0
    cursor: bool = True
    audio: bool = True
    audio_bitrate_kbps: int = 192
    mute_pc_audio: bool = True  # sound plays on the TV only while streaming
    reconnect: bool = True      # keep retrying after a network interruption
    ffmpeg_path: str = "ffmpeg"
    encoder: str = "h264_nvenc"
    allow_cpu_fallback: bool = False  # never fall back to CPU encoding silently

    def validate(self) -> "Config":
        if not (1 <= self.receiver_port <= 65535):
            raise ConfigError(f"receiver_port out of range: {self.receiver_port}")
        if not (1 <= self.fps <= 240):
            raise ConfigError(f"fps must be 1..240, got {self.fps}")
        if (self.width == 0) != (self.height == 0):
            raise ConfigError("width and height must both be 0 (source size) or both set")
        if self.width:
            if not (16 <= self.width <= 8192 and 16 <= self.height <= 8192):
                raise ConfigError(f"resolution out of range: {self.width}x{self.height}")
            if self.width % 2 or self.height % 2:
                raise ConfigError("width and height must be even for H.264 4:2:0")
        if not (100 <= self.bitrate_kbps <= 500_000):
            raise ConfigError(f"bitrate_kbps out of range: {self.bitrate_kbps}")
        if not (32 <= self.audio_bitrate_kbps <= 510):
            raise ConfigError(f"audio_bitrate_kbps out of range: {self.audio_bitrate_kbps}")
        if self.encoder not in ("h264_nvenc", "libx264"):
            raise ConfigError(f"unsupported encoder: {self.encoder}")
        if self.encoder == "libx264" and not self.allow_cpu_fallback:
            raise ConfigError("libx264 (CPU) requires allow_cpu_fallback=true")
        return self

    @classmethod
    def from_file(cls, path: str | Path) -> "Config":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise ConfigError(f"cannot read config {path}: {e}") from e
        known = {f.name for f in fields(cls)}
        unknown = set(raw) - known
        if unknown:
            raise ConfigError(f"unknown config keys: {sorted(unknown)}")
        return cls(**raw).validate()

    def to_dict(self) -> dict:
        return asdict(self)
