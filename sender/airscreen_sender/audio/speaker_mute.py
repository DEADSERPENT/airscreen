"""Silence this PC's speakers while streaming so the sound plays on the TV only.

WASAPI loopback captures the audio *before* the endpoint mute (verified: capture level is unchanged when muted),
so muting the default output does not affect what is sent to the TV.

Safety: the original state is written to disk while engaged. If AirScreen is killed or crashes, the next start
restores it, so the PC is never left silently muted.
"""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path


def _state_path() -> Path:
    d = Path(os.environ.get("APPDATA") or Path.home()) / "AirScreen"
    d.mkdir(parents=True, exist_ok=True)
    return d / "speaker_state.json"


def _endpoint():
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    dev = AudioUtilities.GetSpeakers()
    if hasattr(dev, "Activate"):
        return cast(dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
    return dev.EndpointVolume


class SpeakerMute:
    def __init__(self) -> None:
        self._vol = None
        self._orig: bool | None = None

    def engage(self) -> bool:
        """Mute the default output. Returns False (and leaves audio alone) if it cannot be done."""
        try:
            self._vol = _endpoint()
            self._orig = bool(self._vol.GetMute())
            _state_path().write_text(json.dumps({"was_muted": self._orig}), encoding="utf-8")
            atexit.register(self.restore)
            self._vol.SetMute(1, None)
            return True
        except Exception:
            self._vol = None
            return False

    def restore(self) -> None:
        if self._vol is None:
            return
        try:
            self._vol.SetMute(int(bool(self._orig)), None)
        except Exception:
            pass
        finally:
            self._vol = None
            try:
                _state_path().unlink()
            except OSError:
                pass

    @staticmethod
    def recover() -> None:
        """Call once at startup: undo a mute left behind by a crashed/killed previous run."""
        p = _state_path()
        if not p.exists():
            return
        try:
            was_muted = bool(json.loads(p.read_text(encoding="utf-8")).get("was_muted", False))
            _endpoint().SetMute(int(was_muted), None)
        except Exception:
            pass
        finally:
            try:
                p.unlink()
            except OSError:
                pass
