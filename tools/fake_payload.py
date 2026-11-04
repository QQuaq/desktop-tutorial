"""PS5 olmadan denemek icin sahte payload: Glint HTTP API'sinin kucuk bir taklidi.

Kullanim:  python tools/fake_payload.py [--port 7231]
Sonra:     ps5mirror ayarinda host=127.0.0.1 secip Baslat'a basin.
ffmpeg gerekir; test deseni (testsrc2) H.264 olarak 30 fps akitilir.
"""
from __future__ import annotations

import argparse
import http.server
import json
import shutil
import struct
import subprocess
import sys
import threading
import time

CONFIG = {"platform": "FAKE", "width": 1280, "height": 720, "fps": 30, "audio": None}


def split_access_units(data: bytes) -> list[bytes]:
    """Annex-B akisini AUD (NAL tipi 9) siniriyla erisim birimlerine boler."""
    starts = []
    i = 0
    while True:
        i = data.find(b"\x00\x00\x01", i)
        if i < 0 or i + 3 >= len(data):
            break
        if data[i + 3] & 0x1F == 9:
            starts.append(i - 1 if i > 0 and data[i - 1] == 0 else i)
        i += 3
    return [data[a:b] for a, b in zip(starts, starts[1:] + [len(data)])]


def make_stream(seconds: int) -> list[bytes]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("ffmpeg gerekli")
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
         "-t", str(seconds), "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
         "-g", "30", "-x264-params", "aud=1:repeat-headers=1", "-f", "h264", "-"],
        capture_output=True, check=True).stdout
    return split_access_units(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7231)
    ap.add_argument("--seconds", type=int, default=10)
    args = ap.parse_args()
    units = make_stream(args.seconds)
    print(f"{len(units)} kare hazir; 127.0.0.1:{args.port} dinleniyor")

    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _json(self, obj):
            body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/config.json":
                return self._json(CONFIG)
            if self.path == "/status.json":
                return self._json({"version": "fake", "width": 1280, "height": 720, "fps": 30.0, "viewers": 0})
            if self.path == "/frames":
                self.send_response(200)
                self.send_header("Connection", "close")
                self.end_headers()
                t0 = time.monotonic()
                try:
                    for i, au in enumerate(units):
                        time.sleep(max(0, t0 + i / 30 - time.monotonic()))
                        self.wfile.write(struct.pack(">II", len(au), i * 3000) + au)
                        self.wfile.flush()
                except OSError:
                    pass
                return
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), H)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
