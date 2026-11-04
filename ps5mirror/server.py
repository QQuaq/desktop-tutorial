"""Yerel web arayuzu (yalnizca 127.0.0.1). Harici bagimlilik yok."""
from __future__ import annotations

import json
import shutil
import threading
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import backends, config as cfgmod, discovery, payload, session as sessmod

WEB_DIR = Path(__file__).parent / "web"
MAX_BODY = 64 * 1024


class App:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path
        self.session = sessmod.Session()
        self.lock = threading.Lock()

    def get_config(self) -> cfgmod.Config:
        return cfgmod.load(self.config_path)

    def dependencies(self) -> dict:
        cfg = self.get_config()
        return {
            "chiaki": backends.find_chiaki(cfg.chiaki_path),
            "ffplay": shutil.which("ffplay"),
        }


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ps5mirror/0.1"

        def log_message(self, *args):  # sessiz
            pass

        def _send(self, code: int, payload, content_type="application/json") -> None:
            body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _origin_ok(self) -> bool:
            # DNS rebinding / baska sitelerden gelen istekleri engelle.
            host = self.headers.get("Host", "")
            if host.split(":")[0] not in ("127.0.0.1", "localhost"):
                return False
            origin = self.headers.get("Origin")
            if origin and origin.split("://", 1)[-1].split(":")[0] not in ("127.0.0.1", "localhost"):
                return False
            return True

        def _json_body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise cfgmod.ConfigError("istek cok buyuk")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                raise cfgmod.ConfigError("gecersiz JSON") from None
            if not isinstance(data, dict):
                raise cfgmod.ConfigError("JSON nesnesi bekleniyor")
            return data

        def do_GET(self):
            if not self._origin_ok():
                return self._send(403, {"error": "yasak"})
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                return self._send(200, (WEB_DIR / "index.html").read_bytes(), "text/html")
            if path == "/api/config":
                return self._send(200, asdict(app.get_config()))
            if path == "/api/payload-status":
                cfg = app.get_config()
                if not cfg.host:
                    return self._send(400, {"errors": ["once PS5 IP adresini kaydedin"]})
                try:
                    return self._send(200, {"reachable": True,
                                            "status": payload.get_status(cfg.host, cfg.payload_port)})
                except payload.PayloadError as exc:
                    return self._send(200, {"reachable": False, "error": str(exc)})
            if path == "/api/status":
                st = app.session.status()
                return self._send(200, {**asdict(st), "log": list(app.session.log)[-30:],
                                        "dependencies": app.dependencies()})
            self._send(404, {"error": "bulunamadi"})

        def do_POST(self):
            if not self._origin_ok():
                return self._send(403, {"error": "yasak"})
            path = self.path.split("?")[0]
            try:
                if path == "/api/config":
                    cfg = cfgmod.from_dict(self._json_body())
                    errors = cfg.validate()
                    if errors:
                        return self._send(400, {"errors": errors})
                    cfgmod.save(cfg, app.config_path)
                    return self._send(200, asdict(cfg))
                if path == "/api/discover":
                    body = self._json_body()
                    console = body.get("console", "PS5")
                    if console not in cfgmod.CONSOLES:
                        raise cfgmod.ConfigError("gecersiz console")
                    found = discovery.discover(console, timeout=float(body.get("timeout", 2.0)))
                    return self._send(200, [asdict(f) for f in found])
                if path == "/api/send-elf":
                    body = self._json_body()
                    cfg = app.get_config()
                    cfg.require_valid()
                    elf = str(body.get("path", "")).strip().strip('"')
                    if not elf.lower().endswith(".elf"):
                        raise cfgmod.ConfigError("yalnizca .elf dosyalari gonderilebilir")
                    sent = payload.send_elf(cfg.host, elf, cfg.loader_port)
                    return self._send(200, {"sent_bytes": sent})
                if path == "/api/start":
                    with app.lock:
                        cmd = app.session.start(app.get_config())
                    return self._send(200, {"started": True, "command": cmd})
                if path == "/api/stop":
                    app.session.stop()
                    return self._send(200, {"stopped": True})
            except (cfgmod.ConfigError, TypeError) as exc:
                return self._send(400, {"errors": [str(exc)]})
            except (backends.BackendError, payload.PayloadError) as exc:
                return self._send(409, {"errors": [str(exc)]})
            self._send(404, {"error": "bulunamadi"})

    return Handler


def create_server(app: App, port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))


def serve(port: int = 8765, open_browser: bool = True, config_path: Path | None = None) -> None:
    app = App(config_path)
    httpd = create_server(app, port)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"PS5 Mirror arayuzu: {url}  (Ctrl+C ile cikis)")
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.session.stop()
        httpd.server_close()
