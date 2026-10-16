"""Closeout requirement extraction from specification text.

Carried over from v3 with fixes:
* `%` / percent quantities are now recognised (v3 `%\\b` could never match),
* section headings require a SECTION/ITEM keyword or a CSI number + upper-case
  title (v3 treated any line starting with 3–4 digits as a section),
* table-of-contents lines and running headers are skipped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from spectakeoff.models import CANDIDATE, REQUIREMENT, REVIEW, Finding

# Whole words only: v3 matched "training" inside "air-entraining".
CLOSEOUT_TERMS = re.compile(
    r"(?<![\w-])(?:attic stock|spares?|extra materials?|extra filters?|special tools?|operation(?:s)? and maintenance|o&m|"
    r"operating and maintenance|owner(?:'s)? manuals?|maintenance service|service contract|training|"
    r"warrant(?:y|ies|ed|s)?|as[- ]built|record drawings?|closeout|close-out|turnover|turn over|commissioning|"
    r"test reports?|documentation of (?:the )?tests?(?: performed)?|"
    r"inspection reports?|final reports?|instruction manuals?|replacement parts?|"
    r"maintenance agreement|maintenance materials?|operation manual|service visits?|submittals?|deliverables?|"
    r"certifications?|certificates?|manufacturer(?:'s)? (?:[a-z]+ ){0,2}instructions|spare equipment|extra stock|maintenance data|"
    r"guarant(?:ee|eed|ees|y)|demonstration of (?:the )?(?:system|equipment)s?)(?![\w])",
    re.I,
)
# A submission verb and a document noun in the same sentence: "Friction tests shall be submitted",
# "the Contractor shall provide a supplemental COA". Catches deliverables the keyword list misses.
_DOC = (r"COAs?|COCs?|certificates?|certifications?|(?:test|inspection|calibration|analysis|field|final)\s+reports?|"
        r"tests|test\s+data|test\s+results|documentation\s+of\s+(?:the\s+)?tests?")
_SUBMIT_ACTIVE = r"submit|submits|furnish|furnishes|provide|provides"
_SUBMIT_PASSIVE = r"submitted|furnished|provided"
DELIVERABLE = re.compile(
    rf"\b(?:{_SUBMIT_ACTIVE})\b(?P<gap>(?:\W+\w+){{0,14}}?)\W+(?:{_DOC})\b|"
    rf"\b(?:{_DOC})\b(?:\W+\w+){{0,10}}?\W+(?:be|are|is)\s+(?:{_SUBMIT_PASSIVE})\b",
    re.I,
)
# "furnish instruments ... required for the tests": the tests are not what is handed over
_NOT_OBJECT = re.compile(
    r"\b(?:for|during|after|before|until|required for)\s+(?:the\s+|all\s+|each\s+)?$|"
    r"\b(?:have|has|having|bear|bears|bearing)\s+(?:[\w-]+\s+){0,2}$",   # "luminaires which have FM certification"
    re.I)


def has_deliverable(text: str) -> bool:
    for m in DELIVERABLE.finditer(text):
        if m.group("gap") is not None:
            doc_start = m.start() + len(m.group(0)) - len(re.search(rf"(?:{_DOC})$", m.group(0), re.I).group(0))
            if _NOT_OBJECT.search(text[max(0, doc_start - 30):doc_start]):
                continue
        return True
    return False


# Closeout words used in a sense that is not a deliverable; removed before keyword matching.
NON_DELIVERABLE = re.compile(
    r"certificates? of deposit|bid (?:guarant\w*|bonds?|security)|proposal guarant\w*|guarantee (?:the )?completion|"
    r"guaranteed analysis|spare (?:conduits?|ducts?|capacity|circuits?|breakers? space)|"
    r"late submissions?(?: or resubmissions?)?(?: of submittals?)?|"
    # "one spare normally open auxiliary contact": a built-in feature, not a spare-part deliverable
    r"spare (?:[\w-]+ ){0,3}(?:contacts?|terminals?|poles?|circuits?|spaces?|conduits?|ducts?|capacity|fib(?:er|re)s?|"
    r"pairs?|ports?|slots?|ways?|breakers?|positions?|cores?)\b|"
    # product attributes: "luminaires which have Factory Mutual certification", "bear the UL label"
    r"\b(?:which|that)\s+(?:have|has|bear|bears|carry|carries)\s+(?:[\w-]+\s+){0,3}(?:certifications?|certificates?)\b|"
    # cross-references to other sections are not deliverables of this one
    r"\bsections?\s+\d{2}\s?\d{2}\s?\d{2}(?:\.\d{2}(?:\s\d{2})?)?,?(?:\s+[A-Z][A-Z0-9,&/()'-]*(?:\s+[A-Z][A-Z0-9,&/()'-]*)*)?|"
    r"(?:in (?:strict |full )?accordance (?:with|to)|according to|per|following|follow|as recommended by|as directed by) (?:the )?"
    r"(?:[\w-]+ ){0,2}manufacturer(?:'s|’s|s')? (?:[a-z]+ ){0,2}instructions|manufacturer(?:'s|’s)? printed instructions",
    re.I,
)
# Legal clarifications that mention a deliverable but impose nothing.
CLARIFICATION = re.compile(
    r"\b(?:shall|will|does|do|must)\s+not\s+(?:be\s+)?(?:interpreted|construed|relieve|limit|preclude|constitute|"
    r"waive|release|guarantee)\b|\bnor shall\b|\bmakes? no (?:guarantee|warranty|representation)|\bno guarantee\b",
    re.I,
)
OBLIGATION = re.compile(
    r"\b(shall|must|required to|will provide|provide|furnish|supply|submit|deliver|include|turn over|turnover|"
    r"maintain|warrants|warranted|is to be submitted|are to be submitted)\b(?!\s+not\b)",
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
                                r"record drawings?|maintenance data|manufacturer(?:'s)? (?:[a-z]+ ){0,2}instructions"),
    ("Training / Demonstration", r"training|demonstration"),
    ("Warranty", r"warrant(?:y|ies|ed|s)?|guarant(?:ee|eed|ees|y)"),
    ("Maintenance / Service", r"maintenance service|service contract|maintenance agreement|inspect(?:ion)?s? annually|service visits?"),
    ("Testing / Reports / Certification", r"commissioning|test reports?|inspection reports?|final reports?|certification|certificates?|test results"),
    ("Other Closeout", r"closeout|close-out|turnover|submittals?|deliverables?"),
]


@dataclass
class SectionState:
    section: str = ""
    title: str = ""
    in_note: bool = False          # inside an editor's note block (****** ... ******)
    register: str = ""             # current UFGS submittal-register heading (SD-10 ...)
    closeout_ctx: bool = False     # inside a CLOSEOUT SUBMITTALS / WARRANTY article
    closeout_depth: int = 0        # heading depth of that article (1.7 -> 2); deeper headings stay inside
    list_ctx: bool = False         # lettered items after "... include the following:" of a requirement
    since_req: int = 99            # spans since the last extracted requirement
    last_req_strong: bool = False  # last requirement was about a manual / warranty / report ...


# "*****.", UFGS "] *****", and FAA "*****6" where the next line's first character got glued on
NOTE_DELIM = re.compile(r"^\s*[\[\]]?\s*\*{10,}[\s.\[\]]*(?P<tail>[\w.-]{0,4})\s*$")
# UFGS submittal register: items listed under these SD categories are closeout deliverables
SD_HEADING = re.compile(r"^\s*[\[\]]*\s*(SD-(\d{2})\s+[A-Z][A-Za-z'’ &/-]+?)\s*\]?\s*$")
SD_CATEGORY = {"06": "Testing / Reports / Certification", "07": "Testing / Reports / Certification",
               "09": "Testing / Reports / Certification", "10": "O&M / Manuals / Records",
               "11": "Other Closeout"}
NUMBERED_HEADING = re.compile(r"^\s*(?:PART\s+\d|\d+\.\d+(?:\.\d+)*\s+[A-Z])")
CLOSEOUT_HEADING = re.compile(r"\b(?:CLOSEOUT SUBMITTALS|CLOSE-OUT SUBMITTALS|MAINTENANCE MATERIAL SUBMITTALS|"
                              r"EXTRA MATERIALS|WARRANTY|WARRANTIES|SPARE PARTS|OPERATION AND MAINTENANCE (?:DATA|MANUALS?)|O&M MANUALS?)\b")
# lists inherit an obligation only from these document-type deliverables (contents of a manual, plan, report)
STRONG_DOC = re.compile(r"operation and maintenance|\bo&m\b|\bmanuals?\b|warrant|guarant|as-built|record drawings?|"
                        r"\breports?\b|spare parts|extra materials|closeout|close-out|final acceptance", re.I)
LIST_ITEM = re.compile(r"^(?:[a-z]|[A-Z]|\d{1,2})[.)]\s|^\(\w{1,3}\)\s")


# running footers such as "SECTION 01 78 00  Page 14" carry no content
PAGE_FOOTER = re.compile(r"^\s*SECTION\s+\d{2}\s?\d{2}\s?\d{2}(?:\.\d{2}(?:\s\d{2})?)?\s+Page\s+\d+\s*$", re.I)
NOTE_START = re.compile(r"^(?:NOTE\b|(?:The\s+)?Engineer\b|Note to (?:the )?(?:Engineer|Designer|Specifier))", re.I)
BODY_START = re.compile(r"^(?:SECTION\b|PART\s+\d|ITEM\b|\d+(?:\.\d+)+\s|\d{1,3}-\d{1,2}(?:\.\d+)*\b|[a-z]\.\s|\d{1,2}\.\s|"
                        r"[A-Z][A-Z&/,-]+(?:\s+[A-Z&/,-]+)*\s*$)")


def _segment_is_note(first_line: str, previous_is_note: bool) -> bool:
    if NOTE_START.match(first_line):
        return True
    if first_line and BODY_START.match(first_line):
        return False
    return not previous_is_note      # unknown content: delimiters alternate open / close


def strip_editor_notes(text: str, state: SectionState) -> tuple[str, int]:
    """Drop editor's notes between lines of asterisks (UFGS "NOTE:", FAA "The Engineer ...").

    Notes can cross page breaks and documents also use the asterisk lines as plain
    separators, so each block is judged by how it starts, not by counting delimiters.
    """
    segments: list[list[str]] = [[]]
    footers: list[str] = []
    carry = ""
    for line in (text or "").splitlines():
        m = NOTE_DELIM.match(line)
        if m:
            segments.append([])
            carry = m.group("tail") or ""
            continue
        if carry and line.strip():
            line, carry = carry + line.lstrip(), ""
        if PAGE_FOOTER.match(line):   # keep for section detection, outside the note logic
            segments[-1].append("")
            footers.append(line)
        else:
            segments[-1].append(line)
    out, dropped, prev_note = [], 0, state.in_note
    for k, seg in enumerate(segments):
        first = next((l.strip() for l in seg if l.strip()), "")
        if k == 0:
            note = bool(NOTE_START.match(first)) or (state.in_note and not (first and BODY_START.match(first)))
        else:
            note = _segment_is_note(first, prev_note)
        if note:
            dropped += sum(1 for l in seg if l.strip())
        else:
            out.extend(seg)
        prev_note = note
    state.in_note = prev_note
    return "\n".join(out + footers), dropped


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("­", "").replace("\x00", " ")).strip()


def classify(s: str) -> str:
    s = s.replace("’", "'")
    for label, pattern in CAT_PATTERNS:   # whole words: "air-entraining" is not "training"
        if re.search(rf"(?<![\w-])(?:{pattern})(?![\w])", s, re.I):
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
    prev = ""
    for line in (text or "").splitlines()[:120]:
        line = line.strip()
        if not line:
            continue
        # "...in accordance with\nSection 01 33 00 SUBMITTAL PROCEDURES" is a reference, not a heading
        continues = bool(re.search(r"[a-z,(]$|\b(?:with|in|to|per|of|and|or|see|under|by)$", prev))
        if PAGE_FOOTER.match(line) or line.startswith(("SECTION ", "ITEM ")):
            continues = False          # running headers / footers are never part of a sentence
        if not TOC_LINE.search(line) and not continues:
            for rx in SECTION_PATTERNS:
                m = rx.match(line)
                if m:
                    title = norm(re.sub(r"\bPage\s+\d+\s*$", "", m.group(2), flags=re.I))
                    return replace(state, section=norm(m.group(1)), title=title or state.title
                                   if norm(m.group(1)) == state.section else title)
        prev = line
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
        words = span.split()
        is_heading = (len(words) <= 8 and not span.rstrip("]").endswith((".", ";", ":"))
                      and sum(w[:1].isupper() for w in words if w[:1].isalpha()) >= 0.6 * len(words))
        numbered = NUMBERED_HEADING.match(span)
        if is_heading or numbered:
            num = re.match(r"\s*(\d+(?:\.\d+)*)", span)
            depth = num.group(1).count(".") + 1 if num else 99
            if CLOSEOUT_HEADING.search(span.upper()):
                state.closeout_ctx, state.closeout_depth = True, depth
            elif not (state.closeout_ctx and depth > state.closeout_depth):
                state.closeout_ctx = False
            state.list_ctx, state.since_req, state.last_req_strong = False, 99, False   # a new topic
            continue
        if len(words) >= 4:      # line-wrap fragments like "Include the" do not count as sentences
            state.since_req += 1
        if LIST_ITEM.match(span):
            in_list = state.list_ctx
        else:
            in_list = False
            # "Include the following:" right after a manual / warranty / report requirement opens an item list
            state.list_ctx = (span.rstrip().endswith(":") and len(span.split()) <= 8 and state.since_req <= 4
                              and state.last_req_strong)
        if len(span) < min_span or len(span) > max_span or TOC_LINE.search(span):
            continue
        probe = span.replace("’", "'")
        if in_list:   # "a. [Phase [_____]]": an empty template placeholder, not a list item
            body = re.sub(r"\[[^\]]*\]?|_{2,}|^\W*\w{1,3}[.)]\s*", " ", span)
            in_list = len(re.findall(r"[A-Za-z]{3,}", body)) >= 2
        implied = (state.closeout_ctx and re.match(r"(?:[A-Z]|\d{1,2})\.\s", span)) or in_list
        cleaned = NON_DELIVERABLE.sub(" ", probe)
        if not implied and not CLOSEOUT_TERMS.search(cleaned) and not has_deliverable(cleaned):
            continue
        hits += 1
        if CLARIFICATION.search(probe) or not (implied or OBLIGATION.search(probe)):
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
        if in_list:
            f.flag("List item of the preceding requirement ('... the following:')")
        elif implied:
            f.flag("Obligation implied by the closeout article heading")
        state.since_req = 0
        if not in_list:
            state.last_req_strong = bool(STRONG_DOC.search(span))
        if span.rstrip().endswith(":") and STRONG_DOC.search(span):
            state.list_ctx = True
        if not state.section:
            f.flag("Section number not detected", REVIEW)
        if not q:
            f.flag("No explicit quantity found; do not assume one")
        if len(span) > 500:
            f.flag("Long evidence span; possible multiple obligations", REVIEW)
        out.append(f)
    return out, hits


def extract_submittal_register(text: str, source: str, page: int, state: SectionState, page_sha: str,
                               method: str, confidence: float | None) -> list[Finding]:
    """UFGS lists: items under SD-06/07/09/10/11 headings are closeout deliverables."""
    out: list[Finding] = []
    for line in (text or "").splitlines():
        raw = line.strip().lstrip("[]").strip()
        if not raw or set(raw) <= set("*[] "):
            continue
        m = SD_HEADING.match(raw)
        if m:
            state.register = norm(m.group(1)) if m.group(2) in SD_CATEGORY else ""
            continue
        if NUMBERED_HEADING.match(raw) or re.match(r"^(?:SECTION|PART)\b", raw):
            state.register = ""
            continue
        if not state.register:
            continue
        item = norm(raw)
        while item.endswith("]") and item.count("]") > item.count("["):   # only unbalanced brackets
            item = item[:-1].rstrip()
        if item.endswith(".") and len(item.split()) > 8:   # a prose sentence ends the list
            state.register = ""
            continue
        item = item.rstrip(".").rstrip()
        if not (3 <= len(item) <= 160) or item.upper().startswith("NOTE"):
            continue
        code = state.register.split()[0][3:]
        f = Finding(kind=REQUIREMENT, source_file=source, page=page, text=item, method=method,
                    category=SD_CATEGORY[code], section=state.section, section_title=state.title,
                    division=division_of(state.section), confidence=confidence, status=CANDIDATE,
                    page_sha256=page_sha)
        f.flag(f"Listed under '{state.register}' (submittal register)")
        if re.search(r";\s*G\b", item):
            f.flag("Government approval required (G)")
        f.flag("No explicit quantity found; do not assume one")
        out.append(f)
    return out
