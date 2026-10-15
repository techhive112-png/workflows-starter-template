"""Command line: `spectakeoff run ...` (default) and `spectakeoff eval ...`."""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
import traceback
from pathlib import Path

from spectakeoff import __version__
from spectakeoff.analysis import calculation_rows, coverage_rows, flag_conflicts, load_counts
from spectakeoff.i18n import SUPPORTED
from spectakeoff.models import SourceResult
from spectakeoff.pipeline import IMAGE_SUFFIXES, Config, assign_ids, process_source


def _finding_dict(f) -> dict:
    d = dataclasses.asdict(f)
    d["bbox"] = str(f.bbox) if f.bbox else ""
    return d


def write_outputs(out: Path, results: list[SourceResult], hits: dict[str, int], cfg: Config,
                  counts_path: Path | None, lang: str, argv_meta: dict) -> dict:
    from spectakeoff.excel import build_workbook

    findings = [f for r in results for f in r.findings]
    conflicts = flag_conflicts(findings)
    calc = calculation_rows(findings, load_counts(counts_path))
    cov = coverage_rows(results, hits)
    meta = {"version": __version__, "arguments": argv_meta}
    report = build_workbook(out, results, calc, cov, meta, lang)
    findings_path = out.with_suffix(".findings.json")
    findings_path.write_text(json.dumps({"version": __version__, "findings": [_finding_dict(f) for f in findings]},
                                        ensure_ascii=False, indent=1), encoding="utf-8")
    report.update({
        "findings_json": str(findings_path),
        "sources": [{"source": r.source, "sha256": r.sha256, "pages": len(r.pages), "findings": len(r.findings),
                     "pages_review": sum(1 for p in r.pages if p.status == "REVIEW"),
                     "elapsed_seconds": round(r.elapsed, 2), "error": r.error} for r in results],
        "conflicts_flagged": conflicts, "calculation_rows": len(calc),
        "status": "Excel integrity validation passed; content accuracy not certified",
    })
    out.with_suffix(".run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                                   encoding="utf-8")
    return report


def cmd_run(a: argparse.Namespace) -> int:
    sources = [Path(s).expanduser().resolve() for s in a.inputs]
    missing = [str(s) for s in sources if not s.is_file()]
    if missing:
        print("Not found: " + ", ".join(missing), file=sys.stderr)
        return 2
    bad = [s.name for s in sources if s.suffix.lower() != ".pdf" and s.suffix.lower() not in IMAGE_SUFFIXES]
    if bad:
        print("Unsupported file type: " + ", ".join(bad), file=sys.stderr)
        return 2
    if a.translate:
        try:
            import deep_translator  # noqa: F401
        except ImportError:
            print("--translate needs: pip install deep-translator", file=sys.stderr)
            return 2
    rotations = tuple(int(x) for x in a.rotations.split(",") if x.strip())
    if any(r not in (0, 90) for r in rotations):
        print("--rotations accepts 0 and/or 90", file=sys.stderr)
        return 2
    base = Config(ocr=a.ocr, ocr_lang=a.ocr_lang, ocr_min_chars=a.ocr_min_chars, page_ocr_min_conf=a.page_min_conf,
                  word_min_conf=a.word_min_conf, dpi=a.dpi, rotations=rotations, overlays=a.overlays,
                  tables=a.tables, translate_to=a.translate or "")
    meta = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items() if k != "func"}
    if a.out:   # one combined workbook: cross-file conflicts and calculations
        groups = [(Path(a.out).expanduser().resolve(), sources)]
    else:
        out_dir = Path(a.out_dir).expanduser().resolve() if a.out_dir else None
        groups = [((out_dir or s.parent) / f"{s.stem}_SpecTakeoff_v4.xlsx", [s]) for s in sources]
    if len({g[0] for g in groups}) != len(groups):
        print("Output path collision; use --out-dir or -o", file=sys.stderr)
        return 2
    failures, start = 0, time.time()
    for out, srcs in groups:
        cfg = dataclasses.replace(base, overlay_dir=out.with_name(out.stem + "_review"))
        results, hits = [], {}
        for s in srcs:
            print(f"SpecTakeoff {__version__} | {s.name}", flush=True)
            try:
                r, h = process_source(s, cfg)
                for k, v in h.items():
                    hits[k] = hits.get(k, 0) + v
            except Exception as exc:
                traceback.print_exc()
                r = SourceResult(source=s.name, sha256="", error=f"{type(exc).__name__}: {exc}")
                failures += 1
                if not a.continue_on_error:
                    results.append(r)
                    break
            results.append(r)
            print(f"  pages: {len(r.pages)} | findings: {len(r.findings)} | "
                  f"pages to review: {sum(1 for p in r.pages if p.status == 'REVIEW')} | {r.elapsed:.1f}s", flush=True)
        assign_ids(results)
        try:
            rep = write_outputs(out, results, hits, cfg, Path(a.counts) if a.counts else None, a.lang, meta)
        except Exception:
            traceback.print_exc()
            failures += 1
            if not a.continue_on_error:
                break
            continue
        print(f"  Excel: {rep['output']} ({rep['validated_cells']} cells validated)\n  {rep['status']}")
        if failures and not a.continue_on_error:
            break
    print(f"Done in {time.time() - start:.1f}s, {failures} failure(s).")
    return 1 if failures else 0


def cmd_eval(a: argparse.Namespace) -> int:
    from spectakeoff.evaluate import run_eval

    res = run_eval(Path(a.findings), Path(a.gold), a.threshold)
    if a.report:
        Path(a.report).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"gold {res['gold_items']} | predictions in scope {res['predictions_in_scope']} | "
          f"recall {res['recall']} | precision {res['precision']}")
    for m in res["missed"]:
        print(f"  MISSED: {m['gold']!r} (best similarity {m['best_similarity']})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spectakeoff", description="SpecTakeoff 4.0 — auditable spec, drawing and "
                                "image takeoff. Nothing is certified; every row needs human review.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("run", help="process PDFs and images")
    r.add_argument("inputs", nargs="+", help="PDF or image files (png, jpg, tif, webp, bmp)")
    r.add_argument("-o", "--out", help="one combined workbook for all inputs")
    r.add_argument("--out-dir", help="directory for per-input workbooks (default: next to each input)")
    r.add_argument("--lang", choices=SUPPORTED, default="en", help="workbook language (evidence is never translated)")
    r.add_argument("--no-ocr", dest="ocr", action="store_false")
    r.add_argument("--ocr-lang", default="eng", help="Tesseract languages joined by +, e.g. eng+lav")
    r.add_argument("--ocr-min-chars", type=int, default=80, help="OCR PDF pages with less embedded text")
    r.add_argument("--page-min-conf", type=float, default=75.0, help="page OCR confidence that triggers review")
    r.add_argument("--word-min-conf", type=float, default=60.0, help="drawing OCR word confidence floor")
    r.add_argument("--dpi", type=int, default=300, choices=range(100, 601), metavar="100-600")
    r.add_argument("--rotations", default="0,90", help="drawing text orientations to scan: 0, 90 or 0,90")
    r.add_argument("--no-overlays", dest="overlays", action="store_false", help="skip annotated review images")
    r.add_argument("--no-tables", dest="tables", action="store_false", help="skip schedule/table detection")
    r.add_argument("--counts", help="estimator CSV item,count,verified_by[,source] for R8 calculations")
    r.add_argument("--translate", metavar="LANG", help="best-effort online translation of requirements "
                   "(sends text to a third party)")
    r.add_argument("--continue-on-error", action="store_true")
    r.set_defaults(func=cmd_run)
    e = sub.add_parser("eval", help="score a run against a human-checked gold CSV")
    e.add_argument("findings", help="<output>.findings.json from a run")
    e.add_argument("gold", help="CSV with columns source,page,kind,text")
    e.add_argument("--threshold", type=float, default=0.85, help="text similarity needed for a match")
    e.add_argument("--report", help="write full JSON report here")
    e.set_defaults(func=cmd_eval)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("run", "eval", "-h", "--help", "--version"):
        argv.insert(0, "run")
    a = build_parser().parse_args(argv)
    if not getattr(a, "func", None):
        build_parser().print_help()
        return 2
    return a.func(a)
