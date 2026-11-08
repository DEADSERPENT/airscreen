"""Persistent identity + trusted receivers for the sender (%APPDATA%\\AirScreen\\trust.json)."""
from __future__ import annotations

import base64
import json
import os
import secrets
from pathlib import Path


def _dpapi(data: bytes, protect: bool) -> bytes | None:
    """Windows DPAPI (bound to this Windows user). Returns None when unavailable so callers can fall back safely."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        buf = ctypes.create_string_buffer(data, len(data))
        src = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        dst = Blob()
        fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
        args = (ctypes.byref(src), None, None, None, None, 0, ctypes.byref(dst)) if protect else                (ctypes.byref(src), None, None, None, None, 0, ctypes.byref(dst))
        if not fn(*args):
            return None
        try:
            return ctypes.string_at(dst.pbData, dst.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(dst.pbData)
    except Exception:
        return None


def _seal_key(key: bytes) -> str:
    blob = _dpapi(key, True)
    return "dpapi:" + base64.b64encode(blob).decode() if blob else key.hex()


def _open_key(stored: str) -> bytes | None:
    if stored.startswith("dpapi:"):
        return _dpapi(base64.b64decode(stored[6:]), False)
    return bytes.fromhex(stored)


def default_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "AirScreen" / "trust.json"


class TrustStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else default_path()
        self._data = {"device_id": "", "device_name": os.environ.get("COMPUTERNAME", "Windows PC"), "receivers": {}}
        try:
            self._data.update(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
        if not self._data["device_id"]:
            self._data["device_id"] = secrets.token_hex(8)
            self._save()
        self._migrate_plaintext_keys()

    @property
    def device_id(self) -> str:
        return self._data["device_id"]

    @property
    def device_name(self) -> str:
        return self._data["device_name"]

    def get_key(self, receiver_id: str) -> bytes | None:
        entry = self._data["receivers"].get(receiver_id)
        return _open_key(entry["key"]) if entry else None

    def trust(self, receiver_id: str, name: str, key: bytes) -> None:
        self._data["receivers"][receiver_id] = {"name": name, "key": _seal_key(key)}
        self._save()

    def revoke(self, receiver_id: str) -> None:
        if self._data["receivers"].pop(receiver_id, None) is not None:
            self._save()

    def receivers(self) -> dict[str, str]:
        return {rid: e["name"] for rid, e in self._data["receivers"].items()}

    def _migrate_plaintext_keys(self) -> None:
        """Keys written by older versions are plain hex: protect them in place (only when DPAPI is available)."""
        changed = False
        for entry in self._data["receivers"].values():
            if not entry["key"].startswith("dpapi:"):
                sealed = _seal_key(bytes.fromhex(entry["key"]))
                if sealed.startswith("dpapi:"):
                    entry["key"], changed = sealed, True
        if changed:
            self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)  # contains device keys: lives in the user's profile only
