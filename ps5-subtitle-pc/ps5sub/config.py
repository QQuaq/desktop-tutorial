from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


def config_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home())
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "PS5Altyazi" / "ayarlar.json"


@dataclass
class Config:
    tv_address: str = ""
    token: str = ""
    source_kind: str = "window"  # window | screen | card | file
    source_value: str = "PS Remote Play"
    capture_method: str = "auto"  # auto | printwindow | screen
    # subtitle region, fractions of the game picture: x, y, w, h
    region: list[float] = field(default_factory=lambda: [0.10, 0.72, 0.80, 0.25])
    fps: float = 4.0
    placement: str = "over"  # over: on top of the English text; bottom: fixed strip at the bottom
    ttl_ms: int = 15000
    send_to_tv: bool = True
    preview: bool = False
    server_url: str = ""  # optional live-translate PC server (sunucu.bat)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or config_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path | None = None) -> None:
        path = path or config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
