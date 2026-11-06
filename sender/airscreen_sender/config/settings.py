"""Sender configuration: JSON-loadable, validated, never silently clamped."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, fields
from pathlib import Path


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    receiver_ip: str = ""
    receiver_port: int = 5000
    monitor: int = 0            # output index on the capture device
    width: int = 1920           # encoded size; 0 = same as source
    height: int = 1080
    fps: int = 30
    bitrate_kbps: int = 12000
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
