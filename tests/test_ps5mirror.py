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

from ps5mirror import backends, config, discovery, server, wakeup

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
        cfg = {"host": "10.0.0.2", "chiaki_path": "/yok/chiaki"}
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


if __name__ == "__main__":
    unittest.main()
