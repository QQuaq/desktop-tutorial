import json
import os
import stat
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
import socket
import struct
import sys
import http.server

from ps5mirror import backends, config, discovery, payload, server, session, wakeup

SAMPLE = (
    "HTTP/1.1 200 Ok\n"
    "host-id:A1B2C3D4E5F6\n"
    "host-type:PS5\n"
    "host-name:PS5-Salon\n"
    "host-request-port:997\n"
    "device-discovery-protocol-version:00030010\n"
    "system-version:05000000\n"
).encode()


class ConfigTests(unittest.TestCase):
    def test_defaults_need_host(self):
        errors = config.Config().validate()
        self.assertTrue(any("IP" in e for e in errors))

    def test_valid(self):
        self.assertEqual(config.Config(host="192.168.1.50").validate(), [])
        self.assertEqual(config.Config(host="ps5.local").validate(), [])

    def test_invalid_host_and_profile(self):
        self.assertTrue(config.Config(host="-evil").validate())
        self.assertTrue(config.Config(host="a b").validate())
        self.assertTrue(config.Config(host="1.2.3.4", chiaki_profile="--x").validate())
        self.assertTrue(config.Config(host="1.2.3.4", console="Xbox").validate())

    def test_roundtrip_and_errors(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "sub" / "c.json"
            cfg = config.Config(host="10.0.0.2", chiaki_profile="Salon")
            config.save(cfg, path)
            self.assertEqual(config.load(path), cfg)
            path.write_text("{bozuk")
            with self.assertRaises(config.ConfigError):
                config.load(path)
            path.write_text('{"nope": 1}')
            with self.assertRaises(config.ConfigError):
                config.load(path)
            self.assertEqual(config.load(Path(d) / "yok.json"), config.Config())


class DiscoveryTests(unittest.TestCase):
    def test_packet(self):
        self.assertIn(b"SRCH * HTTP/1.1", discovery.build_search_packet("PS5"))
        self.assertIn(b"00030010", discovery.build_search_packet("PS5"))

    def test_parse(self):
        info = discovery.parse_response(SAMPLE, "10.0.0.9")
        self.assertEqual(info.host_name, "PS5-Salon")
        self.assertEqual(info.host_type, "PS5")
        self.assertEqual(info.address, "10.0.0.9")
        self.assertFalse(info.is_standby)

    def test_parse_standby_and_garbage(self):
        info = discovery.parse_response(b"HTTP/1.1 620 Server Standby\nhost-type:PS5\n", "1.1.1.1")
        self.assertTrue(info.is_standby)
        self.assertEqual(info.address, "1.1.1.1")
        self.assertIsNone(discovery.parse_response(b"foo", "1.1.1.1"))

    def test_discover_against_fake_console(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]

        def respond():
            data, addr = srv.recvfrom(1024)
            if data.startswith(b"SRCH"):
                srv.sendto(SAMPLE, addr)

        t = threading.Thread(target=respond, daemon=True)
        t.start()
        found = discovery.discover("PS5", timeout=1.0, target="127.0.0.1", port=port)
        srv.close()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].host_name, "PS5-Salon")


class WakeupTests(unittest.TestCase):
    def test_packet(self):
        pkt = wakeup.build_wakeup_packet("123456789", "PS5").decode()
        self.assertTrue(pkt.startswith("WAKEUP * HTTP/1.1"))
        self.assertIn("user-credential:123456789", pkt)

    def test_bad_credential(self):
        for bad in ("", "abc", "12 3"):
            with self.assertRaises(ValueError):
                wakeup.build_wakeup_packet(bad)

    def test_send_to_local_udp(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        srv.bind(("127.0.0.1", 0))
        srv.settimeout(2)
        wakeup.wake("127.0.0.1", "42", port=srv.getsockname()[1])
        data, _ = srv.recvfrom(1024)
        srv.close()
        self.assertIn(b"user-credential:42", data)


class BackendTests(unittest.TestCase):
    def test_command(self):
        cfg = config.Config(host="10.0.0.2", chiaki_profile="Salon")
        self.assertEqual(backends.build_remoteplay_command(cfg, "/x/chiaki-ng"),
                         ["/x/chiaki-ng", "stream", "Salon", "10.0.0.2"])
        cfg = config.Config(host="10.0.0.2")
        self.assertEqual(backends.build_remoteplay_command(cfg, "c")[2], "PS5")

    def test_template(self):
        cfg = config.Config(host="10.0.0.2", extra={"remoteplay_template": ["{chiaki}", "--host={host}", "{profile}"]})
        self.assertEqual(backends.build_remoteplay_command(cfg, "c"), ["c", "--host=10.0.0.2", "PS5"])

    def test_find_chiaki(self):
        self.assertIsNone(backends.find_chiaki("/yok/boyle/bir/dosya"))

    def test_windows_candidate_dirs(self):
        env = {"LOCALAPPDATA": "C:/Users/Q/AppData/Local", "ProgramFiles": "C:/Program Files"}
        dirs = backends._windows_candidate_dirs(env)
        self.assertEqual(len(dirs), 2)
        self.assertTrue(dirs[0].endswith("chiaki-ng") and "Programs" in dirs[0])

    def test_find_chiaki_in_windows_install_dir(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "Programs" / "chiaki-ng"
            target.mkdir(parents=True)
            exe = target / "chiaki-ng.exe"
            exe.write_text("")
            old = {k: os.environ.get(k) for k in ("LOCALAPPDATA", "PATH")}
            os.environ["LOCALAPPDATA"] = d
            os.environ["PATH"] = ""
            try:
                self.assertEqual(backends.find_chiaki("", system="Windows"), str(exe))
                self.assertIsNone(backends.find_chiaki("", system="Linux"))
            finally:
                for k, v in old.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v

    def test_configured_path_with_quotes(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / "chiaki-ng.exe"
            exe.write_text("")
            self.assertEqual(backends.find_chiaki(f'"{exe}"'), str(exe))

    def _fake_chiaki(self, d: str, body: str) -> str:
        path = Path(d) / "fake-chiaki"
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return str(path)

    @unittest.skipIf(os.name == "nt", "sh gerekli")
    def test_session_lifecycle_with_fake_chiaki(self):
        with tempfile.TemporaryDirectory() as d:
            fake = self._fake_chiaki(d, 'echo "args: $@"\nsleep 30\n')
            cfg = config.Config(host="10.0.0.2", chiaki_path=fake)
            s = backends.Session()
            cmd = s.start(cfg)
            self.assertEqual(cmd[1:], ["stream", "PS5", "10.0.0.2"])
            self.assertTrue(s.status().running)
            with self.assertRaises(backends.BackendError):
                s.start(cfg)
            for _ in range(20):
                if s.log:
                    break
                time.sleep(0.1)
            self.assertIn("args: stream PS5 10.0.0.2", list(s.log))
            s.stop()
            self.assertFalse(s.status().running)

    @unittest.skipIf(os.name == "nt", "sh gerekli")
    def test_session_reports_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            fake = self._fake_chiaki(d, "exit 3\n")
            s = backends.Session()
            s.start(config.Config(host="10.0.0.2", chiaki_path=fake))
            for _ in range(30):
                if not s.status().running:
                    break
                time.sleep(0.1)
            self.assertEqual(s.status().exit_code, 3)

    def test_missing_chiaki_message(self):
        cfg = config.Config(host="10.0.0.2", chiaki_path="/yok/chiaki")
        with self.assertRaises(backends.BackendError) as ctx:
            backends.Session().start(cfg)
        self.assertIn("chiaki-ng", str(ctx.exception))

    def test_invalid_config_blocks_start(self):
        with self.assertRaises(config.ConfigError):
            backends.Session().start(config.Config())


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = server.App(Path(self.tmp.name) / "c.json")
        self.httpd = server.create_server(self.app, 0)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def req(self, path, body=None, headers=None):
        data = None if body is None else json.dumps(body).encode()
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data,
                                   headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read() or b"null") if resp.headers["Content-Type"].startswith("application/json") else resp.read()
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_index_served(self):
        code, body = self.req("/")
        self.assertEqual(code, 200)
        self.assertIn(b"PS5 Mirror", body)

    def test_config_save_and_load(self):
        code, cfg = self.req("/api/config")
        self.assertEqual(code, 200)
        cfg["host"] = "192.168.1.50"
        code, _ = self.req("/api/config", cfg)
        self.assertEqual(code, 200)
        self.assertEqual(self.req("/api/config")[1]["host"], "192.168.1.50")

    def test_config_validation_error(self):
        code, body = self.req("/api/config", {"host": "bad host"})
        self.assertEqual(code, 400)
        self.assertIn("errors", body)

    def test_unknown_field(self):
        code, _ = self.req("/api/config", {"zzz": 1})
        self.assertEqual(code, 400)

    def test_start_without_host_is_400_and_missing_chiaki_is_409(self):
        self.assertEqual(self.req("/api/start", {})[0], 400)
        cfg = {"mode": "remoteplay", "host": "10.0.0.2", "chiaki_path": "/yok/chiaki"}
        self.assertEqual(self.req("/api/config", cfg)[0], 200)
        code, body = self.req("/api/start", {})
        self.assertEqual(code, 409)
        self.assertIn("chiaki-ng", body["errors"][0])

    def test_status(self):
        code, body = self.req("/api/status")
        self.assertEqual(code, 200)
        self.assertFalse(body["running"])
        self.assertIn("dependencies", body)

    def test_rejects_foreign_origin_and_host(self):
        code, _ = self.req("/api/config", {"host": "1.2.3.4"}, {"Origin": "http://evil.example"})
        self.assertEqual(code, 403)
        code, _ = self.req("/api/status", headers={"Host": "evil.example"})
        self.assertEqual(code, 403)

    def test_discover_endpoint_rejects_bad_console(self):
        self.assertEqual(self.req("/api/discover", {"console": "Xbox"})[0], 400)

    def test_payload_status_endpoint(self):
        fake = FakePayload()
        try:
            self.assertEqual(self.req("/api/config", {"host": "127.0.0.1", "payload_port": fake.port})[0], 200)
            code, body = self.req("/api/payload-status")
            self.assertEqual((code, body["reachable"]), (200, True))
        finally:
            fake.close()
        code, body = self.req("/api/payload-status")
        self.assertFalse(body["reachable"])

    def test_send_elf_endpoint(self):
        loader = FakeLoader()
        elf = Path(self.tmp.name) / "a.elf"
        elf.write_bytes(b"\x7fELFabc")
        self.req("/api/config", {"host": "127.0.0.1", "loader_port": loader.port})
        code, body = self.req("/api/send-elf", {"path": str(elf)})
        loader.thread.join(3)
        self.assertEqual((code, body["sent_bytes"]), (200, 7))
        self.assertEqual(loader.received, b"\x7fELFabc")

    def test_send_elf_endpoint_refuses_other_files(self):
        self.req("/api/config", {"host": "127.0.0.1"})
        code, _ = self.req("/api/send-elf", {"path": "/etc/passwd"})
        self.assertEqual(code, 400)

    def test_invalid_ports_and_mode(self):
        self.assertEqual(self.req("/api/config", {"host": "1.2.3.4", "payload_port": 0})[0], 400)
        self.assertEqual(self.req("/api/config", {"host": "1.2.3.4", "mode": "x"})[0], 400)


CONFIG_JSON = {"platform": "PS5", "width": 1920, "height": 1080, "fps": 60,
               "audio": {"codec": "pcm_f32le", "channels": 2, "rate": 48000, "bits": 32}}
FRAMES = [b"\x00\x00\x00\x01frame-%d" % i for i in range(5)]


def frame_bytes(data: bytes, pts: int) -> bytes:
    return struct.pack(">II", len(data), pts) + data


class FakePayload:
    """Glint HTTP API'sinin kucuk bir taklidi."""

    def __init__(self, busy=False, bad_length=False):
        outer = self

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
                    return self._json(CONFIG_JSON)
                if self.path == "/status.json":
                    return self._json({"version": "1.3", "width": 1920, "height": 1080, "fps": 60.0, "viewers": 0})
                if self.path in ("/frames", "/audio"):
                    if busy:
                        self.send_response(409)
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    self.send_response(200)
                    self.send_header("Connection", "close")
                    self.end_headers()
                    if bad_length:
                        self.wfile.write(struct.pack(">II", 0x7FFFFFFF, 0))
                        return
                    items = FRAMES if self.path == "/frames" else [b"\x00" * 16]
                    for i, f in enumerate(items):
                        self.wfile.write(frame_bytes(f, i * 1500))
                    self.wfile.flush()
                    return
                self.send_response(200)
                self.send_header("Content-Length", "11")
                self.end_headers()
                self.wfile.write(b"Unavailable")

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class FakeLoader:
    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.received = b""
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        conn, _ = self.sock.accept()
        with conn:
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                self.received += chunk
        self.sock.close()


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sink = Path(self.tmp.name) / "sink.bin"
        script = Path(self.tmp.name) / "player.py"
        script.write_text(
            "import sys, os\n"
            "out = open(sys.argv[1], 'ab', buffering=0)\n"
            "while True:\n"
            "    chunk = os.read(0, 65536)\n"
            "    if not chunk:\n"
            "        break\n"
            "    out.write(chunk)\n")
        self.player = [sys.executable, str(script), str(self.sink)]

    def tearDown(self):
        self.tmp.cleanup()

    def cfg(self, port, **kw):
        return config.Config(host="127.0.0.1", payload_port=port,
                             extra={"player_command": self.player}, **kw)

    def wait_done(self, s, timeout=5):
        end = time.time() + timeout
        while time.time() < end and s.status().running:
            time.sleep(0.05)
        time.sleep(0.2)

    def test_send_elf(self):
        loader = FakeLoader()
        elf = Path(self.tmp.name) / "p.elf"
        elf.write_bytes(b"\x7fELF" + b"\x01" * 100000)
        sent = payload.send_elf("127.0.0.1", str(elf), loader.port)
        loader.thread.join(3)
        self.assertEqual(sent, 100004)
        self.assertEqual(loader.received, elf.read_bytes())

    def test_send_elf_rejects_non_elf_and_missing_loader(self):
        bad = Path(self.tmp.name) / "x.elf"
        bad.write_bytes(b"MZ....")
        with self.assertRaises(payload.PayloadError):
            payload.send_elf("127.0.0.1", str(bad), 1)
        good = Path(self.tmp.name) / "g.elf"
        good.write_bytes(b"\x7fELFxx")
        with self.assertRaises(payload.PayloadError):
            payload.send_elf("127.0.0.1", str(good), 1)
        with self.assertRaises(payload.PayloadError):
            payload.send_elf("127.0.0.1", str(Path(self.tmp.name) / "yok.elf"), 1)

    def test_status_and_config(self):
        fake = FakePayload()
        try:
            self.assertEqual(payload.get_config("127.0.0.1", fake.port)["fps"], 60)
            self.assertEqual(payload.get_status("127.0.0.1", fake.port)["version"], "1.3")
        finally:
            fake.close()
        with self.assertRaises(payload.PayloadError):
            payload.get_status("127.0.0.1", fake.port)

    def test_iter_frames_framing(self):
        fake = FakePayload()
        try:
            conn, resp = payload.open_stream("127.0.0.1", fake.port, "/frames")
            frames = list(self._take(resp))
            conn.close()
        finally:
            fake.close()
        self.assertEqual([d for _, d in frames], FRAMES)
        self.assertEqual([p for p, _ in frames], [i * 1500 for i in range(5)])

    @staticmethod
    def _take(resp):
        try:
            yield from payload.iter_frames(resp, payload.MAX_VIDEO_FRAME)
        except EOFError:
            return

    def test_oversized_frame_rejected(self):
        fake = FakePayload(bad_length=True)
        try:
            conn, resp = payload.open_stream("127.0.0.1", fake.port, "/frames")
            with self.assertRaises(payload.PayloadError):
                next(payload.iter_frames(resp, payload.MAX_VIDEO_FRAME))
            conn.close()
        finally:
            fake.close()

    def test_busy_viewer_message(self):
        fake = FakePayload(busy=True)
        try:
            with self.assertRaises(payload.PayloadError) as ctx:
                payload.open_stream("127.0.0.1", fake.port, "/frames")
            self.assertIn("izleyici", str(ctx.exception))
        finally:
            fake.close()

    def test_session_pipes_raw_h264_to_player(self):
        fake = FakePayload()
        try:
            s = payload.PayloadSession()
            cmd = s.start(self.cfg(fake.port))
            self.assertIn("/frames", cmd[0])
            self.wait_done(s)
            self.assertEqual(self.sink.read_bytes(), b"".join(FRAMES))
            self.assertFalse(s.status().running)
        finally:
            fake.close()

    def test_session_unreachable_payload_gives_hint(self):
        from ps5mirror.backends import BackendError
        fake = FakePayload()
        port = fake.port
        fake.close()
        with self.assertRaises(BackendError) as ctx:
            payload.PayloadSession().start(self.cfg(port))
        self.assertIn("send-elf", str(ctx.exception))

    def test_facade_selects_by_mode(self):
        fake = FakePayload()
        try:
            s = session.Session()
            s.start(self.cfg(fake.port))
            self.wait_done(s)
            self.assertEqual(self.sink.read_bytes(), b"".join(FRAMES))
        finally:
            fake.close()


if __name__ == "__main__":
    unittest.main()
