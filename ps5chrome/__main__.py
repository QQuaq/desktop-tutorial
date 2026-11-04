"""PS5 icin uzak Chrome: python -m ps5chrome [--port 8080] [--url https://...]"""
from __future__ import annotations

import argparse
import sys

from . import chrome as chromemod, controller, server


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ps5chrome", description="PS5 tarayicisinda uzak Chrome")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="0.0.0.0", help="dinlenecek adres (varsayilan: tum LAN)")
    ap.add_argument("--url", default="https://www.google.com", help="acilis sayfasi")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--quality", type=int, default=60, help="JPEG kalitesi (1-100)")
    ap.add_argument("--chrome", default="", help="Chrome/Edge yolu")
    ap.add_argument("--show-window", action="store_true", help="Chrome penceresini goster (headless degil)")
    ap.add_argument("--token", default="", help="erisim anahtari (bos: rastgele)")
    args = ap.parse_args(argv)

    exe = chromemod.find_chrome(args.chrome)
    if not exe:
        print("Hata: Chrome/Edge bulunamadi. --chrome ile yolunu verin.", file=sys.stderr)
        return 2
    try:
        start_url = controller.normalize_url(args.url)
    except ValueError as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 2
    if not 1 <= args.quality <= 100 or not 320 <= args.width <= 3840 or not 240 <= args.height <= 2160:
        print("Hata: gecersiz boyut/kalite", file=sys.stderr)
        return 2

    inst = chromemod.ChromeInstance(exe, args.width, args.height, not args.show_window, start_url)
    ctrl = controller.Controller(inst, args.quality)
    token = args.token or server.new_token()
    httpd = server.create_server(ctrl, token, args.host, args.port)
    shown = server.lan_ip() if args.host in ("0.0.0.0", "") else args.host
    print("PS5'in tarayicisinda su adresi acin:")
    print(f"  http://{shown}:{httpd.server_address[1]}/?k={token}")
    print("Anahtari paylasmayin; ayni agdaki herkes bu adresle Chrome'unuzu kullanabilir. Ctrl+C ile cikis.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        ctrl.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
