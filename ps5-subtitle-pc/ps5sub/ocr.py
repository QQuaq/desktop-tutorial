"""English subtitle OCR with RapidOCR (PaddleOCR models on ONNX Runtime, CPU only).

RapidOCR ships its models inside the pip wheel, so it works offline right after `pip install`
on any Windows 10/11 PC. Windows.Media.Ocr needs an English OCR language pack, which a
Turkish-language Windows often does not have.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

MIN_SCORE = 0.6
LETTER = re.compile(r"[A-Za-z]")


@dataclass
class OcrLine:
    text: str
    box: tuple[float, float, float, float]  # x0, y0, x1, y1 in crop pixels


@dataclass
class OcrResult:
    lines: list[OcrLine]

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines).strip()

    @property
    def box(self) -> tuple[float, float, float, float] | None:
        if not self.lines:
            return None
        xs0, ys0, xs1, ys1 = zip(*(line.box for line in self.lines))
        return min(xs0), min(ys0), max(xs1), max(ys1)


class OcrEngine:
    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR

        self._ocr = RapidOCR()

    def read(self, rgb: np.ndarray) -> OcrResult:
        import cv2

        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        h = gray.shape[0]
        scale = 1.0
        if h < 90:
            scale = 90 / h
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        raw, _ = self._ocr(cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB))
        words = []
        for quad, text, score in raw or []:
            text = str(text).strip()
            if float(score) < MIN_SCORE or len(LETTER.findall(text)) < 1:
                continue
            xs = [p[0] / scale for p in quad]
            ys = [p[1] / scale for p in quad]
            words.append(OcrLine(text, (min(xs), min(ys), max(xs), max(ys))))
        return OcrResult(assemble_lines(words))


def assemble_lines(words: list[OcrLine]) -> list[OcrLine]:
    """Merge word boxes into text lines (top to bottom) and drop overlap fragments."""
    rows: list[list[OcrLine]] = []
    for w in sorted(words, key=lambda w: (w.box[1] + w.box[3]) / 2):
        cy = (w.box[1] + w.box[3]) / 2
        for row in rows:
            r0 = min(x.box[1] for x in row)
            r1 = max(x.box[3] for x in row)
            if r0 <= cy <= r1:
                row.append(w)
                break
        else:
            rows.append([w])

    lines = []
    for row in rows:
        row.sort(key=lambda w: w.box[0])
        merged: list[OcrLine] = []
        for w in row:
            if merged:
                prev = merged[-1]
                height = max(w.box[3] - w.box[1], 1)
                overlap = prev.box[2] - w.box[0]
                width = max(w.box[2] - w.box[0], 1)
                if overlap > 0.6 * width:
                    if len(w.text) > len(prev.text):
                        merged[-1] = w
                    continue
                if overlap > 0.25 * height:
                    tokens = prev.text.split()
                    if len(tokens) > 1 and len(tokens[-1]) <= 2:
                        merged[-1] = OcrLine(" ".join(tokens[:-1]), prev.box)
            merged.append(w)
        text = re.sub(r"\s+", " ", " ".join(w.text for w in merged)).strip()
        if len(LETTER.findall(text)) < 2:
            continue
        lines.append(
            OcrLine(
                text,
                (
                    min(w.box[0] for w in merged),
                    min(w.box[1] for w in merged),
                    max(w.box[2] for w in merged),
                    max(w.box[3] for w in merged),
                ),
            )
        )
    return lines
