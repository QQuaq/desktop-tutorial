"""Komut satiri: python -m ps5mirror <ui|discover|wake|start|check>"""
from __future__ import annotations

import argparse
import sys
import time

import os

from . import backends, config as cfgmod, discovery, server, wakeup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ps5mirror", description="PS5 ekran yansitma")
    parser.add_argument("--config", help="ayar dosyasi yolu")
    sub = parser.add_subparsers(dest="cmd")

    p_ui = sub.add_parser("ui", help="web arayuzunu baslat (varsayilan)")
    p_ui.add_argument("--port", type=int, default=8765)
    p_ui.add_argument("--no-browser", action="store_true")

    p_disc = sub.add_parser("discover", help="agdaki konsollari bul")
    p_disc.add_argument("--console", choices=cfgmod.CONSOLES, default="PS5")
    p_disc.add_argument("--timeout", type=float, default=2.0)

    p_wake = sub.add_parser("wake", help="dinlenme modundaki konsolu uyandir (regist anahtari gerekir)")
    p_wake.add_argument("--host", required=True)
    p_wake.add_argument("--console", choices=cfgmod.CONSOLES, default="PS5")

    sub.add_parser("start", help="kayitli ayarlarla yansitmayi baslat")
    sub.add_parser("check", help="ayarlari ve bagimliliklari kontrol et")

    args = parser.parse_args(argv)
    path = None
    if args.config:
        from pathlib import Path
        path = Path(args.config)

    if args.cmd in (None, "ui"):
        server.serve(getattr(args, "port", 8765), not getattr(args, "no_browser", False), path)
        return 0

    if args.cmd == "discover":
        found = discovery.discover(args.console, args.timeout)
        if not found:
            print("Konsol bulunamadi (ayni agda ve acik/dinlenme modunda mi?).")
            return 1
        for f in found:
            print(f"{f.address}\t{f.host_type}\t{f.host_name}\t{f.status}")
        return 0

    if args.cmd == "wake":
        credential = os.environ.get("PS5_CREDENTIAL", "").strip()
        try:
            wakeup.wake(args.host, credential, args.console)
        except ValueError as exc:
            print(f"Hata: {exc} (ortam degiskeni PS5_CREDENTIAL)", file=sys.stderr)
            return 2
        print("Uyandirma paketi gonderildi.")
        return 0

    try:
        cfg = cfgmod.load(path)
    except cfgmod.ConfigError as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 2

    if args.cmd == "check":
        errors = cfg.validate()
        for e in errors:
            print(f"AYAR: {e}")
        print("chiaki-ng:", backends.find_chiaki(cfg.chiaki_path) or "YOK")
        return 1 if errors else 0

    if args.cmd == "start":
        session = backends.Session()
        try:
            cmd = session.start(cfg)
        except (cfgmod.ConfigError, backends.BackendError) as exc:
            print(f"Hata: {exc}", file=sys.stderr)
            return 2
        print("Calisiyor:", " ".join(cmd))
        try:
            while session.status().running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            session.stop()
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
