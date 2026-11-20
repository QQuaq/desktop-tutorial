"""Frame sources. Every source returns the full game picture as an RGB numpy array (or None)."""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

import numpy as np

from . import winapi

WINDOW_HINTS = ("ps remote play", "chiaki", "remote play")


class CaptureError(Exception):
    pass


def trim_black_bars(frame: np.ndarray, aspect: float = 16 / 9) -> np.ndarray:
    """Remote Play / chiaki letterbox the 16:9 picture inside their window; cut those bars off."""
    h, w = frame.shape[:2]
    if h < 20 or w < 20:
        return frame
    lum = frame.max(axis=2)
    rows = np.where(lum.mean(axis=1) > 12)[0]
    cols = np.where(lum.mean(axis=0) > 12)[0]
    if len(rows) == 0 or len(cols) == 0:
        return frame
    y0, y1, x0, x1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
    if (y0, y1, x0, x1) == (0, h, 0, w):
        return frame
    if abs((x1 - x0) / max(y1 - y0, 1) - aspect) / aspect > 0.04:
        return frame
    return frame[y0:y1, x0:x1]


class Source:
    name = ""

    def grab(self) -> np.ndarray | None:
        raise NotImplementedError

    def close(self) -> None:
        pass


class WindowSource(Source):
    """`method`: auto (PrintWindow, screen copy if black), printwindow, screen."""

    def __init__(self, title: str, method: str = "auto"):
        if not winapi.IS_WINDOWS:
            raise CaptureError("Pencere yakalama yalnızca Windows'ta çalışır.")
        self.title = title
        self.method = method
        self.hwnd = winapi.find_window(title)
        if not self.hwnd:
            raise CaptureError(f"'{title}' penceresi bulunamadı. PS Remote Play açık ve bağlı mı?")
        self.name = title
        self._sct = None

    def _screen(self) -> np.ndarray | None:
        import mss

        if self._sct is None:
            self._sct = mss.mss()
        x, y, w, h = winapi.client_rect(self.hwnd)
        if w <= 0 or h <= 0:
            return None
        shot = self._sct.grab({"left": x, "top": y, "width": w, "height": h})
        return np.asarray(shot)[:, :, 2::-1].copy()

    def grab(self) -> np.ndarray | None:
        if not winapi.window_exists(self.hwnd):
            raise CaptureError("Remote Play penceresi kapandı.")
        if winapi.is_minimized(self.hwnd):
            raise CaptureError("Remote Play penceresi simge durumuna küçültülmüş. Pencereyi geri açın (arkada kalabilir).")
        frame = None
        if self.method in ("auto", "printwindow"):
            frame = winapi.print_window(self.hwnd)
            if self.method == "auto" and (frame is None or frame.max() < 16):
                frame = self._screen()
        else:
            frame = self._screen()
        return None if frame is None else trim_black_bars(frame)

    def close(self) -> None:
        if self._sct is not None:
            self._sct.close()


class ScreenSource(Source):
    def __init__(self, monitor: int = 1):
        import mss

        self._sct = mss.mss()
        if monitor >= len(self._sct.monitors):
            monitor = 1
        self.monitor = self._sct.monitors[monitor]
        self.name = f"Ekran {monitor}"

    def grab(self) -> np.ndarray | None:
        return np.asarray(self._sct.grab(self.monitor))[:, :, 2::-1].copy()

    def close(self) -> None:
        self._sct.close()


class CardSource(Source):
    """USB capture card (or OBS Virtual Camera) through OpenCV/DirectShow."""

    def __init__(self, index: int = 0):
        import cv2

        api = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        self.cap = cv2.VideoCapture(index, api)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        if not self.cap.isOpened():
            raise CaptureError(f"Yakalama kartı #{index} açılamadı.")
        self.name = f"Yakalama kartı #{index}"

    def grab(self) -> np.ndarray | None:
        import cv2

        ok, frame = self.cap.read()
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if ok else None

    def close(self) -> None:
        self.cap.release()


class FileSource(Source):
    """Images (folder / glob / single file) or a video file; for testing with recordings."""

    VIDEO = (".mp4", ".mkv", ".avi", ".mov", ".webm")

    def __init__(self, path: str, loop: bool = False):
        self.loop = loop
        self.name = os.path.basename(path.rstrip("/\\")) or path
        self.cap = None
        p = Path(path)
        if p.suffix.lower() in self.VIDEO:
            import cv2

            self.cap = cv2.VideoCapture(str(p))
            if not self.cap.isOpened():
                raise CaptureError(f"Video açılamadı: {path}")
            self.files: list[str] = []
        else:
            pattern = str(p / "*.png") if p.is_dir() else path
            self.files = sorted(glob.glob(pattern)) + (sorted(glob.glob(str(p / "*.jpg"))) if p.is_dir() else [])
            if not self.files:
                raise CaptureError(f"Görüntü bulunamadı: {path}")
        self.i = 0

    @property
    def finished(self) -> bool:
        return not self.loop and self.cap is None and self.i >= len(self.files)

    def grab(self) -> np.ndarray | None:
        if self.cap is not None:
            import cv2

            ok, frame = self.cap.read()
            if not ok and self.loop:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self.cap.read()
            if not ok:
                self.cap.release()
                self.cap = None
                self.files, self.i = [], 0
                return None
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if self.i >= len(self.files):
            if not self.loop:
                return None
            self.i = 0
        from PIL import Image

        frame = np.asarray(Image.open(self.files[self.i]).convert("RGB"))
        self.i += 1
        return frame


def open_source(kind: str, value: str, method: str = "auto") -> Source:
    if kind == "window":
        return WindowSource(value, method)
    if kind == "screen":
        return ScreenSource(int(value or 1))
    if kind == "card":
        return CardSource(int(value or 0))
    if kind == "file":
        return FileSource(value, loop=True)
    raise CaptureError(f"Bilinmeyen kaynak: {kind}")


def suggest_window() -> str:
    for _, title in winapi.list_windows():
        if any(h in title.lower() for h in WINDOW_HINTS):
            return title
    return ""
