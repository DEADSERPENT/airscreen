"""Minimal sender window (blueprint section 13): receiver IP, status, Connect / Disconnect."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .config.settings import Config, ConfigError
from .session import StreamSession


def run_gui(cfg: Config) -> None:
    root = tk.Tk()
    root.title("AirScreen")
    root.resizable(False, False)
    frm = ttk.Frame(root, padding=16)
    frm.grid()

    ip = tk.StringVar(value=cfg.receiver_ip)
    status = tk.StringVar(value="Disconnected")
    stats = tk.StringVar(value="")
    ttk.Label(frm, text="AirScreen", font=("Segoe UI", 16, "bold")).grid(columnspan=2, pady=(0, 8))
    ttk.Label(frm, text="Receiver IP:").grid(row=1, column=0, sticky="e")
    entry = ttk.Entry(frm, textvariable=ip, width=22)
    entry.grid(row=1, column=1, pady=2)
    quality = f"{cfg.width}x{cfg.height}" if cfg.width else "source size"
    ttk.Label(frm, text=f"Quality: {quality} / {cfg.fps} FPS / {cfg.bitrate_kbps // 1000} Mbit/s").grid(columnspan=2, sticky="w")
    ttk.Label(frm, text=f"Encoder: {cfg.encoder}").grid(columnspan=2, sticky="w")
    ttk.Label(frm, textvariable=status, wraplength=300).grid(columnspan=2, pady=6, sticky="w")
    ttk.Label(frm, textvariable=stats).grid(columnspan=2, sticky="w")
    btns = ttk.Frame(frm)
    btns.grid(columnspan=2, pady=(8, 0))
    connect = ttk.Button(btns, text="Connect")
    disconnect = ttk.Button(btns, text="Disconnect", state="disabled")
    connect.grid(row=0, column=0, padx=4)
    disconnect.grid(row=0, column=1, padx=4)

    state: dict = {"session": None, "msg": None}

    def on_status(msg: str) -> None:
        state["msg"] = msg  # worker thread: hand over via polling, never touch Tk from here

    def reset_controls() -> None:
        connect.config(state="normal")
        disconnect.config(state="disabled")
        entry.config(state="normal")

    def do_connect() -> None:
        cfg.receiver_ip = ip.get().strip()
        try:
            if not cfg.receiver_ip:
                raise ConfigError("enter the receiver IP shown on the TV")
            cfg.validate()
        except ConfigError as e:
            status.set(f"Error: {e}")
            return
        state["msg"] = None
        state["session"] = StreamSession(cfg, on_status)
        state["session"].start()
        connect.config(state="disabled")
        disconnect.config(state="normal")
        entry.config(state="disabled")

    def do_disconnect() -> None:
        s = state["session"]
        state["session"] = None
        if s:
            s.stop()
        reset_controls()
        status.set("Disconnected")
        stats.set("")

    def poll() -> None:
        s = state["session"]
        if state["msg"]:
            status.set(state["msg"])
        if s:
            if s.stats:
                st = s.stats
                stats.set(f"{st['fps_in']:.0f} fps | {st['mbps']:.1f} Mbit/s | dropped {int(st['dropped'])}")
            if not s.running:  # ended by itself (error or receiver went away): keep the message visible
                msg = state["msg"] or "Disconnected"
                state["session"] = None
                reset_controls()
                stats.set("")
                status.set(msg)
        root.after(250, poll)

    connect.config(command=do_connect)
    disconnect.config(command=do_disconnect)
    root.protocol("WM_DELETE_WINDOW", lambda: (do_disconnect(), root.destroy()))
    poll()
    root.mainloop()
