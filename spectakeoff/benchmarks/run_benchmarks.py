"""Precision benchmarks on public specifications.

    python benchmarks/run_benchmarks.py [--cache DIR] [--llm [--llm-model ID]]

Downloads the public PDFs (FAA, WBDG/UFGS) into a cache directory, runs
SpecTakeoff and compares the extracted requirement rows with the labelled
CSV files in this folder (precision of extracted rows), and with the fully
labelled page samples gold_*.xlsx (every sentence marked: recall + precision). Labels: true_positive / false_positive / borderline
(borderline is excluded from scores). Labels cover the rows that were
extracted plus misses found by reading submittal lists by hand; they are not
a full recall measurement of every page.
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


def llm_usage(out: Path) -> dict:
    """Sum the --llm token usage the run report records per source."""
    rep = json.loads(out.with_suffix(".run_report.json").read_text(encoding="utf-8"))
    total: Counter = Counter()
    for src in rep["sources"]:
        total.update({k: v for k, v in src.get("llm", {}).items() if isinstance(v, int)})
    return dict(total)


def main() -> int:
    from spectakeoff.cli import main as cli

    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "spectakeoff_bench"))
    ap.add_argument("--llm", action="store_true", help="also run the LLM recall pass (needs an API key; costs money)")
    ap.add_argument("--llm-model", default="", help="model id passed to spectakeoff --llm-model")
    a = ap.parse_args()
    if a.llm:
        from spectakeoff.keystore import load

        if not load():   # fail before downloading anything
            print("--llm needs ANTHROPIC_API_KEY or a key saved with `spectakeoff key`")
            return 2
    extra = ["--no-overlays"] + (["--llm"] + (["--llm-model", a.llm_model] if a.llm_model else []) if a.llm else [])
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    report = {}
    for labels, files in SETS.items():
        paths = [str(fetch(cache, name)) for name in files]
        out = cache / (Path(labels).stem + ".xlsx")
        if cli(paths + ["-o", str(out)] + extra) != 0:
            return 1
        found = json.loads(out.with_suffix(".findings.json").read_text(encoding="utf-8"))["findings"]
        report[labels] = score(found, HERE / labels)
        if a.llm:
            report[labels]["llm_usage"] = llm_usage(out)
    # fully labelled page samples (every sentence marked) -> recall AND precision
    from spectakeoff.evaluate import evaluate, read_gold

    for gold_path in sorted(HERE.glob("gold_*.xlsx")):
        gold, meta = read_gold(gold_path)
        paths = [str(fetch(cache, s["name"])) for s in meta["sources"]]
        out = cache / (gold_path.stem + ".xlsx")
        if cli(paths + ["-o", str(out)] + extra) != 0:
            return 1
        found = json.loads(out.with_suffix(".findings.json").read_text(encoding="utf-8"))["findings"]
        r = evaluate(found, gold)
        report[gold_path.name] = {k: r[k] for k in ("pages_scored", "gold_requirements", "true_positives",
                                                   "recall", "recall_ci95", "precision", "precision_ci95")}
        report[gold_path.name]["missed"] = [m["text"][:120] for m in r["missed"]]
        report[gold_path.name]["false_positives"] = [m["found"][:120] for m in r["false_positives"]]
        if a.llm:
            report[gold_path.name]["llm_usage"] = llm_usage(out)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
