"""Komut satiri: python -m ps5mirror <ui|send-elf|discover|wake|start|check>"""
from __future__ import annotations

import argparse
import sys
import os
import time

from . import backends, config as cfgmod, discovery, payload, server, session as sessmod, wakeup


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

    p_elf = sub.add_parser("send-elf", help="ELF payload'ini konsoldaki ELF loader'a gonder")
    p_elf.add_argument("elf", help="gonderilecek .elf dosyasi")
    p_elf.add_argument("--host", help="bos ise kayitli ayardaki host")
    p_elf.add_argument("--port", type=int, help="loader portu (varsayilan 9021)")

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

    if args.cmd == "send-elf":
        try:
            cfg = cfgmod.load(path)
            host = args.host or cfg.host
            if not host or not cfgmod.is_valid_host(host):
                print("Hata: --host verin veya ayarlarda host kaydedin", file=sys.stderr)
                return 2
            sent = payload.send_elf(host, args.elf, args.port or cfg.loader_port)
        except (cfgmod.ConfigError, payload.PayloadError) as exc:
            print(f"Hata: {exc}", file=sys.stderr)
            return 2
        print(f"{sent} bayt gonderildi. Konsolda payload'in acilmasini bekleyin, sonra 'start'.")
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
        import shutil
        print("mod:", cfg.mode)
        print("ffplay:   ", shutil.which("ffplay") or "YOK")
        print("chiaki-ng:", backends.find_chiaki(cfg.chiaki_path) or "YOK")
        if cfg.mode == "payload" and cfg.host:
            try:
                st = payload.get_status(cfg.host, cfg.payload_port)
                print(f"payload: ULASILDI ({st.get('width')}x{st.get('height')}, {st.get('fps')} fps)")
            except payload.PayloadError as exc:
                print(f"payload: ulasilamadi ({exc})")
        return 1 if errors else 0

    if args.cmd == "start":
        session = sessmod.Session()
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
