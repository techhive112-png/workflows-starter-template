"""Precision benchmarks on public specifications.

    python benchmarks/run_benchmarks.py [--cache DIR]

Downloads the public PDFs (FAA, WBDG/UFGS) into a cache directory, runs
SpecTakeoff and compares the extracted requirement rows with the labelled
CSV files in this folder. Labels: true_positive / false_positive / borderline
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
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    report = {}
    for labels, files in SETS.items():
        paths = []
        for name, url in files.items():
            p = cache / name
            if not p.exists():
                print(f"Downloading {url}")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                p.write_bytes(urllib.request.urlopen(req, timeout=120).read())
            paths.append(str(p))
        out = cache / (Path(labels).stem + ".xlsx")
        if cli(paths + ["-o", str(out), "--no-overlays"]) != 0:
            return 1
        found = json.loads(out.with_suffix(".findings.json").read_text(encoding="utf-8"))["findings"]
        report[labels] = score(found, HERE / labels)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
