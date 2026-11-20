"""End-to-end on the recorded GTA-style frames: file source -> RapidOCR -> stabilizer -> (fake) translation -> mock TV."""

import json

from ps5sub.capture import FileSource
from ps5sub.config import Config
from ps5sub.pipeline import Pipeline
from ps5sub.receiver import TvReceiver
from ps5sub.stabilizer import normalize, similar
from ps5sub.translate import Translator

from conftest import ROOT

SAMPLES = ROOT / "samples"


def test_samples_ocr(ocr_engine):
    from PIL import Image
    import numpy as np

    from ps5sub.pipeline import crop_region

    for item in json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8")):
        frame = np.asarray(Image.open(SAMPLES / item["file"]).convert("RGB"))
        text = ocr_engine.read(crop_region(frame, Config().region)).text
        if item["text"] is None:
            assert text == "", item["file"]
        else:
            assert similar(normalize(text), normalize(item["text"].replace("\n", " ")), 0.9), (item["file"], text)


def test_full_pipeline_to_mock_tv(ocr_engine, mock_tv):
    cfg = Config(tv_address=mock_tv.address, token="secret12", fps=50)
    translator = Translator(providers=[lambda text: f"[TR] {text}"])
    events = []
    pipeline = Pipeline(
        cfg, FileSource(str(SAMPLES)), ocr_engine, translator,
        TvReceiver(cfg.tv_address, cfg.token), lambda kind, data: events.append((kind, data)),
    )
    pipeline.run()

    subtitles = [d for k, d in events if k == "subtitle"]
    assert [s["english"].split(":")[0] for s in subtitles] == ["Jason", "Lucia", "Meet me at the marina before sunset."]
    assert not [d for k, d in events if k == "error"]
    assert len(mock_tv.frames) == 3
    lucia = mock_tv.frames[1]["boxes"][0]
    assert lucia["lines"] == 2 and lucia["text"].startswith("Lucia: [TR] Relax.")
    for frame in mock_tv.frames:
        box = frame["boxes"][0]
        assert 0.7 < box["y"] < 0.95 and box["x"] + box["w"] <= 1.0
    assert mock_tv.clears >= 1
