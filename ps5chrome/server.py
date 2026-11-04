"""PS5 tarayicisi icin HTTP sunucusu: sayfa, MJPEG akisi ve girdi API'si.

Guvenlik: sunucu LAN'dan erisilebilir oldugu icin her istek rastgele bir anahtar
(?k=...) ister. Anahtar URL'de PS5'e yazilir; kimse bilmeden Chrome'unuza erisemez.
"""
from __future__ import annotations

import hmac
import json
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .controller import Controller

WEB_DIR = Path(__file__).parent / "web"
BOUNDARY = "ps5frame"
MAX_BODY = 8 * 1024


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def make_handler(ctrl: Controller, token: str):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"
        server_version = "ps5chrome/0.1"

        def log_message(self, *args):
            pass

        def _authorized(self) -> bool:
            q = parse_qs(urlparse(self.path).query)
            given = (q.get("k") or [""])[0]
            return hmac.compare_digest(given, token)

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, json.dumps(obj).encode(), "application/json; charset=utf-8")

        def do_GET(self):
            path = urlparse(self.path).path
            if not self._authorized():
                return self._json(403, {"error": "anahtar gerekli"})
            if path == "/":
                return self._send(200, (WEB_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
            if path == "/state":
                return self._json(200, ctrl.state())
            if path == "/frame.jpg":
                frame = ctrl.latest_frame()
                if frame is None:
                    return self._json(503, {"error": "henuz kare yok"})
                return self._send(200, frame, "image/jpeg")
            if path == "/stream":
                return self._stream()
            self._json(404, {"error": "bulunamadi"})

        def _stream(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            last = 0
            try:
                while True:
                    last, frame = ctrl.wait_frame(last, timeout=5.0)
                    if frame is None:
                        continue
                    self.wfile.write(
                        f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(frame)}\r\n\r\n".encode()
                        + frame + b"\r\n")
                    self.wfile.flush()
            except OSError:
                return

        def do_POST(self):
            if not self._authorized():
                return self._json(403, {"error": "anahtar gerekli"})
            if urlparse(self.path).path != "/input":
                return self._json(404, {"error": "bulunamadi"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY:
                    return self._json(413, {"error": "istek cok buyuk"})
                event = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(event, dict):
                    raise ValueError("JSON nesnesi bekleniyor")
                self._json(200, ctrl.handle(event))
            except (ValueError, KeyError, TypeError) as exc:
                self._json(400, {"error": str(exc) or "gecersiz istek"})
            except Exception as exc:  # CDP hatalari
                self._json(502, {"error": str(exc)})

    return Handler


def create_server(ctrl: Controller, token: str, host: str = "0.0.0.0", port: int = 8080) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(ctrl, token))
    httpd.daemon_threads = True
    return httpd


def new_token() -> str:
    return secrets.token_urlsafe(9)
