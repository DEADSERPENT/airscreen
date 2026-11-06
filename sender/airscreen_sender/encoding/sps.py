"""Rewrite an H.264 SPS so decoders know the stream needs no frame reordering.

Hardware decoders (this TV's Realtek one) assume the worst when the SPS has no `bitstream_restriction` VUI:
they hold back up to a full DPB of frames before output (~4 frames at 1080p = ~120 ms at 30 fps).
We declare max_num_reorder_frames = 0 and a small max_dec_frame_buffering, which the stream truly satisfies
(no B-frames), so the decoder can output each frame immediately.
"""
from __future__ import annotations


class _Bits:
    def __init__(self, data: bytes) -> None:
        self.d, self.pos = data, 0

    def bit(self) -> int:
        b = (self.d[self.pos >> 3] >> (7 - (self.pos & 7))) & 1
        self.pos += 1
        return b

    def u(self, n: int) -> int:
        v = 0
        for _ in range(n):
            v = (v << 1) | self.bit()
        return v

    def ue(self) -> int:
        zeros = 0
        while self.bit() == 0:
            zeros += 1
        return (1 << zeros) - 1 + self.u(zeros)

    def se(self) -> int:
        k = self.ue()
        return (k + 1) // 2 if k & 1 else -(k // 2)


def _unescape(nal_payload: bytes) -> bytes:
    out, zeros = bytearray(), 0
    for b in nal_payload:
        if zeros >= 2 and b == 3:
            zeros = 0
            continue
        out.append(b)
        zeros = zeros + 1 if b == 0 else 0
    return bytes(out)


def _escape(rbsp: bytes) -> bytes:
    out, zeros = bytearray(), 0
    for b in rbsp:
        if zeros >= 2 and b <= 3:
            out.append(3)
            zeros = 0
        out.append(b)
        zeros = zeros + 1 if b == 0 else 0
    return bytes(out)


def _ue_bits(v: int) -> str:
    v += 1
    n = v.bit_length()
    return "0" * (n - 1) + format(v, "b")


def _skip_scaling_list(r: _Bits, size: int) -> None:
    last = nxt = 8
    for _ in range(size):
        if nxt != 0:
            nxt = (last + r.se() + 256) % 256
        last = last if nxt == 0 else nxt


def _skip_hrd(r: _Bits) -> None:
    cpb_cnt = r.ue() + 1
    r.u(8)
    for _ in range(cpb_cnt):
        r.ue(); r.ue(); r.u(1)
    r.u(20)


def _restriction_bits(max_refs: int) -> str:
    return ("1" + "1" + _ue_bits(0) + _ue_bits(0) + _ue_bits(15) + _ue_bits(15)
            + _ue_bits(0) + _ue_bits(max(max_refs, 1)))


def patch_sps(sps_nal: bytes) -> bytes:
    """Return the SPS NAL (with its 1-byte header) declaring no reordering. On any parse problem return it unchanged."""
    try:
        header, rbsp = sps_nal[:1], _unescape(sps_nal[1:])
        r = _Bits(rbsp)
        profile = r.u(8); r.u(8); r.u(8)
        r.ue()
        if profile in (100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 139, 134, 135):
            chroma = r.ue()
            if chroma == 3:
                r.u(1)
            r.ue(); r.ue(); r.u(1)
            if r.u(1):
                for i in range(8 if chroma != 3 else 12):
                    if r.u(1):
                        _skip_scaling_list(r, 16 if i < 6 else 64)
        r.ue()
        poc = r.ue()
        if poc == 0:
            r.ue()
        elif poc == 1:
            r.u(1); r.se(); r.se()
            for _ in range(r.ue()):
                r.se()
        max_refs = r.ue()
        r.u(1); r.ue(); r.ue()
        if not r.u(1):
            r.u(1)
        r.u(1)
        if r.u(1):
            r.ue(); r.ue(); r.ue(); r.ue()
        vui_flag_pos = r.pos
        bits = "".join(format(b, "08b") for b in rbsp)
        if not r.u(1):  # no VUI at all: add a minimal one that only carries the restriction
            tail = "1" + "0" * 7 + _restriction_bits(max_refs)
            new = bits[:vui_flag_pos] + tail
        else:
            if r.u(1):
                if r.u(8) == 255:
                    r.u(16); r.u(16)
            if r.u(1):
                r.u(1)
            if r.u(1):
                r.u(4)
                if r.u(1):
                    r.u(24)
            if r.u(1):
                r.ue(); r.ue()
            if r.u(1):
                r.u(32); r.u(32); r.u(1)
            nal_hrd = r.u(1)
            if nal_hrd:
                _skip_hrd(r)
            vcl_hrd = r.u(1)
            if vcl_hrd:
                _skip_hrd(r)
            if nal_hrd or vcl_hrd:
                r.u(1)
            r.u(1)
            new = bits[:r.pos] + _restriction_bits(max_refs)
        new += "1"                               # rbsp_stop_one_bit
        new += "0" * (-len(new) % 8)
        out = bytes(int(new[i:i + 8], 2) for i in range(0, len(new), 8))
        return header + _escape(out)
    except Exception:
        return sps_nal


def read_restriction(sps_nal: bytes) -> tuple[int, int] | None:
    """(max_num_reorder_frames, max_dec_frame_buffering) if the SPS carries them, else None. Used by tests."""
    try:
        rbsp = _unescape(sps_nal[1:])
        r = _Bits(rbsp)
        profile = r.u(8); r.u(8); r.u(8); r.ue()
        if profile in (100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 139, 134, 135):
            chroma = r.ue()
            if chroma == 3:
                r.u(1)
            r.ue(); r.ue(); r.u(1)
            if r.u(1):
                for i in range(8 if chroma != 3 else 12):
                    if r.u(1):
                        _skip_scaling_list(r, 16 if i < 6 else 64)
        r.ue(); poc = r.ue()
        if poc == 0:
            r.ue()
        elif poc == 1:
            r.u(1); r.se(); r.se()
            for _ in range(r.ue()):
                r.se()
        r.ue(); r.u(1); r.ue(); r.ue()
        if not r.u(1):
            r.u(1)
        r.u(1)
        if r.u(1):
            r.ue(); r.ue(); r.ue(); r.ue()
        if not r.u(1):
            return None
        if r.u(1):
            if r.u(8) == 255:
                r.u(16); r.u(16)
        if r.u(1):
            r.u(1)
        if r.u(1):
            r.u(4)
            if r.u(1):
                r.u(24)
        if r.u(1):
            r.ue(); r.ue()
        if r.u(1):
            r.u(32); r.u(32); r.u(1)
        nal = r.u(1)
        if nal:
            _skip_hrd(r)
        vcl = r.u(1)
        if vcl:
            _skip_hrd(r)
        if nal or vcl:
            r.u(1)
        r.u(1)
        if not r.u(1):
            return None
        r.u(1); r.ue(); r.ue(); r.ue(); r.ue()
        return r.ue(), r.ue()
    except Exception:
        return None
