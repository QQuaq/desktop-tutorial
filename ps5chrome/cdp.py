"""Minimal WebSocket istemcisi (RFC 6455) ve Chrome DevTools Protocol baglantisi.

Yalnizca standart kutuphane kullanilir.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import threading
from typing import Callable
from urllib.parse import urlparse

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class CDPError(RuntimeError):
    pass


class WebSocket:
    def __init__(self, url: str, timeout: float = 10.0) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "ws" or parsed.hostname not in ("127.0.0.1", "localhost"):
            raise CDPError("yalnizca yerel ws:// adreslerine baglanilir")
        self.sock = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        self.sock.sendall((
            f"GET {path} HTTP/1.1\r\nHost: {parsed.hostname}:{parsed.port}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        header = b""
        while b"\r\n\r\n" not in header:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CDPError("el sikisma basarisiz (baglanti kapandi)")
            header += chunk
            if len(header) > 16384:
                raise CDPError("el sikisma yaniti cok buyuk")
        head, _, rest = header.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        if " 101 " not in lines[0]:
            raise CDPError(f"el sikisma reddedildi: {lines[0]}")
        accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
        if f"sec-websocket-accept: {accept}".lower() not in head.decode("latin-1").lower():
            raise CDPError("gecersiz Sec-WebSocket-Accept")
        self._buf = rest
        self.sock.settimeout(None)
        self._send_lock = threading.Lock()

    def _recv_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise EOFError("websocket kapandi")
            self._buf += chunk
        data, self._buf = self._buf[:n], self._buf[n:]
        return data

    def send_text(self, text: str) -> None:
        self._send_frame(0x1, text.encode())

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        header = bytes([0x80 | opcode])
        n = len(payload)
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        masked = _mask_big(payload, mask)
        with self._send_lock:
            self.sock.sendall(header + mask + masked)

    def recv_text(self) -> str:
        message = b""
        while True:
            b0, b1 = self._recv_exact(2)
            fin, opcode = b0 & 0x80, b0 & 0x0F
            length = b1 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._recv_exact(8))[0]
            if b1 & 0x80:
                mask = self._recv_exact(4)
                data = _mask_big(self._recv_exact(length), mask)
            else:
                data = self._recv_exact(length)
            if opcode == 0x8:
                raise EOFError("websocket kapatildi")
            if opcode == 0x9:
                self._send_frame(0xA, data)
                continue
            if opcode == 0xA:
                continue
            message += data
            if fin:
                return message.decode("utf-8")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def _mask_big(data: bytes, mask: bytes) -> bytes:
    n = len(data)
    full = (mask * (n // 4 + 1))[:n]
    return (int.from_bytes(data, "big") ^ int.from_bytes(full, "big")).to_bytes(n, "big") if n else b""


class CDP:
    """Tek bir sayfa hedefine CDP baglantisi: komut/yanit ve olaylar."""

    def __init__(self, ws_url: str) -> None:
        self.ws = WebSocket(ws_url)
        self._id = 0
        self._id_lock = threading.Lock()
        self._pending: dict[int, dict] = {}
        self._handlers: dict[str, list[Callable[[dict], None]]] = {}
        self.closed = threading.Event()
        threading.Thread(target=self._reader, daemon=True).start()

    def on(self, method: str, handler: Callable[[dict], None]) -> None:
        self._handlers.setdefault(method, []).append(handler)

    def _reader(self) -> None:
        try:
            while True:
                msg = json.loads(self.ws.recv_text())
                if "id" in msg:
                    slot = self._pending.get(msg["id"])
                    if slot:
                        slot["result"] = msg
                        slot["event"].set()
                else:
                    for h in self._handlers.get(msg.get("method", ""), []):
                        try:
                            h(msg.get("params", {}))
                        except Exception:  # bir isleyici hatasi okuyucuyu durdurmasin
                            pass
        except (EOFError, OSError, ValueError):
            pass
        finally:
            self.closed.set()
            for slot in list(self._pending.values()):
                slot["event"].set()

    def call(self, method: str, params: dict | None = None, timeout: float = 15.0) -> dict:
        with self._id_lock:
            self._id += 1
            cid = self._id
        slot = {"event": threading.Event(), "result": None}
        self._pending[cid] = slot
        try:
            self.ws.send_text(json.dumps({"id": cid, "method": method, "params": params or {}}))
            if not slot["event"].wait(timeout):
                raise CDPError(f"{method}: zaman asimi")
            msg = slot["result"]
            if msg is None:
                raise CDPError("baglanti kapandi")
            if "error" in msg:
                raise CDPError(f"{method}: {msg['error'].get('message', msg['error'])}")
            return msg.get("result", {})
        finally:
            self._pending.pop(cid, None)

    def send(self, method: str, params: dict | None = None) -> None:
        """Yanit beklemeden komut gonder."""
        with self._id_lock:
            self._id += 1
            cid = self._id
        self.ws.send_text(json.dumps({"id": cid, "method": method, "params": params or {}}))

    def close(self) -> None:
        self.ws.close()
