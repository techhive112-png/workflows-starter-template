from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from spectakeoff.evaluate import similarity
from spectakeoff.ocr import installed_languages
from spectakeoff.vision import BLANK, DRAWING_RASTER, PHOTO, classify_raster, scan_drawing
from synthetic import LABELS, VERTICAL_LABELS, make_drawing, make_photo

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
needs_ocr = pytest.mark.skipif("eng" not in installed_languages(), reason="Tesseract eng not installed")


def load(name):
    return cv2.cvtColor(np.array(Image.open(EXAMPLES / name).convert("RGB")), cv2.COLOR_RGB2BGR)


def test_classification():
    assert classify_raster(make_drawing()[0])[0] == DRAWING_RASTER
    assert classify_raster(make_photo())[0] == PHOTO
    assert classify_raster(np.full((400, 600), 255, np.uint8))[0] == BLANK
    assert classify_raster(load("steel_connection_photo.webp"))[0] == PHOTO
    assert classify_raster(load("isometric_details_drawing.webp"))[0] == DRAWING_RASTER


@needs_ocr
def test_synthetic_drawing_recall_and_positions():
    img, truth = make_drawing()
    scan = scan_drawing(img, "eng")
    found = 0
    for t in truth:
        best = max(scan.lines, key=lambda ln: similarity(ln.text, t["text"]))
        if similarity(best.text, t["text"]) >= 0.85:
            found += 1
            x0, y0, x1, y1 = t["bbox"]
            cx, cy = (best.bbox.x0 + best.bbox.x1) / 2, (best.bbox.y0 + best.bbox.y1) / 2
            assert x0 - 15 <= cx <= x1 + 15 and y0 - 15 <= cy <= y1 + 15, t["text"]
    assert found >= len(LABELS + VERTICAL_LABELS) - 1, [ln.text for ln in scan.lines]
    # nothing invented: every accepted line must correspond to a real label
    for ln in scan.lines:
        assert max(similarity(ln.text, t["text"]) for t in truth) >= 0.5, ln.text


@needs_ocr
def test_vertical_dimension_text_is_read():
    img, _ = make_drawing()
    texts = [ln.text for ln in scan_drawing(img, "eng").lines if ln.rotation == 90]
    assert any(similarity(t, "1200 mm") >= 0.85 for t in texts), texts


@needs_ocr
def test_photo_yields_no_invented_text():
    scan = scan_drawing(make_photo(), "eng", rotations=(0,), max_scale=2.0)
    assert scan.lines == []


@needs_ocr
def test_real_drawing_labels_flagged_unreadable_not_guessed():
    scan = scan_drawing(load("isometric_details_drawing.webp"), "eng")
    assert len(scan.unreadable) >= 8          # label rows are located for human review
    assert len(scan.lines) <= 3               # and not turned into fake text
