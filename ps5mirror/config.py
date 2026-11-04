"""Ayar dosyasi yukleme/kaydetme ve dogrulama."""
from __future__ import annotations

import ipaddress
import json
import os
import platform
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONSOLES = ("PS5", "PS4")
MODES = ("payload", "remoteplay")


class ConfigError(ValueError):
    """Gecersiz ayar."""


def default_config_path() -> Path:
    override = os.environ.get("PS5MIRROR_CONFIG")
    if override:
        return Path(override)
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "ps5mirror" / "config.json"


@dataclass
class Config:
    # payload: jailbreak'li PS5'e yuklenen ELF'in actigi HTTP portundan izle (varsayilan)
    # remoteplay: chiaki-ng ile PS Remote Play (PSN gerekir)
    mode: str = "payload"
    console: str = "PS5"
    host: str = ""
    payload_port: int = 7231
    loader_port: int = 9021
    audio: bool = False
    # Cozunurluk/FPS/codec chiaki-ng icinde ayarlanir.
    chiaki_path: str = ""
    chiaki_profile: str = ""
    extra: dict = field(default_factory=dict)

    def validate(self) -> list[str]:
        """Hata mesajlari listesi dondurur (bos liste = gecerli)."""
        errors: list[str] = []
        if self.mode not in MODES:
            errors.append(f"mode su degerlerden biri olmali: {', '.join(MODES)}")
        for name in ("payload_port", "loader_port"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 65535:
                errors.append(f"{name} 1-65535 araligindaki bir sayi olmali")
        if not isinstance(self.audio, bool):
            errors.append("audio true/false olmali")
        if self.console not in CONSOLES:
            errors.append(f"console su degerlerden biri olmali: {', '.join(CONSOLES)}")
        if not self.host:
            errors.append("PS5 IP adresi/host gerekli")
        elif not is_valid_host(self.host):
            errors.append(f"gecersiz host: {self.host!r}")
        if self.chiaki_profile.startswith("-"):
            errors.append("chiaki_profile '-' ile baslayamaz")
        for key in ("remoteplay_template", "player_command"):
            value = self.extra.get(key)
            if value is not None and not (
                isinstance(value, list) and value and all(isinstance(t, str) for t in value)
            ):
                errors.append(f"extra.{key} bos olmayan bir metin listesi olmali")
        return errors

    def require_valid(self) -> None:
        errors = self.validate()
        if errors:
            raise ConfigError("; ".join(errors))


def is_valid_host(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    return bool(re.fullmatch(r"[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", host))


def from_dict(data: dict) -> Config:
    known = {f for f in Config.__dataclass_fields__}
    unknown = set(data) - known
    if unknown:
        raise ConfigError(f"bilinmeyen ayar(lar): {', '.join(sorted(unknown))}")
    cfg = Config(**data)
    if not isinstance(cfg.extra, dict):
        raise ConfigError("extra bir nesne olmali")
    return cfg


def load(path: Path | None = None) -> Config:
    path = path or default_config_path()
    if not path.exists():
        return Config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"ayar dosyasi bozuk ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("ayar dosyasi bir JSON nesnesi olmali")
    return from_dict(data)


def save(cfg: Config, path: Path | None = None) -> Path:
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return path
