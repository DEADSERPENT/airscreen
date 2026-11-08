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


_crash_file = None


def install_diagnostics(api_ref: list) -> None:
    """Crash + hang evidence for a windowed exe that has no console: native crashes, uncaught exceptions
    (any thread) and a watchdog that dumps every thread's stack if the UI stops polling for 10 s."""
    import faulthandler
    import traceback
    global _crash_file
    try:
        _crash_file = open(data_dir() / "crash.log", "a", buffering=1, encoding="utf-8")
        _crash_file.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} AirScreen {__version__} start ---\n")
        faulthandler.enable(_crash_file, all_threads=True)
    except OSError:
        return

    def note(kind: str, exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            _crash_file.write(f"{time.strftime('%H:%M:%S')} {kind}\n{text}")
            if api_ref:
                api_ref[0].log(f"{kind}: {exc_type.__name__}: {exc}")
        except Exception:
            pass

    sys.excepthook = lambda t, e, tb: note("Uncaught error", t, e, tb)
    threading.excepthook = lambda a: note(f"Thread {getattr(a.thread, 'name', '?')} failed", a.exc_type, a.exc_value, a.exc_traceback)

    def watchdog() -> None:
        dumped = False
        while True:
            time.sleep(2)
            api = api_ref[0] if api_ref else None
            if not api or not api.window_ready:
                continue
            stale = time.monotonic() - api.last_poll
            if stale > 10 and not dumped:
                dumped = True
                _crash_file.write(f"{time.strftime('%H:%M:%S')} UI not polling for {stale:.0f}s: thread dump\n")
                faulthandler.dump_traceback(_crash_file, all_threads=True)
                api.log(f"UI stopped responding for {stale:.0f}s (thread dump in crash.log)")
            elif stale <= 10:
                dumped = False

    threading.Thread(target=watchdog, name="watchdog", daemon=True).start()


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
        self.last_poll = time.monotonic()   # UI heartbeat for the hang watchdog
        self.window_ready = False
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
        self.last_poll = time.monotonic()
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
            "verify": (self.session.verify_code if self.session else ""),
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

    def connect_by_key(self, key: str) -> dict:
        """The user typed the pair key shown on the TV: find the TV on the network and pair with it."""
        if self.session and self.session.running:
            return {"ok": False, "error": "Already streaming"}
        from .networking import crypto
        try:
            k = crypto.normalize_key(key)
            cfg = self._build_config("", 5000)
        except (ValueError, ConfigError) as e:
            return {"ok": False, "error": str(e)}
        self.history.clear()
        self.pairing_for = ""
        self.phase, self.status = "connecting", "Looking for your TV…"
        self.log("Looking for a TV that shows this pair key")

        def work() -> None:
            try:
                from .networking.discovery import discover
                found = discover(2.5)
            except Exception as e:
                found = []
                self.log(f"Discovery failed: {e}")
            if not found:
                self.phase, self.status = "error", "No TV found on your network. Open AirScreen on the TV, or connect by IP address."
                return
            cfg.receiver_ip, cfg.receiver_port = found[0].ip, found[0].port
            s = StreamSession(cfg, self._on_status, self.store, k)
            s.candidates = [(r.ip, r.port) for r in found]
            s.set_muted(self.muted)
            self.session = s
            s.start()

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    def shutdown(self) -> None:
        """Stop the stream and give the PC its sound back BEFORE the process exits (ffmpeg children, WASAPI, mute)."""
        s, self.session = self.session, None
        if s:
            try:
                s.stop()
            except Exception as e:
                self.log(f"Shutdown: {e}")

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
        for c in [preflight.check_ffmpeg(ff)] + [preflight.check_encoder(ff, n) for n in preflight.HW_ENCODERS]:
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
            w.destroy()          # the window's closing handler stops the stream first


def run() -> int:
    from .audio.speaker_mute import SpeakerMute
    api_ref: list = []
    install_diagnostics(api_ref)
    SpeakerMute.recover()      # undo a mute left by a crashed previous run
    api = Api()
    api_ref.append(api)
    index = ui_dir() / "index.html"
    # pywebview walks every attribute of js_api (recursing into window.native WinForms/COM objects off the UI thread,
    # which spams errors and stalls the UI), so hand it a bridge that carries only the callable methods.
    class _Bridge:
        pass
    bridge = _Bridge()
    for name in ("state", "scan", "connect", "connect_by_key", "disconnect", "set_muted", "save_settings", "forget",
                 "get_logs", "open_data_folder", "checks", "win"):
        setattr(bridge, name, getattr(api, name))
    window = webview.create_window(
        "AirScreen", url=str(index), js_api=bridge, width=1180, height=760, min_size=(980, 640),
        background_color="#080B16",
    )
    api.window = window

    def dark_titlebar() -> None:
        """Title bar: dark, and translucent (Windows 11 Mica) so the desktop shows through it; plain near-black elsewhere."""
        try:
            import ctypes
            hwnd = window.native.Handle.ToInt32()
            dwm = ctypes.windll.dwmapi
            dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)            # immersive dark mode
            dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ctypes.c_uint(0xFFFFFFFF)), 4)  # caption colour: system default (lets Mica show)
            dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(ctypes.c_int(0x00E6E6E6)), 4)   # caption text
            # DWMWA_SYSTEMBACKDROP_TYPE = 38; 2 = Mica, 3 = acrylic, 4 = Mica Alt (Windows 11 22621+)
            hr = dwm.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(ctypes.c_int(3)), 4)
            if hr != 0:                                                                       # older Windows: match the page instead
                dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ctypes.c_int(0x000C0B0A)), 4)
        except Exception:
            pass

    def set_window_icon() -> None:
        """Title bar + taskbar icon from our own .ico (independent of the exe icon cache / pywebview default)."""
        try:
            import ctypes
            ico = str(ui_dir() / "AirScreen.ico")
            hwnd = window.native.Handle.ToInt32()
            user32 = ctypes.windll.user32
            for which, size in ((0, 16), (1, 48)):       # ICON_SMALL, ICON_BIG
                h = user32.LoadImageW(None, ico, 1, size, size, 0x10)   # IMAGE_ICON, LR_LOADFROMFILE
                if h:
                    user32.SendMessageW(hwnd, 0x80, which, h)           # WM_SETICON
        except Exception:
            pass

    def on_loaded() -> None:
        set_window_icon()
        dark_titlebar()
        try:  # first paint straight away; later updates are polled by the page
            window.evaluate_js("window.__boot && window.__boot(%s)" % json.dumps(api.state()))
        except Exception:
            pass

    def on_closing() -> None:
        api.shutdown()         # covers Alt+F4 / taskbar close as well as our own close button

    window.events.loaded += on_loaded
    window.events.closing += on_closing
    api.window_ready = True
    webview.start(debug=bool(os.environ.get("AIRSCREEN_DEBUG")), private_mode=False,
                  storage_path=str(data_dir() / "webview"))
    api.shutdown()
    api.log("AirScreen closed")
    if getattr(sys, "frozen", False):
        os._exit(0)            # skip interpreter finalisation: daemon threads inside COM/ctypes can crash it
    return 0
