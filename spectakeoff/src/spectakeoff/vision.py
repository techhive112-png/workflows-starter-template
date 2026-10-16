"""Raster image analysis: page classification and drawing text scanning.

Why the v3 approach failed on drawings: full-page Tesseract reads leader lines,
dimension lines and hatching as letters, and drawing labels are often only a
few pixels tall. This module:

1. estimates the text height and upscales so letters are ~30 px tall,
2. removes long straight lines (horizontal, vertical and diagonal/isometric),
3. finds text-line regions from character-sized blobs,
4. OCRs all regions in one batched mosaic (fast) at 0° and 90°,
5. filters every word through `quality.judge_line` so noise never becomes data.

Photos are classified and sent to visual review: classical CV cannot count
objects such as bolts reliably, so 4.0 does not invent counts from photos.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from spectakeoff.models import BBox
from spectakeoff.ocr import ocr_words
from spectakeoff.quality import LineVerdict, judge_line

BLANK, SCAN_TEXT, DRAWING_RASTER, PHOTO = "blank", "scan_text", "drawing_raster", "photo"

MAX_WORK_PIXELS = 90_000_000      # cap on upscaled image size (memory / time)
TARGET_TEXT_PX = 30               # Tesseract is most accurate around 25–35 px cap height
MOSAIC_MAX_H = 20_000             # Tesseract hard limit is 32767 px


@dataclass
class RasterMetrics:
    white_fraction: float
    ink_fraction: float
    midtone_fraction: float
    saturation: float
    line_ratio: float
    text_height: float

    def as_dict(self) -> dict:
        return {k: round(v, 4) for k, v in self.__dict__.items()}


@dataclass
class TextLine:
    bbox: BBox                    # original image pixel coordinates
    rotation: int
    verdict: LineVerdict

    @property
    def text(self) -> str:
        return self.verdict.text


@dataclass
class DrawingScan:
    lines: list[TextLine] = field(default_factory=list)
    unreadable: list[tuple[BBox, str]] = field(default_factory=list)  # label-shaped but unreadable
    regions: int = 0
    rejected: int = 0
    scale: float = 1.0
    text_height: float = 0.0
    line_mask: np.ndarray | None = None   # original-size mask of removed lines


def to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _background(gray: np.ndarray) -> int:
    return int(np.percentile(gray, 90))


def _thresholds(gray: np.ndarray) -> tuple[int, int]:
    """(ink threshold for faint anti-aliased text, strong threshold for lines)."""
    bg = _background(gray)
    return int(np.clip(bg - 40, 100, 230)), int(np.clip(bg - 70, 60, 200))


def estimate_text_height(gray: np.ndarray) -> float:
    ink_thr, _ = _thresholds(gray)
    ink = (gray < ink_thr).astype(np.uint8)
    n, _, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    hs = [int(s[3]) for s in st[1:] if 4 <= s[3] <= 80 and s[2] <= 2.5 * s[3] and s[4] >= 8
          and s[4] / float(s[2] * s[3]) > 0.15]
    if len(hs) < 15:
        return 12.0
    return float(np.median(hs))


def _long_lines(binary: np.ndarray, length: int, hough_min: int, thickness: int) -> np.ndarray:
    lines = np.zeros_like(binary)
    for k in ((length, 1), (1, length)):
        lines |= cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, k))
    hl = cv2.HoughLinesP(binary, 1, np.pi / 360, max(15, hough_min // 2), minLineLength=hough_min,
                         maxLineGap=max(2, thickness))
    if hl is not None:
        for x1, y1, x2, y2 in hl.reshape(-1, 4):
            cv2.line(lines, (int(x1), int(y1)), (int(x2), int(y2)), 255, thickness)
    return lines


def classify_raster(img: np.ndarray) -> tuple[str, RasterMetrics]:
    gray = to_gray(img)
    h, w = gray.shape
    f = min(1.0, 1600.0 / max(h, w))
    small = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else gray
    ink_thr, strong_thr = _thresholds(small)
    ink = (small < ink_thr).astype(np.uint8) * 255
    strong = (small < strong_thr).astype(np.uint8) * 255
    white = float(np.mean(small > 225))
    ink_frac = float(np.mean(ink > 0))
    mid = float(np.mean((small > 60) & (small < 200)))
    sat = 0.0
    if img.ndim == 3:
        hsv = cv2.cvtColor(cv2.resize(img[:, :, :3], (small.shape[1], small.shape[0])), cv2.COLOR_BGR2HSV)
        sat = float(np.mean(hsv[:, :, 1])) / 255.0
    th = estimate_text_height(small)
    lines = _long_lines(strong, max(25, int(th * 3)), max(30, int(th * 4)), 2)
    line_ratio = float(np.sum((lines > 0) & (ink > 0))) / max(1.0, float(np.sum(ink > 0)))
    m = RasterMetrics(white, ink_frac, mid, sat, line_ratio, th)
    if ink_frac < 0.002:
        return BLANK, m
    if white > 0.5 and mid < 0.4 and sat < 0.25:
        return (DRAWING_RASTER if line_ratio > 0.2 else SCAN_TEXT), m
    return PHOTO, m


def _text_regions(clean: np.ndarray, ink_thr: int, th: float) -> list[tuple[int, int, int, int]]:
    ink = (clean < ink_thr).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    keep = np.zeros(n, bool)
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if 0.35 * th <= h <= 2.0 * th and a >= 0.02 * th * th and w <= 40 * th:
            keep[i] = True
    mask = keep[lab].astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(1.3 * th)), max(1, int(0.2 * th))))
    blob = cv2.dilate(mask, k)
    cs, _ = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in cs:
        x, y, w, h = cv2.boundingRect(c)
        if h <= 2.8 * th and w >= 0.6 * th and w >= h * 0.8:
            boxes.append((x, y, w, h))
    boxes.sort(key=lambda b: (b[1], b[0]))
    return boxes


def _looks_like_text_row(work: np.ndarray, box, ink_thr: int, th: float) -> bool:
    """Character-sized blobs with aligned tops and similar heights (not hatching)."""
    x, y, w, h = box
    if w < 4 * th:
        return False
    ink = (work[y:y + h, x:x + w] < ink_thr).astype(np.uint8)
    n, _, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    comps = [s for s in st[1:] if s[3] >= 0.4 * th and s[4] >= 0.02 * th * th]
    if len(comps) < 3:
        return False
    hs = np.array([c[3] for c in comps], float)
    tops = np.array([c[1] for c in comps], float)
    return hs.std() / hs.mean() < 0.35 and tops.std() < 0.25 * th


def _ocr_mosaic(clean: np.ndarray, boxes, th: float, lang: str):
    """OCR many small regions with few Tesseract calls; returns words per box."""
    pad = max(4, int(0.3 * th))
    gap = max(10, int(0.9 * th))
    per_box: list[list[tuple[str, float]]] = [[] for _ in boxes]
    i = 0
    while i < len(boxes):
        crops, offsets, y, width = [], [], gap, 0
        while i < len(boxes):
            x, by, w, h = boxes[i]
            crop = clean[max(0, by - pad):by + h + pad, max(0, x - pad):x + w + pad]
            if y + crop.shape[0] + gap > MOSAIC_MAX_H and crops:
                break
            crops.append(crop)
            offsets.append((i, y, y + crop.shape[0]))
            y += crop.shape[0] + gap
            width = max(width, crop.shape[1])
            i += 1
        mosaic = np.full((y, width + 2 * gap), 255, np.uint8)
        for crop, (_, y0, y1) in zip(crops, offsets):
            mosaic[y0:y1, gap:gap + crop.shape[1]] = crop
        words = ocr_words(mosaic, lang, psm=6, extra="-c preserve_interword_spaces=1")
        for wd in words:
            cy = wd.y + wd.h / 2
            for idx, y0, y1 in offsets:
                if y0 <= cy <= y1:
                    per_box[idx].append((wd.x, wd.text, wd.conf))
                    break
    return [[(t, c) for _, t, c in sorted(ws)] for ws in per_box]


def _iou(a: BBox, b: BBox) -> float:
    ix = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    iy = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    inter = ix * iy
    union = (a.x1 - a.x0) * (a.y1 - a.y0) + (b.x1 - b.x0) * (b.y1 - b.y0) - inter
    return inter / union if union > 0 else 0.0


def scan_drawing(img: np.ndarray, lang: str = "eng", min_conf: float = 60.0,
                 rotations: tuple[int, ...] = (0, 90), max_scale: float = 5.0) -> DrawingScan:
    gray = to_gray(img)
    H, W = gray.shape
    th0 = estimate_text_height(gray)
    scale = float(np.clip(TARGET_TEXT_PX / th0, 1.0, max_scale))
    scale = min(scale, (MAX_WORK_PIXELS / float(H * W)) ** 0.5)
    scale = max(scale, 1.0)
    g = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC) if scale > 1 else gray.copy()
    th = th0 * scale
    ink_thr, strong_thr = _thresholds(g)
    strong = (g < strong_thr).astype(np.uint8) * 255
    stroke = max(2, int(round(th * 0.12)))
    lines = _long_lines(strong, max(15, int(th * 2.5)), max(20, int(th * 3)), stroke)
    lines = cv2.dilate(lines, np.ones((3, 3), np.uint8))
    clean = g.copy()
    clean[lines > 0] = 255

    scan = DrawingScan(scale=scale, text_height=th0)
    scan.line_mask = cv2.resize(lines, (W, H), interpolation=cv2.INTER_NEAREST) if scale > 1 else lines
    candidates: list[TextLine] = []
    for rot in rotations:
        work = clean if rot == 0 else cv2.rotate(clean, cv2.ROTATE_90_CLOCKWISE)
        boxes = _text_regions(work, ink_thr, th)
        scan.regions += len(boxes)
        if not boxes:
            continue
        for (x, y, w, h), words in zip(boxes, _ocr_mosaic(work, boxes, th, lang)):
            if not words:
                continue
            v = judge_line(words, min_conf)
            if rot == 0:
                bb = BBox(x / scale, y / scale, (x + w) / scale, (y + h) / scale)
            else:  # undo 90° clockwise rotation: rotated (x', y') -> original (y', Hs-1-x')
                hs = clean.shape[0]
                bb = BBox(y / scale, (hs - x - w) / scale, (y + h) / scale, (hs - x) / scale)
            if v.keep:
                candidates.append(TextLine(bb, rot, v))
            else:
                scan.rejected += 1
                if (sum(ch.isalpha() for ch in v.raw) >= 5
                        and _looks_like_text_row(work, (x, y, w, h), ink_thr, th)):
                    scan.unreadable.append((bb, v.raw))
    # Same text found in both orientations: keep the more confident reading.
    candidates.sort(key=lambda t: -t.verdict.confidence)
    for c in candidates:
        if all(_iou(c.bbox, k.bbox) < 0.3 for k in scan.lines):
            scan.lines.append(c)
        else:
            scan.rejected += 1
    scan.lines.sort(key=lambda t: (round(t.bbox.y0 / max(1.0, th0)), t.bbox.x0))
    found = [ln.bbox for ln in scan.lines]
    uniq: list[tuple[BBox, str]] = []
    for bb, raw in sorted(scan.unreadable, key=lambda u: (u[0].y0, u[0].x0)):
        if all(_iou(bb, f) < 0.2 for f in found) and all(_iou(bb, u[0]) < 0.3 for u in uniq):
            uniq.append((bb, raw))
    scan.unreadable = uniq
    return scan


def draw_overlay(img: np.ndarray, scan: DrawingScan | None, label: str) -> np.ndarray:
    """Annotated copy for human review: green = candidate, orange = review, red = unreadable."""
    out = img.copy() if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if out.shape[2] == 4:
        out = cv2.cvtColor(out, cv2.COLOR_BGRA2BGR)
    if scan is not None:
        if scan.line_mask is not None:
            tint = out.copy()
            tint[scan.line_mask > 0] = (255, 200, 120)
            out = cv2.addWeighted(tint, 0.25, out, 0.75, 0)
        for n, ln in enumerate(scan.lines, 1):
            b = ln.bbox
            colour = (0, 140, 255) if ln.verdict.needs_review else (0, 170, 0)
            cv2.rectangle(out, (int(b.x0) - 2, int(b.y0) - 2), (int(b.x1) + 2, int(b.y1) + 2), colour, 2)
            cv2.putText(out, str(n), (int(b.x0), max(10, int(b.y0) - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                        0.4, colour, 1, cv2.LINE_AA)
        for n, (b, _) in enumerate(scan.unreadable, 1):
            cv2.rectangle(out, (int(b.x0) - 2, int(b.y0) - 2), (int(b.x1) + 2, int(b.y1) + 2), (0, 0, 230), 1)
            cv2.putText(out, f"U{n}", (int(b.x0), max(10, int(b.y0) - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                        0.35, (0, 0, 230), 1, cv2.LINE_AA)
    cv2.rectangle(out, (0, 0), (min(out.shape[1] - 1, 12 + 8 * len(label)), 22), (40, 40, 40), -1)
    cv2.putText(out, label, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return out
