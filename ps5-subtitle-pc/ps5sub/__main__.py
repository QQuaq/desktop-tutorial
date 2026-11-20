"""Entry point.

  PS5Altyazi.exe                      -> GUI
  PS5Altyazi.exe --self-test          -> OCR + translation check, exit code 0/1
  python -m ps5sub --cli --source file --value samples --tv 192.168.1.50 --token ABCD1234
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _assets() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "ps5sub" / "assets"


def self_test() -> int:
    import numpy as np
    from PIL import Image

    from .ocr import OcrEngine
    from .pipeline import crop_region
    from .translate import TranslationError, Translator

    frame = np.asarray(Image.open(_assets() / "selftest.png").convert("RGB"))
    text = OcrEngine().read(crop_region(frame, [0.15, 0.72, 0.70, 0.25])).text
    print(f"OCR: {text!r}")
    ok = "marina" in text.lower()
    try:
        print(f"Çeviri: {Translator().translate(text)!r}")
    except TranslationError as e:
        print(f"Çeviri: (internet yok?) {e}")
    print("SELF-TEST", "OK" if ok else "FAILED")
    return 0 if ok else 1


def cli(args) -> int:
    from .capture import open_source
    from .config import Config
    from .ocr import OcrEngine
    from .pipeline import Pipeline
    from .receiver import TvReceiver
    from .translate import Translator

    cfg = Config.load()
    cfg.source_kind, cfg.source_value = args.source, args.value
    if args.tv:
        cfg.tv_address, cfg.token = args.tv, args.token or cfg.token
    if args.region:
        cfg.region = [float(v) for v in args.region.split(",")]
    cfg.fps = args.fps
    source = open_source(cfg.source_kind, cfg.source_value, cfg.capture_method)
    if args.source == "file":
        source.loop = False
    receiver = TvReceiver(cfg.tv_address, cfg.token) if cfg.tv_address else None

    def listen(kind, data):
        if kind == "subtitle":
            print(f"EN: {data['english']}\nTR: {data['turkish']}\n", flush=True)
        elif kind in ("error", "status"):
            print(f"[{kind}] {data['message']}", flush=True)

    pipeline = Pipeline(cfg, source, OcrEngine(), Translator(server_url=cfg.server_url), receiver, listen)
    try:
        pipeline.run()
    except KeyboardInterrupt:
        pipeline.stop()
    return 0


def _attach_log() -> None:
    """The windowed .exe has no console (sys.stdout is None); write prints to a log file instead."""
    if sys.stdout is not None:
        return
    from .config import config_path

    path = config_path().with_name("ps5altyazi.log")
    path.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout = sys.stderr = open(path, "w", encoding="utf-8", buffering=1)


def main() -> int:
    _attach_log()
    parser = argparse.ArgumentParser(prog="ps5sub")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--cli", action="store_true", help="arayüzsüz çalıştır")
    parser.add_argument("--source", default="window", choices=["window", "screen", "card", "file"])
    parser.add_argument("--value", default="PS Remote Play")
    parser.add_argument("--tv", default="")
    parser.add_argument("--token", default="")
    parser.add_argument("--region", default="", help="x,y,w,h (0-1)")
    parser.add_argument("--fps", type=float, default=4.0)
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.cli:
        return cli(args)
    from .gui import main as gui_main

    gui_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
