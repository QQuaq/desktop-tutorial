"""CI check on real Windows: show a fake "PS Remote Play" window with a sample frame, capture it with
both methods (covered-window PrintWindow and screen copy), OCR the subtitle region, build the GUI."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageTk  # noqa: E402

from ps5sub import winapi  # noqa: E402
from ps5sub.capture import WindowSource, suggest_window  # noqa: E402
from ps5sub.ocr import OcrEngine  # noqa: E402
from ps5sub.pipeline import crop_region  # noqa: E402


def main() -> int:
    winapi.make_dpi_aware()
    root = tk.Tk()
    root.title("PS Remote Play")
    img = Image.open(ROOT / "samples" / "frame_08.png").resize((1024, 576))
    photo = ImageTk.PhotoImage(img)
    # letterbox like Remote Play does when the window is not 16:9
    tk.Label(root, image=photo, bg="black", bd=0).pack(padx=0, pady=40)
    root.configure(bg="black")
    root.geometry("+50+50")
    for _ in range(20):
        root.update()
    root.after(300)
    root.update()

    print("windows:", [t for _, t in winapi.list_windows()][:15])
    assert suggest_window() == "PS Remote Play", "suggest_window did not find the fake Remote Play window"
    ocr = OcrEngine()
    ok = False
    for method in ("printwindow", "screen", "auto"):
        src = WindowSource("PS Remote Play", method)
        frame = src.grab()
        root.update()
        src.close()
        text = ocr.read(crop_region(frame, [0.15, 0.72, 0.70, 0.25])).text if frame is not None else ""
        ok = "marina" in text.lower()
        print(f"{method}: frame={None if frame is None else frame.shape} ok={ok} text={text!r}")
        if frame is not None:
            Image.fromarray(frame).save(ROOT / f"smoke_{method}.png")
    root.destroy()

    from ps5sub.gui import App

    app = App()
    app.update()
    app.destroy()
    print("GUI ok")
    return 0 if ok else 1  # "auto" is the default the user gets


if __name__ == "__main__":
    sys.exit(main())
