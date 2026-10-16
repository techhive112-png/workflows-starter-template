"""Separate real drawing text from OCR noise (hatching, leader lines, symbols).

Tesseract happily "reads" hatch patterns as SS, ///, Ww, etc. with moderate
confidence. A word is only kept when it is a recognised construction token, a
vocabulary word, or a plausible word read with high confidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from spectakeoff.patterns import VOCABULARY, find_tokens, fold

VOWELS = set("AEIOUYĀĒĪŪ")


@dataclass
class WordVerdict:
    text: str
    confidence: float
    keep: bool
    reason: str          # token | vocabulary | word | number | noise:<why>


def _junk_reason(w: str) -> str:
    letters = [c for c in w if c.isalpha()]
    alnum = [c for c in w if c.isalnum()]
    if not alnum:
        return "symbols only"
    if len(alnum) / max(1, len(w)) < 0.6:
        return "mostly symbols"
    up = "".join(letters).upper()
    if letters and len(set(up)) == 1 and len(up) <= 4:
        return "repeated letter (hatch pattern)"
    if len(up) >= 3 and not (set(up) & VOWELS):
        return "no vowels"
    if re.search(r"[a-z][A-Z][a-z]|[A-Z]{2}[a-z][A-Z]", w):
        return "random case mix"
    return ""


def judge_word(text: str, confidence: float, min_conf: float = 60.0, word_conf: float = 80.0) -> WordVerdict:
    w = text.strip().strip(".,;:")
    if not w:
        return WordVerdict(text, confidence, False, "noise:empty")
    if find_tokens(w):
        ok = confidence >= min_conf * 0.75
        return WordVerdict(text, confidence, ok, "token" if ok else "noise:low confidence token")
    if re.fullmatch(r"(?:[A-Za-z]\.){2,}[A-Za-z]?\.?", w) and fold(w) in VOCABULARY:
        ok = confidence >= min_conf * 0.8
        return WordVerdict(text, confidence, ok, "vocabulary" if ok else "noise:low confidence")
    if re.fullmatch(r"[^\W\d_]+(?:[-/][^\W\d_]+)*", w) and fold(w) in VOCABULARY:
        short = len(w) <= 3
        ok = confidence >= (min_conf if short else min_conf * 0.8) and (w.isupper() or not short)
        return WordVerdict(text, confidence, ok, "vocabulary" if ok else "noise:low confidence")
    if re.fullmatch(r"[\d.,/'\"+-]+", w) and any(c.isdigit() for c in w):
        if sum(c.isdigit() for c in w) < 2:
            return WordVerdict(text, confidence, False, "noise:lone digit")
        ok = confidence >= min_conf
        return WordVerdict(text, confidence, ok, "number" if ok else "noise:low confidence number")
    junk = _junk_reason(w)
    if junk:
        return WordVerdict(text, confidence, False, "noise:" + junk)
    if len([c for c in w if c.isalnum()]) < 3:
        return WordVerdict(text, confidence, False, "noise:too short to verify")
    ok = confidence >= word_conf
    return WordVerdict(text, confidence, ok, "word" if ok else "noise:low confidence word")


@dataclass
class LineVerdict:
    text: str                 # kept words only, verbatim; [?] marks a dropped word
    raw: str                  # everything OCR returned
    confidence: float         # mean confidence of kept words
    keep: bool
    needs_review: bool
    words: list[WordVerdict]


def judge_line(words: list[tuple[str, float]], min_conf: float = 60.0) -> LineVerdict:
    words = [(t.strip(), c) for t, c in words if t.strip()]
    # Tokens can span several OCR words: "(4) 3/4" A325 BOLTS", "100 mm", "PL 3/4" x 10"".
    raw = " ".join(t for t, _ in words)
    spans, pos = [], 0
    for t, _ in words:
        spans.append((pos, pos + len(t)))
        pos += len(t) + 1
    in_token = [False] * len(words)
    for tok in find_tokens(raw):
        idx = [i for i, (s, e) in enumerate(spans) if s < tok.end and e > tok.start]
        if len(idx) > 1 and sum(words[i][1] for i in idx) / len(idx) >= min_conf * 0.75:
            for i in idx:
                in_token[i] = True
    verdicts = [WordVerdict(t, c, True, "token") if in_token[i] else judge_word(t, c, min_conf)
                for i, (t, c) in enumerate(words)]
    kept = [v for v in verdicts if v.keep]
    if not kept:
        return LineVerdict("", raw, 0.0, False, False, verdicts)
    strong = [v for v in kept if v.reason in ("token", "vocabulary")]
    # A line made only of unverifiable "words" needs at least two of them.
    keep = bool(strong) or len(kept) >= 2
    if len(kept) == 1 and kept[0].reason == "vocabulary" and sum(c.isalnum() for c in kept[0].text) <= 3:
        keep = False      # a lone short abbreviation ("NO", "EA") is usually noise and says nothing
    parts = [v.text if v.keep else "[?]" for v in verdicts]
    while parts and parts[0] == "[?]":
        parts.pop(0)
    while parts and parts[-1] == "[?]":
        parts.pop()
    text = re.sub(r"(\[\?\]\s?)+", "[?] ", " ".join(parts)).strip()
    conf = sum(v.confidence for v in kept) / len(kept)
    review = any(not v.keep for v in verdicts) or any(v.reason == "word" for v in kept) or conf < 85
    return LineVerdict(text, raw, round(conf, 1), keep, review, verdicts)
