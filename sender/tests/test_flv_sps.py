"""FLV framing + SPS low-latency patch, verified against a real NVENC stream (skipped if FFmpeg/NVENC is unavailable)."""
import shutil
import subprocess

import pytest

from airscreen_sender.encoding.flv import FlvVideoParser
from airscreen_sender.encoding.sps import patch_sps, read_restriction

FFMPEG = shutil.which("ffmpeg") or r"C:\ffmpeg\ffmpeg.exe"


def _encode_flv(frames=45) -> bytes:
    p = subprocess.run(
        [FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30",
         "-frames:v", str(frames), "-c:v", "h264_nvenc", "-bf", "0", "-g", "30", "-flvflags", "no_duration_filesize",
         "-f", "flv", "pipe:1"], capture_output=True, timeout=60)
    if p.returncode != 0 or not p.stdout:
        pytest.skip("FFmpeg/NVENC not available")
    return p.stdout


def test_flv_yields_every_frame_and_keyframes():
    data = _encode_flv(45)
    parser = FlvVideoParser()
    aus = []
    for i in range(0, len(data), 1000):          # feed in awkward chunks, like a pipe would
        aus += list(parser.feed(data[i:i + 1000]))
    assert len(aus) == 45
    assert aus[0][1] is True and aus[30][1] is True           # IDR every 30 frames
    assert aus[0][0].startswith(b"\x00\x00\x00\x01") and b"\x00\x00\x00\x01\x67" in aus[0][0]  # SPS in front of keyframes


def test_patched_sps_declares_no_reordering_and_still_decodes(tmp_path):
    data = _encode_flv(45)
    plain = FlvVideoParser()
    patched = FlvVideoParser(sps_filter=patch_sps)
    list(plain.feed(data))
    aus = list(patched.feed(data))
    sps_plain = plain._sps[4:]
    sps_patched = patched._sps[4:]
    assert read_restriction(sps_patched) is not None
    assert read_restriction(sps_patched)[0] == 0                # max_num_reorder_frames = 0
    assert read_restriction(sps_patched)[1] >= 1                # max_dec_frame_buffering
    out = tmp_path / "patched.h264"
    out.write_bytes(b"".join(a for a, _ in aus))
    r = subprocess.run([FFMPEG, "-v", "error", "-i", str(out), "-f", "null", "-"], capture_output=True, text=True)
    assert r.returncode == 0 and r.stderr.strip() == ""         # ffmpeg decodes every frame with no complaint
    probe = subprocess.run([FFMPEG, "-hide_banner", "-i", str(out), "-f", "null", "-"], capture_output=True, text=True).stderr
    assert "frame=   45" in probe or "frame=45" in probe.replace(" ", "")


def test_patch_is_safe_on_garbage():
    assert patch_sps(b"\x67\xff") == b"\x67\xff" or isinstance(patch_sps(b"\x67\xff"), bytes)
