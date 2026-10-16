"""Recognisers for structured construction tokens found on drawings and in specs.

Each recogniser returns the exact matched text (evidence) plus a normalised
value. Recognising a token never implies a quantity: counts come only from
explicit count notes, schedules, or an estimator.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

STEEL_SHAPE = "Steel shape"
BOLT = "Bolt / fastener"
WELD = "Weld"
EQUIPMENT_TAG = "Equipment / device tag"
DIMENSION = "Dimension"
NUMBER = "Number (possible dimension, unit not stated)"
ELEVATION = "Elevation / level"
DETAIL_REF = "Detail / sheet reference"
COUNT_NOTE = "Count note"
SPEC_SECTION = "Spec section reference"

_X = r"\s?[xX×]\s?"
_N = r"\d+(?:[.,]\d+)?"
_FRAC = r"\d+(?:\s?\d/\d{1,2}|[./]\d+)?"

_SINGLE_PREFIX = "P|B|F|E|T|H|L|M|D|C|G|K"
_MULTI_PREFIX = (
    "AHU|RTU|EF|SF|RF|FCU|VAV|CUH|UH|CH|CT|HX|ACCU|MAU|ERV|HRV|DOAS|WH|HWH|BLR|PMP|"
    "LP|PP|MDP|PNL|DP|RP|TX|XFMR|ATS|GEN|UPS|MCC|VFD|FD|SD|FSD|CD|GRD|RG|SG|EG|"
    "FA|FACP|CR|DR|WD|SK|LAV|WC|UR|DF|FE|FHC"
)

RECOGNISERS: list[tuple[str, re.Pattern[str]]] = [
    # Metric bolts before steel shapes: M20x60 is a bolt, M12x11.8 is an AISC M-shape.
    (BOLT, re.compile(r"\bM(?:8|10|12|16|20|22|24|27|30|36)(?:\s?[xX×]\s?(?:[2-9]\d|\d{3}))?(?:\s?(?:8\.8|10\.9))?(?![xX×.]?\d)")),
    (STEEL_SHAPE, re.compile(rf"\bHSS\s?{_N}(?:{_X}{_FRAC}){{1,2}}", re.I)),
    (STEEL_SHAPE, re.compile(rf"\b(?:RHS|SHS|CHS)\s?{_N}(?:{_X}{_N}){{1,2}}", re.I)),
    (STEEL_SHAPE, re.compile(rf"\bL\s?{_N}{_X}{_N}{_X}{_FRAC}", re.I)),
    (STEEL_SHAPE, re.compile(rf"\b(?:W|M|S|HP|WT|MT|ST|C|MC)\s?\d{{1,2}}(?:\.\d+)?{_X}\d{{1,3}}(?:\.\d+)?\b")),
    (STEEL_SHAPE, re.compile(r"\b(?:IPE|IPN|UPN|UPE|HE[ABM]|HE\s?\d{2,4}\s?[ABM])\s?\d{2,4}\b", re.I)),
    (STEEL_SHAPE, re.compile(rf"\bPL\.?\s?{_FRAC}\s?(?:\"|mm)?(?:{_X}{_N}\s?(?:\"|mm)?){{0,2}}", re.I)),
    (BOLT, re.compile(r"(?:\(\d{1,3}\)\s?)?\b\d/\d{1,2}\"?\s?(?:Ø|DIA\.?)?\s?(?:A325|A490|F1852|F2280|A307)?(?:[- ]?[NXS]C?)?\s?(?:H\.?S\.?\s?)?BOLTS?\b", re.I)),
    (BOLT, re.compile(r"\b(?:A325|A490|F1852|F2280|A307)(?:-[NXS]C?)?\b", re.I)),
    (WELD, re.compile(r"\b(?:\d/\d{1,2}\"?\s?)?(?:FILLET\s?WELD|FILLET|CJP|PJP|FW)\b", re.I)),
    (ELEVATION, re.compile(r"\b(?:EL\.?|ELEV\.?|T\.?O\.?[SCFW]\.?|TOS|BOS|B\.O\.[SF]?\.?)\s?[+-]?\d+(?:'\s?-?\s?\d{1,2}(?:\s\d/\d{1,2})?\"?|[.,]\d+)?", re.I)),
    (ELEVATION, re.compile(r"(?<![\w.])[+±-]\s?\d{1,3}[.,]\d{3}\b")),
    (DIMENSION, re.compile(r"(?<![\w'])\d{1,3}'\s?-?\s?\d{1,2}(?:\s\d/\d{1,2})?\"?")),
    (DIMENSION, re.compile(rf"(?<![\w.]){_N}\s?(?:mm|cm|m){_X}{_N}\s?(?:mm|cm|m)?\b|(?<![\w.]){_N}{_X}{_N}\s?(?:mm|cm|m)\b", re.I)),
    (DIMENSION, re.compile(r"(?<![\w.])\d{1,5}(?:[.,]\d+)?\s?(?:mm|cm|m)\b", re.I)),
    (DETAIL_REF, re.compile(r"(?<![\d/])\d{1,2}\s?/\s?[A-Z]{1,2}-?\d{1,4}(?:\.\d{1,2})?\b")),
    (EQUIPMENT_TAG, re.compile(rf"\b(?:{_MULTI_PREFIX})[-\s]?\d{{1,3}}[A-Z]?\b")),
    (EQUIPMENT_TAG, re.compile(rf"\b(?:{_SINGLE_PREFIX})-\d{{1,3}}[A-Z]?\b")),
    (COUNT_NOTE, re.compile(r"\(\s?\d{1,3}\s?\)(?=\s?[A-Z0-9])|\b\d{1,3}\s?(?:PLACES|PLCS|PL\.|EQ\.?\s?SP\.?|EA\.?|PCS|GAB\.?|VIETAS)(?!\w)", re.I)),
    (SPEC_SECTION, re.compile(r"\b\d{2}\s\d{2}\s\d{2}(?:\.\d{2})?\b")),
    (NUMBER, re.compile(r"(?<![\w.,'/-])\d{3,5}(?![\w.,'\"/])")),
]


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    value: str
    unit: str
    start: int
    end: int


def _unit_of(kind: str, text: str) -> str:
    t = text.lower()
    if kind == DIMENSION:
        if "'" in t or '"' in t:
            return "ft-in"
        m = re.search(r"(mm|cm|m)\b", t)
        return m.group(1) if m else ""
    if kind == COUNT_NOTE:
        return "EA"
    return ""


def _value_of(kind: str, text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    if kind == COUNT_NOTE:
        m = re.search(r"\d+", t)
        return m.group(0) if m else ""
    if kind == STEEL_SHAPE:
        return re.sub(r"\s?[xX×]\s?", "x", t).upper().replace(" ", "")
    if kind == EQUIPMENT_TAG:
        return re.sub(r"[\s-]+", "-", t.upper())
    return t


def find_tokens(text: str) -> list[Token]:
    """Return non-overlapping tokens; earlier recognisers win on overlap."""
    taken: list[tuple[int, int]] = []
    out: list[Token] = []
    for kind, rx in RECOGNISERS:
        for m in rx.finditer(text or ""):
            s, e = m.span()
            if e - s < 2 or any(s < te and e > ts for ts, te in taken):
                continue
            raw = m.group(0).strip()
            taken.append((s, e))
            out.append(Token(kind, raw, _value_of(kind, raw), _unit_of(kind, raw), s, e))
    out.sort(key=lambda t: t.start)
    return out


# Construction vocabulary used to tell real drawing words from OCR noise.
# English + Latvian, upper-case, without diacritics (compared after folding).
VOCABULARY = set("""
ABOVE ACCESS ACOUSTIC ADHESIVE AIR ALIGN ALUMINIUM ALUMINUM ANCHOR ANGLE ARCHITECTURAL ASPHALT ASSEMBLY
BACKER BAR BARRIER BASE BATT BEAM BEARING BELOW BLOCK BOARD BOLT BOLTS BOTTOM BRACE BRACKET BRICK BUILT
CANOPY CAP CAVITY CEILING CEMENT CHANNEL CLADDING CLEAR CLIP COATING COLUMN COMPOSITE CONCRETE CONNECTION
CONTINUOUS CONTROL COPING CORNER COURSE COVER CURB CURTAIN DAMPPROOF DECK DETAIL DIA DIMENSION DOOR DOWEL
DRAIN DRIP DRYWALL DUCT EACH EDGE ELEVATION EMBED END EPDM EQ EXISTING EXPANSION EXTERIOR FACE FASCIA FIBER
FIBRE FILL FILLET FINISH FIRE FIRESTOP FLANGE FLASHING FLOOR FLUID FOAM FOOTING FRAME FRAMING FULL GALV
GALVANIZED GALVANISED GAP GIRDER GLASS GLAZING GRADE GRAVEL GRID GROUT GUSSET GUTTER GYPSUM HANGER HEAD HEIGHT
HOLE HOLLOW INSULATION INSULATED INTERIOR JAMB JOINT JOIST LAP LAYER LEDGER LEVEL LINE LINTEL LOAD MASONRY
MATERIAL MEMBRANE MESH METAL MIN MAX MINERAL MORTAR MULLION NOTE NOTES NUT OPENING PANEL PARAPET PARTITION
PAVING PIER PIPE PLASTER PLATE PLYWOOD POLY PRECAST PRIMER PROFILE PROVIDE PURLIN RAIL RAINSCREEN REBAR
REINFORCEMENT REINFORCED RIGID ROOF ROOFING SCHEDULE SCREW SEALANT SECTION SEE SHEATHING SHEET SHIM SIDING
SILL SLAB SLEEVE SOFFIT SPACING SPRAY STAINLESS STEEL STIFFENER STONE STRUCTURAL STRUCTURE STUD STUDS
SUBFLOOR SUPPORT SURFACE SYSTEM TAPE THERMAL THICK THRESHOLD TIE TILE TIMBER TOP TRACK TRIM TYP TYPICAL
UNDERLAY UNIT VAPOR VAPOUR VENEER VENT VERIFY VERTICAL WALL WASHER WATERPROOF WATERPROOFING WEATHER WEB WELD
WELDED WINDOW WIRE WOOD WRAP ZINC
EL ELEV TOS BOS TOC TOW BOF FFL SSL NTS TYP DIA CL OC CTR CTRS EQ SP SIM REF REQD NO QTY EA GALV HDG
SIJA KOLONNA PLATNE PLATE SKRUVE SKRUVES BULTSKRUVE UZGRIEZNIS PAPLAKSNE METINAJUMS BETONS DZELZSBETONS
IZOLACIJA SILTUMIZOLACIJA HIDROIZOLACIJA TVAIKIZOLACIJA MEMBRANA SIENA SIENAS GRIESTI GRIDA JUMTS
PARSEGUMS PAMATI LOGS LOGI DURVIS PALODZE APDARE FASADE KARKASS PROFILS LENKIS TERAUDS ALUMINIJS KOKS
GIPSKARTONS LISTE SKARDA NOTEKA STIPRINAJUMS ENKURS MEZGLS GRIEZUMS SKATS PLANS PIEZIME TIPVEIDA
AUGSTUMS PLATUMS BIEZUMS GARUMS SLANIS
""".split())


def fold(word: str) -> str:
    """Upper-case and strip Latvian/European diacritics for vocabulary lookup."""
    table = str.maketrans("ĀČĒĢĪĶĻŅŠŪŽÄÖÜÉÈÀ", "ACEGIKLNSUZAOUEEA")
    return re.sub(r"[^A-Z0-9]", "", word.upper().translate(table))
