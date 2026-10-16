"""Precision benchmarks on public specifications.

    python benchmarks/run_benchmarks.py [--cache DIR] [--report FILE]
    python benchmarks/run_benchmarks.py --llm [--llm-model ID] [--compare-md FILE]

Downloads the public PDFs (FAA, WBDG/UFGS) into a cache directory, runs
SpecTakeoff and compares the extracted requirement rows with the labelled
CSV files in this folder (precision of extracted rows), and with the fully
labelled page samples gold_*.xlsx (every sentence marked: recall + precision). Labels: true_positive / false_positive / borderline
(borderline is excluded from scores). Labels cover the rows that were
extracted plus misses found by reading submittal lists by hand; they are not
a full recall measurement of every page.

With --llm the whole benchmark runs twice, rules only and rules + language model
(outputs of the second run get an "_llm" suffix), and a side-by-side table is printed.
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
    model = ""
    for src in rep["sources"]:
        llm = src.get("llm") or {}
        total.update({k: v for k, v in llm.items() if isinstance(v, int)})
        model = llm.get("model") or model
    return {"model": model, **total} if model else dict(total)


def bench(cli, cache: Path, extra: list[str], suffix: str) -> dict | None:
    """One full benchmark pass; outputs get `suffix` so rules-only and --llm runs sit side by side."""
    from spectakeoff.evaluate import evaluate, read_gold

    report = {}

    def run(paths: list[str], stem: str) -> list[dict] | None:
        out = cache / (stem + suffix + ".xlsx")
        if cli(paths + ["-o", str(out), "--no-overlays"] + extra) != 0:
            return None
        if "--llm" in extra:
            report.setdefault("llm_usage", Counter()).update(
                {k: v for k, v in llm_usage(out).items() if isinstance(v, int)})
            report.setdefault("llm_model", llm_usage(out).get("model", ""))
        return json.loads(out.with_suffix(".findings.json").read_text(encoding="utf-8"))["findings"]

    for labels, files in SETS.items():
        found = run([str(fetch(cache, name)) for name in files], Path(labels).stem)
        if found is None:
            return None
        report[labels] = score(found, HERE / labels)
    # fully labelled page samples (every sentence marked) -> recall AND precision
    for gold_path in sorted(HERE.glob("gold_*.xlsx")):
        gold, meta = read_gold(gold_path)
        found = run([str(fetch(cache, s["name"])) for s in meta["sources"]], gold_path.stem)
        if found is None:
            return None
        r = evaluate(found, gold)
        report[gold_path.name] = {k: r[k] for k in ("pages_scored", "gold_requirements", "true_positives",
                                                   "recall", "recall_ci95", "precision", "precision_ci95")}
        report[gold_path.name]["missed"] = [m["text"][:120] for m in r["missed"]]
        report[gold_path.name]["false_positives"] = [m["found"][:120] for m in r["false_positives"]]
    if "llm_usage" in report:
        report["llm_usage"] = dict(report["llm_usage"])
    return report


def pct(x: int, n: int) -> str:
    return f"{100 * x / n:.1f}%" if n else "–"


def comparison_md(rules: dict, llm: dict) -> str:
    """Side-by-side table: rules only vs rules + --llm, on the fully labelled gold pages."""
    rows, tot = [], Counter()
    for name in sorted(k for k in rules if k.startswith("gold_")):
        a, b = rules[name], llm[name]
        fa, fb = a["true_positives"] + len(a["false_positives"]), b["true_positives"] + len(b["false_positives"])
        tot.update({"gold": a["gold_requirements"], "tp_a": a["true_positives"], "tp_b": b["true_positives"],
                    "f_a": fa, "f_b": fb})
        rows.append(f"| {name[:-5]} | {a['gold_requirements']} | {a['true_positives']} → {b['true_positives']} | "
                    f"{len(a['false_positives'])} → {len(b['false_positives'])} |")
    use = llm.get("llm_usage", {})
    return "\n".join([
        f"Modelis: `{llm.get('llm_model') or '?'}`; tokeni: ievade {use.get('input_tokens', '?')}, "
        f"izvade {use.get('output_tokens', '?')}.",
        "",
        "| Etalons | Īstās prasības | Atrastas (noteikumi → +LLM) | Kļūdainas (noteikumi → +LLM) |",
        "|---|---|---|---|", *rows,
        f"| **Kopā** | {tot['gold']} | {tot['tp_a']} → {tot['tp_b']} | "
        f"{tot['f_a'] - tot['tp_a']} → {tot['f_b'] - tot['tp_b']} |",
        "",
        f"Recall: {pct(tot['tp_a'], tot['gold'])} → {pct(tot['tp_b'], tot['gold'])}; "
        f"precision: {pct(tot['tp_a'], tot['f_a'])} → {pct(tot['tp_b'], tot['f_b'])}.",
    ]) + "\n"


def main() -> int:
    from spectakeoff.cli import main as cli

    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "spectakeoff_bench"))
    ap.add_argument("--llm", action="store_true", help="run rules-only AND rules + LLM pass, and compare "
                                                       "(needs an API key; costs tokens)")
    ap.add_argument("--llm-model", default="", help="model id passed to spectakeoff --llm-model")
    ap.add_argument("--llm-cache", default="", help="answer cache passed to spectakeoff --llm-cache")
    ap.add_argument("--report", help="also write the JSON report to this file")
    ap.add_argument("--compare-md", help="with --llm: write the comparison table (Markdown) to this file")
    a = ap.parse_args()
    if a.llm:
        from spectakeoff.keystore import load

        if not load():   # fail before downloading anything
            print("--llm needs ANTHROPIC_API_KEY or a key saved with `spectakeoff key`")
            return 2
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    rules = bench(cli, cache, [], "")
    if rules is None:
        return 1
    report = rules
    if a.llm:
        extra = ["--llm"] + (["--llm-model", a.llm_model] if a.llm_model else []) + \
                (["--llm-cache", a.llm_cache] if a.llm_cache else [])
        llm = bench(cli, cache, extra, "_llm")
        if llm is None:
            return 1
        report = {"rules_only": rules, "with_llm": llm}
        table = comparison_md(rules, llm)
        print(table)
        if a.compare_md:
            Path(a.compare_md).write_text(table, encoding="utf-8")
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if a.report:
        Path(a.report).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
