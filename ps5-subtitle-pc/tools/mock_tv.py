"""Stand-in for the TV app's overlay receiver (same routes, token check and box parsing as
live-translate-tv RemoteOverlayServer.kt). Run: python tools/mock_tv.py [port] [token]"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class MockTv:
    def __init__(self, port: int = 0, token: str = "secret12", screen=(1920, 1080)):
        self.token = token
        self.screen = screen
        self.frames: list[dict] = []
        self.clears = 0
        tv = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _reply(self, code: int, body: dict):
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _authorised(self) -> bool:
                header = self.headers.get("X-Token") or (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
                query = self.path.partition("token=")[2].split("&")[0]
                return header == tv.token or query == tv.token

            def _route(self, method: str):
                path = self.path.split("?")[0]
                if path in ("/", "/ping"):
                    return self._reply(200, {"app": "live-translate-tv"})
                if not self._authorised():
                    return self._reply(401, {"error": "missing or wrong token"})
                if method == "GET" and path == "/status":
                    return self._reply(200, {"screen": {"width": tv.screen[0], "height": tv.screen[1]}})
                if method == "POST" and path == "/overlay":
                    body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                    boxes = []
                    if str(body.get("subtitle") or "").strip():
                        boxes.append({"x": 0.1, "y": 0.8, "w": 0.8, "h": 0.09, "text": body["subtitle"].strip(), "lines": 1})
                    for i, b in enumerate(body.get("boxes") or []):
                        if not str(b.get("text") or "").strip():
                            continue
                        for key in ("x", "y", "w", "h"):
                            if key not in b:
                                return self._reply(400, {"error": f"box {i}: missing '{key}'"})
                        boxes.append(b)
                    tv.frames.append({"boxes": boxes, "ttlMs": body.get("ttlMs", 10000)})
                    return self._reply(200, {"ok": True, "boxes": len(boxes)})
                if (method == "DELETE" and path == "/overlay") or (method == "POST" and path == "/clear"):
                    tv.clears += 1
                    return self._reply(200, {"ok": True})
                return self._reply(404, {"error": "unknown endpoint"})

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

            def do_DELETE(self):
                self._route("DELETE")

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.port = self.server.server_address[1]

    @property
    def address(self) -> str:
        return f"127.0.0.1:{self.port}"

    def start(self) -> "MockTv":
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def stop(self) -> None:
        self.server.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    tv = MockTv(port, sys.argv[2] if len(sys.argv) > 2 else "secret12").start()
    print(f"Mock TV on http://{tv.address} token={tv.token}")
    threading.Event().wait()
