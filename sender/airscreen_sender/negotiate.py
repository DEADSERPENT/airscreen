"""Pick the best stream settings the whole chain can sustain (receiver decoder/display/link, capture pipe).

Receiver capabilities arrive in AUTH_CHALLENGE["caps"]:
  {"video": {"modes": [{"w":3840,"h":2160,"fps":30}, ...]},        # H.264 decoder, largest first
   "display": {"w":3840,"h":2160,"refresh":60},
   "net": {"type":"wifi"|"ethernet"|"unknown", "link_mbps": 866},
   "audio": {"max_channels":2}}
Resolution is preferred over frame rate (desktop text), but never below 30 fps.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# DXcam hands raw BGRA frames to FFmpeg through a pipe; beyond this the pipe, not the GPU, is the limit.
# (Replaced by a GPU capture path in a later milestone.)
MAX_PIPE_MBYTES_PER_S = 600
BITS_PER_PIXEL = 0.15          # H.264 desktop content at "high quality"
MIN_KBPS, MAX_KBPS = 4_000, 80_000
LINK_SHARE = 0.4               # never plan to use more than 40% of the reported link speed
FALLBACK_MODES = [{"w": 1920, "h": 1080, "fps": 30}]


@dataclass
class Choice:
    width: int
    height: int
    fps: int
    bitrate_kbps: int
    notes: list[str] = field(default_factory=list)


def _even(v: float) -> int:
    return int(v) // 2 * 2


def negotiate(caps: dict | None, src_w: int, src_h: int, src_refresh: int = 60) -> Choice:
    notes: list[str] = []
    caps = caps or {}
    modes = (caps.get("video") or {}).get("modes") or []
    if not modes:
        modes = FALLBACK_MODES
        notes.append("receiver reported no decoder info: assuming 1080p30")
    disp = caps.get("display") or {}
    max_w = min(src_w, disp.get("w") or src_w)
    max_h = min(src_h, disp.get("h") or src_h)
    refresh = min(src_refresh, int(disp.get("refresh") or src_refresh), 60)

    pipe_fps = int(MAX_PIPE_MBYTES_PER_S * 1e6 / (src_w * src_h * 4))
    candidates = []
    for m in modes:
        # fit the source's aspect ratio inside both the decoder mode and the display; never upscale
        scale = min(m["w"] / src_w, m["h"] / src_h, max_w / src_w, max_h / src_h, 1.0)
        w, h = _even(src_w * scale), _even(src_h * scale)
        fps = max(1, min(m["fps"], refresh, pipe_fps))
        candidates.append((w, h, fps, m["fps"] > pipe_fps and pipe_fps < min(m["fps"], refresh)))
    smooth = [c for c in candidates if c[2] >= 30] or candidates
    if not [c for c in candidates if c[2] >= 30]:
        notes.append("no mode reaches 30 fps")
    # resolution first, then frame rate
    w, h, fps, pipe_limited = max(smooth, key=lambda c: (c[0] * c[1], c[2]))
    if pipe_limited:
        notes.append(f"capture pipe limits {src_w}x{src_h} to {pipe_fps} fps")

    kbps = int(w * h * fps * BITS_PER_PIXEL / 1000)
    kbps = max(MIN_KBPS, min(MAX_KBPS, kbps))
    link = (caps.get("net") or {}).get("link_mbps")
    if link:
        budget = int(link * 1000 * LINK_SHARE)
        if budget < kbps:
            kbps = max(MIN_KBPS, budget)
            notes.append(f"bitrate limited by {link} Mbit/s link")
    net_type = (caps.get("net") or {}).get("type")
    if net_type == "wifi" and fps > 30:
        notes.append("receiver is on Wi-Fi: Ethernet is more reliable for 60 fps")
    return Choice(w, h, fps, kbps, notes)
