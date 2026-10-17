"""Measure extraction quality against a human-labelled gold set.

Two gold formats are accepted:

* the workbook from `spectakeoff label` (every candidate on sampled pages marked
  Jā/Nē/?) - gives true recall AND precision;
* a CSV with columns source,page,text[,kind][,label] - rows without a label are
  treated as positives (the original 4.0 format; recall only, precision approximate).

Pages where any candidate is still unlabelled are excluded, because recall on a
half-labelled page would be wrong.
"""
from __future__ import annotations

import csv
import json
import math
import re
from difflib import SequenceMatcher
from pathlib import Path

YES = {"jā", "ja", "j", "yes", "y", "1", "x", "true", "true_positive", "tp"}
NO = {"nē", "ne", "n", "no", "0", "false", "false_positive", "fp"}
SKIP = {"?", "borderline", "apšaubāms", "apšaubāma", "skip", "izlaist"}


def _n(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("[?]", " ").replace("’", "'")).strip().casefold()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _n(a), _n(b)).ratio()


def match_score(pred: str, gold: str) -> float:
    """1.0 when one text contains the other (and is not a tiny fragment of it), else similarity."""
    a, b = _n(pred), _n(gold)
    if not a or not b:
        return 0.0
    short, long_ = sorted((a, b), key=len)
    if short in long_ and (len(short) >= 0.5 * len(long_) or len(short) >= 40):
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round((c - r) / d, 4), round((c + r) / d, 4)


def parse_label(v) -> str | None:
    s = str(v or "").strip().casefold()
    if not s:
        return None
    if s in YES:
        return "yes"
    if s in NO:
        return "no"
    if s in SKIP:
        return "skip"
    raise ValueError(f"Nesaprotama atzīme {v!r} (lieto Jā, Nē vai ?)")


def read_gold(path: Path) -> tuple[list[dict], dict]:
    """Return (rows, meta). Row: source, page, text, label (yes/no/skip/None), note, kind."""
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook

        from spectakeoff.labeling import META, SHEET

        wb = load_workbook(path, read_only=True, data_only=True)
        try:
            meta = json.loads(wb[META]["A1"].value) if META in wb.sheetnames else {}
            ws = wb[SHEET] if SHEET in wb.sheetnames else wb.worksheets[0]
            it = ws.iter_rows(values_only=True)
            head = [str(h or "").strip().casefold() for h in next(it)]

            def col(*names):
                return next((i for i, h in enumerate(head) if any(h.startswith(n) for n in names)), None)

            cs, cp, ct = col("fails", "source"), col("lapa", "page"), col("teksts", "text")
            cl, cn = col("prasība", "label", "is requirement"), col("piezīme", "note")
            if None in (cs, cp, ct, cl):
                raise ValueError("Etalona lapā trūkst kolonnu Fails / Lapa / Teksts / Prasība?")
            rows = []
            for n, r in enumerate(it, start=2):
                if r is None or r[ct] in (None, ""):
                    continue
                rows.append({"source": str(r[cs]), "page": _page_number(r[cp], n), "text": str(r[ct]),
                             "label": parse_label(r[cl]), "note": str(r[cn] or "") if cn is not None else "",
                             "kind": "requirement"})
        finally:
            wb.close()
        return rows, meta
    with open(path, newline="", encoding="utf-8-sig") as fh:
        raw = [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)]
    if raw and not {"source", "page", "text"} <= set(raw[0]):
        raise ValueError("CSV etalonā vajag kolonnas source, page, text")
    rows = [{"source": r["source"], "page": _page_number(r["page"], n), "text": r["text"],
             "label": parse_label(r["label"]) if "label" in r else "yes",
             "note": r.get("reason", r.get("note", "")), "kind": r.get("kind", "")}
            for n, r in enumerate(raw, start=2)]
    return rows, {}


def _page_number(v, row: int) -> int:
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        raise ValueError(f"Etalona rindā {row} nav derīga lapas numura ({v!r})") from None


def evaluate(findings: list[dict], gold: list[dict], threshold: float = 0.85, kind: str = "") -> dict:
    pages: dict[tuple[str, int], list[dict]] = {}
    for g in gold:
        pages.setdefault((g["source"], int(g["page"])), []).append(g)
    incomplete = sorted(k for k, rows in pages.items() if any(r.get("label", "yes") is None for r in rows))
    scope = {k for k in pages if k not in incomplete}
    labelled = [g for k in sorted(scope) for g in pages[k]]
    has_negatives = any(g.get("label", "yes") == "no" for g in labelled)
    kinds = {kind} if kind else ({g["kind"] for g in labelled if g.get("kind")} or {"requirement"})
    preds = [f for f in findings if (f["source_file"], int(f["page"])) in scope and f["kind"] in kinds]

    hit: set[int] = set()            # indices of positive gold rows found
    tp_preds, fp_preds, ignored = [], [], 0
    for f in preds:
        # best match wins; ties (e.g. two rows containing "Plumbing System") go to the most similar text
        cands = [(match_score(f["text"], g["text"]), similarity(f["text"], g["text"]), i, g)
                 for i, g in enumerate(labelled)
                 if g["source"] == f["source_file"] and int(g["page"]) == int(f["page"])]
        best4 = max(cands, default=(0.0, 0.0, -1, None), key=lambda c: (c[0], c[1]))
        best = (best4[0], best4[2], best4[3])
        if best[0] >= threshold and best[2].get("label", "yes") == "yes" and best[1] in hit:
            # a second row for an already matched requirement is a duplicate, not another true positive
            fp_preds.append({"source": f["source_file"], "page": f["page"], "found": f["text"],
                             "why": "dublikāts jau atrastai etalona rindai", "gold": best[2]["text"], "note": ""})
        elif best[0] >= threshold and best[2].get("label", "yes") == "yes":
            hit.add(best[1])
            tp_preds.append({"source": f["source_file"], "page": f["page"], "found": f["text"],
                             "gold": best[2]["text"], "score": round(best[0], 3)})
        elif best[0] >= threshold and best[2].get("label", "yes") == "skip":
            ignored += 1
        elif best[0] >= threshold and best[2].get("label", "yes") == "no":
            fp_preds.append({"source": f["source_file"], "page": f["page"], "found": f["text"],
                             "why": "atzīmēts kā Nē", "gold": best[2]["text"], "note": best[2].get("note", "")})
        else:   # in a positives-only gold set everything true is listed, so this is also an error
            fp_preds.append({"source": f["source_file"], "page": f["page"], "found": f["text"],
                             "why": "nav atbilstošas etalona rindas", "gold": "", "note": ""})
    positives = [i for i, g in enumerate(labelled) if g.get("label", "yes") == "yes"]
    missed = [{"source": labelled[i]["source"], "page": labelled[i]["page"], "text": labelled[i]["text"],
               "note": labelled[i].get("note", "")} for i in positives if i not in hit]
    tp_gold, n_pos = len(positives) - len(missed), len(positives)
    n_pred = len(tp_preds) + len(fp_preds)
    return {
        "mode": "full" if has_negatives else "positives_only",
        "pages_scored": len(scope), "pages_incomplete": [f"{s} p{p}" for s, p in incomplete],
        "gold_rows": len(labelled), "gold_requirements": n_pos,
        "gold_not_requirements": sum(1 for g in labelled if g.get("label", "yes") == "no"),
        "gold_unclear": sum(1 for g in labelled if g.get("label", "yes") == "skip"),
        "predictions": len(preds), "predictions_scored": n_pred, "predictions_ignored": ignored,
        "true_positives": tp_gold,
        "recall": round(tp_gold / n_pos, 4) if n_pos else None, "recall_ci95": wilson(tp_gold, n_pos),
        "precision": round(len(tp_preds) / n_pred, 4) if n_pred else None,
        "precision_ci95": wilson(len(tp_preds), n_pred),
        "threshold": threshold, "missed": missed, "false_positives": fp_preds, "matched": tp_preds,
        "note": ("Rezultāts attiecas tikai uz šīm lapām; tā nav garantija citiem dokumentiem."
                 + ("" if has_negatives else " Etalonā nav 'Nē' rindu, tāpēc precision ir aptuvena.")),
    }


def run_eval(findings_json: Path, gold_path: Path, threshold: float, kind: str = "") -> dict:
    data = json.loads(findings_json.read_text(encoding="utf-8"))
    gold, _ = read_gold(gold_path)
    return evaluate(data["findings"], gold, threshold, kind)


def write_report_xlsx(res: dict, path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    from spectakeoff.excel import clean

    def pct(v):
        return "" if v is None else f"{v * 100:.1f}%"

    def ci(v):
        return "" if not v else f"{v[0] * 100:.1f}% – {v[1] * 100:.1f}%"

    wb = Workbook()
    s = wb.active
    s.title = "Kopsavilkums"
    rows = [("Rādītājs", "Vērtība"),
            ("Recall (cik no īstajām prasībām atrastas)", pct(res["recall"])),
            ("Recall 95% ticamības intervāls", ci(res["recall_ci95"])),
            ("Precision (cik no atrastajām ir pareizas)", pct(res["precision"])),
            ("Precision 95% ticamības intervāls", ci(res["precision_ci95"])),
            ("Novērtētās lapas", res["pages_scored"]),
            ("Nepabeigtas lapas (netiek vērtētas)", ", ".join(res["pages_incomplete"]) or "nav"),
            ("Īstās prasības etalonā", res["gold_requirements"]),
            ("Atrastas pareizi", res["true_positives"]),
            ("Palaistas garām", len(res["missed"])),
            ("Kļūdaini atrastas", len(res["false_positives"])),
            ("Neskaidras (?) rindas, nevērtētas", res["gold_unclear"]),
            ("Režīms", "pilns etalons" if res["mode"] == "full" else "tikai pozitīvie piemēri"),
            ("Piezīme", res["note"])]
    for r in rows:
        s.append(list(r))
    s.column_dimensions["A"].width = 46
    s.column_dimensions["B"].width = 80
    sheets = [("Palaistas garām", ["Fails", "Lapa", "Teksts", "Piezīme"],
               [[m["source"], m["page"], m["text"], m["note"]] for m in res["missed"]]),
              ("Kļūdaini atrastas", ["Fails", "Lapa", "Programmas atrastais", "Iemesls", "Etalona rinda", "Piezīme"],
               [[f["source"], f["page"], f["found"], f["why"], f["gold"], f["note"]] for f in res["false_positives"]]),
              ("Pareizi atrastas", ["Fails", "Lapa", "Programmas atrastais", "Etalona rinda"],
               [[m["source"], m["page"], m["found"], m["gold"]] for m in res["matched"]])]
    for title, head, data in sheets:
        ws = wb.create_sheet(title)
        ws.append(head)
        for r in data:
            ws.append([clean(v) for v in r])
        for col, w in zip("ABCDEF", (24, 7, 80, 24, 60, 30)):
            ws.column_dimensions[col].width = w
    for ws in wb.worksheets:
        ws.freeze_panes = "A2"
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="17365D")
        for row in ws.iter_rows(min_row=2):
            for c in row:
                if isinstance(c.value, str):
                    c.data_type = "s"
                c.alignment = Alignment(wrap_text=True, vertical="top")
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
