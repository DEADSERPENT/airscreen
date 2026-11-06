"""Desktop capture via DXcam. Yields BGRA frames; repeats the last frame when the screen is static."""
from __future__ import annotations

import time

import dxcam
import numpy as np


class DesktopCapture:
    def __init__(self, monitor: int = 0, cursor: bool = True) -> None:
        self._cam = dxcam.create(output_idx=monitor, output_color="BGRA")
        if self._cam is None:
            raise RuntimeError(f"cannot open capture on monitor {monitor}")
        self.width: int = self._cam.width
        self.height: int = self._cam.height
        self._cursor = None
        if cursor:
            try:
                dc = self._cam._output.desc.DesktopCoordinates  # monitor origin on the virtual desktop
                origin = (int(dc.left), int(dc.top))
            except Exception:
                origin = (0, 0)
            from .cursor import CursorOverlay
            self._cursor = CursorOverlay(origin)
        self._last: np.ndarray | None = None
        self.errors = 0

    def grab(self) -> np.ndarray:
        """Newest frame with the cursor drawn; repeats the previous frame if the screen is unchanged."""
        frame = self._grab_raw()
        return self._cursor.draw(frame) if self._cursor else frame

    def _grab_raw(self) -> np.ndarray:
        try:
            frame = self._cam.grab()
        except Exception:
            self.errors += 1
            frame = None
        if frame is not None:
            self._last = frame
            return frame
        if self._last is not None:
            return self._last
        # Nothing captured yet (static desktop at start): retry briefly.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            frame = self._cam.grab()
            if frame is not None:
                self._last = frame
                return frame
            time.sleep(0.01)
        raise RuntimeError("capture produced no frames")

    def close(self) -> None:
        try:
            self._cam.release()
        except Exception:
            pass
