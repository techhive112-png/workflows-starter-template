"""Measure extraction quality against a human-checked gold set.

Gold CSV columns: source, page, kind (optional: requirement / drawing_text / token /
schedule_row), text. Only pages that appear in the gold file are scored, so a gold
set can cover a sample of pages.
"""
from __future__ import annotations

import csv
import json
import re
from difflib import SequenceMatcher
from pathlib import Path


def _n(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("[?]", " ")).strip().casefold()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _n(a), _n(b)).ratio()


def evaluate(findings: list[dict], gold: list[dict], threshold: float = 0.85) -> dict:
    scope = {(g["source"], int(g["page"])) for g in gold}
    kinds = {g.get("kind") for g in gold if g.get("kind")}
    preds = [f for f in findings if (f["source_file"], int(f["page"])) in scope
             and (not kinds or f["kind"] in kinds)]
    used: set[int] = set()
    matched, missed = [], []
    for g in gold:
        best, best_i = 0.0, -1
        for i, f in enumerate(preds):
            if i in used or f["source_file"] != g["source"] or int(f["page"]) != int(g["page"]):
                continue
            if g.get("kind") and f["kind"] != g["kind"]:
                continue
            s = similarity(f["text"], g["text"])
            if s > best:
                best, best_i = s, i
        if best >= threshold:
            used.add(best_i)
            matched.append({"gold": g["text"], "found": preds[best_i]["text"], "similarity": round(best, 3)})
        else:
            missed.append({"gold": g["text"], "best_similarity": round(best, 3)})
    tp = len(matched)
    extra = [f["text"] for i, f in enumerate(preds) if i not in used]
    return {
        "gold_items": len(gold), "predictions_in_scope": len(preds), "true_positives": tp,
        "recall": round(tp / len(gold), 4) if gold else None,
        "precision": round(tp / len(preds), 4) if preds else None,
        "threshold": threshold, "matched": matched, "missed": missed, "unmatched_predictions": extra,
        "note": "Scores apply to this gold set only; they are not a guarantee for other documents.",
    }


def run_eval(findings_json: Path, gold_csv: Path, threshold: float) -> dict:
    data = json.loads(findings_json.read_text(encoding="utf-8"))
    with open(gold_csv, newline="", encoding="utf-8-sig") as fh:
        gold = [{k.strip().lower(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)]
    return evaluate(data["findings"], gold, threshold)
