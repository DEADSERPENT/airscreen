"""Minimal Ogg demuxer: yields complete packets from a byte stream (used for libopus output)."""
from __future__ import annotations

from typing import Iterator


class OggPacketParser:
    def __init__(self) -> None:
        self._buf = bytearray()
        self._partial = bytearray()  # packet continued across segments/pages

    def feed(self, chunk: bytes) -> Iterator[bytes]:
        self._buf += chunk
        while True:
            buf = self._buf
            if len(buf) < 27:
                return
            if buf[:4] != b"OggS":
                # resync to the next capture pattern
                i = buf.find(b"OggS", 1)
                del buf[: i if i > 0 else len(buf) - 3]
                continue
            nsegs = buf[26]
            if len(buf) < 27 + nsegs:
                return
            lacing = buf[27:27 + nsegs]
            body_len = sum(lacing)
            total = 27 + nsegs + body_len
            if len(buf) < total:
                return
            pos = 27 + nsegs
            for lace in lacing:
                self._partial += buf[pos:pos + lace]
                pos += lace
                if lace < 255:  # packet ends here
                    pkt = bytes(self._partial)
                    self._partial.clear()
                    yield pkt
            del buf[:total]


def opus_head(channels: int, preskip: int, rate: int) -> bytes:
    return b"OpusHead" + bytes([1, channels]) + preskip.to_bytes(2, "little") + rate.to_bytes(4, "little") + b"\x00\x00\x00"


def parse_opus_head(pkt: bytes) -> dict:
    if not pkt.startswith(b"OpusHead") or len(pkt) < 19:
        raise ValueError("not an OpusHead packet")
    return {"channels": pkt[9], "preskip": int.from_bytes(pkt[10:12], "little"),
            "rate": int.from_bytes(pkt[12:16], "little")}
