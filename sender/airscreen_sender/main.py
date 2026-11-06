"""AirScreen sender entry point. `python -m airscreen_sender` opens the GUI; --ip runs headless."""
from __future__ import annotations

import argparse
import sys
import time

from .config.settings import Config, ConfigError
from .diagnostics import preflight
from .session import StreamSession


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="airscreen_sender", description="Mirror the Windows desktop to an AirScreen receiver.")
    p.add_argument("--ip", help="receiver (TV) IP address; omit to open the GUI")
    p.add_argument("--port", type=int, help="receiver port (default 5000)")
    p.add_argument("--config", help="JSON config file (explicit flags override it)")
    p.add_argument("--monitor", type=int)
    p.add_argument("--size", help="encoded size WxH, or 'source'")
    p.add_argument("--fps", type=int)
    p.add_argument("--bitrate", type=int, help="kbit/s")
    p.add_argument("--ffmpeg", help="path to ffmpeg.exe")
    p.add_argument("--allow-cpu", action="store_true", help="permit libx264 (CPU) instead of NVENC; never automatic")
    p.add_argument("--preflight", action="store_true", help="run hardware/network checks and exit")
    return p


def config_from_args(a: argparse.Namespace) -> Config:
    cfg = Config.from_file(a.config) if a.config else Config()
    if a.ip:
        cfg.receiver_ip = a.ip
    if a.port:
        cfg.receiver_port = a.port
    if a.monitor is not None:
        cfg.monitor = a.monitor
    if a.size:
        if a.size == "source":
            cfg.width = cfg.height = 0
        else:
            try:
                w, h = a.size.lower().split("x")
                cfg.width, cfg.height = int(w), int(h)
            except ValueError:
                raise ConfigError(f"--size must be WxH or 'source', got {a.size!r}")
    if a.fps:
        cfg.fps = a.fps
    if a.bitrate:
        cfg.bitrate_kbps = a.bitrate
    if a.ffmpeg:
        cfg.ffmpeg_path = a.ffmpeg
    if a.allow_cpu:
        cfg.allow_cpu_fallback = True
        cfg.encoder = "libx264"
    return cfg


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    try:
        cfg = config_from_args(a)
        if a.preflight:
            bad = 0
            for c in preflight.run_all(cfg.ffmpeg_path, cfg.receiver_ip, cfg.receiver_port):
                print(f"[{'OK' if c.ok else 'FAIL'}] {c.name}: {c.detail}")
                bad += not c.ok
            return 1 if bad else 0
        if not cfg.receiver_ip:
            from .gui import run_gui
            run_gui(cfg)
            return 0
        cfg.validate()
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    session = StreamSession(cfg, on_status=lambda s: print(s, flush=True))
    session.start()
    try:
        while session.running:
            time.sleep(1)
            if session.stats:
                s = session.stats
                print(f"  in {s['fps_in']:.1f} fps | {s['mbps']:.1f} Mbit/s | dropped {int(s['dropped'])}", flush=True)
    except KeyboardInterrupt:
        print("stopping...")
    finally:
        session.stop()
    return 1 if session.error else 0
