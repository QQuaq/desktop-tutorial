"""EN -> TR translation, same keyless chain as live-translate (server gtx -> Lingva -> MyMemory),
with an optional offline Argos Translate fallback when it is installed."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from collections import OrderedDict
from typing import Callable

USER_AGENT = "Mozilla/5.0 (compatible; PS5Altyazi/1.0)"
SPEAKER = re.compile(r"^([A-Z][A-Za-z.' -]{0,20}):\s+(.+)$")
Provider = Callable[[str], "str | None"]


class TranslationError(Exception):
    pass


def _is_bad(text: str) -> bool:
    return bool(re.search(r"MYMEMORY WARNING", text, re.I) or re.match(r"NEXT AVAILABLE IN", text, re.I))


def _get_json(url: str, timeout: float, data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def via_google_gtx(text: str, timeout: float = 6.0) -> str | None:
    q = urllib.parse.urlencode({"client": "gtx", "sl": "en", "tl": "tr", "dt": "t", "q": text})
    data = _get_json(f"https://translate.googleapis.com/translate_a/single?{q}", timeout)
    segments = data[0] if isinstance(data, list) else None
    if not isinstance(segments, list):
        return None
    out = "".join(str(p[0] or "") for p in segments if isinstance(p, list)).strip()
    return out or None


def via_lingva(text: str, timeout: float = 6.0) -> str | None:
    data = _get_json(f"https://lingva.ml/api/v1/en/tr/{urllib.parse.quote(text, safe='')}", timeout)
    out = str(data.get("translation") or "").strip()
    return out if out and not _is_bad(out) else None


def via_mymemory(text: str, timeout: float = 6.0) -> str | None:
    q = urllib.parse.urlencode({"q": text, "langpair": "en|tr"})
    data = _get_json(f"https://api.mymemory.translated.net/get?{q}", timeout)
    if data.get("responseStatus") == 403:
        return None
    out = str((data.get("responseData") or {}).get("translatedText") or "").strip()
    return out if out and not _is_bad(out) else None


def via_live_translate_server(base_url: str) -> Provider:
    """The repo's live-translate PC server (sunucu.bat), POST /api/translate."""

    def run(text: str, timeout: float = 6.0) -> str | None:
        body = json.dumps({"text": text}).encode("utf-8")
        data = _get_json(base_url.rstrip("/") + "/api/translate", timeout, body, {"Content-Type": "application/json"})
        out = str(data.get("translated") or "").strip()
        return out or None

    return run


def argos_provider() -> Provider | None:
    """Offline fallback; only if `argostranslate` and its en->tr package are installed."""
    try:
        from argostranslate import translate as argos  # type: ignore
    except Exception:
        return None
    langs = {lang.code: lang for lang in argos.get_installed_languages()}
    if "en" not in langs or "tr" not in langs:
        return None
    translation = langs["en"].get_translation(langs["tr"])
    if translation is None:
        return None
    return lambda text: translation.translate(text).strip() or None


class Translator:
    def __init__(self, providers: list[Provider] | None = None, server_url: str = "", cache_size: int = 500):
        if providers is None:
            providers = []
            if server_url.strip():
                providers.append(via_live_translate_server(server_url.strip()))
            providers += [via_google_gtx, via_lingva, via_mymemory]
            offline = argos_provider()
            if offline:
                providers.append(offline)
        self.providers = providers
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._cache_size = cache_size

    def translate(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            raise TranslationError("Çevrilecek metin boş.")
        speaker = SPEAKER.match(text)
        if speaker:
            return f"{speaker.group(1)}: {self._translate_cached(speaker.group(2))}"
        return self._translate_cached(text)

    def _translate_cached(self, text: str) -> str:
        if text in self._cache:
            self._cache.move_to_end(text)
            return self._cache[text]
        for provider in self.providers:
            try:
                result = provider(text)
            except Exception:
                result = None
            if result and not _is_bad(result):
                self._cache[text] = result
                if len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
                return result
        raise TranslationError("Çeviri kotası veya servis hatası. Biraz bekleyip tekrar deneyin.")
