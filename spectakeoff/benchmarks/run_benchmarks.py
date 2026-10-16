"""Precision benchmarks on public specifications.

    python benchmarks/run_benchmarks.py [--cache DIR] [--llm [--llm-model ID]]

Downloads the public PDFs (FAA, WBDG/UFGS) into a cache directory, runs
SpecTakeoff and compares the extracted requirement rows with the labelled
CSV files in this folder (precision of extracted rows), and with the fully
labelled page samples gold_*.xlsx (every sentence marked: recall + precision). Labels: true_positive / false_positive / borderline
(borderline is excluded from scores). Labels cover the rows that were
extracted plus misses found by reading submittal lists by hand; they are not
a full recall measurement of every page.

With --llm every run adds the language-model recall pass; outputs get an "_llm" suffix so
they sit next to the rules-only ones, and the report adds the token usage under "llm_usage".
"""
from __future__ import annotations

import argparse
import csv
import json
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
UFGS = "https://www.wbdg.org/FFC/DOD/UFGS/UFGS%20{}.pdf"
SETS = {
    "faa_150-5370-10H_requirement_labels.csv": {
        "150-5370-10H.pdf": "https://www.faa.gov/documentLibrary/media/Advisory_Circular/150-5370-10H.pdf"},
    "ufgs_requirement_labels.csv": {
        f"UFGS_{n.replace(' ', '_')}.pdf": UFGS.format(n.replace(" ", "%20"))
        for n in ("01 78 00", "23 05 93", "26 20 00")},
    "ufgs_heldout_requirement_labels.csv": {
        f"UFGS_{n.replace(' ', '_')}.pdf": UFGS.format(n.replace(" ", "%20")) for n in ("22 00 00", "08 71 00")},
}


def url_for(name: str) -> str:
    if name == "150-5370-10H.pdf":
        return SETS["faa_150-5370-10H_requirement_labels.csv"][name]
    if name.startswith("UFGS_"):
        return UFGS.format(name[5:-4].replace("_", "%20"))
    raise ValueError(f"no download URL known for {name}")


def fetch(cache: Path, name: str) -> Path:
    p = cache / name
    if not p.exists():
        url = url_for(name)
        print(f"Downloading {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        p.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    return p


def score(findings: list[dict], labels_csv: Path) -> dict:
    labels = {(r["source"], int(r["page"]), r["text"]): r["label"]
              for r in csv.DictReader(open(labels_csv, encoding="utf-8", newline=""))}
    got = {(f["source_file"], f["page"], f["text"]) for f in findings if f["kind"] == "requirement"}
    kept = Counter(labels[k] for k in got if k in labels)
    total = Counter(labels.values())
    tp, fp = kept["true_positive"], kept["false_positive"]
    return {"rows": len(got), "true_positives_found": f"{tp}/{total['true_positive']}",
            "false_positives_left": f"{fp}/{total['false_positive']}", "borderline": kept["borderline"],
            "unlabelled_rows": len(got - set(labels)),
            "precision_on_labelled": round(tp / (tp + fp), 4) if tp + fp else None}


def main() -> int:
    from spectakeoff.cli import main as cli

    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "spectakeoff_bench"))
    ap.add_argument("--llm", action="store_true", help="add the language-model pass (needs an API key, costs tokens)")
    ap.add_argument("--llm-model", default="", help="model id passed to spectakeoff --llm-model")
    ap.add_argument("--llm-cache", default="", help="answer cache passed to spectakeoff --llm-cache")
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    extra, suffix = ["--no-overlays"], ""
    if a.llm:
        extra += ["--llm"] + (["--llm-model", a.llm_model] if a.llm_model else []) + \
                 (["--llm-cache", a.llm_cache] if a.llm_cache else [])
        suffix = "_llm"
    report, usage = {}, Counter()

    def run(paths: list[str], stem: str) -> Path | None:
        out = cache / (stem + suffix + ".xlsx")
        if cli(paths + ["-o", str(out)] + extra) != 0:
            return None
        for src in json.loads(out.with_suffix(".run_report.json").read_text(encoding="utf-8"))["sources"]:
            llm = src.get("llm") or {}
            usage.update({k: v for k, v in llm.items() if isinstance(v, int)})
            if llm.get("model"):
                report.setdefault("llm_usage", {})["model"] = llm["model"]
        return out

    for labels, files in SETS.items():
        paths = [str(fetch(cache, name)) for name in files]
        out = run(paths, Path(labels).stem)
        if out is None:
            return 1
        found = json.loads(out.with_suffix(".findings.json").read_text(encoding="utf-8"))["findings"]
        report[labels] = score(found, HERE / labels)
    # fully labelled page samples (every sentence marked) -> recall AND precision
    from spectakeoff.evaluate import evaluate, read_gold

    for gold_path in sorted(HERE.glob("gold_*.xlsx")):
        gold, meta = read_gold(gold_path)
        paths = [str(fetch(cache, s["name"])) for s in meta["sources"]]
        out = run(paths, gold_path.stem)
        if out is None:
            return 1
        found = json.loads(out.with_suffix(".findings.json").read_text(encoding="utf-8"))["findings"]
        r = evaluate(found, gold)
        report[gold_path.name] = {k: r[k] for k in ("pages_scored", "gold_requirements", "true_positives",
                                                   "recall", "recall_ci95", "precision", "precision_ci95")}
        report[gold_path.name]["missed"] = [m["text"][:120] for m in r["missed"]]
        report[gold_path.name]["false_positives"] = [m["found"][:120] for m in r["false_positives"]]
    if a.llm:
        report.setdefault("llm_usage", {}).update(usage)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
