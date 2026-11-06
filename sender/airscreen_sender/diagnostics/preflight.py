"""Milestone 0 checks: FFmpeg, NVENC, GPU, receiver reachability."""
from __future__ import annotations

import shutil
import socket
import subprocess
from dataclasses import dataclass


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _run(cmd: list[str], timeout: float = 15) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout


def check_ffmpeg(ffmpeg: str = "ffmpeg") -> Check:
    path = shutil.which(ffmpeg)
    if not path:
        return Check("ffmpeg", False, f"'{ffmpeg}' not found on PATH")
    first = _run([path, "-hide_banner", "-version"]).splitlines()[:1]
    return Check("ffmpeg", True, f"{path} ({first[0] if first else 'unknown version'})")


def check_nvenc(ffmpeg: str = "ffmpeg") -> Check:
    path = shutil.which(ffmpeg)
    if not path:
        return Check("h264_nvenc", False, "ffmpeg missing")
    if "h264_nvenc" not in _run([path, "-hide_banner", "-encoders"]):
        return Check("h264_nvenc", False, "this FFmpeg build has no h264_nvenc")
    # Listing is not proof; actually open the encoder on a tiny synthetic input.
    p = subprocess.run(
        [path, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2",
         "-c:v", "h264_nvenc", "-f", "null", "-"],
        capture_output=True, text=True, timeout=30,
    )
    if p.returncode != 0:
        return Check("h264_nvenc", False, (p.stderr.strip() or "encoder failed to open")[:300])
    return Check("h264_nvenc", True, "encoder opened successfully")


def check_gpu() -> Check:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return Check("nvidia-gpu", False, "nvidia-smi not found")
    out = _run([smi, "--query-gpu=name,driver_version", "--format=csv,noheader"]).strip()
    return Check("nvidia-gpu", bool(out), out or "no NVIDIA GPU reported")


def check_receiver(ip: str, port: int, timeout: float = 3.0) -> Check:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return Check("receiver", True, f"{ip}:{port} accepts connections")
    except OSError as e:
        return Check("receiver", False, f"{ip}:{port} unreachable: {e} (is the TV app open and waiting?)")


def run_all(ffmpeg: str = "ffmpeg", ip: str = "", port: int = 5000) -> list[Check]:
    checks = [check_ffmpeg(ffmpeg), check_gpu(), check_nvenc(ffmpeg)]
    if ip:
        checks.append(check_receiver(ip, port))
    return checks
