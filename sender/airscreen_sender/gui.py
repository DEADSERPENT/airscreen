"""Sender window: pick/enter a receiver, pair once, connect, mute, live stats."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from .config.settings import Config, ConfigError
from .networking.trust_store import TrustStore
from .session import StreamSession


def run_gui(cfg: Config) -> None:
    root = tk.Tk()
    root.title("AirScreen")
    root.resizable(False, False)
    store = TrustStore()
    frm = ttk.Frame(root, padding=16)
    frm.grid()

    ip = tk.StringVar(value=cfg.receiver_ip)
    code = tk.StringVar()
    status = tk.StringVar(value="Disconnected")
    stats = tk.StringVar(value="")
    muted = tk.BooleanVar(value=False)
    found: dict[str, tuple[str, int]] = {}

    ttk.Label(frm, text="AirScreen", font=("Segoe UI", 16, "bold")).grid(columnspan=3, pady=(0, 8))
    ttk.Label(frm, text="Receiver:").grid(row=1, column=0, sticky="e")
    combo = ttk.Combobox(frm, textvariable=ip, width=26)
    combo.grid(row=1, column=1, pady=2)
    scan = ttk.Button(frm, text="Find TVs")
    scan.grid(row=1, column=2, padx=4)
    ttk.Label(frm, text="Pairing code:").grid(row=2, column=0, sticky="e")
    code_entry = ttk.Entry(frm, textvariable=code, width=28)
    code_entry.grid(row=2, column=1, pady=2)
    ttk.Label(frm, text="(first time only, shown on the TV)", foreground="gray").grid(row=2, column=2, sticky="w")
    quality = f"{cfg.width}x{cfg.height}" if cfg.width else "source size"
    ttk.Label(frm, text=f"{quality} / {cfg.fps} FPS / {cfg.bitrate_kbps // 1000} Mbit/s / {cfg.encoder}").grid(
        columnspan=3, sticky="w", pady=(6, 0))
    ttk.Label(frm, textvariable=status, wraplength=420).grid(columnspan=3, pady=6, sticky="w")
    ttk.Label(frm, textvariable=stats).grid(columnspan=3, sticky="w")
    mute = ttk.Checkbutton(frm, text="Mute TV audio", variable=muted)
    mute.grid(columnspan=3, sticky="w")
    btns = ttk.Frame(frm)
    btns.grid(columnspan=3, pady=(8, 0))
    connect = ttk.Button(btns, text="Connect")
    disconnect = ttk.Button(btns, text="Disconnect", state="disabled")
    connect.grid(row=0, column=0, padx=4)
    disconnect.grid(row=0, column=1, padx=4)

    state: dict = {"session": None, "msg": None, "scan": None}

    def on_status(msg: str) -> None:
        state["msg"] = msg  # worker thread: hand over via polling, never touch Tk from here

    def do_scan() -> None:
        scan.config(state="disabled")
        status.set("Searching for TVs...")

        def work() -> None:
            try:
                from .networking.discovery import discover
                state["scan"] = discover(3.0)
            except Exception as e:  # surfaced in the UI
                state["scan"] = e

        threading.Thread(target=work, daemon=True).start()

    def reset_controls() -> None:
        connect.config(state="normal")
        disconnect.config(state="disabled")
        combo.config(state="normal")
        scan.config(state="normal")

    def start_session() -> None:
        target = ip.get().strip()
        host, port = found.get(target, (target, cfg.receiver_port))
        cfg.receiver_ip, cfg.receiver_port = host, port
        try:
            if not cfg.receiver_ip:
                raise ConfigError("pick a TV or enter the IP shown on it")
            cfg.validate()
        except ConfigError as e:
            status.set(f"Error: {e}")
            return
        state["msg"] = None
        s = StreamSession(cfg, on_status, store, code.get().strip() or None)
        s.set_muted(muted.get())
        s.start()
        state["session"] = s
        connect.config(state="disabled")
        disconnect.config(state="normal")
        combo.config(state="disabled")
        scan.config(state="disabled")

    def do_disconnect() -> None:
        s, state["session"] = state["session"], None
        if s:
            s.stop()
        reset_controls()
        status.set("Disconnected")
        stats.set("")

    def poll() -> None:
        s = state["session"]
        if state["scan"] is not None:
            res, state["scan"] = state["scan"], None
            scan.config(state="normal" if not s else "disabled")
            if isinstance(res, Exception):
                status.set(f"Discovery failed: {res}")
            else:
                found.clear()
                found.update({f"{r.name} ({r.ip})": (r.ip, r.port) for r in res})
                combo["values"] = list(found)
                if found:
                    ip.set(next(iter(found)))
                status.set(f"Found {len(found)} TV(s)" if found else "No TVs found - enter the IP shown on the TV")
        elif state["msg"]:
            status.set(state["msg"])
        if s:
            s.set_muted(muted.get())
            if s.stats:
                st = s.stats
                stats.set(f"{st['fps_in']:.0f} fps | {st['mbps']:.1f} Mbit/s | dropped {int(st['dropped'])}")
            if not s.running:  # ended by itself (error / pairing needed): keep the message visible
                msg = state["msg"] or "Disconnected"
                state["session"] = None
                reset_controls()
                stats.set("")
                status.set(msg)
                if s.pairing_required:
                    code_entry.focus_set()
        root.after(250, poll)

    scan.config(command=do_scan)
    connect.config(command=start_session)
    disconnect.config(command=do_disconnect)
    root.protocol("WM_DELETE_WINDOW", lambda: (do_disconnect(), root.destroy()))
    poll()
    root.mainloop()
