"""AirScreen wire protocol v1 (see shared/protocol/PROTOCOL.md)."""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass

MAGIC = b"ASCR"
VERSION = 1
HEADER = struct.Struct(">4sBBBBIQI")
HEADER_SIZE = HEADER.size  # 24
MAX_PAYLOAD = 8 * 1024 * 1024

TYPE_HELLO = 1
TYPE_VIDEO = 2
TYPE_BYE = 3

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


def pack_message(msg_type: int, seq: int, pts_us: int, payload: bytes = b"", flags: int = 0) -> bytes:
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError(f"payload too large: {len(payload)}")
    header = HEADER.pack(MAGIC, VERSION, msg_type, flags, 0, seq & 0xFFFFFFFF, pts_us, len(payload))
    return header + payload


def parse_header(data: bytes) -> Header:
    if len(data) != HEADER_SIZE:
        raise ProtocolError("short header")
    magic, version, msg_type, flags, _reserved, seq, pts_us, length = HEADER.unpack(data)
    if magic != MAGIC:
        raise ProtocolError("bad magic")
    if version != VERSION:
        raise ProtocolError(f"unsupported version {version}")
    if msg_type not in (TYPE_HELLO, TYPE_VIDEO, TYPE_BYE):
        raise ProtocolError(f"unknown type {msg_type}")
    if length > MAX_PAYLOAD:
        raise ProtocolError(f"payload too large: {length}")
    return Header(msg_type, flags, seq, pts_us, length)


def hello_payload(width: int, height: int, fps: int) -> bytes:
    return json.dumps({"codec": "h264", "width": width, "height": height, "fps": fps}).encode()
