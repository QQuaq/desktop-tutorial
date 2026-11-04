"""Ayarlardaki moda gore dogru oturumu secen ince katman."""
from __future__ import annotations

from collections import deque

from .backends import Session as RemotePlaySession, Status
from .config import Config
from .payload import PayloadSession


class Session:
    def __init__(self) -> None:
        self._remote = RemotePlaySession()
        self._payload = PayloadSession()
        self._active = self._payload

    @property
    def log(self) -> deque:
        return self._active.log

    def start(self, cfg: Config) -> list[str]:
        cfg.require_valid()
        self._active = self._payload if cfg.mode == "payload" else self._remote
        return self._active.start(cfg)

    def stop(self) -> None:
        self._remote.stop()
        self._payload.stop()

    def status(self) -> Status:
        return self._active.status()
