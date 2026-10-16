"""Cross-finding analysis: conflicts (R10), verified-count calculations (R8), coverage (R11/R16)."""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spectakeoff.models import CONFLICT, REQUIREMENT, SCHEDULE_ROW, TOKEN, Finding, SourceResult

WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
            "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
            "fifty": 50, "sixty": 60, "ninety": 90, "hundred": 100}
UNIT_ALIASES = {"YEARS": "YEAR", "YRS": "YEAR", "YR": "YEAR", "MONTHS": "MONTH", "MOS": "MONTH", "MO": "MONTH",
                "WEEKS": "WEEK", "DAYS": "DAY", "HOURS": "HOUR", "HRS": "HOUR", "HR": "HOUR", "COPY": "COPIES",
                "SETS": "SET", "EA": "EACH", "PCS": "PIECE", "PC": "PIECE", "PIECES": "PIECE"}
# per-unit wording -> tag prefixes that can count that item on drawings/schedules
ITEM_PREFIXES = {
    "air handling unit": ["AHU"], "air handler": ["AHU"], "ahu": ["AHU"], "rooftop unit": ["RTU"], "rtu": ["RTU"],
    "fan coil": ["FCU"], "exhaust fan": ["EF"], "supply fan": ["SF"], "fan": ["EF", "SF", "RF"],
    "pump": ["P", "PMP"], "unit heater": ["UH", "CUH"], "boiler": ["B", "BLR"], "chiller": ["CH"],
    "cooling tower": ["CT"], "vav box": ["VAV"], "vav": ["VAV"], "panel": ["LP", "PP", "PNL", "DP", "RP"],
    "panelboard": ["LP", "PP", "PNL", "DP", "RP"], "transformer": ["TX", "XFMR"], "generator": ["GEN"],
    "water heater": ["WH", "HWH"], "damper": ["FD", "SD", "FSD"], "door": ["D"], "unit": [],
}
PER_UNIT = re.compile(r"\b(?:per|for each|for every|each)\s+((?:[a-z]+\s){0,2}?(?:" +
                      "|".join(sorted((re.escape(k) for k in ITEM_PREFIXES), key=len, reverse=True)) + r"))s?\b",
                      re.I)


def num(v: str) -> float | None:
    v = (v or "").strip().lower().replace(",", ".")
    if v in WORD_NUM:
        return float(WORD_NUM[v])
    try:
        return float(v)
    except ValueError:
        return None


def unit_key(u: str) -> str:
    u = (u or "").upper()
    return UNIT_ALIASES.get(u, u)


def flag_conflicts(findings: list[Finding]) -> int:
    groups: dict[tuple, list[Finding]] = defaultdict(list)
    for f in findings:
        if f.kind == REQUIREMENT and f.section and f.value and num(f.value) is not None:
            groups[(f.section, f.category, unit_key(f.unit))].append(f)
    n = 0
    for (sec, cat, unit), fs in groups.items():
        values = sorted({num(f.value) for f in fs})
        if len(values) > 1:
            desc = " vs ".join(f"{v:g} {unit}" for v in values)
            where = ", ".join(sorted({f"{f.source_file} p{f.page}" for f in fs}))
            for f in fs:
                f.flag(f"Possible conflict in {sec} / {cat}: {desc} ({where}) — verify which applies", CONFLICT)
                n += 1
    return n


@dataclass
class VerifiedCount:
    item: str
    count: float
    verified_by: str
    source: str


def load_counts(path: Path | None) -> dict[str, VerifiedCount]:
    """Estimator CSV: item,count,verified_by[,source]. Rows without verified_by are ignored."""
    if not path:
        return {}
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            c = num(row.get("count", ""))
            if row.get("item") and c is not None and row.get("verified_by"):
                out[row["item"].lower()] = VerifiedCount(row["item"], c, row["verified_by"], row.get("source", ""))
    return out


def calculation_rows(findings: list[Finding], counts: dict[str, VerifiedCount]) -> list[list[Any]]:
    """R8: per-unit requirement × verified count. Never multiplies unverified counts."""
    tags_by_prefix: dict[str, set[str]] = defaultdict(set)
    for f in findings:
        if f.kind in (TOKEN, SCHEDULE_ROW) and f.tag:
            tags_by_prefix[f.tag.split("-")[0]].add(f.tag)
    rows = []
    for f in findings:
        if f.kind != REQUIREMENT or not f.value:
            continue
        m = PER_UNIT.search(f.text)
        per = num(f.value)
        if not m or per is None:
            continue
        item = m.group(1).lower().strip()
        key = next((k for k in sorted(ITEM_PREFIXES, key=len, reverse=True) if item.endswith(k)), item)
        vc = counts.get(key) or counts.get(item)
        evidence = []
        for pre in ITEM_PREFIXES.get(key, []):
            if tags_by_prefix.get(pre):
                tags = sorted(tags_by_prefix[pre])
                evidence.append(f"{len(tags)} distinct {pre} tag(s): {', '.join(tags[:12])}")
        if vc:
            status = f"Calculated from count verified by {vc.verified_by} — review"
        else:
            status = "Needs verified count (--counts CSV); total left blank"
        rows.append([f.id, f.source_file, f.page, f.text, per, f.unit, key, vc.count if vc else None,
                     (vc.source or "estimator") if vc else "", bool(vc), "; ".join(evidence) or "none found",
                     status])
    return rows


def coverage_rows(results: list[SourceResult], hits: dict[str, int]) -> list[list[Any]]:
    stats: dict[str, dict] = {}
    for r in results:
        for p in r.pages:
            if p.section:
                s = stats.setdefault(p.section, {"titles": set(), "pages": [], "n": 0})
                s["pages"].append(p.page)
                if p.section_title:
                    s["titles"].add(p.section_title)
        for f in r.findings:
            if f.kind == REQUIREMENT and f.section in stats:
                stats[f.section]["n"] += 1
    rows = []
    for sec, s in sorted(stats.items()):
        digits = re.sub(r"\D", "", sec)
        div = digits[:2] if len(digits) >= 6 else ""
        h = hits.get(sec, 0)
        if s["n"]:
            status = "Candidates found — review required"
        elif h:
            status = "CHECK — closeout keywords but no candidate rows"
        else:
            status = "No candidate found — not proof that no requirement exists"
        if div in ("23", "26") and not s["n"]:
            status = f"CHECK — Division {div} section without closeout candidates"
        pages = sorted(set(s["pages"]))
        rows.append([sec, "; ".join(sorted(s["titles"])), div, f"{pages[0]}-{pages[-1]}", h, s["n"], status])
    return rows

