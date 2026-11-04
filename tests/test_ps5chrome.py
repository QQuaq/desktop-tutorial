import base64
import http.client
import json
import os
import shutil
import socket
import struct
import tempfile
import threading
import time
import unittest
import http.server
import urllib.request

from ps5chrome import cdp, chrome, controller, server

HAVE_CHROME = chrome.find_chrome() is not None


class UrlTests(unittest.TestCase):
    def test_accepts_http_and_adds_scheme(self):
        n = controller.normalize_url
        self.assertEqual(n("example.com"), "https://example.com")
        self.assertEqual(n("http://192.168.1.2:8080/x"), "http://192.168.1.2:8080/x")
        self.assertEqual(n("localhost:3000"), "https://localhost:3000")

    def test_search_query(self):
        self.assertTrue(controller.normalize_url("ps5 oyunlari").startswith("https://www.google.com/search?q=ps5+oyunlari"))

    def test_rejects_dangerous(self):
        for bad in ("file:///etc/passwd", "javascript:alert(1)", "data:text/html,x", "about:blank",
                    "chrome://settings", "view-source:http://a", "ftp://x.com", "", "   ",
                    "http://a b/c", "x\r\ny", "http://"):
            with self.assertRaises(ValueError, msg=bad):
                controller.normalize_url(bad)


class FakeWSServer:
    """RFC 6455 sunucu tarafi: el sikisma + yankilama + parcali mesaj + ping."""

    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.got = []
        threading.Thread(target=self._run, daemon=True).start()

    def _read_frame(self, conn):
        def exact(n):
            b = b""
            while len(b) < n:
                c = conn.recv(n - len(b))
                if not c:
                    raise EOFError
                b += c
            return b
        b0, b1 = exact(2)
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack(">H", exact(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", exact(8))[0]
        mask = exact(4)
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(exact(n)))
        assert b1 & 0x80, "istemci cercevesi maskeli olmali"
        return b0 & 0x0F, data

    def _run(self):
        conn, _ = self.sock.accept()
        req = b""
        while b"\r\n\r\n" not in req:
            req += conn.recv(4096)
        key = [l.split(b": ")[1] for l in req.split(b"\r\n") if l.lower().startswith(b"sec-websocket-key")][0].decode()
        import hashlib
        acc = base64.b64encode(hashlib.sha1((key + cdp.GUID).encode()).digest()).decode()
        conn.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {acc}\r\n\r\n").encode())
        try:
            while True:
                op, data = self._read_frame(conn)
                self.got.append(data)
                msg = json.loads(data)
                # once ping, sonra parcali (2 parca) yanit
                conn.sendall(b"\x89\x00")
                reply = json.dumps({"id": msg["id"], "result": {"echo": msg["method"], "pad": "x" * 70000}}).encode()
                half = len(reply) // 2
                conn.sendall(bytes([0x01]) + self._len(half) + reply[:half])
                conn.sendall(bytes([0x80]) + self._len(len(reply) - half) + reply[half:])
                conn.sendall(self._text(json.dumps({"method": "Test.event", "params": {"a": 1}}).encode()))
        except (EOFError, ValueError, OSError):
            pass
        finally:
            conn.close()
            self.sock.close()

    @staticmethod
    def _len(n):
        if n < 126:
            return bytes([n])
        if n < 65536:
            return bytes([126]) + struct.pack(">H", n)
        return bytes([127]) + struct.pack(">Q", n)

    def _text(self, data):
        return bytes([0x81]) + self._len(len(data)) + data


class WebSocketTests(unittest.TestCase):
    def test_roundtrip_fragments_ping_and_events(self):
        srv = FakeWSServer()
        c = cdp.CDP(f"ws://127.0.0.1:{srv.port}/x")
        events = []
        got = threading.Event()
        c.on("Test.event", lambda p: (events.append(p), got.set()))
        res = c.call("Foo.bar", {"x": 1})
        self.assertEqual(res["echo"], "Foo.bar")
        self.assertEqual(len(res["pad"]), 70000)
        self.assertTrue(got.wait(2))
        self.assertEqual(events, [{"a": 1}])
        self.assertEqual(json.loads(srv.got[0])["params"], {"x": 1})
        c.close()

    def test_rejects_remote_url(self):
        with self.assertRaises(cdp.CDPError):
            cdp.WebSocket("ws://example.com/x")

    def test_mask_helper(self):
        mask = b"\x01\x02\x03\x04"
        data = bytes(range(10))
        self.assertEqual(cdp._mask_big(data, mask), bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
        self.assertEqual(cdp._mask_big(b"", mask), b"")


PAGE = b"""<!doctype html><title>start</title>
<body style="margin:0;background:#fff">
<button id=b style="position:absolute;left:100px;top:100px;width:300px;height:120px;font-size:40px"
 onclick="document.title='clicked';this.style.background='#0f0'">Tikla</button>
<input id=i style="position:absolute;left:100px;top:300px;width:400px;height:60px;font-size:30px"
 oninput="document.title='typed:'+this.value">
<div style="height:3000px"></div>
<script>onscroll=function(){document.title='scrolled'+(scrollY>0?'-yes':'')};</script>
</body>"""


@unittest.skipUnless(HAVE_CHROME, "Chrome yok")
class ChromeIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(PAGE)))
                self.end_headers()
                self.wfile.write(PAGE)

        cls.site = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=cls.site.serve_forever, daemon=True).start()
        cls.site_url = f"http://127.0.0.1:{cls.site.server_address[1]}/"
        os.environ["PS5CHROME_NO_SANDBOX"] = "1"
        cls.inst = chrome.ChromeInstance(chrome.find_chrome(), 1280, 720, True, "about:blank")
        cls.ctrl = controller.Controller(cls.inst, 50)
        cls.token = "testtoken"
        cls.httpd = server.create_server(cls.ctrl, cls.token, "127.0.0.1", 0)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.ctrl.close()
        cls.site.shutdown()

    def url(self, path):
        sep = "&" if "?" in path else "?"
        return f"http://127.0.0.1:{self.port}{path}{sep}k={self.token}"

    def post(self, ev, token=None):
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}/input?k={token or self.token}",
                                   data=json.dumps(ev).encode(), method="POST")
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def title(self, expect, timeout=5):
        end = time.time() + timeout
        t = ""
        while time.time() < end:
            t = self.inst.page_info().get("title", "")
            if t == expect:
                return t
            time.sleep(0.1)
        return t

    def test_flow(self):
        code, res = self.post({"type": "go", "url": self.site_url})
        self.assertEqual((code, res["url"]), (200, self.site_url))
        self.assertEqual(self.title("start"), "start")

        # ekran goruntusu: gecerli JPEG
        end = time.time() + 5
        frame = None
        while time.time() < end and not frame:
            frame = self.ctrl.latest_frame()
            time.sleep(0.1)
        self.assertTrue(frame and frame[:2] == b"\xff\xd8")
        with urllib.request.urlopen(self.url("/frame.jpg")) as r:
            self.assertEqual(r.read(2), b"\xff\xd8")

        # tikla
        self.assertEqual(self.post({"type": "click", "x": 200, "y": 150})[0], 200)
        self.assertEqual(self.title("clicked"), "clicked")

        # yazi: once input'a tikla, sonra metin
        self.post({"type": "click", "x": 200, "y": 330})
        self.post({"type": "text", "text": "merhaba"})
        self.assertEqual(self.title("typed:merhaba"), "typed:merhaba")
        self.post({"type": "key", "key": "Backspace"})
        self.assertEqual(self.title("typed:merhab"), "typed:merhab")

        # kaydirma
        self.post({"type": "wheel", "x": 600, "y": 400, "dy": 500})
        self.assertEqual(self.title("scrolled-yes"), "scrolled-yes")

        # yeniden yukle + gecmis
        self.post({"type": "reload"})
        self.assertIn(self.title("start"), ("start", "scrolled-yes"))
        self.assertEqual(self.post({"type": "back"})[0], 200)

    def test_mjpeg_stream(self):
        self.post({"type": "go", "url": self.site_url})
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", f"/stream?k={self.token}")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertIn("multipart/x-mixed-replace", resp.getheader("Content-Type"))
        first = resp.read(200)
        self.assertTrue(first.startswith(b"--ps5frame"))
        self.assertIn(b"image/jpeg", first)
        conn.close()

    def test_auth_and_validation(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/")
        self.assertEqual(ctx.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/?k=yanlis")
        self.assertEqual(ctx.exception.code, 403)
        self.assertEqual(self.post({"type": "click", "x": 1, "y": 1}, token="yanlis")[0], 403)
        self.assertEqual(self.post({"type": "go", "url": "file:///etc/passwd"})[0], 400)
        self.assertEqual(self.post({"type": "nope"})[0], 400)
        self.assertEqual(self.post({"type": "key", "key": "F13"})[0], 400)
        self.assertEqual(self.post({"type": "click", "x": "abc", "y": 1})[0], 400)
        with urllib.request.urlopen(self.url("/")) as r:
            self.assertIn(b"PS5 Chrome", r.read())


if __name__ == "__main__":
    unittest.main()
