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
    p.add_argument("--code", help="pairing code shown on the TV (first connection only)")
    p.add_argument("--no-audio", action="store_true")
    p.add_argument("--no-cursor", action="store_true")
    p.add_argument("--no-reconnect", action="store_true")
    p.add_argument("--discover", action="store_true", help="list receivers found via mDNS and exit")
    p.add_argument("--forget", metavar="RECEIVER_ID", help="revoke trust for a paired receiver and exit")
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
    if a.size or a.fps or a.bitrate:
        cfg.auto_quality = False  # any explicit quality flag means manual mode
    if a.fps:
        cfg.fps = a.fps
    if a.bitrate:
        cfg.bitrate_kbps = a.bitrate
    if a.ffmpeg:
        cfg.ffmpeg_path = a.ffmpeg
    if a.no_audio:
        cfg.audio = False
    if a.no_cursor:
        cfg.cursor = False
    if a.no_reconnect:
        cfg.reconnect = False
    if a.allow_cpu:
        cfg.allow_cpu_fallback = True
        cfg.encoder = "libx264"
    return cfg


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    try:
        cfg = config_from_args(a)
        if a.discover:
            from .networking.discovery import discover
            found = discover()
            for r in found:
                print(f"{r.name}	{r.ip}:{r.port}	id={r.receiver_id}")
            if not found:
                print("no receivers found (is the TV app open? same network?)")
            return 0 if found else 1
        if a.forget:
            from .networking.trust_store import TrustStore
            TrustStore().revoke(a.forget)
            print(f"revoked {a.forget}")
            return 0
        if a.preflight:
            bad = 0
            for c in preflight.run_all(cfg.ffmpeg_path, cfg.receiver_ip, cfg.receiver_port):
                print(f"[{'OK' if c.ok else 'FAIL'}] {c.name}: {c.detail}")
                bad += not c.ok
            return 1 if bad else 0
        if not cfg.receiver_ip:
            try:
                from .app import run
                return run()
            except ImportError:  # pywebview unavailable: fall back to the basic window
                from .gui import run_gui
                run_gui(cfg)
                return 0
        cfg.validate()
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    code = a.code
    while True:
        session = StreamSession(cfg, on_status=lambda s: print(s, flush=True), pairing_code=code)
        session.start()
        try:
            while session.running:
                time.sleep(1)
                if session.stats:
                    s = session.stats
                    print(f"  in {s['fps_in']:.1f} fps | {s['mbps']:.1f} Mbit/s | dropped {int(s['dropped'])}"
                          f" | audio pkts {int(s['audio_packets'])}"
                          f" | encode {s['enc_ms']:.0f}/{s['enc_ms_max']:.0f} ms | send {s['net_ms']:.0f}/{s['net_ms_max']:.0f} ms", flush=True)
        except KeyboardInterrupt:
            print("stopping...")
            session.stop()
            return 0
        finally:
            session.stop()
        if session.pairing_required and sys.stdin.isatty() and not code:
            code = input("Pairing code from the TV (XXXX-XXXX-XXXX-XXXX): ").strip()
            continue
        return 1 if session.error else 0
