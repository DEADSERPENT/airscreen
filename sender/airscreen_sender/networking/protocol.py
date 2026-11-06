"""AirScreen wire protocol v2 (see shared/protocol/PROTOCOL.md)."""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass

MAGIC = b"ASCR"
VERSION = 2
HEADER = struct.Struct(">4sBBBBIQI")
HEADER_SIZE = HEADER.size  # 24
MAX_PAYLOAD = 8 * 1024 * 1024
MAX_CONTROL_PAYLOAD = 4096

TYPE_HELLO = 1
TYPE_VIDEO = 2
TYPE_BYE = 3
TYPE_AUDIO = 4
TYPE_AUTH_REQUEST = 5    # sender -> receiver
TYPE_AUTH_CHALLENGE = 6  # receiver -> sender
TYPE_AUTH_PROOF = 7      # sender -> receiver
TYPE_AUTH_OK = 8         # receiver -> sender
TYPE_AUTH_FAIL = 9       # receiver -> sender
ALL_TYPES = frozenset(range(1, 10))
AUTH_TYPES = frozenset(range(5, 10))

FLAG_KEYFRAME = 0x01


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Header:
    type: int
    flags: int
    seq: int
    pts_us: int
    length: int

    @property
    def keyframe(self) -> bool:
        return bool(self.flags & FLAG_KEYFRAME)


def pack_header(msg_type: int, seq: int, pts_us: int, length: int, flags: int = 0) -> bytes:
    if length > MAX_PAYLOAD:
        raise ProtocolError(f"payload too large: {length}")
    return HEADER.pack(MAGIC, VERSION, msg_type, flags, 0, seq & 0xFFFFFFFF, pts_us, length)


def pack_message(msg_type: int, seq: int, pts_us: int, payload: bytes = b"", flags: int = 0) -> bytes:
    return pack_header(msg_type, seq, pts_us, len(payload), flags) + payload


def parse_header(data: bytes) -> Header:
    if len(data) != HEADER_SIZE:
        raise ProtocolError("short header")
    magic, version, msg_type, flags, _reserved, seq, pts_us, length = HEADER.unpack(data)
    if magic != MAGIC:
        raise ProtocolError("bad magic")
    if version != VERSION:
        raise ProtocolError(f"unsupported version {version}")
    if msg_type not in ALL_TYPES:
        raise ProtocolError(f"unknown type {msg_type}")
    if length > MAX_PAYLOAD:
        raise ProtocolError(f"payload too large: {length}")
    if msg_type in AUTH_TYPES and length > MAX_CONTROL_PAYLOAD:
        raise ProtocolError("control payload too large")
    return Header(msg_type, flags, seq, pts_us, length)


def hello_payload(width: int, height: int, fps: int, audio: dict | None = None) -> bytes:
    body: dict = {"codec": "h264", "width": width, "height": height, "fps": fps}
    if audio:
        body["audio"] = audio
    return json.dumps(body).encode()
