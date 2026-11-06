"""Persistent identity + trusted receivers for the sender (%APPDATA%\\AirScreen\\trust.json)."""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path


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

    @property
    def device_id(self) -> str:
        return self._data["device_id"]

    @property
    def device_name(self) -> str:
        return self._data["device_name"]

    def get_key(self, receiver_id: str) -> bytes | None:
        entry = self._data["receivers"].get(receiver_id)
        return bytes.fromhex(entry["key"]) if entry else None

    def trust(self, receiver_id: str, name: str, key: bytes) -> None:
        self._data["receivers"][receiver_id] = {"name": name, "key": key.hex()}
        self._save()

    def revoke(self, receiver_id: str) -> None:
        if self._data["receivers"].pop(receiver_id, None) is not None:
            self._save()

    def receivers(self) -> dict[str, str]:
        return {rid: e["name"] for rid, e in self._data["receivers"].items()}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)  # contains device keys: lives in the user's profile only
