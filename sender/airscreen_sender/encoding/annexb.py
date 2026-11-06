"""Split a raw H.264 Annex B byte stream into access units.

The encoder is run with access-unit delimiters enabled (`-aud 1`), so every access unit
starts with a NAL of type 9. An access unit is emitted when the next delimiter begins.
"""
from __future__ import annotations

from typing import Iterator

NAL_SLICE_IDR = 5
NAL_AUD = 9


def _nal_type(data: bytes | bytearray, start_code_end: int) -> int:
    return data[start_code_end] & 0x1F


class AccessUnitSplitter:
    def __init__(self) -> None:
        self._buf = bytearray()
        self._scan_from = 0

    def feed(self, chunk: bytes) -> Iterator[tuple[bytes, bool]]:
        """Feed bytes; yield (access_unit, is_keyframe) for each completed access unit."""
        self._buf += chunk
        buf = self._buf
        while True:
            # Find the next AUD start code after position 0 (position 0 is the current AU's own AUD).
            idx = self._find_next_aud(buf, self._scan_from)
            if idx < 0:
                # Resume scanning near the end next time (a start code may straddle chunks).
                self._scan_from = max(0, len(buf) - 4)
                return
            au = bytes(buf[:idx])
            del buf[:idx]
            self._scan_from = 4
            if au:
                yield au, self._is_keyframe(au)

    @staticmethod
    def _find_next_aud(buf: bytearray, start: int) -> int:
        """Return index of the start code (00 00 01 or 00 00 00 01) of the next AUD NAL beyond index 0."""
        pos = max(start, 4)  # skip the current access unit's own leading start code + NAL header
        while True:
            i = buf.find(b"\x00\x00\x01", pos)
            if i < 0 or i + 3 >= len(buf):
                return -1
            if buf[i + 3] & 0x1F == NAL_AUD:
                # Include a leading zero byte if this is a 4-byte start code.
                return i - 1 if i > 0 and buf[i - 1] == 0 else i
            pos = i + 3

    @staticmethod
    def _is_keyframe(au: bytes) -> bool:
        pos = 0
        while True:
            i = au.find(b"\x00\x00\x01", pos)
            if i < 0 or i + 3 >= len(au):
                return False
            if _nal_type(au, i + 3) == NAL_SLICE_IDR:
                return True
            pos = i + 3
