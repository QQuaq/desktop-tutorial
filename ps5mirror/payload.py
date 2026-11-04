"""Jailbreak'li PS5'te calisan bir payload'in HTTP akisini izleme.

PS5 tarafinda bir ELF payload (ornegin acik kaynak Glint, GPLv3) konsolun kendi
H.264 kodlayicisindan goruntuyu alip HTTP ile sunar. Bu modul:
  * ELF'i konsoldaki ELF loader portuna (varsayilan 9021) gonderir,
  * payload'in HTTP API'sini (varsayilan 7231) okur,
  * /frames akisini cozup ffplay'e H.264 olarak verir (istege bagli /audio).

Protokol, Glint docs/API.md belgesine dayanir. Gercek konsolla test edilmemistir;
sahte bir payload sunucusuna karsi birim testlidir.
"""
from __future__ import annotations

import http.client
import json
import os
import shutil
import socket
import struct
import subprocess
import threading
from collections import deque

from .backends import BackendError, Status
from .config import Config

MAX_VIDEO_FRAME = 2 * 1024 * 1024
MAX_AUDIO_PACKET = 64 * 1024
PCM_FORMATS = {"pcm_f32le": "f32le", "pcm_s16le": "s16le", "pcm_s32le": "s32le"}
ELF_MAGIC = b"\x7fELF"


class PayloadError(RuntimeError):
    """Payload ile iletisim hatasi."""


def send_elf(host: str, path: str, port: int = 9021, timeout: float = 10.0) -> int:
    """ELF dosyasini konsoldaki ELF loader'a TCP ile gonderir; gonderilen bayt sayisini dondurur."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise PayloadError(f"ELF okunamadi: {exc}") from exc
    if not data.startswith(ELF_MAGIC):
        raise PayloadError("dosya bir ELF degil (basinda 7f 45 4c 46 yok)")
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(data)
    except OSError as exc:
        raise PayloadError(
            f"{host}:{port} adresine baglanilamadi ({exc}). ELF loader acik mi?") from exc
    return len(data)


def _get_json(host: str, port: int, path: str, timeout: float = 3.0) -> dict:
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read(1 << 20)
        if resp.status != 200:
            raise PayloadError(f"{path}: HTTP {resp.status}")
        return json.loads(body)
    except (OSError, http.client.HTTPException, json.JSONDecodeError) as exc:
        raise PayloadError(f"{host}:{port}{path} okunamadi: {exc}") from exc
    finally:
        conn.close()


def get_config(host: str, port: int = 7231) -> dict:
    return _get_json(host, port, "/config.json")


def get_status(host: str, port: int = 7231) -> dict:
    return _get_json(host, port, "/status.json")


def read_exactly(resp, n: int) -> bytes:
    chunks: list[bytes] = []
    remaining = n
    while remaining:
        chunk = resp.read(remaining)
        if not chunk:
            raise EOFError("akis kapandi")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def iter_frames(resp, max_size: int):
    """[u32 uzunluk BE][u32 zaman damgasi BE][veri] cercevelerini uretir: (pts, veri)."""
    while True:
        header = read_exactly(resp, 8)
        length, pts = struct.unpack(">II", header)
        if length > max_size:
            raise PayloadError(f"gecersiz cerceve boyutu: {length}")
        yield pts, read_exactly(resp, length) if length else b""


def open_stream(host: str, port: int, path: str, timeout: float = 10.0):
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
    except (OSError, http.client.HTTPException) as exc:
        conn.close()
        raise PayloadError(f"{host}:{port} adresine baglanilamadi: {exc}") from exc
    if resp.status == 409:
        conn.close()
        raise PayloadError("baska bir izleyici bagli (tarayici veya Glint.exe'yi kapatin)")
    if resp.status == 503:
        conn.close()
        raise PayloadError("payload mesgul (cok fazla istemci)")
    if resp.status != 200:
        conn.close()
        raise PayloadError(f"{path}: HTTP {resp.status}")
    return conn, resp


def default_player_command(ffplay: str, fmt: str, extra: list[str] | None = None, video: bool = True) -> list[str]:
    cmd = [ffplay, "-hide_banner", "-loglevel", "warning"]
    if video:
        cmd += ["-window_title", "PS5 Mirror", "-fflags", "nobuffer", "-flags", "low_delay",
                "-framedrop", "-probesize", "32", "-analyzeduration", "0"]
    else:
        cmd += ["-nodisp", "-autoexit"]
    cmd += ["-f", fmt]
    cmd += extra or []
    cmd += ["-i", "-"]
    return cmd


class PayloadSession:
    """Payload akisini oynatici sureclere (ffplay) aktaran oturum."""

    def __init__(self) -> None:
        self.log: deque[str] = deque(maxlen=200)
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._procs: list[subprocess.Popen] = []
        self._conns: list = []
        self._lock = threading.Lock()
        self._cmd: list[str] | None = None
        self._running = False
        self._error: str | None = None

    def start(self, cfg: Config) -> list[str]:
        cfg.require_valid()
        with self._lock:
            if self._running:
                raise BackendError("zaten calisan bir oturum var")
        custom = cfg.extra.get("player_command")
        ffplay = None if custom else shutil.which("ffplay")
        if not custom and not ffplay:
            raise BackendError("ffplay bulunamadi. FFmpeg kurun: winget install Gyan.FFmpeg")

        try:
            conf = get_config(cfg.host, cfg.payload_port)
        except PayloadError as exc:
            raise BackendError(
                f"payload'a ulasilamadi: {exc}. ELF'i gonderdiniz mi? "
                f"(ps5mirror send-elf <dosya.elf>)") from exc

        video_cmd = custom or default_player_command(ffplay, "h264")
        audio_cmd = None
        audio_conf = conf.get("audio")
        if cfg.audio and audio_conf:
            fmt = PCM_FORMATS.get(audio_conf.get("codec", ""))
            if fmt and ffplay:
                audio_cmd = default_player_command(
                    ffplay, fmt,
                    ["-ar", str(audio_conf.get("rate", 48000)), "-ac", str(audio_conf.get("channels", 2))],
                    video=False)
        try:
            vconn, vresp = open_stream(cfg.host, cfg.payload_port, "/frames")
        except PayloadError as exc:
            raise BackendError(str(exc)) from exc

        self._stop.clear()
        self.log.clear()
        self._error = None
        try:
            vproc = subprocess.Popen(video_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as exc:
            vconn.close()
            raise BackendError(f"oynatici baslatilamadi: {exc}") from exc
        self._procs = [vproc]
        self._conns = [vconn]
        self._threads = [threading.Thread(
            target=self._pump, args=("video", vresp, vproc, MAX_VIDEO_FRAME), daemon=True)]

        if audio_cmd:
            try:
                aconn, aresp = open_stream(cfg.host, cfg.payload_port, "/audio")
                aproc = subprocess.Popen(audio_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self._procs.append(aproc)
                self._conns.append(aconn)
                self._threads.append(threading.Thread(
                    target=self._pump, args=("audio", aresp, aproc, MAX_AUDIO_PACKET), daemon=True))
            except (PayloadError, OSError) as exc:
                self.log.append(f"ses acilamadi, yalnizca goruntu: {exc}")

        self._cmd = [f"payload http://{cfg.host}:{cfg.payload_port}/frames", "->"] + video_cmd
        self._running = True
        self.log.append(f"{conf.get('width')}x{conf.get('height')}@{conf.get('fps')} akis basladi")
        for t in self._threads:
            t.start()
        return self._cmd

    def _pump(self, name: str, resp, proc: subprocess.Popen, max_size: int) -> None:
        try:
            for _pts, data in iter_frames(resp, max_size):
                if self._stop.is_set():
                    return
                if proc.poll() is not None:
                    self.log.append(f"{name} oynaticisi kapandi")
                    return
                proc.stdin.write(data)
                proc.stdin.flush()
        except (EOFError, OSError, PayloadError, http.client.HTTPException) as exc:
            if not self._stop.is_set():
                self._error = f"{name}: {exc}"
                self.log.append(f"{name} akisi bitti: {exc}")
        finally:
            if name == "video":
                self._finish()
            else:
                try:
                    proc.stdin.close()
                except OSError:
                    pass

    def _finish(self, graceful: bool = True) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
        self._stop.set()
        for conn in self._conns:
            try:
                conn.close()
            except OSError:
                pass
        for proc in self._procs:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except OSError:
                pass
            if graceful:
                try:
                    proc.wait(timeout=2)  # oynatici kalan kareleri bitirsin
                except subprocess.TimeoutExpired:
                    pass
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()

    def stop(self) -> None:
        self._stop.set()
        self._finish(graceful=False)

    def status(self):
        if self._cmd is None:
            return Status(running=False)
        return Status(running=self._running, command=self._cmd,
                      exit_code=None if self._running else (1 if self._error else 0))
