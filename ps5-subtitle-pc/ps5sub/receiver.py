"""Client for the TV app's LAN overlay receiver (live-translate-tv, "Ağdan çeviri alıcı", port 8765)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

DEFAULT_PORT = 8765


class ReceiverError(Exception):
    pass


def base_url(address: str) -> str:
    address = address.strip().rstrip("/")
    if not address:
        raise ReceiverError("TV IP adresini yazın (TV'deki alıcı ekranında görünür, ör. 192.168.1.50).")
    if not re.match(r"^https?://", address):
        address = "http://" + address
    host = re.sub(r"^https?://", "", address)
    if ":" not in host.split("/")[0]:
        address += f":{DEFAULT_PORT}"
    return address


class TvReceiver:
    def __init__(self, address: str, token: str, timeout: float = 3.0):
        self.url = base_url(address)
        self.token = token.strip()
        self.timeout = timeout

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method)
        req.add_header("X-Token", self.token)
        if data is not None:
            req.add_header("Content-Type", "application/json; charset=utf-8")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                return json.loads(res.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise ReceiverError("Eşleştirme kodu yanlış. TV ekranındaki 8 karakterlik kodu girin.") from e
            raise ReceiverError(f"TV hata döndü (HTTP {e.code}).") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ReceiverError(
                f"TV'ye ulaşılamadı ({self.url}). TV'de 'Ağ alıcısını aç' açık mı, IP doğru mu, "
                "PC ile TV aynı ağda mı?"
            ) from e

    def ping(self) -> bool:
        return self._call("GET", "/ping").get("app") == "live-translate-tv"

    def status(self) -> dict:
        return self._call("GET", "/status")

    def show(self, text: str, box: tuple[float, float, float, float], lines: int = 1, ttl_ms: int = 15000) -> dict:
        x, y, w, h = box
        return self._call(
            "POST",
            "/overlay",
            {
                "coords": "normalized",
                "ttlMs": ttl_ms,
                "boxes": [
                    {
                        "x": round(x, 4),
                        "y": round(y, 4),
                        "w": round(w, 4),
                        "h": round(h, 4),
                        "text": text,
                        "lines": max(1, min(lines, 20)),
                        "bg": "#E6000000",
                        "fg": "#FFFFFF",
                    }
                ],
            },
        )

    def clear(self) -> dict:
        return self._call("DELETE", "/overlay")

    def test(self) -> str:
        """Turkish one-line result for the GUI's "Bağlantıyı dene" button."""
        if not self.ping():
            raise ReceiverError("Bu adreste Live Translate TV alıcısı yok.")
        screen = self.status().get("screen") or {}
        self.show("Bağlantı tamam — PS5 altyazı çevirmeni", (0.2, 0.82, 0.6, 0.07), 1, ttl_ms=4000)
        return f"Bağlantı tamam. TV ekranı {screen.get('width', '?')}x{screen.get('height', '?')}; TV'de test yazısı çıktı mı?"
