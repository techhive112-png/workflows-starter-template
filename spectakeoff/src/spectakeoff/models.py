"""Unified data model shared by every extractor (roadmap item 1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Finding kinds
REQUIREMENT = "requirement"        # obligation sentence from spec text
DRAWING_TEXT = "drawing_text"      # a label / note line read from a drawing
TOKEN = "token"                    # structured token: tag, steel shape, dimension...
SCHEDULE_ROW = "schedule_row"      # row of a table / schedule
VISUAL_REVIEW = "visual_review"    # page needs a human eye (photo, unreadable drawing)

# Review statuses — nothing is ever "certified" by the tool
CANDIDATE = "CANDIDATE"            # good evidence, still needs human sign-off
REVIEW = "REVIEW"                  # weak / ambiguous evidence, check first
CONFLICT = "CONFLICT"              # contradicts another finding

# Evidence methods
PDF_TEXT = "PDF text layer"
PDF_VECTOR = "PDF vector drawing text"
PDF_TABLE = "PDF table detection"
OCR_PAGE = "OCR (full page)"
OCR_DRAWING = "OCR (drawing, lines removed)"
NONE = "No machine-readable evidence"


@dataclass
class BBox:
    x0: float
    y0: float
    x1: float
    y1: float

    def __str__(self) -> str:
        return f"{self.x0:.0f},{self.y0:.0f},{self.x1:.0f},{self.y1:.0f}"


@dataclass
class Finding:
    kind: str
    source_file: str
    page: int
    text: str                      # verbatim evidence, never reworded
    method: str
    category: str = ""
    value: str = ""                # quantity / normalised token value
    unit: str = ""
    tag: str = ""                  # equipment / device tag the finding refers to
    section: str = ""
    section_title: str = ""
    division: str = ""
    bbox: Optional[BBox] = None    # pixel (raster) or point (PDF) coordinates
    confidence: Optional[float] = None   # OCR word confidence, NOT correctness
    status: str = CANDIDATE
    flags: list[str] = field(default_factory=list)
    translated: str = ""
    page_sha256: str = ""
    id: str = ""

    def flag(self, msg: str, status: Optional[str] = None) -> None:
        if msg not in self.flags:
            self.flags.append(msg)
        if status == CONFLICT or (status == REVIEW and self.status == CANDIDATE):
            self.status = status


@dataclass
class PageRecord:
    source_file: str
    page: int
    page_kind: str                 # spec_text | drawing_vector | drawing_raster | photo | scan_text | blank
    method: str
    characters: int = 0
    images: int = 0
    ocr_confidence: Optional[float] = None
    section: str = ""
    section_title: str = ""
    sha256: str = ""
    text_regions: int = 0
    accepted_lines: int = 0
    rejected_noise: int = 0
    findings: int = 0
    status: str = "Read"           # Read | REVIEW
    warnings: list[str] = field(default_factory=list)
    overlay: str = ""              # path of annotated review image
    text: str = ""                 # raw page text, only kept for labelling (Config.keep_text)

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)
        self.status = "REVIEW"


@dataclass
class SourceResult:
    source: str
    sha256: str
    pages: list[PageRecord] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    error: str = ""
    elapsed: float = 0.0
