"""Capture -> crop -> OCR -> stabilize -> translate -> TV overlay."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .capture import CaptureError, Source
from .config import Config
from .ocr import OcrEngine, OcrResult
from .receiver import ReceiverError, TvReceiver
from .stabilizer import SubtitleStabilizer
from .translate import TranslationError, Translator

Listener = Callable[[str, dict], None]


def crop_region(frame: np.ndarray, region: list[float]) -> np.ndarray:
    h, w = frame.shape[:2]
    x, y, rw, rh = region
    x0, y0 = int(max(0.0, x) * w), int(max(0.0, y) * h)
    x1, y1 = int(min(1.0, x + rw) * w), int(min(1.0, y + rh) * h)
    return frame[y0:max(y1, y0 + 1), x0:max(x1, x0 + 1)]


def overlay_box(cfg: Config, crop_shape: tuple[int, ...], ocr: OcrResult) -> tuple[float, float, float, float]:
    """Normalized TV box covering the English subtitle (Turkish is ~15% longer, so widen it)."""
    lines = max(1, len(ocr.lines))
    if cfg.placement != "over" or ocr.box is None:
        h = 0.055 * lines
        return 0.10, 0.93 - h, 0.80, h
    ch, cw = crop_shape[:2]
    rx, ry, rw, rh = cfg.region
    bx0, by0, bx1, by1 = ocr.box
    x0, x1 = rx + bx0 / cw * rw, rx + bx1 / cw * rw
    y0, y1 = ry + by0 / ch * rh, ry + by1 / ch * rh
    width = min(1.0, max((x1 - x0) * 1.2, 0.3))
    cx = (x0 + x1) / 2
    left = min(max(0.0, cx - width / 2), 1.0 - width)
    pad = (y1 - y0) * 0.12
    top = max(0.0, y0 - pad)
    return left, top, width, min(1.0 - top, (y1 - y0) + 2 * pad)


@dataclass
class StepResult:
    english: str
    event: str | None = None  # "show" | "clear"
    turkish: str = ""


class Pipeline:
    def __init__(
        self,
        cfg: Config,
        source: Source,
        ocr: OcrEngine,
        translator: Translator,
        receiver: TvReceiver | None,
        listener: Listener | None = None,
    ):
        self.cfg = cfg
        self.source = source
        self.ocr = ocr
        self.translator = translator
        self.receiver = receiver
        self.listener = listener or (lambda kind, data: None)
        self.stabilizer = SubtitleStabilizer()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_thumb: np.ndarray | None = None
        self._last_ocr = OcrResult([])
        self._sent: tuple | None = None
        self._sent_at = 0.0

    def emit(self, kind: str, **data) -> None:
        try:
            self.listener(kind, data)
        except Exception:
            pass

    def _send(self, text: str, box, lines: int) -> None:
        self._sent, self._sent_at = (text, box, lines), time.monotonic()
        if self.receiver is None:
            return
        try:
            self.receiver.show(text, box, lines, self.cfg.ttl_ms)
        except ReceiverError as e:
            self.emit("error", message=str(e))

    def _clear(self) -> None:
        self._sent = None
        if self.receiver is None:
            return
        try:
            self.receiver.clear()
        except ReceiverError as e:
            self.emit("error", message=str(e))

    def step(self, frame: np.ndarray) -> StepResult:
        crop = crop_region(frame, self.cfg.region)
        thumb = crop[::4, ::4].mean(axis=2)
        if (
            self._last_thumb is not None
            and self._last_thumb.shape == thumb.shape
            and float(np.abs(thumb - self._last_thumb).mean()) < 1.5
        ):
            ocr = self._last_ocr
        else:
            ocr = self.ocr.read(crop)
        self._last_thumb, self._last_ocr = thumb, ocr

        result = StepResult(ocr.text)
        event = self.stabilizer.feed(ocr.text)
        if event is None:
            if self._sent and time.monotonic() - self._sent_at > self.cfg.ttl_ms / 2000:
                self._send(*self._sent)
            return result
        result.event = event.kind
        if event.kind == "clear":
            self._clear()
            self.emit("clear")
            return result
        try:
            turkish = self.translator.translate(event.text)
        except TranslationError as e:
            self.emit("error", message=str(e))
            self.stabilizer.shown = None
            return result
        result.turkish = turkish
        box = overlay_box(self.cfg, crop.shape, ocr)
        self._send(turkish, box, len(ocr.lines))
        self.emit("subtitle", english=event.text, turkish=turkish, box=box)
        return result

    def run(self) -> None:
        interval = 1.0 / max(0.5, self.cfg.fps)
        self.emit("status", message=f"Çalışıyor: {self.source.name}")
        last_error = ""
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                frame = self.source.grab()
                if frame is None:
                    if getattr(self.source, "finished", False):
                        break
                else:
                    self.step(frame)
                    last_error = ""
            except CaptureError as e:
                if str(e) != last_error:
                    self.emit("error", message=str(e))
                    last_error = str(e)
            except Exception as e:  # keep running through one bad frame
                self.emit("error", message=f"Beklenmeyen hata: {e!r}")
            self._stop.wait(max(0.0, interval - (time.monotonic() - started)))
        if self._sent:
            self._clear()
        self.source.close()
        self.emit("status", message="Durduruldu.")
        self.emit("stopped")

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
