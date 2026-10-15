"""Thin Tesseract wrapper: availability, language packs, word-level results."""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache

import numpy as np


@dataclass
class OcrWord:
    text: str
    conf: float
    x: int
    y: int
    w: int
    h: int
    block: int
    par: int
    line: int


class OcrUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=1)
def installed_languages() -> tuple[str, ...]:
    exe = shutil.which("tesseract")
    if not exe:
        return ()
    try:
        p = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return ()
    return tuple(x.strip() for x in (p.stdout or "").splitlines()[1:] if x.strip())


def resolve_languages(requested: str) -> tuple[str, list[str]]:
    """Return (tesseract lang string, missing packs). Raises when nothing usable."""
    have = installed_languages()
    if not have:
        raise OcrUnavailable("Tesseract executable not installed")
    want = [x for x in requested.split("+") if x]
    usable = [x for x in want if x in have]
    missing = [x for x in want if x not in have]
    if not usable:
        raise OcrUnavailable("No requested OCR language packs installed: " + ",".join(missing))
    return "+".join(usable), missing


def ocr_words(img: np.ndarray, lang: str, psm: int, extra: str = "") -> list[OcrWord]:
    import pytesseract

    d = pytesseract.image_to_data(
        img, lang=lang, config=f"--psm {psm} {extra}".strip(), output_type=pytesseract.Output.DICT
    )
    out = []
    for i, t in enumerate(d.get("text", [])):
        t = (t or "").strip()
        try:
            c = float(d["conf"][i])
        except (TypeError, ValueError):
            c = -1.0
        if t and c >= 0:
            out.append(OcrWord(t, c, d["left"][i], d["top"][i], d["width"][i], d["height"][i],
                               d["block_num"][i], d["par_num"][i], d["line_num"][i]))
    return out


def detect_rotation(gray: np.ndarray) -> int:
    """Clockwise degrees Tesseract OSD says the page is rotated by (0 if unsure)."""
    import pytesseract

    if "osd" not in installed_languages():
        return 0
    try:
        osd = pytesseract.image_to_osd(gray, output_type=pytesseract.Output.DICT)
    except Exception:  # OSD fails on pages with too little text
        return 0
    if float(osd.get("orientation_conf", 0)) < 2.0:
        return 0
    return int(osd.get("rotate", 0)) % 360
