"""Windows window listing and capture via ctypes (no pywin32)."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

import numpy as np

IS_WINDOWS = sys.platform == "win32"
PW_CLIENTONLY = 1
PW_RENDERFULLCONTENT = 2


def _declare() -> None:
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    H = wintypes.HANDLE
    u.GetDC.argtypes, u.GetDC.restype = [wintypes.HWND], H
    u.ReleaseDC.argtypes = [wintypes.HWND, H]
    u.PrintWindow.argtypes, u.PrintWindow.restype = [wintypes.HWND, H, wintypes.UINT], wintypes.BOOL
    u.IsIconic.argtypes = u.IsWindow.argtypes = u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    g.CreateCompatibleDC.argtypes, g.CreateCompatibleDC.restype = [H], H
    g.CreateCompatibleBitmap.argtypes, g.CreateCompatibleBitmap.restype = [H, ctypes.c_int, ctypes.c_int], H
    g.SelectObject.argtypes, g.SelectObject.restype = [H, H], H
    g.DeleteObject.argtypes = [H]
    g.DeleteDC.argtypes = [H]
    g.GetDIBits.argtypes = [H, H, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]


if IS_WINDOWS:
    _declare()


def make_dpi_aware() -> None:
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def list_windows() -> list[tuple[int, str]]:
    if not IS_WINDOWS:
        return []
    user32 = ctypes.windll.user32
    found: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                found.append((int(hwnd), buf.value))
        return True

    user32.EnumWindows(callback, 0)
    return found


def find_window(title_part: str) -> int | None:
    title_part = title_part.lower()
    for hwnd, title in list_windows():
        if title_part and title_part in title.lower():
            return hwnd
    return None


def is_minimized(hwnd: int) -> bool:
    return bool(IS_WINDOWS and ctypes.windll.user32.IsIconic(hwnd))


def window_exists(hwnd: int) -> bool:
    return bool(IS_WINDOWS and ctypes.windll.user32.IsWindow(hwnd))


def client_rect(hwnd: int) -> tuple[int, int, int, int]:
    """Client area in screen pixels: left, top, width, height."""
    user32 = ctypes.windll.user32
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, rect.right - rect.left, rect.bottom - rect.top


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def print_window(hwnd: int) -> np.ndarray | None:
    """Client area as RGB via PrintWindow(PW_RENDERFULLCONTENT); works while covered, not when minimized."""
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    _, _, w, h = client_rect(hwnd)
    if w <= 0 or h <= 0:
        return None
    hdc = user32.GetDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mem, bmp)
    try:
        if not user32.PrintWindow(hwnd, mem, PW_CLIENTONLY | PW_RENDERFULLCONTENT):
            return None
        info = BITMAPINFOHEADER()
        info.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.biWidth, info.biHeight = w, -h
        info.biPlanes, info.biBitCount = 1, 32
        buf = ctypes.create_string_buffer(w * h * 4)
        if not gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(info), 0):
            return None
        bgra = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)
        return bgra[:, :, 2::-1].copy()
    finally:
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(hwnd, hdc)
