"""Per-source processing: route every PDF page / image to the right extractor."""
from __future__ import annotations

import hashlib
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from spectakeoff.models import (REQUIREMENT, CANDIDATE, DRAWING_TEXT, NONE, OCR_DRAWING, OCR_PAGE, PDF_TABLE, PDF_TEXT,
                                PDF_VECTOR, REVIEW, SCHEDULE_ROW, TOKEN, VISUAL_REVIEW, BBox, Finding, PageRecord,
                                SourceResult)
from spectakeoff.ocr import OcrUnavailable, detect_rotation, ocr_words, resolve_languages
from spectakeoff.patterns import COUNT_NOTE, EQUIPMENT_TAG, NUMBER, find_tokens
from spectakeoff.quality import LineVerdict
from spectakeoff.specs import (SectionState, detect_section, extract_requirements, extract_submittal_register,
                               norm, strip_editor_notes)
from spectakeoff.vision import (BLANK, DRAWING_RASTER, PHOTO, SCAN_TEXT, DrawingScan, TextLine, classify_raster,
                                draw_overlay, scan_drawing, to_gray)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"}
MAX_RENDER_PIXELS = 40_000_000
QTY_HEADER = re.compile(r"^(?:qty|quantity|quan\.?|no\.?|count|nos\.?|daudz\w*|skaits|gab\.?)$", re.I)
TAG_HEADER = re.compile(r"^(?:tag|mark|id|symbol|label|apz\w*|marķ\w*|pozīcija|poz\.?)$", re.I)


@dataclass
class Config:
    ocr: bool = True
    ocr_lang: str = "eng"
    ocr_min_chars: int = 80
    page_ocr_min_conf: float = 75.0       # page mean confidence below this -> page review
    word_min_conf: float = 60.0
    dpi: int = 300
    rotations: tuple[int, ...] = (0, 90)
    overlays: bool = True
    overlay_dir: Path | None = None
    tables: bool = True
    translate_to: str = ""
    min_span: int = 18
    max_span: int = 1600
    keep_text: bool = False             # keep raw page text on PageRecord (labelling)
    llm: bool = False                   # optional language-model pass (sends candidate sentences out)
    llm_model: str = ""
    llm_cache: Path | None = None


@dataclass
class _Ctx:
    cfg: Config
    source: str
    stem: str
    result: SourceResult
    state: SectionState = field(default_factory=SectionState)
    hits: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    lang: str = ""
    lang_error: str = ""
    translate_cache: dict = field(default_factory=dict)
    llm_queue: list = field(default_factory=list)


def sha(s: str | bytes) -> str:
    return hashlib.sha256(s if isinstance(s, bytes) else s.encode("utf-8", "replace")).hexdigest()


def _maybe_translate(ctx: _Ctx, text: str) -> str:
    if not ctx.cfg.translate_to or not text:
        return ""
    key = (text, ctx.cfg.translate_to)
    if key not in ctx.translate_cache:
        try:
            from deep_translator import GoogleTranslator
            ctx.translate_cache[key] = GoogleTranslator(source="auto", target=ctx.cfg.translate_to).translate(text) or ""
        except Exception:
            ctx.translate_cache[key] = ""
    return ctx.translate_cache[key]


def _add_requirements(ctx: _Ctx, rec: PageRecord, text: str, method: str, conf: float | None) -> None:
    if ctx.cfg.keep_text:
        rec.text = text
    text, dropped = strip_editor_notes(text, ctx.state)
    if dropped:
        rec.warnings.append(f"{dropped} line(s) of editor's notes (****** blocks) not treated as requirements")
    ctx.state = detect_section(text, ctx.state)
    rec.section, rec.section_title = ctx.state.section, ctx.state.title
    found, hits = extract_requirements(text, ctx.source, rec.page, ctx.state, rec.sha256, method, conf,
                                       ctx.cfg.min_span, ctx.cfg.max_span)
    have = {f.text.casefold() for f in found}
    if ctx.cfg.llm:   # sentences the rules skipped but that could be deliverables
        from spectakeoff.llm import is_candidate
        from spectakeoff.specs import split_spans

        for span in split_spans(text):
            if span.casefold() not in have and is_candidate(span):
                ctx.llm_queue.append((rec, span, ctx.state.section, ctx.state.title, method, conf))
    found += [f for f in extract_submittal_register(text, ctx.source, rec.page, ctx.state, rec.sha256, method,
                                                    conf) if f.text.casefold() not in have]
    if ctx.state.section:
        ctx.hits[ctx.state.section] += hits
    for f in found:
        if conf is not None and conf < ctx.cfg.page_ocr_min_conf:
            f.flag("OCR confidence below threshold — verify against page image", REVIEW)
        if method.startswith("OCR"):
            f.flag("OCR text: verify against page image")
        f.translated = _maybe_translate(ctx, f.text)
        if ctx.cfg.translate_to and not f.translated:
            f.flag("Translation unavailable; original quote retained")
    ctx.result.findings.extend(found)
    rec.findings += len(found)


def _add_lines(ctx: _Ctx, rec: PageRecord, lines: list[TextLine], method: str) -> None:
    for ln in lines:
        v = ln.verdict
        conf = None if method == PDF_VECTOR else v.confidence
        f = Finding(kind=DRAWING_TEXT, source_file=ctx.source, page=rec.page, text=v.text, method=method,
                    category="Drawing label / note", bbox=ln.bbox, confidence=conf, section=rec.section,
                    section_title=rec.section_title, page_sha256=rec.sha256)
        if v.needs_review:
            f.flag("Partly unreadable or low-confidence OCR — compare with review image" if "[?]" in v.text
                   else "OCR reading — compare with review image", REVIEW)
        if ln.rotation:
            f.flag(f"Text rotated {ln.rotation}°")
        ctx.result.findings.append(f)
        rec.findings += 1
        for tok in find_tokens(v.text.replace("[?]", " ")):
            t = Finding(kind=TOKEN, source_file=ctx.source, page=rec.page, text=tok.text, method=method,
                        category=tok.kind, value=tok.value, unit=tok.unit, bbox=ln.bbox, confidence=conf,
                        section=rec.section, section_title=rec.section_title, page_sha256=rec.sha256,
                        tag=tok.value if tok.kind == EQUIPMENT_TAG else "", status=f.status)
            t.flags = [x for x in f.flags]
            t.flag(f"From line: {v.text}")
            if tok.kind == COUNT_NOTE:
                t.flag("Count note — confirm what it counts before using it", REVIEW)
            if tok.kind == NUMBER:
                t.flag("Unit not stated", REVIEW)
            ctx.result.findings.append(t)
            rec.findings += 1


def _find_tables(rec: PageRecord, page) -> list:
    try:
        return page.find_tables().tables
    except Exception as exc:  # table finder is best effort
        rec.warn(f"Table detection failed: {type(exc).__name__}")
        return []


def _add_schedules(ctx: _Ctx, rec: PageRecord, tables: list) -> None:
    """Keep schedule-like tables (with a quantity or tag column); others are only counted."""
    skipped = 0
    for ti, tb in enumerate(tables, 1):
        rows = tb.extract()
        if len(rows) < 2 or max(len(r) for r in rows) < 2:
            continue
        header = [norm(h or f"col{i + 1}") for i, h in enumerate(rows[0])]
        qcol = next((i for i, h in enumerate(header) if QTY_HEADER.match(h)), None)
        tcol = next((i for i, h in enumerate(header) if TAG_HEADER.match(h)), None)
        has_tags = any(t.kind == EQUIPMENT_TAG for r in rows[1:] for c in r for t in find_tokens(norm(c or "")))
        if qcol is None and tcol is None and not has_tags:
            skipped += 1
            continue
        x0, y0, x1, y1 = tb.bbox
        for ri, row in enumerate(rows[1:], 1):
            cells = [norm(c or "") for c in row]
            if not any(cells):
                continue
            text = " | ".join(f"{h}: {c}" for h, c in zip(header, cells) if c)
            tag = cells[tcol] if tcol is not None and tcol < len(cells) else ""
            if not tag:
                tag = next((t.value for c in cells for t in find_tokens(c) if t.kind == EQUIPMENT_TAG), "")
            f = Finding(kind=SCHEDULE_ROW, source_file=ctx.source, page=rec.page, text=text, method=PDF_TABLE,
                        category=f"Table {ti}", tag=tag, bbox=BBox(x0, y0, x1, y1), section=rec.section,
                        section_title=rec.section_title, page_sha256=rec.sha256)
            if qcol is not None and qcol < len(cells) and cells[qcol]:
                f.value, f.unit = cells[qcol], "EA"
                f.flag("Schedule quantity — verify against the drawing before use")
            ctx.result.findings.append(f)
            rec.findings += 1
    if skipped:
        rec.warnings.append(f"{skipped} table(s) without quantity/tag column not extracted as schedules")


def _vector_lines(page) -> list[TextLine]:
    out = []
    for b in page.get_text("dict").get("blocks", []):
        for ln in b.get("lines", []):
            text = norm(" ".join(s.get("text", "") for s in ln.get("spans", [])))
            if sum(c.isalnum() for c in text) < 2:
                continue
            dx, dy = ln.get("dir", (1, 0))
            rot = 0 if abs(dx) >= abs(dy) else 90
            x0, y0, x1, y1 = ln["bbox"]
            out.append(TextLine(BBox(x0, y0, x1, y1), rot, LineVerdict(text, text, 100.0, True, False, [])))
    return out


def _save_overlay(ctx: _Ctx, rec: PageRecord, img: np.ndarray, scan: DrawingScan | None, label: str) -> None:
    if not (ctx.cfg.overlays and ctx.cfg.overlay_dir):
        return
    ov = draw_overlay(img, scan, label)
    h, w = ov.shape[:2]
    if w > 3000:
        ov = cv2.resize(ov, None, fx=3000 / w, fy=3000 / w, interpolation=cv2.INTER_AREA)
    ctx.cfg.overlay_dir.mkdir(parents=True, exist_ok=True)
    path = ctx.cfg.overlay_dir / f"{ctx.stem}_p{rec.page:04d}.png"
    cv2.imwrite(str(path), ov)
    rec.overlay = str(path)


def _ocr_lang(ctx: _Ctx, rec: PageRecord) -> str:
    if not ctx.cfg.ocr:
        rec.warn("OCR disabled (--no-ocr)")
        return ""
    if not ctx.lang and not ctx.lang_error:
        try:
            ctx.lang, missing = resolve_languages(ctx.cfg.ocr_lang)
            if missing:
                ctx.lang_error = "Missing OCR language packs: " + ",".join(missing)
        except OcrUnavailable as exc:
            ctx.lang_error = str(exc)
    if ctx.lang_error and ctx.lang_error.startswith("Missing"):
        rec.warnings.append(ctx.lang_error)
    elif ctx.lang_error:
        rec.warn(ctx.lang_error)
    return ctx.lang


def _process_raster(ctx: _Ctx, rec: PageRecord, img: np.ndarray, page_label: str) -> None:
    kind, metrics = classify_raster(img)
    rec.page_kind = kind
    gray = to_gray(img)
    rec.sha256 = sha(gray.tobytes())
    if kind == BLANK:
        rec.method = NONE
        rec.warn("Blank or near-blank page")
        return
    lang = _ocr_lang(ctx, rec)
    if not lang:
        rec.method = NONE
        _visual(ctx, rec, "No OCR available — page must be reviewed visually")
        _save_overlay(ctx, rec, img, None, f"{page_label} | {kind} | NO OCR")
        return
    if kind == SCAN_TEXT:
        rot = detect_rotation(gray)
        if rot:
            gray = np.ascontiguousarray(np.rot90(gray, k=-(rot // 90)))
            rec.warnings.append(f"Page rotated {rot}° before OCR")
        words = ocr_words(gray, lang, psm=3)
        lines: dict[tuple[int, int, int], list[str]] = defaultdict(list)
        for w in words:   # Tesseract numbers lines per paragraph
            lines[(w.block, w.par, w.line)].append(w.text)
        text, last_par = [], None
        for (b, par, _), ws in sorted(lines.items()):
            if last_par is not None and (b, par) != last_par:
                text.append("")
            text.append(" ".join(ws))
            last_par = (b, par)
        page_text = "\n".join(text)
        conf = round(sum(w.conf for w in words) / len(words), 1) if words else 0.0
        rec.method, rec.characters, rec.ocr_confidence = OCR_PAGE, len(norm(page_text)), conf
        rec.sha256 = sha(norm(page_text)) if page_text else rec.sha256
        if conf < ctx.cfg.page_ocr_min_conf:
            rec.warn(f"Mean OCR confidence {conf:.1f}% below {ctx.cfg.page_ocr_min_conf:.0f}%")
        _add_requirements(ctx, rec, page_text, OCR_PAGE, conf)
        _save_overlay(ctx, rec, img, None, f"{page_label} | scanned text | conf {conf:.0f}")
        return
    rotations = ctx.cfg.rotations if kind == DRAWING_RASTER else (0,)
    # photos: only look for large signage/labels, no aggressive upscaling
    scan = scan_drawing(img, lang, ctx.cfg.word_min_conf, rotations, 5.0 if kind == DRAWING_RASTER else 2.0)
    rec.method = OCR_DRAWING
    rec.text_regions, rec.accepted_lines, rec.rejected_noise = scan.regions, len(scan.lines), scan.rejected
    rec.characters = sum(len(ln.text) for ln in scan.lines)
    if scan.lines:
        rec.ocr_confidence = round(sum(ln.verdict.confidence for ln in scan.lines) / len(scan.lines), 1)
    _add_lines(ctx, rec, scan.lines, OCR_DRAWING)
    for n, (bb, raw) in enumerate(scan.unreadable, 1):
        f = Finding(kind=VISUAL_REVIEW, source_file=ctx.source, page=rec.page, text=f"[unreadable label U{n}]",
                    method=OCR_DRAWING, category="Unreadable drawing label", bbox=bb, status=REVIEW,
                    page_sha256=rec.sha256)
        f.flag(f"Region looks like a text label but OCR is unreliable (guess, do not use: {raw!r}). "
               f"Read it on the review image (box U{n}).")
        ctx.result.findings.append(f)
        rec.findings += 1
    if kind == PHOTO:
        rec.warn("Photograph — no drawing/spec text; quantities must be counted by an estimator")
        _visual(ctx, rec, "Photograph: SpecTakeoff 4.0 does not count objects (bolts, members, fixtures) from "
                          "photos. Count manually or supply verified counts via --counts.")
    else:
        if scan.unreadable:
            rec.warn(f"{len(scan.unreadable)} label(s) detected but unreadable — see review image")
        if not scan.lines:
            rec.warn("No readable text found on drawing")
        _add_requirements(ctx, rec, "\n".join(ln.text for ln in scan.lines), OCR_DRAWING, rec.ocr_confidence)
    _save_overlay(ctx, rec, img, scan,
                  f"{page_label} | {kind} | {len(scan.lines)} read, {len(scan.unreadable)} unreadable")


def _visual(ctx: _Ctx, rec: PageRecord, msg: str) -> None:
    f = Finding(kind=VISUAL_REVIEW, source_file=ctx.source, page=rec.page, text="[whole page]", method=NONE,
                category="Visual review", status=REVIEW, page_sha256=rec.sha256)
    f.flag(msg)
    ctx.result.findings.append(f)
    rec.findings += 1


def _process_pdf_page(ctx: _Ctx, page, pno: int) -> PageRecord:
    import pymupdf

    text = page.get_text("text", sort=True) or ""
    cleaned = norm(text)
    rec = PageRecord(ctx.source, pno, "spec_text", PDF_TEXT, characters=len(cleaned), sha256=sha(cleaned))
    infos = page.get_image_info()
    rec.images = len(infos)
    area = max(1.0, page.rect.width * page.rect.height)
    img_cover = min(1.0, sum(max(0.0, (i["bbox"][2] - i["bbox"][0]) * (i["bbox"][3] - i["bbox"][1]))
                             for i in infos) / area)
    try:
        n_paths = len(page.get_drawings())
    except Exception:
        n_paths = 0
    vlines = _vector_lines(page)
    words_per_line = (sum(len(ln.text.split()) for ln in vlines) / len(vlines)) if vlines else 0
    tables = _find_tables(rec, page) if n_paths >= 8 else []
    is_vector_drawing = n_paths >= 300 and bool(vlines) and words_per_line < 5
    if is_vector_drawing and tables:
        # a big ruled table (many short numeric cells) is not a drawing
        in_tab = sum(len(ln.text) for ln in vlines if any(
            t.bbox[0] <= (ln.bbox.x0 + ln.bbox.x1) / 2 <= t.bbox[2] and t.bbox[1] <= (ln.bbox.y0 + ln.bbox.y1) / 2
            <= t.bbox[3] for t in tables))
        is_vector_drawing = in_tab < 0.5 * max(1, sum(len(ln.text) for ln in vlines))
    # Render + OCR only when the text layer may be missing content: no text at all, embedded
    # images, or many paths (text converted to outlines). A short text page stays text.
    needs_raster = not cleaned or img_cover >= 0.1 or n_paths >= 50
    if len(cleaned) < ctx.cfg.ocr_min_chars and needs_raster and not is_vector_drawing:
        z = ctx.cfg.dpi / 72.0
        z = min(z, (MAX_RENDER_PIXELS / area) ** 0.5)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False)
        img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR) if pix.n == 3 else img[:, :, 0].copy()
        if cleaned:
            rec.warnings.append("Sparse PDF text layer; page rendered and OCR'd")
        _process_raster(ctx, rec, img, f"p{pno}")
        return rec
    if is_vector_drawing:
        rec.page_kind, rec.method = "drawing_vector", PDF_VECTOR
        rec.accepted_lines = len(vlines)
        _add_requirements(ctx, rec, text, PDF_TEXT, None)
        _add_lines(ctx, rec, vlines, PDF_VECTOR)
        if ctx.cfg.overlays and ctx.cfg.overlay_dir:
            z = min(150 / 72.0, (12_000_000 / area) ** 0.5)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False)
            img = cv2.cvtColor(np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3),
                               cv2.COLOR_RGB2BGR)
            scaled = [TextLine(BBox(l.bbox.x0 * z, l.bbox.y0 * z, l.bbox.x1 * z, l.bbox.y1 * z), l.rotation,
                               l.verdict) for l in vlines]
            _save_overlay(ctx, rec, img, DrawingScan(lines=scaled), f"p{pno} | vector drawing | {len(vlines)} lines")
    else:
        _add_requirements(ctx, rec, text, PDF_TEXT, None)
    if img_cover >= 0.1:
        rec.warn(f"Embedded image(s) cover {img_cover:.0%} of the page — check for content not in the text layer")
    if ctx.cfg.tables and tables:
        _add_schedules(ctx, rec, tables)
    return rec


def process_source(path: Path, cfg: Config) -> tuple[SourceResult, dict[str, int]]:
    start = time.time()
    data = path.read_bytes()
    res = SourceResult(source=path.name, sha256=sha(data))
    ctx = _Ctx(cfg, path.name, re.sub(r"[^\w.-]+", "_", path.stem)[:40], res)
    if path.suffix.lower() == ".pdf":
        import pymupdf

        with pymupdf.open(path) as doc:
            for i, page in enumerate(doc, 1):
                res.pages.append(_process_pdf_page(ctx, page, i))
    elif path.suffix.lower() in IMAGE_SUFFIXES:
        from PIL import Image, ImageSequence

        with Image.open(path) as im:
            for i, frame in enumerate(ImageSequence.Iterator(im), 1):
                rgb = np.array(frame.convert("RGB"))
                rec = PageRecord(ctx.source, i, "photo", NONE, images=1)
                _process_raster(ctx, rec, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), f"{path.name} #{i}")
                res.pages.append(rec)
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    if ctx.llm_queue:
        _run_llm(ctx)
    res.elapsed = time.time() - start
    return res, dict(ctx.hits)


def _run_llm(ctx: _Ctx) -> None:
    from spectakeoff.llm import DEFAULT_MODEL, Classifier
    from spectakeoff.specs import classify, division_of

    known = {(f.page, f.text.casefold()) for f in ctx.result.findings}
    queue = [q for q in ctx.llm_queue if (q[0].page, q[1].casefold()) not in known]
    clf = Classifier(ctx.cfg.llm_model or DEFAULT_MODEL, ctx.cfg.llm_cache)
    for (rec, span, sec, title, method, conf), yes in zip(queue, clf.classify([q[1] for q in queue])):
        if not yes:
            continue
        f = Finding(kind=REQUIREMENT, source_file=ctx.source, page=rec.page, text=span,
                    method=f"Language model ({clf.model})", category=classify(span), section=sec,
                    section_title=title, division=division_of(sec), confidence=conf, status=REVIEW,
                    page_sha256=rec.sha256)
        f.flag("Found by the language model, not by the rules - verify against the page")
        ctx.result.findings.append(f)
        rec.findings += 1
    ctx.result.llm = {"model": clf.model, **clf.stats.__dict__}


def assign_ids(results: list[SourceResult]) -> None:
    code = {"requirement": "R", "drawing_text": "D", "token": "T", "schedule_row": "S", "visual_review": "V"}
    for r in results:
        stem = re.sub(r"[^\w-]+", "", Path(r.source).stem)[:12]
        for n, f in enumerate(r.findings, 1):
            f.id = f"{stem}-P{f.page:04d}-{code.get(f.kind, 'X')}{n:05d}"
            if f.status == CANDIDATE and f.kind == VISUAL_REVIEW:
                f.status = REVIEW
