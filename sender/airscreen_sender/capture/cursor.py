"""Draws a mouse pointer onto captured frames (DXcam/Desktop Duplication frames exclude the cursor)."""
from __future__ import annotations

import ctypes
from ctypes import wintypes

import numpy as np

CURSOR_SHOWING = 0x1


class _CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hCursor", wintypes.HANDLE),
                ("ptScreenPos", wintypes.POINT)]


# Classic arrow, hot-spot at (0, 0), in a 12x19 cell.
_ARROW = [(0, 0), (0, 16), (4, 12), (7, 18), (9, 17), (6, 11), (11, 11)]


def _arrow_masks(scale: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (fill_mask, outline_mask) rasterised with an even-odd point-in-polygon test."""
    pts = [(x * scale, y * scale) for x, y in _ARROW]
    w, h = 12 * scale + 4, 19 * scale + 4
    ys, xs = np.mgrid[0:h, 0:w]
    px, py = xs + 0.5, ys + 0.5
    inside = np.zeros((h, w), dtype=bool)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        cond = (y1 > py) != (y2 > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            xcross = (x2 - x1) * (py - y1) / (y2 - y1) + x1
        inside ^= cond & (px < xcross)
    grown = inside.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            grown |= np.roll(np.roll(inside, dy, 0), dx, 1)
    return inside, grown & ~inside


class CursorOverlay:
    def __init__(self, origin: tuple[int, int] = (0, 0), scale: int = 2) -> None:
        try:  # physical pixels, matching the captured frame
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
        self._origin = origin
        self._fill, self._outline = _arrow_masks(scale)
        self._info = _CURSORINFO()
        self._info.cbSize = ctypes.sizeof(_CURSORINFO)

    def draw(self, frame: np.ndarray) -> np.ndarray:
        """Return a frame with the cursor drawn. The input is never modified (it may be re-sent)."""
        if not ctypes.windll.user32.GetCursorInfo(ctypes.byref(self._info)) or not (self._info.flags & CURSOR_SHOWING):
            return frame
        x = self._info.ptScreenPos.x - self._origin[0]
        y = self._info.ptScreenPos.y - self._origin[1]
        fh, fw = frame.shape[:2]
        mh, mw = self._fill.shape
        if x >= fw or y >= fh or x + mw <= 0 or y + mh <= 0:
            return frame
        out = frame.copy()
        x0, y0 = max(x, 0), max(y, 0)
        x1, y1 = min(x + mw, fw), min(y + mh, fh)
        fill = self._fill[y0 - y:y1 - y, x0 - x:x1 - x]
        outline = self._outline[y0 - y:y1 - y, x0 - x:x1 - x]
        region = out[y0:y1, x0:x1]
        region[outline] = (0, 0, 0, 255)
        region[fill] = (255, 255, 255, 255)
        return out
