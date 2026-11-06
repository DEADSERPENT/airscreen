"""Demux FFmpeg's FLV output into H.264 access units (Annex B).

Why FLV: every tag carries an explicit size, so a frame is forwarded the instant FFmpeg writes it.
Splitting a raw Annex B stream on access-unit delimiters can only emit a frame when the *next* one begins,
which costs one full frame of latency.
"""
from __future__ import annotations

from typing import Callable, Iterator

START = b"\x00\x00\x00\x01"


class FlvVideoParser:
    def __init__(self, sps_filter: Callable[[bytes], bytes] | None = None) -> None:
        self._buf = bytearray()
        self._header_done = False
        self._nal_len = 4
        self._sps = b""
        self._pps = b""
        self._sps_filter = sps_filter

    def feed(self, chunk: bytes) -> Iterator[tuple[bytes, bool]]:
        """Yield (annexb_access_unit, is_keyframe). Keyframes carry SPS+PPS in front."""
        self._buf += chunk
        if not self._header_done:
            if len(self._buf) < 13:
                return
            if bytes(self._buf[:3]) != b"FLV":
                raise ValueError("encoder output is not FLV")
            offset = int.from_bytes(self._buf[5:9], "big")
            if len(self._buf) < offset + 4:
                return
            del self._buf[: offset + 4]  # header + PreviousTagSize0
            self._header_done = True
        while len(self._buf) >= 11:
            tag_type = self._buf[0]
            size = int.from_bytes(self._buf[1:4], "big")
            total = 11 + size + 4
            if len(self._buf) < total:
                return
            data = bytes(self._buf[11:11 + size])
            del self._buf[:total]
            if tag_type != 9 or len(data) < 5 or (data[0] & 0x0F) != 7:  # video, AVC only
                continue
            key = (data[0] >> 4) == 1
            packet_type = data[1]
            if packet_type == 0:
                self._parse_avcc(data[5:])
            elif packet_type == 1:
                yield self._to_annexb(data[5:], key), key

    def _parse_avcc(self, rec: bytes) -> None:
        self._nal_len = (rec[4] & 0x03) + 1
        pos = 6
        sps_list, pps_list = [], []
        for _ in range(rec[5] & 0x1F):
            n = int.from_bytes(rec[pos:pos + 2], "big")
            sps_list.append(rec[pos + 2:pos + 2 + n])
            pos += 2 + n
        count = rec[pos]
        pos += 1
        for _ in range(count):
            n = int.from_bytes(rec[pos:pos + 2], "big")
            pps_list.append(rec[pos + 2:pos + 2 + n])
            pos += 2 + n
        if self._sps_filter:
            sps_list = [self._sps_filter(s) for s in sps_list]
        self._sps = b"".join(START + s for s in sps_list)
        self._pps = b"".join(START + p for p in pps_list)

    def _to_annexb(self, payload: bytes, key: bool) -> bytes:
        out = bytearray()
        if key:
            out += self._sps + self._pps
        pos, n = 0, self._nal_len
        while pos + n <= len(payload):
            size = int.from_bytes(payload[pos:pos + n], "big")
            pos += n
            out += START + payload[pos:pos + size]
            pos += size
        return bytes(out)
