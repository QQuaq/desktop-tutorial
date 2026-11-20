"""Generate GTA-style test frames (white outlined subtitle over a busy game-like scene).

Usage: python tools/make_samples.py [out_dir]
Writes frame_XX.png plus manifest.json ({"file": ..., "text": ... or null}).
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720

TIMELINE: list[str | None] = [
    None,
    "Jason: We need to get out of here, now!",
    "Jason: We need to get out of here, now!",
    "Jason: We need to get out of here, now!",
    "Lucia: Relax. Nobody followed us from the bank.\nJust keep driving and stay on the highway.",
    "Lucia: Relax. Nobody followed us from the bank.\nJust keep driving and stay on the highway.",
    None,
    None,
    "Meet me at the marina before sunset.",
    "Meet me at the marina before sunset.",
]

FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def scene(seed: int) -> Image.Image:
    rnd = random.Random(seed)
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    top = (rnd.randint(200, 255), rnd.randint(120, 180), rnd.randint(80, 140))
    bottom = (rnd.randint(40, 90), rnd.randint(60, 120), rnd.randint(110, 170))
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    for _ in range(40):
        x, y = rnd.randint(-100, W), rnd.randint(H // 3, H)
        w, h = rnd.randint(40, 260), rnd.randint(60, 400)
        c = tuple(rnd.randint(30, 230) for _ in range(3))
        d.rectangle([x, y - h, x + w, y], fill=c)
    for _ in range(8):  # palm-tree-ish blobs and cars
        x, y = rnd.randint(0, W), rnd.randint(H // 2, H)
        r = rnd.randint(20, 70)
        d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(rnd.randint(0, 255) for _ in range(3)))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    d = ImageDraw.Draw(img)
    # minimap + money HUD, which must stay outside / be ignored by the subtitle region
    d.ellipse([30, H - 200, 210, H - 20], fill=(30, 40, 50), outline=(240, 240, 240), width=3)
    d.text((W - 220, 30), "$1,250,400", font=font(34), fill=(120, 230, 120), stroke_width=2, stroke_fill=(0, 0, 0))
    return img


def draw_subtitle(img: Image.Image, text: str) -> None:
    d = ImageDraw.Draw(img)
    f = font(30)
    lines = text.split("\n")
    line_h = 40
    y = int(H * 0.86) - line_h * (len(lines) - 1)
    for line in lines:
        name, sep, rest = line.partition(": ")
        parts = [(name + sep, (250, 200, 60)), (rest, (255, 255, 255))] if sep else [(line, (255, 255, 255))]
        total = sum(d.textlength(p, font=f) for p, _ in parts)
        x = (W - total) / 2
        for part, colour in parts:
            d.text((x, y), part, font=f, fill=colour, stroke_width=3, stroke_fill=(0, 0, 0))
            x += d.textlength(part, font=f)
        y += line_h


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "samples")
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, text in enumerate(TIMELINE):
        img = scene(seed=i // 3)
        if text:
            draw_subtitle(img, text)
        name = f"frame_{i:02d}.png"
        img.save(out / name, optimize=True)
        manifest.append({"file": name, "text": text})
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(manifest)} frames -> {out}")


if __name__ == "__main__":
    main()
