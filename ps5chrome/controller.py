"""Chrome'u yonetir: ekran goruntusu akisi ve girdi olaylari."""
from __future__ import annotations

import base64
import re
import threading
from urllib.parse import quote_plus, urlparse

from .chrome import ChromeInstance
from .cdp import CDPError

ALLOWED_SCHEMES = ("http", "https")
SPECIAL_KEYS = {
    "Enter": (13, "\r"), "Backspace": (8, ""), "Tab": (9, ""), "Escape": (27, ""),
    "ArrowLeft": (37, ""), "ArrowUp": (38, ""), "ArrowRight": (39, ""), "ArrowDown": (40, ""),
    "PageUp": (33, ""), "PageDown": (34, ""), "Home": (36, ""), "End": (35, ""), "Delete": (46, ""),
}


def normalize_url(raw: str) -> str:
    """Kullanici girdisini guvenli bir http(s) adresine cevirir; aksi halde ValueError.

    Bosluklu metin arama sorgusu sayilir. file:, javascript:, data:, about:, chrome:
    gibi sema'lar reddedilir (uzak Chrome yerel dosyalari okumasin).
    """
    raw = (raw or "").strip()
    if not raw or len(raw) > 2048 or any(c in raw for c in "\r\n\t"):
        raise ValueError("gecersiz adres")
    if " " in raw:
        if "://" in raw:
            raise ValueError("gecersiz adres")
        return "https://www.google.com/search?q=" + quote_plus(raw)
    if "://" not in raw:
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:(?!\d)", raw):
            raise ValueError("yalnizca http ve https adreslerine izin verilir")
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.hostname:
        raise ValueError("yalnizca http ve https adreslerine izin verilir")
    return raw


class Controller:
    def __init__(self, chrome: ChromeInstance, quality: int = 60) -> None:
        self.chrome = chrome
        self.cdp = chrome.cdp
        self.width, self.height = chrome.width, chrome.height
        self.quality = quality
        self._frame: bytes | None = None
        self._frame_no = 0
        self._cond = threading.Condition()
        self.cdp.on("Page.screencastFrame", self._on_frame)
        self.cdp.call("Page.enable")
        self.cdp.call("Emulation.setDeviceMetricsOverride", {
            "width": self.width, "height": self.height, "deviceScaleFactor": 1, "mobile": False})
        self.cdp.call("Page.startScreencast", {
            "format": "jpeg", "quality": quality, "maxWidth": self.width,
            "maxHeight": self.height, "everyNthFrame": 1})

    def _on_frame(self, params: dict) -> None:
        data = base64.b64decode(params["data"])
        self.cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
        with self._cond:
            self._frame = data
            self._frame_no += 1
            self._cond.notify_all()

    def latest_frame(self) -> bytes | None:
        return self._frame

    def wait_frame(self, last_no: int, timeout: float = 15.0) -> tuple[int, bytes | None]:
        with self._cond:
            if self._frame_no == last_no:
                self._cond.wait(timeout)
            return self._frame_no, self._frame

    def _clamp(self, x, y) -> tuple[float, float]:
        x = min(max(float(x), 0), self.width - 1)
        y = min(max(float(y), 0), self.height - 1)
        return x, y

    def click(self, x, y, button: str = "left") -> None:
        if button not in ("left", "right", "middle"):
            raise ValueError("gecersiz dugme")
        x, y = self._clamp(x, y)
        base = {"x": x, "y": y, "button": button, "clickCount": 1}
        self.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        self.cdp.call("Input.dispatchMouseEvent", {**base, "type": "mousePressed"})
        self.cdp.call("Input.dispatchMouseEvent", {**base, "type": "mouseReleased"})

    def move(self, x, y) -> None:
        x, y = self._clamp(x, y)
        self.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})

    def wheel(self, x, y, dx=0, dy=0) -> None:
        x, y = self._clamp(x, y)
        dx = max(-5000, min(5000, float(dx)))
        dy = max(-5000, min(5000, float(dy)))
        self.cdp.call("Input.dispatchMouseEvent",
                      {"type": "mouseWheel", "x": x, "y": y, "deltaX": dx, "deltaY": dy})

    def text(self, text: str) -> None:
        if len(text) > 2000:
            raise ValueError("metin cok uzun")
        if text:
            self.cdp.call("Input.insertText", {"text": text})

    def key(self, key: str) -> None:
        if key not in SPECIAL_KEYS:
            raise ValueError("desteklenmeyen tus")
        code, text = SPECIAL_KEYS[key]
        params = {"key": key, "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code}
        self.cdp.call("Input.dispatchKeyEvent", {**params, "type": "keyDown", **({"text": text} if text else {})})
        self.cdp.call("Input.dispatchKeyEvent", {**params, "type": "keyUp"})

    def navigate(self, raw_url: str) -> str:
        url = normalize_url(raw_url)
        self.cdp.call("Page.navigate", {"url": url})
        return url

    def history(self, delta: int) -> bool:
        info = self.cdp.call("Page.getNavigationHistory")
        index = info["currentIndex"] + delta
        entries = info["entries"]
        if not 0 <= index < len(entries):
            return False
        self.cdp.call("Page.navigateToHistoryEntry", {"entryId": entries[index]["id"]})
        return True

    def reload(self) -> None:
        self.cdp.call("Page.reload")

    def state(self) -> dict:
        info = self.chrome.page_info()
        info.update({"width": self.width, "height": self.height})
        return info

    def handle(self, event: dict) -> dict:
        """Tarayicidan gelen JSON girdi olayini isler."""
        kind = event.get("type")
        if kind == "click":
            self.click(event["x"], event["y"], event.get("button", "left"))
        elif kind == "move":
            self.move(event["x"], event["y"])
        elif kind == "wheel":
            self.wheel(event.get("x", 0), event.get("y", 0), event.get("dx", 0), event.get("dy", 0))
        elif kind == "text":
            self.text(str(event.get("text", "")))
        elif kind == "key":
            self.key(str(event.get("key", "")))
        elif kind == "go":
            return {"url": self.navigate(str(event.get("url", "")))}
        elif kind == "back":
            return {"ok": self.history(-1)}
        elif kind == "forward":
            return {"ok": self.history(1)}
        elif kind == "reload":
            self.reload()
        else:
            raise ValueError("bilinmeyen olay turu")
        return {"ok": True}

    def close(self) -> None:
        try:
            self.cdp.call("Page.stopScreencast", timeout=2)
        except (CDPError, OSError):
            pass
        self.chrome.close()
