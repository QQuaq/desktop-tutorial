import numpy as np
import pytest

from ps5sub.capture import trim_black_bars
from ps5sub.config import Config
from ps5sub.ocr import OcrLine, assemble_lines
from ps5sub.pipeline import overlay_box
from ps5sub.ocr import OcrResult
from ps5sub.receiver import ReceiverError, TvReceiver, base_url
from ps5sub.stabilizer import SubtitleStabilizer
from ps5sub.translate import TranslationError, Translator


def test_stabilizer_needs_two_frames_and_ignores_jitter():
    s = SubtitleStabilizer()
    assert s.feed("We need to get out of here") is None
    ev = s.feed("We need to get out of here!")
    assert ev.kind == "show" and ev.text == "We need to get out of here!"
    assert s.feed("We need to get out of hene") is None
    assert s.feed("We need to get out of here") is None


def test_stabilizer_switches_and_clears():
    s = SubtitleStabilizer()
    s.feed("First line of dialogue")
    s.feed("First line of dialogue")
    assert s.feed("Completely different sentence") is None
    assert s.feed("Completely different sentence").text == "Completely different sentence"
    assert s.feed("") is None
    assert s.feed("$1") is None
    assert s.feed("").kind == "clear"
    assert s.feed("") is None


def test_assemble_lines_merges_words_and_drops_fragments():
    words = [
        OcrLine("We need to get out of here, r", (100, 10, 400, 40)),
        OcrLine("now!", (390, 12, 450, 40)),
        OcrLine("Second", (120, 60, 200, 90)),
        OcrLine("line", (210, 60, 260, 90)),
    ]
    lines = assemble_lines(words)
    assert [l.text for l in lines] == ["We need to get out of here, now!", "Second line"]
    assert lines[0].box == (100, 10, 450, 40)


def test_translator_chain_falls_back_and_caches():
    calls = []

    def broken(text):
        calls.append("broken")
        raise OSError("offline")

    def quota(text):
        calls.append("quota")
        return "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS"

    def good(text):
        calls.append("good")
        return {"We have to go.": "Gitmeliyiz."}[text]

    t = Translator(providers=[broken, quota, good])
    assert t.translate("Jason: We have to go.") == "Jason: Gitmeliyiz."
    assert t.translate("We  have to go.") == "Gitmeliyiz."
    assert calls == ["broken", "quota", "good"]
    with pytest.raises(TranslationError):
        Translator(providers=[broken]).translate("hi there")


def test_base_url():
    assert base_url("192.168.1.50") == "http://192.168.1.50:8765"
    assert base_url(" http://192.168.1.50:9000/ ") == "http://192.168.1.50:9000"
    with pytest.raises(ReceiverError):
        base_url("")


def test_receiver_against_mock(mock_tv):
    rx = TvReceiver(mock_tv.address, "secret12")
    assert "Bağlantı tamam" in rx.test()
    assert mock_tv.frames[-1]["boxes"][0]["text"].startswith("Bağlantı tamam")
    rx.clear()
    assert mock_tv.clears == 1
    with pytest.raises(ReceiverError, match="kodu yanlış"):
        TvReceiver(mock_tv.address, "wrong").status()
    with pytest.raises(ReceiverError, match="ulaşılamadı"):
        TvReceiver("127.0.0.1:1", "x", timeout=1).ping()


def test_trim_black_bars_only_for_16_9_content():
    frame = np.zeros((800, 1280, 3), np.uint8)
    frame[40:760, :] = 120  # 1280x720 picture with 40 px bars
    assert trim_black_bars(frame).shape == (720, 1280, 3)
    dark_scene = np.full((720, 1280, 3), 120, np.uint8)
    dark_scene[:300] = 0
    assert trim_black_bars(dark_scene).shape == (720, 1280, 3)


def test_overlay_box_maps_crop_to_screen():
    cfg = Config(region=[0.1, 0.7, 0.8, 0.3])
    ocr = OcrResult([OcrLine("hello there", (100, 50, 300, 80))])
    x, y, w, h = overlay_box(cfg, (300, 1000, 3), ocr)
    assert 0 <= x and x + w <= 1 and 0 <= y and y + h <= 1
    assert abs((x + w / 2) - (0.1 + 200 / 1000 * 0.8)) < 1e-6
    assert w == pytest.approx(0.3)
    cfg.placement = "bottom"
    assert overlay_box(cfg, (300, 1000, 3), ocr) == (0.10, 0.93 - 0.055, 0.80, 0.055)
