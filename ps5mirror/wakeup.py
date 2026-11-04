"""Beklemedeki (rest mode) PS5'i uyandirma.

Gereksinim: konsolla Remote Play kaydi (registration) yapilmis olmali ve
'user-credential' (regist key) elde edilmis olmali. Bu islem PSN hesabi ve
konsoldaki 8 haneli PIN ile yapilir; prototip bunu otomatiklestirmez.
Gercek konsolla test EDILMEMISTIR.
"""
from __future__ import annotations

import socket

from .discovery import PROTOCOL_VERSIONS

WAKEUP_PORTS = {"PS5": 9295, "PS4": 987}


def build_wakeup_packet(credential: str, console: str = "PS5") -> bytes:
    if not credential or not credential.isdigit():
        raise ValueError("credential yalnizca rakamlardan olusmali (regist user-credential)")
    version = PROTOCOL_VERSIONS[console]
    return (
        "WAKEUP * HTTP/1.1\n"
        "client-type:vr\n"
        "auth-type:R\n"
        "model:w\n"
        "app-type:r\n"
        f"user-credential:{credential}\n"
        f"device-discovery-protocol-version:{version}\n"
    ).encode()


def wake(host: str, credential: str, console: str = "PS5", port: int | None = None) -> None:
    packet = build_wakeup_packet(credential, console)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(packet, (host, port or WAKEUP_PORTS[console]))
