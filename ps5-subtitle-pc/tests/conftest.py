import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


@pytest.fixture
def mock_tv():
    from mock_tv import MockTv

    tv = MockTv().start()
    yield tv
    tv.stop()


@pytest.fixture(scope="session")
def ocr_engine():
    from ps5sub.ocr import OcrEngine

    return OcrEngine()
