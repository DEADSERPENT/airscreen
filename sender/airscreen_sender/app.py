"""AirScreen desktop app: a native window (Edge WebView2) hosting the HTML UI, bridged to the sender engine."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

import webview

from . import __version__
from .config.settings import Config, ConfigError, resolve_ffmpeg
from .diagnostics import preflight
from .networking.protocol import VERSION as PROTOCOL_VERSION
from .networking.trust_store import TrustStore
from .session import StreamSession


def data_dir() -> Path:
    d = Path(os.environ.get("APPDATA") or Path.home()) / "AirScreen"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ui_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "webui" if (base / "webui").exists() else Path(__file__).resolve().parent / "webui"


DEFAULT_SETTINGS = {
    "resolution": "auto",  # auto | 1280x720 | 1920x1080 | 2560x1440 | source
    "fps": "auto",         # auto | 30 | 60
    "bitrate": "auto",     # auto | kbit/s as a number
    "audio": True,
    "mute_pc": True,        # play sound on the TV only
    "cursor": True,
    "reconnect": True,
    "last_receiver": "",
}


class Api:
    """Methods callable from JavaScript as window.pywebview.api.<name>()."""

    def __init__(self) -> None:
        self.window: webview.Window | None = None
        self.store = TrustStore()
        self.settings = dict(DEFAULT_SETTINGS)
        self._settings_path = data_dir() / "settings.json"
        try:
            self.settings.update(json.loads(self._settings_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
        self.session: StreamSession | None = None
        self.phase = "idle"       # idle | connecting | streaming | reconnecting | pairing | error
        self.status = "Ready to cast"
        self.receiver_name = ""
        self.pairing_for = ""
        self.logs: deque[dict] = deque(maxlen=500)
        self.devices: list[dict] = []
        self.scanning = False
        self.muted = False
        self.history: deque[float] = deque(maxlen=60)
        self._ssid, self._ssid_at = "", 0.0
        self._lock = threading.Lock()
        self._log_file = data_dir() / "airscreen.log"
        self.log("AirScreen %s started (protocol v%d)" % (__version__, PROTOCOL_VERSION))

    # ---- logging / status ----
    def log(self, msg: str) -> None:
        entry = {"t": time.strftime("%H:%M:%S"), "msg": msg}
        self.logs.append(entry)
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d')} {entry['t']} {msg}\n")
        except OSError:
            pass

    def _on_status(self, msg: str) -> None:
        self.status = msg
        self.log(msg)
        if msg.startswith("Streaming to"):
            self.phase = "streaming"
            m = re.match(r"Streaming to (.+?):", msg)
            self.receiver_name = m.group(1) if m else self.receiver_name
        elif "Reconnecting" in msg:
            self.phase = "reconnecting"
        elif msg.startswith(("Error", "Authentication failed")):
            self.phase = "error"
        elif msg.startswith(("Checking", "Starting", "Connecting")):
            self.phase = "connecting"

    # ---- state for the UI ----
    def state(self) -> dict:
        s = self.session
        if s and not s.running:
            if s.pairing_required:
                self.phase, self.pairing_for = "pairing", s.pairing_required.receiver_name
            elif self.phase in ("streaming", "connecting", "reconnecting"):
                self.phase = "error" if s.error else "idle"
            self.session = None
            s_stats = {}
        else:
            s_stats = dict(s.stats) if s and s.stats else {}
        if s_stats:
            self.history.append(round(s_stats.get("mbps", 0.0), 2))
        return {
            "version": __version__, "protocol": PROTOCOL_VERSION,
            "phase": self.phase, "status": self.status, "receiver": self.receiver_name,
            "pairing_for": self.pairing_for, "stats": s_stats, "history": list(self.history),
            "devices": self.devices, "scanning": self.scanning,
            "paired": [{"id": rid, "name": n} for rid, n in self.store.receivers().items()],
            "settings": self.settings, "muted": self.muted, "ssid": self._wifi_ssid(),
            "pc_name": self.store.device_name,
        }

    def _wifi_ssid(self) -> str:
        """Cached SSID; refreshed on a worker thread so state() never blocks on netsh."""
        if time.time() - self._ssid_at > 10 and not getattr(self, "_ssid_busy", False):
            self._ssid_busy = True

            def work() -> None:
                try:
                    out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True,
                                         timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
                    m = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.M)
                    self._ssid = m.group(1).strip() if m else ""
                except Exception:
                    self._ssid = ""
                finally:
                    self._ssid_at = time.time()
                    self._ssid_busy = False

            threading.Thread(target=work, daemon=True).start()
        return self._ssid

    # ---- actions ----
    def scan(self) -> None:
        if self.scanning:
            return
        self.scanning = True

        def work() -> None:
            try:
                from .networking.discovery import discover
                found = discover(3.0)
                self.devices = [{"name": r.name, "ip": r.ip, "port": r.port, "id": r.receiver_id,
                                 "paired": r.receiver_id in self.store.receivers()} for r in found]
                self.log(f"Found {len(found)} TV(s) on the network")
            except Exception as e:
                self.log(f"Discovery failed: {e}")
            finally:
                self.scanning = False

        threading.Thread(target=work, daemon=True).start()

    def _build_config(self, ip: str, port: int) -> Config:
        st = self.settings
        cfg = Config(receiver_ip=ip, receiver_port=port, audio=bool(st["audio"]), cursor=bool(st["cursor"]),
                     reconnect=bool(st["reconnect"]), mute_pc_audio=bool(st.get("mute_pc", True)))
        cfg.ffmpeg_path = resolve_ffmpeg(cfg.ffmpeg_path)
        if st["resolution"] == "source":
            cfg.auto_quality, cfg.width, cfg.height = False, 0, 0
        elif st["resolution"] != "auto":
            w, h = st["resolution"].split("x")
            cfg.force_width, cfg.force_height = int(w), int(h)
        if st["fps"] != "auto":
            cfg.force_fps = int(st["fps"])
        if st["bitrate"] != "auto":
            cfg.force_bitrate_kbps = int(st["bitrate"])
        return cfg.validate()

    def connect(self, ip: str, port: int = 5000, code: str = "") -> dict:
        if self.session and self.session.running:
            return {"ok": False, "error": "Already streaming"}
        ip = (ip or "").strip()
        if not ip:
            return {"ok": False, "error": "Pick a TV or enter its IP address"}
        try:
            cfg = self._build_config(ip, int(port))
        except (ConfigError, ValueError) as e:
            return {"ok": False, "error": str(e)}
        self.settings["last_receiver"] = ip
        self._save_settings()
        self.history.clear()
        self.pairing_for = ""
        self.phase = "connecting"
        self.session = StreamSession(cfg, self._on_status, self.store, (code or "").strip() or None)
        self.session.set_muted(self.muted)
        self.session.start()
        return {"ok": True}

    def disconnect(self) -> None:
        s, self.session = self.session, None
        if s:
            threading.Thread(target=s.stop, daemon=True).start()
        self.phase, self.status, self.receiver_name, self.pairing_for = "idle", "Ready to cast", "", ""

    def set_muted(self, muted: bool) -> None:
        self.muted = bool(muted)
        if self.session:
            self.session.set_muted(self.muted)

    def save_settings(self, new: dict) -> dict:
        for k in DEFAULT_SETTINGS:
            if k in new:
                self.settings[k] = new[k]
        self._save_settings()
        return self.settings

    def _save_settings(self) -> None:
        try:
            self._settings_path.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
        except OSError:
            pass

    def forget(self, receiver_id: str) -> None:
        self.store.revoke(receiver_id)
        self.log(f"Forgot paired TV {receiver_id}")

    def get_logs(self) -> list:
        return list(self.logs)

    def open_data_folder(self) -> None:
        os.startfile(str(data_dir()))  # noqa: S606 - local folder chosen by us

    def checks(self) -> list:
        ff = resolve_ffmpeg()
        out = []
        for c in (preflight.check_ffmpeg(ff), preflight.check_gpu(), preflight.check_nvenc(ff)):
            out.append({"name": c.name, "ok": c.ok, "detail": c.detail})
        return out

    # ---- custom title bar ----
    def win(self, action: str) -> None:
        w = self.window
        if not w:
            return
        if action == "min":
            w.minimize()
        elif action == "max":
            if getattr(self, "_maxed", False):
                w.restore()
            else:
                w.maximize()
            self._maxed = not getattr(self, "_maxed", False)
        elif action == "close":
            self.disconnect()
            w.destroy()


def run() -> int:
    from .audio.speaker_mute import SpeakerMute
    SpeakerMute.recover()      # undo a mute left by a crashed previous run
    api = Api()
    index = ui_dir() / "index.html"
    window = webview.create_window(
        "AirScreen", url=str(index), js_api=api, width=1180, height=760, min_size=(980, 640),
        background_color="#080B16",
    )
    api.window = window

    def dark_titlebar() -> None:
        """Native title bar (spec 4.1), themed dark to match the sidebar (Windows 10 20H1+/11)."""
        try:
            import ctypes
            hwnd = window.native.Handle.ToInt32()
            dwm = ctypes.windll.dwmapi
            dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)            # immersive dark mode
            dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ctypes.c_int(0x0022120D)), 4)   # caption colour #0D1222 (BGR)
            dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(ctypes.c_int(0x00D0BDB3)), 4)   # caption text #B3BDD0
        except Exception:
            pass

    def on_loaded() -> None:
        dark_titlebar()
        try:  # first paint straight away; later updates are polled by the page
            window.evaluate_js("window.__boot && window.__boot(%s)" % json.dumps(api.state()))
        except Exception:
            pass

    window.events.loaded += on_loaded
    webview.start(debug=bool(os.environ.get("AIRSCREEN_DEBUG")), private_mode=False,
                  storage_path=str(data_dir() / "webview"))
    return 0
