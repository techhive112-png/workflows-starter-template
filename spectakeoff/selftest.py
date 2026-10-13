#!/usr/bin/env python3
"""
SpecTakeoff self-test - the quality gate. Run this after EVERY change to spectakeoff.py.

It does not trust spectakeoff.py's own agents: it re-reads the PDF itself and re-checks the
delivered rows against it. Nothing here can create or change a row; it only passes or fails.

  python selftest.py RCCD.pdf                     all universal checks
  python selftest.py RCCD.pdf -m ALL_IN_ONE.md    also checks the golden baseline in section 7
  python selftest.py *.pdf                        every spec in turn

CHECKS
  1 run     the run completes and ends with DONE, agent 4 verified, agent 7 English
  2 R4      every Qty is a number that appears in that row's own quote
  3 R2      every quote appears word for word in the raw text of its cited page
  4 R5      Qty is empty if and only if Type is "Quantity Not Specified"
  5 golden  the output reproduces section 7 of the .md exactly          (only with -m)
  6 repeat  two runs produce identical rows                             (parallel reader)
  7 time    the run finishes inside the 300 second limit
Exit code 0 only if every check passes.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TIME_LIMIT = 300
PASS, FAIL = "PASS", "FAIL"


def _load(path):
    from openpyxl import load_workbook
    wb = load_workbook(path)
    ws = wb["Closeout Schedule"]
    cols = [c.value for c in ws[2]]
    rows = [dict(zip(cols, r)) for r in ws.iter_rows(min_row=3, values_only=True)
            if any(v not in (None, "") for v in r)]
    return wb, rows


def _run(pdf, out):
    t0 = time.time()
    p = subprocess.run([sys.executable, os.path.join(HERE, "spectakeoff.py"), pdf, "-o", out],
                       capture_output=True, text=True)
    return p.stdout + p.stderr, time.time() - t0


BASELINE_RE = re.compile(r"^## \d+\.\s+(\S+)\s+regression baseline.*?$(.*?)(?=^## \d+\.|\Z)",
                         re.S | re.M)


def _golden(md_path, spec_name):
    """The rows of the baseline section for this spec, as
    (section, type, item, qty, unit, page, quote). None if the .md has no baseline for it."""
    md = open(md_path, encoding="utf-8").read()
    stem = re.sub(r"\.pdf$", "", os.path.basename(spec_name), flags=re.I).lower()
    m = next((x for x in BASELINE_RE.finditer(md) if x.group(1).lower() == stem), None)
    if not m:
        return None
    out = []
    for line in m.group(2).splitlines():
        if not line.startswith("| "):
            continue
        c = [x.strip().replace("\\|", "|") for x in line.strip().strip("|").split("|")]
        if len(c) < 8 or not c[0].isdigit():
            continue
        out.append(tuple(c[1:8]))
    return out


def check(pdf, md_path=None):
    import spectakeoff as st
    name = os.path.basename(pdf)
    out = os.path.join(HERE, re.sub(r"\.pdf$", "", name, flags=re.I) + "_selftest.xlsx")
    results = []

    log, secs = _run(pdf, out)
    ok = ("DONE" in log and "[agent 4 Delivery]" in log and "file re-opened and verified" in log
          and "[agent 7 Language]" in log and "is entirely English" in log and os.path.exists(out))
    results.append(("1 run", PASS if ok else FAIL,
                    f"{secs:.0f}s" if ok else "run did not deliver a file:\n" + log[-600:]))
    if not ok:
        return results, None

    wb, rows = _load(out)

    # 2 R4 - the quantity must be readable from the quote itself
    bad = []
    for i, r in enumerate(rows, 1):
        if r["Qty"] in (None, ""):
            continue
        q = st.norm(r["Spec Language (verbatim)"])
        found = {(a, b) for a, b, _ in st.quantities(q)}
        per_unit = r["Qty"] == 1 and r["Unit"] == "EA" and re.search(r"for each", q, re.I)
        words = re.search(r"duplicate|triplicate", q, re.I)
        if (r["Qty"], r["Unit"]) not in found and not per_unit and not words:
            bad.append(f"row {i} {r['Spec Section']} p.{r['Page']}: Qty {r['Qty']} {r['Unit']} "
                       f"not in quote (quote gives {sorted(found) or 'no number'})")
    results.append(("2 R4 qty from quote", PASS if not bad else FAIL,
                    f"{len(rows)} rows, 0 violations" if not bad else "\n".join("  " + b for b in bad)))

    # 3 R2 - the quote must be word for word on the cited page
    pages = st.read_pages(pdf)
    raw = [st.norm(" ".join(l for l in p.splitlines() if len(l.strip()) > 3)) for p in pages]
    furniture = st.furniture_lines(pages)
    per = {}
    for no, t in st.body_lines(pages, furniture):
        per.setdefault(no, []).append(t)
    body = [st.norm(" ".join(per.get(i, []))) for i in range(1, len(pages) + 1)]
    miss, footer = [], []
    for i, r in enumerate(rows, 1):
        pg, q = r["Page"], st.norm(r["Spec Language (verbatim)"])
        win = lambda ts: ts[pg - 1] + " " + (ts[pg] if pg < len(ts) else "")
        if q in win(raw):
            continue
        (footer if q in win(body) else miss).append(f"row {i} p.{pg}: {q[:70]}")
    note = f"{len(rows)} quotes verbatim"
    if footer:
        note += f"; {len(footer)} match only with the page header/footer removed (bounded R2 case):\n" \
                + "\n".join("  " + f for f in footer)
    results.append(("3 R2 verbatim on page", PASS if not miss else FAIL,
                    note if not miss else "\n".join("  " + x for x in miss)))

    # 4 R5 - empty Qty if and only if "Quantity Not Specified"
    bad = [f"row {i}: Type '{r['Type']}' with Qty {r['Qty']!r}" for i, r in enumerate(rows, 1)
           if (r["Qty"] in (None, "")) != (r["Type"] == "Quantity Not Specified")]
    results.append(("4 R5 empty qty rule", PASS if not bad else FAIL,
                    "consistent" if not bad else "\n".join("  " + b for b in bad)))

    # 5 golden baseline
    if md_path:
        want = _golden(md_path, pdf)
        if want is None:
            results.append(("5 golden baseline", "SKIP",
                            "the .md has no baseline section for this spec yet - create one with "
                            "`package.py --baseline %s`" % os.path.basename(pdf)))
        else:
            # a markdown table cell cannot carry leading or trailing spaces, so both sides are stripped
            got = [tuple(x.strip() for x in (
                    str(r["Spec Section"] or ""), str(r["Type"] or ""), str(r["Item Required"] or ""),
                    "" if r["Qty"] in (None, "") else str(r["Qty"]), str(r["Unit"] or ""),
                    str(r["Page"] or ""), str(r["Spec Language (verbatim)"] or ""))) for r in rows]
            want = [tuple(x.strip() for x in w) for w in want]
            if got == want:
                results.append(("5 golden baseline", PASS, f"reproduces its baseline in the .md exactly ({len(want)} rows)"))
            else:
                d = [f"{len(want)} rows in the baseline, {len(got)} in the run"]
                for i, (a, b) in enumerate(zip(want, got), 1):
                    if a != b:
                        d.append(f"  row {i} differs: baseline {a[:4]} / run {b[:4]}")
                results.append(("5 golden baseline", FAIL, "\n".join(d[:12])))

    # 6 determinism
    out2 = out.replace("_selftest", "_selftest2")
    _run(pdf, out2)
    same = os.path.exists(out2) and [tuple(str(v) for v in r.values()) for r in _load(out2)[1]] == \
        [tuple(str(v) for v in r.values()) for r in rows]
    results.append(("6 two runs identical", PASS if same else FAIL,
                    "identical" if same else "the two runs disagree - the parallel reader is not deterministic"))
    if os.path.exists(out2):
        os.remove(out2)

    # 7 time
    results.append(("7 under %ds" % TIME_LIMIT, PASS if secs < TIME_LIMIT else FAIL,
                    f"{secs:.0f}s, {TIME_LIMIT - secs:.0f}s to spare"))
    return results, out


def main():
    ap = argparse.ArgumentParser(description="SpecTakeoff self-test")
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("-m", "--md", help="SPECTAKEOFF_ALL_IN_ONE.md, to check section 7 as the golden baseline")
    a = ap.parse_args()
    sys.path.insert(0, HERE)
    code = open(os.path.join(HERE, "spectakeoff.py"), "rb").read()
    print(f"spectakeoff.py  {len(code.decode().splitlines())} lines  md5 {hashlib.md5(code).hexdigest()[:10]}")
    worst = 0
    for pdf in a.pdfs:
        print(f"\n=== {os.path.basename(pdf)} ===")
        results, _ = check(pdf, a.md)
        for label, verdict, detail in results:
            print(f"[{verdict}] {label:24s} {detail if chr(10) not in detail else ''}")
            if chr(10) in detail:
                print(detail)
            if verdict == FAIL:
                worst = 1
        print("ALL CHECKS PASSED" if not worst else "SELF-TEST FAILED")
    sys.exit(worst)


if __name__ == "__main__":
    main()
