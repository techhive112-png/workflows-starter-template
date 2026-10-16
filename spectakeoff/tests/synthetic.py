"""Synthetic drawings with known ground truth, used by tests and `spectakeoff eval`."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

LABELS = [
    "W12x26 BEAM",
    "HSS6x6x1/4 COLUMN",
    "(4) 3/4\" A325 BOLTS",
    "GYPSUM BOARD",
    "RIGID INSULATION 100 mm",
    "SEE DETAIL 3/A501",
    "AHU-1",
    "VAPOUR BARRIER",
    "PL 3/4\" x 10\" STIFFENER",
    "T.O.S. EL. 102'-6\"",
]
VERTICAL_LABELS = ["2'-6\"", "1200 mm"]


def _font(px: int):
    try:
        return ImageFont.truetype(FONT, px)
    except OSError:
        return ImageFont.load_default()


def make_drawing(path: Path | None = None, text_px: int = 12, seed: int = 4):
    """Isometric-style detail sheet: grid, diagonals, hatching, leaders, labels."""
    rng = np.random.default_rng(seed)
    W, H = 2000, 1100
    im = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(im)
    # frame + light construction grid
    d.rectangle([10, 10, W - 10, H - 10], outline=40, width=3)
    for x in range(60, W, 140):
        d.line([(x, 20), (x, H - 20)], fill=215, width=1)
    # isometric object outlines
    for i in range(6):
        x0, y0 = 120 + i * 140, 300 + (i % 2) * 60
        L = 260
        d.line([(x0, y0), (x0 + L * math.cos(math.radians(30)), y0 - L * 0.5)], fill=60, width=2)
        d.line([(x0, y0), (x0, y0 + 300)], fill=60, width=2)
    # hatched insulation band
    for k in range(0, 360, 9):
        d.line([(200 + k, 700), (240 + k, 640)], fill=110, width=1)
    d.rectangle([200, 640, 600, 700], outline=60, width=2)
    font = _font(text_px)
    truth = []
    for n, label in enumerate(LABELS):
        lx = 1150 + (n % 2) * 380
        ly = 90 + n * 90
        ax, ay = int(rng.integers(150, 900)), int(rng.integers(200, 1000))
        tw = d.textlength(label, font=font)
        d.line([(ax, ay), (lx - 10, ly + text_px + 4)], fill=70, width=1)          # leader
        d.line([(lx - 10, ly + text_px + 4), (lx + tw, ly + text_px + 4)], fill=70, width=1)  # underline
        d.ellipse([ax - 3, ay - 3, ax + 3, ay + 3], fill=70)
        d.text((lx, ly), label, fill=30, font=font)
        truth.append({"text": label, "bbox": (lx, ly, lx + tw, ly + text_px)})
    # vertical dimension strings (read bottom-to-top) with dimension lines
    for n, label in enumerate(VERTICAL_LABELS):
        tw = int(d.textlength(label, font=font)) + 4
        tile = Image.new("L", (tw, text_px + 6), 255)
        ImageDraw.Draw(tile).text((2, 1), label, fill=30, font=font)
        tile = tile.rotate(90, expand=True)
        x, y = 70 + n * 900, 450
        im.paste(tile, (x, y))
        d.line([(x + text_px + 12, y - 60), (x + text_px + 12, y + tw + 60)], fill=60, width=1)
        truth.append({"text": label, "bbox": (x, y, x + text_px + 6, y + tw)})
    if path:
        im.save(path)
    return np.array(im), truth


def make_photo(path: Path | None = None, seed: int = 1):
    """Textured mid-tone 'photo' with no text."""
    rng = np.random.default_rng(seed)
    base = np.linspace(60, 180, 800)[None, :].repeat(500, 0)
    img = np.clip(base + rng.normal(0, 25, (500, 800)), 0, 255).astype(np.uint8)
    rgb = np.stack([img, (img * 0.9).astype(np.uint8), (img * 0.7).astype(np.uint8)], -1)
    if path:
        Image.fromarray(rgb).save(path)
    return rgb[:, :, ::-1].copy()
