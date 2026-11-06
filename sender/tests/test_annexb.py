from airscreen_sender.encoding.annexb import AccessUnitSplitter

AUD = b"\x00\x00\x00\x01\x09\x10"
SPS = b"\x00\x00\x00\x01\x67\x42\x00\x1f"
PPS = b"\x00\x00\x00\x01\x68\xce\x3c\x80"
IDR = b"\x00\x00\x00\x01\x65\x88\x84\x00"
P = b"\x00\x00\x01\x41\x9a\x00\x10"  # 3-byte start code

KEY_AU = AUD + SPS + PPS + IDR
P_AU = AUD + P


def collect(chunks):
    s, out = AccessUnitSplitter(), []
    for c in chunks:
        out += list(s.feed(c))
    return out


def test_splits_and_flags_keyframes():
    out = collect([KEY_AU + P_AU + P_AU + AUD])
    assert [k for _, k in out] == [True, False, False]
    assert out[0][0] == KEY_AU and out[1][0] == P_AU


def test_byte_at_a_time_matches_whole():
    stream = KEY_AU + P_AU + P_AU + KEY_AU + AUD
    whole = collect([stream])
    trickle = collect([stream[i:i + 1] for i in range(len(stream))])
    assert whole == trickle and len(whole) == 4


def test_incomplete_au_not_emitted():
    assert collect([KEY_AU]) == []
