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
                     "elapsed_seconds": round(r.elapsed, 2), "error": r.error, "llm": r.llm} for r in results],
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
                  tables=a.tables, translate_to=a.translate or "", llm=a.llm, llm_model=a.llm_model,
                  llm_cache=Path(a.llm_cache).expanduser() if a.llm_cache else
                  Path.home() / ".cache" / "spectakeoff" / "llm_cache.json")
    if a.llm:
        from spectakeoff.keystore import load

        if not _have_sdk():
            return 2
        if not load():
            print("Kļūda: --llm vajag API atslēgu. Palaid vienreiz: spectakeoff key", file=sys.stderr)
            return 2
        print("NOTE: --llm sends candidate sentences (not whole pages) to the Anthropic API.", file=sys.stderr)
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


def _config_from(a: argparse.Namespace) -> Config:
    return Config(ocr=a.ocr, ocr_lang=a.ocr_lang, dpi=a.dpi, overlays=False)


def cmd_label(a: argparse.Namespace) -> int:
    from spectakeoff.labeling import build_label_workbook

    sources = [Path(s).expanduser().resolve() for s in a.inputs]
    missing = [str(s) for s in sources if not s.is_file()]
    if missing:
        print("Not found: " + ", ".join(missing), file=sys.stderr)
        return 2
    out = Path(a.out).expanduser().resolve()
    rep = build_label_workbook(sources, out, _config_from(a), a.sample, a.pages, a.seed, a.show_predictions)
    print(f"Etalona fails: {rep['output']}\n  lapas: {rep['pages']} (no {rep['eligible_pages']} ar tekstu) | "
          f"rindas atzīmēšanai: {rep['rows']}\n  Atzīmē kolonnu 'Prasība?' ar Jā/Nē, tad: spectakeoff eval {out.name}")
    return 0


def cmd_eval(a: argparse.Namespace) -> int:
    from spectakeoff.evaluate import evaluate, read_gold, write_report_xlsx

    if len(a.files) == 2:
        findings_path, gold_path = Path(a.files[0]), Path(a.files[1])
    elif len(a.files) == 1:
        findings_path, gold_path = None, Path(a.files[0])
    else:
        print("Usage: spectakeoff eval [FINDINGS.json] GOLD.xlsx|csv", file=sys.stderr)
        return 2
    try:
        gold, meta = read_gold(gold_path)
    except ValueError as exc:
        print(f"Etalona kļūda: {exc}", file=sys.stderr)
        return 2
    if findings_path is not None:
        findings = json.loads(findings_path.read_text(encoding="utf-8"))["findings"]
    else:   # re-run the tool on the documents recorded in the labelling workbook
        if not meta.get("sources"):
            print("Etalonā nav avota failu saraksta - norādi arī findings.json", file=sys.stderr)
            return 2
        import hashlib

        base = gold_path.resolve().parent
        results = []
        for src in meta["sources"]:
            p = Path(src["path"])
            if not p.is_file():
                p = base / src["name"]
            if not p.is_file():
                print(f"Nav atrasts avota fails {src['name']} (meklēts {src['path']} un {base})", file=sys.stderr)
                return 2
            if hashlib.sha256(p.read_bytes()).hexdigest() != src["sha256"]:
                print(f"BRĪDINĀJUMS: {p.name} atšķiras no faila, kuram veidots etalons", file=sys.stderr)
            print(f"SpecTakeoff {__version__} | {p.name}", flush=True)
            results.append(process_source(p, _config_from(a))[0])
        assign_ids(results)
        findings = [_finding_dict(f) for r in results for f in r.findings]
    res = evaluate(findings, gold, a.threshold, a.kind)
    xlsx = Path(a.xlsx) if a.xlsx else gold_path.with_name(gold_path.stem + "_eval.xlsx")
    write_report_xlsx(res, xlsx)
    if a.report:
        Path(a.report).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    def pct(v, ci):
        return "n/a" if v is None else f"{v * 100:.1f}% (95% CI {ci[0] * 100:.1f}–{ci[1] * 100:.1f}%)"

    print(f"Novērtētas lapas: {res['pages_scored']} | īstās prasības: {res['gold_requirements']} | "
          f"programmas atradumi: {res['predictions_scored']}")
    print(f"  Recall:    {pct(res['recall'], res['recall_ci95'])}")
    print(f"  Precision: {pct(res['precision'], res['precision_ci95'])}")
    if res["pages_incomplete"]:
        print(f"  Nepabeigtas lapas (nav vērtētas): {', '.join(res['pages_incomplete'])}")
    print(f"  Palaistas garām: {len(res['missed'])} | kļūdaini atrastas: {len(res['false_positives'])}")
    print(f"  Atskaite: {xlsx}")
    return 0


def _have_sdk() -> bool:
    """Check for the Anthropic SDK before any work, not after a long OCR run."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        print("Kļūda: --llm vajag Anthropic SDK. Instalē: pip install -e .[llm]", file=sys.stderr)
        return False
    return True


def cmd_key(a: argparse.Namespace) -> int:
    import getpass

    from spectakeoff import keystore

    if a.remove:
        print("Atslēga izdzēsta." if keystore.remove() else "Saglabātas atslēgas nav.")
        return 0
    if a.status:
        k = keystore.load()
        print(f"Atslēga ir iestatīta ({k[:14]}…)." if k else "Atslēga nav iestatīta. Palaid: spectakeoff key")
        return 0
    if not a.no_check and not _have_sdk():
        return 2
    print("Ielīmē API atslēgu no platform.claude.com → API Keys (teksts netiks rādīts) un spied Enter:")
    key = keystore.normalise(getpass.getpass(""))
    err = keystore.problem(key) or ("" if a.no_check else keystore.verify(key))
    if err:
        print(f"Kļūda: {err}", file=sys.stderr)
        return 1
    print(f"Atslēga strādā un ir saglabāta: {keystore.save(key)}")
    print("Tagad vari lietot: spectakeoff run fails.pdf --llm --llm-model claude-haiku-5-5")
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
    r.add_argument("--llm", action="store_true", help="extra recall pass with a Claude model; sends candidate "
                   "sentences to the Anthropic API (run `spectakeoff key` once, or set ANTHROPIC_API_KEY)")
    r.add_argument("--llm-model", default="", help="model id (default claude-opus-5-5; claude-haiku-5-5 is far cheaper)")
    r.add_argument("--llm-cache", help="answer cache file (default ~/.cache/spectakeoff/llm_cache.json)")
    r.add_argument("--continue-on-error", action="store_true")
    r.set_defaults(func=cmd_run)
    lb = sub.add_parser("label", help="create a gold-set workbook to label by hand (Jā/Nē)")
    lb.add_argument("inputs", nargs="+", help="PDF or image files")
    lb.add_argument("-o", "--out", default="etalons.xlsx", help="workbook to create (default etalons.xlsx)")
    lb.add_argument("--sample", type=int, default=20, help="number of random pages (default 20)")
    lb.add_argument("--pages", default="", help="explicit pages instead of a sample, e.g. 3,7-9")
    lb.add_argument("--seed", type=int, default=1, help="random seed for the page sample")
    lb.add_argument("--show-predictions", action="store_true",
                    help="add a column with what the tool found (biases the labeller; off by default)")
    lb.set_defaults(func=cmd_label)
    e = sub.add_parser("eval", help="measure recall/precision against a labelled gold set")
    e.add_argument("files", nargs="+", metavar="FILE",
                   help="[FINDINGS.json] GOLD - GOLD is the labelled etalons.xlsx (or a CSV); without "
                        "FINDINGS the tool re-processes the documents recorded in the workbook")
    e.add_argument("--threshold", type=float, default=0.85, help="text similarity needed for a match")
    e.add_argument("--kind", default="", help="finding kind to score (default: requirement)")
    e.add_argument("--report", help="also write the full JSON result here")
    e.add_argument("--xlsx", help="report workbook (default: <gold>_eval.xlsx)")
    e.set_defaults(func=cmd_eval)
    k = sub.add_parser("key", help="save your Anthropic API key once for --llm")
    k.add_argument("--remove", action="store_true", help="delete the saved key")
    k.add_argument("--status", action="store_true", help="show whether a key is set")
    k.add_argument("--no-check", action="store_true", help="save without the 1-token test request")
    k.set_defaults(func=cmd_key)
    for sp in (lb, e):
        sp.add_argument("--no-ocr", dest="ocr", action="store_false")
        sp.add_argument("--ocr-lang", default="eng")
        sp.add_argument("--dpi", type=int, default=300)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("run", "eval", "label", "key", "-h", "--help", "--version"):
        argv.insert(0, "run")
    a = build_parser().parse_args(argv)
    if not getattr(a, "func", None):
        build_parser().print_help()
        return 2
    return a.func(a)
