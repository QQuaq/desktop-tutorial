"""Turns noisy per-frame OCR text into clean "show" / "clear" subtitle events."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

_NON_WORD = re.compile(r"[^a-z0-9 ]+")
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    return _SPACES.sub(" ", _NON_WORD.sub(" ", text.lower())).strip()


def similar(a: str, b: str, threshold: float) -> bool:
    if not a or not b:
        return False
    return a == b or SequenceMatcher(None, a, b).ratio() >= threshold


@dataclass
class Event:
    kind: str  # "show" or "clear"
    text: str = ""


class SubtitleStabilizer:
    """
    - A subtitle is shown only after it was read the same way (fuzzy) in `min_stable` frames,
      so half-faded or typewriter frames are skipped.
    - OCR jitter on the same subtitle ("I'm" / "Im") does not trigger a new translation.
    - After `clear_after` frames without text the overlay is cleared.
    """

    def __init__(self, min_stable: int = 2, clear_after: int = 3, threshold: float = 0.85, min_letters: int = 4):
        self.min_stable = min_stable
        self.clear_after = clear_after
        self.threshold = threshold
        self.min_letters = min_letters
        self.shown: str | None = None
        self._pending = ""
        self._pending_raw = ""
        self._pending_count = 0
        self._empty = 0

    def feed(self, text: str) -> Event | None:
        norm = normalize(text)
        if sum(c.isalpha() for c in norm) < self.min_letters:
            self._pending, self._pending_count = "", 0
            self._empty += 1
            if self.shown is not None and self._empty >= self.clear_after:
                self.shown = None
                return Event("clear")
            return None

        self._empty = 0
        if similar(norm, self._pending, self.threshold):
            self._pending_count += 1
            if len(text) >= len(self._pending_raw):
                self._pending_raw = text
        else:
            self._pending, self._pending_raw, self._pending_count = norm, text, 1

        if self._pending_count < self.min_stable:
            return None
        if self.shown is not None and similar(self._pending, self.shown, self.threshold):
            return None
        self.shown = self._pending
        return Event("show", self._pending_raw.strip())

    def reset(self) -> None:
        self.__init__(self.min_stable, self.clear_after, self.threshold, self.min_letters)
