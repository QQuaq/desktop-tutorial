"""Yerel agda PS4/PS5 kesfi (Remote Play discovery protokolu, UDP).

NOT: Paket bicimi chiaki projesinin belgelenmis davranisina dayanir. Gercek bir
konsolla dogrulanmamistir; ayrisim (parse) kismi birim testlidir.
"""
from __future__ import annotations

import re
import socket
import time
from dataclasses import dataclass

PORTS = {"PS5": 9302, "PS4": 987}
PROTOCOL_VERSIONS = {"PS5": "00030010", "PS4": "00020020"}


@dataclass
class DiscoveredConsole:
    address: str
    host_type: str = ""
    host_name: str = ""
    host_id: str = ""
    status: str = ""
    request_port: str = ""
    system_version: str = ""
    running_app: str = ""

    @property
    def is_standby(self) -> bool:
        # 620 "Server Standby": konsol dinlenme modunda (once uyandirilmali)
        return "standby" in self.status.lower()


def build_search_packet(console: str = "PS5") -> bytes:
    version = PROTOCOL_VERSIONS[console]
    return f"SRCH * HTTP/1.1\ndevice-discovery-protocol-version:{version}\n".encode()


def parse_response(data: bytes, address: str) -> DiscoveredConsole | None:
    text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
    lines = text.split("\n")
    match = re.match(r"HTTP/1\.1 (200|620)\b\s*(.*)", lines[0] if lines else "")
    if not match:
        return None
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip().lower()] = value.strip()
    status_line = match.group(2).strip()
    return DiscoveredConsole(
        address=address,
        host_type=fields.get("host-type", ""),
        host_name=fields.get("host-name", ""),
        host_id=fields.get("host-id", ""),
        status=status_line,
        request_port=fields.get("host-request-port", ""),
        system_version=fields.get("system-version", ""),
        running_app=fields.get("running-app-name", ""),
    )


def discover(
    console: str = "PS5",
    timeout: float = 2.0,
    target: str = "255.255.255.255",
    port: int | None = None,
) -> list[DiscoveredConsole]:
    """Broadcast gonderip yanit verenleri toplar."""
    port = port or PORTS[console]
    found: dict[str, DiscoveredConsole] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.2)
        sock.sendto(build_search_packet(console), (target, port))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            info = parse_response(data, addr[0])
            if info:
                found[info.address] = info
    return list(found.values())
