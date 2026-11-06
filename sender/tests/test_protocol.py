import pytest

from airscreen_sender.networking import protocol as p


def test_roundtrip():
    msg = p.pack_message(p.TYPE_VIDEO, 7, 123456, b"abc", p.FLAG_KEYFRAME)
    h = p.parse_header(msg[: p.HEADER_SIZE])
    assert (h.type, h.seq, h.pts_us, h.length, h.keyframe) == (p.TYPE_VIDEO, 7, 123456, 3, True)
    assert msg[p.HEADER_SIZE:] == b"abc"


@pytest.mark.parametrize("mutate", [
    lambda b: b"XXXX" + b[4:],               # bad magic
    lambda b: b[:4] + b"\x09" + b[5:],       # bad version
    lambda b: b[:5] + b"\x63" + b[6:],       # unknown type
    lambda b: b[:20] + b"\xff\xff\xff\xff",  # oversized length
    lambda b: b[:10],                        # short header
])
def test_malformed_rejected(mutate):
    good = p.pack_message(p.TYPE_VIDEO, 0, 0, b"")[: p.HEADER_SIZE]
    with pytest.raises(p.ProtocolError):
        p.parse_header(mutate(good))
