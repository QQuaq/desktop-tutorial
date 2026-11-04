"""PS Remote Play arka ucu: chiaki-ng sureci icin komut olusturma ve yonetimi.

Goruntu/ses cozme ve gosterme chiaki-ng tarafindan yapilir; bu modul onu
ayarlardan baslatir/durdurur ve ciktisini izler.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
from collections import deque
from dataclasses import dataclass

from .config import Config

CHIAKI_BINARY_NAMES = ("chiaki-ng", "chiaki", "chiaki-ng.AppImage")


class BackendError(RuntimeError):
    """Arka uc baslatilamadi."""


def _windows_candidate_dirs(env: dict[str, str] | None = None) -> list[str]:
    env = os.environ if env is None else env
    dirs: list[str] = []
    for var, sub in (
        ("LOCALAPPDATA", r"Programs\chiaki-ng"),
        ("ProgramFiles", "chiaki-ng"),
        ("ProgramFiles(x86)", "chiaki-ng"),
        ("USERPROFILE", r"Downloads\chiaki-ng"),
        ("USERPROFILE", "chiaki-ng"),
    ):
        base = env.get(var)
        if base:
            dirs.append(os.path.join(base, *sub.split("\\")))
    return dirs


def find_chiaki(configured: str = "", system: str | None = None) -> str | None:
    """chiaki-ng yurutulebilir dosyasini bulur (PATH, Windows'ta yaygin kurulum klasorleri)."""
    system = system or platform.system()
    if configured:
        configured = configured.strip().strip('"')
        return configured if shutil.which(configured) or os.path.isfile(configured) else None
    for name in CHIAKI_BINARY_NAMES:
        path = shutil.which(name)
        if path:
            return path
    if system == "Windows":
        for directory in _windows_candidate_dirs():
            for name in ("chiaki-ng.exe", "chiaki.exe"):
                candidate = os.path.join(directory, name)
                if os.path.isfile(candidate):
                    return candidate
    return None


def build_remoteplay_command(cfg: Config, chiaki: str) -> list[str]:
    """chiaki-ng 'stream' alt komutu: chiaki-ng stream <profil> <host>.

    Profil, chiaki-ng icinde onceden kaydedilmis (registered) konsol adidir.
    Cozunurluk/FPS/codec chiaki-ng ayarlarindan gelir. Komut satiri bicimi
    gercek kurulumla dogrulanmamistir; uyusmazsa ayarlardaki
    extra.remoteplay_template ile ({chiaki}, {profile}, {host}) degistirilebilir.
    """
    profile = cfg.chiaki_profile or cfg.console
    template = cfg.extra.get("remoteplay_template")
    if template:
        return [part.format(chiaki=chiaki, profile=profile, host=cfg.host) for part in template]
    return [chiaki, "stream", profile, cfg.host]


@dataclass
class Status:
    running: bool
    command: list[str] | None = None
    exit_code: int | None = None


class Session:
    """Tek bir Remote Play sureci (chiaki-ng)."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._cmd: list[str] | None = None
        self.log: deque[str] = deque(maxlen=200)
        self._lock = threading.Lock()

    def start(self, cfg: Config) -> list[str]:
        cfg.require_valid()
        chiaki = find_chiaki(cfg.chiaki_path)
        if not chiaki:
            raise BackendError(
                "chiaki-ng bulunamadi. Kurun (https://github.com/streetpea/chiaki-ng), "
                "konsolu chiaki-ng icinde kaydedin (registration) ya da chiaki_path "
                "ayarini girin.")
        cmd = build_remoteplay_command(cfg, chiaki)
        with self._lock:
            if self._proc and self._proc.poll() is None:
                raise BackendError("zaten calisan bir oturum var")
            try:
                self._proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    # Windows'ta konsol penceresi acilmasin
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except OSError as exc:
                raise BackendError(f"surec baslatilamadi: {exc}") from exc
            self._cmd = cmd
            self.log.clear()
            threading.Thread(target=self._pump, args=(self._proc,), daemon=True).start()
        return cmd

    def _pump(self, proc: subprocess.Popen) -> None:
        assert proc.stdout is not None
        with proc.stdout:
            for line in proc.stdout:
                self.log.append(line.rstrip())

    def stop(self) -> None:
        with self._lock:
            proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def status(self) -> Status:
        proc = self._proc
        if proc is None:
            return Status(running=False)
        code = proc.poll()
        return Status(running=code is None, command=self._cmd, exit_code=code)
