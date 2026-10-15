"""Closeout requirement extraction from specification text.

Carried over from v3 with fixes:
* `%` / percent quantities are now recognised (v3 `%\\b` could never match),
* section headings require a SECTION/ITEM keyword or a CSI number + upper-case
  title (v3 treated any line starting with 3–4 digits as a section),
* table-of-contents lines and running headers are skipped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from spectakeoff.models import CANDIDATE, REQUIREMENT, REVIEW, Finding

CLOSEOUT_TERMS = re.compile(
    r"attic stock|spares?\b|extra materials?|extra filters?|special tools?|operation(?:s)? and maintenance|\bo&m\b|"
    r"operating and maintenance|owner(?:'s)? manuals?|maintenance service|service contract|training|"
    r"warrant(?:y|ies|ed)|as[- ]built|record drawings?|closeout|close-out|turnover|turn over|commissioning|"
    r"test reports?|inspection reports?|final reports?|instruction manuals?|replacement parts?|"
    r"maintenance agreement|maintenance materials?|operation manual|service visits?|submittals?|deliverables?|"
    r"certifications?|certificates?|manufacturer(?:'s)? instructions|spare equipment|extra stock|maintenance data|"
    r"guarantee|demonstration of (?:the )?(?:system|equipment)s?",
    re.I,
)
OBLIGATION = re.compile(
    r"\b(shall|must|required to|will provide|provide|furnish|supply|submit|deliver|include|turn over|turnover|"
    r"maintain|warrants|warranted|guarantees?d?|is to be submitted|are to be submitted)\b",
    re.I,
)
_NUM_WORDS = "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|sixty|ninety|hundred"
QTY_RE = re.compile(
    rf"(?<![\w.])(?P<num>\d+(?:[,.]\d+)?|{_NUM_WORDS})(?:\s*\(\d+\))?\s*[-–]?\s*"
    r"(?P<unit>(?:calendar|working)\s+days?|years?|yrs?\.?|months?|mos?\.?|weeks?|days?|hours?|hrs?\.?|sets?|"
    r"each|ea\.?|pieces?|pcs?\.?|copies|copy|kits?|pairs?|boxes|box|cartons?|gallons?|liters?|litres?|"
    r"rolls?|percent(?:age)?|%)(?![\w])",
    re.I,
)
# "one spare filter set", "two complete sets": countable unit up to three words after the number
QTY_GAP_RE = re.compile(
    rf"(?<![\w.])(?P<num>\d+|{_NUM_WORDS})(?:\s*\(\d+\))?\s+(?:[a-z][a-z-]*\s+){{1,3}}?"
    r"(?P<unit>sets?|copies|kits?|pairs?|boxes|cartons?|rolls?|pieces?|spares)(?![\w])",
    re.I,
)
SECTION_PATTERNS = [
    re.compile(r"^\s*SECTION\s+(\d{2}\s?\d{2}\s?\d{2}(?:\.\d{2})?)\s*[-–:.]?\s*(.{3,140}?)\s*$", re.I),
    re.compile(r"^\s*(\d{2}\s\d{2}\s\d{2}(?:\.\d{2})?)\s+([A-Z][A-Z0-9 ,&/()'-]{3,140})\s*$"),
    re.compile(r"^\s*ITEM\s+([A-Z]{1,2}-\d{2,4}[A-Z]?)\s*[-–:.]?\s*(.{3,140}?)\s*$", re.I),
    re.compile(r"^\s*SECTION\s+(\d{1,4})\s*[-–:.]\s*(.{3,140}?)\s*$", re.I),
    # "Section 50 Control of Work" (FAA AC 150/5370 style): keyword + number + capitalised title
    re.compile(r"^\s*(?:SECTION|Section)\s+(\d{1,4})\s+([A-Z][A-Za-z0-9 ,&/()'-]{2,120}?)\s*$"),
]
TOC_LINE = re.compile(r"\.{3,}\s*\d+\s*$|\s{2,}\d{1,4}\s*$")
CAT_PATTERNS = [
    ("Attic Stock", r"attic stock|stock of"),
    ("Spare Part / Extra Material", r"spares?\b|replacement parts?|extra materials?|extra stock|maintenance materials?"),
    ("Special Tool", r"special tools?|special keys?|special wrench|special equipment"),
    ("O&M / Manuals / Records", r"operation(?:s)? and maintenance|\bo&m\b|operating and maintenance|manuals?|as[- ]built|"
                                r"record drawings?|maintenance data|manufacturer(?:'s)? instructions"),
    ("Training / Demonstration", r"training|demonstration"),
    ("Warranty", r"warrant(?:y|ies|ed)|guarantee"),
    ("Maintenance / Service", r"maintenance service|service contract|maintenance agreement|inspect(?:ion)?s? annually|service visits?"),
    ("Testing / Reports / Certification", r"commissioning|test reports?|inspection reports?|final reports?|certification|certificates?|test results"),
    ("Other Closeout", r"closeout|close-out|turnover|submittals?|deliverables?"),
]


@dataclass
class SectionState:
    section: str = ""
    title: str = ""


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("­", "").replace("\x00", " ")).strip()


def classify(s: str) -> str:
    for label, pattern in CAT_PATTERNS:
        if re.search(pattern, s, re.I):
            return label
    return "Other Closeout"


def quantity(s: str) -> tuple[str, str]:
    m = QTY_RE.search(s) or QTY_GAP_RE.search(s)
    if not m:
        return "", ""
    unit = norm(m.group("unit")).upper().replace(".", "")
    return m.group("num"), "PERCENT" if unit in ("%", "PERCENT", "PERCENTAGE") else unit


def division_of(section: str) -> str:
    digits = re.sub(r"\D", "", section or "")
    return digits[:2] if len(digits) >= 6 else ""


def detect_section(text: str, state: SectionState) -> SectionState:
    for line in (text or "").splitlines()[:120]:
        line = line.strip()
        if not line or TOC_LINE.search(line):
            continue
        for rx in SECTION_PATTERNS:
            m = rx.match(line)
            if m:
                return SectionState(norm(m.group(1)), norm(m.group(2)))
    return state


def split_spans(text: str) -> list[str]:
    """Sentence-ish spans; joins hyphenated / wrapped lines first."""
    t = re.sub(r"-\n(?=[a-z])", "", text or "")
    # headings (SECTION lines, short ALL-CAPS titles) never merge into the next sentence
    lines = []
    for line in t.splitlines():
        s = line.strip()
        letters = [c for c in s if c.isalpha()]
        heading = any(rx.match(s) for rx in SECTION_PATTERNS) or (
            letters and len(s) <= 80 and sum(c.isupper() for c in letters) / len(letters) > 0.8
            and not s.endswith((".", ",", ";", ":")))
        lines.extend(["", line, ""] if heading else [line])
    t = "\n".join(lines)
    paras = re.split(r"\n\s*\n|\n(?=\s*(?:[A-Z]\.|\d+\.|[a-z]\)|\(\w\)|•|-)\s)", t)
    spans: list[str] = []
    carry = ""
    for p in paras:
        p = norm(p)
        if not p:
            continue
        if re.fullmatch(r"(?:[A-Za-z]|\d{1,2})\.", p):   # OCR put the list marker in its own block
            carry = p + " "
            continue
        p, carry = carry + p, ""
        chunks = [c.strip() for c in re.split(r"(?<=[.;!?])\s+(?=[A-Z0-9\[(])", p) if c.strip()]
        merged: list[str] = []
        for c in chunks:   # keep list markers ("A.", "2.", "a.") with their sentence
            if merged and re.fullmatch(r"(?:[A-Za-z]|\d{1,2})\.", merged[-1]):
                merged[-1] += " " + c
            else:
                merged.append(c)
        spans.extend(merged)
    return spans


def extract_requirements(text: str, source: str, page: int, state: SectionState, page_sha: str,
                         method: str, confidence: float | None, min_span: int = 18,
                         max_span: int = 1600) -> tuple[list[Finding], int]:
    """Return (findings, closeout keyword hits on this page)."""
    out: list[Finding] = []
    seen: set[str] = set()
    hits = 0
    for span in split_spans(text):
        if len(span) < min_span or len(span) > max_span or TOC_LINE.search(span):
            continue
        if not CLOSEOUT_TERMS.search(span):
            continue
        hits += 1
        if not OBLIGATION.search(span):
            continue
        key = span.casefold()
        if key in seen:
            continue
        seen.add(key)
        q, u = quantity(span)
        f = Finding(kind=REQUIREMENT, source_file=source, page=page, text=span, method=method,
                    category=classify(span), value=q, unit=u, section=state.section,
                    section_title=state.title, division=division_of(state.section),
                    confidence=confidence, status=CANDIDATE, page_sha256=page_sha)
        if not state.section:
            f.flag("Section number not detected", REVIEW)
        if not q:
            f.flag("No explicit quantity found; do not assume one")
        if len(span) > 500:
            f.flag("Long evidence span; possible multiple obligations", REVIEW)
        out.append(f)
    return out, hits
