#!/usr/bin/env python3
"""
SpecTakeoff - closeout requirements extractor for US construction specifications
(CSI MasterFormat project manuals, with full Division 23 HVAC and Division 26 Electrical coverage).

ONE FILE. Everything is in here: extraction, 8 check agents, Excel output.

WHAT IT DOES
  Reads a project manual PDF and writes an Excel schedule of everything the contractor must hand
  over or provide to the Owner: attic stock, spare parts, special tools, O&M deliverables,
  training, warranties and maintenance service contracts. Every row cites the spec section and
  PDF page and quotes the spec word for word.

HOW TO RUN
  Google Colab:  upload this file and the spec PDF to /content, then run a cell with
                     !python /content/spectakeoff.py
                 (it installs what it needs, finds every PDF in /content and writes
                  <pdf name>_Closeout_Schedule.xlsx next to it)
  Computer:      python spectakeoff.py spec.pdf -o result.xlsx
  With drawings: python spectakeoff.py spec.pdf --drawings M-drawings.pdf E-drawings.pdf
  With counts:   python spectakeoff.py spec.pdf --counts counts.csv
                 (counts.csv columns: Spec Section,Match,Count,Source
                  e.g.  26 28 13,fuse,12,E-601 panel schedules)

THE 8 AGENTS (deterministic code, not AI - they cannot invent data)
  1 Precision  quote is word-for-word on the cited page; section exists and matches the page;
               quantity and unit are read from the quote itself
  2 Quality    duplicates, padding, conflicts (e.g. monthly vs every 2 months), pages to review
  3 Labor      hours / days / persons / visits only from the spec text; missing = "Needs input"
  4 Delivery   re-opens the finished Excel and compares every cell; on any difference the file
               is deleted and NOT delivered
  5 OCR        reads scanned pages with Tesseract; rows from pages under 75% confidence removed
  6 Drawings   equipment tags and schedules from drawings (or an estimator counts file)
               multiply per-unit quantities; "each type and size" only from schedule columns
  7 Language   the delivered file is entirely English; quotes are never translated
  8 Div 23/26  every Division 23 (HVAC) and 26 (Electrical) section is listed with its closeout
               subsections and rows; sections with closeout text but no row are flagged CHECK

RULES FOR ANYONE (HUMAN OR AI) CHANGING THIS FILE
  - Never write output rows by hand or from general knowledge. Output comes only from running this file.
  - There is no target row count. Never pad, repeat or invent rows.
  - Never remove or weaken a check, never add a bypass.
  - An invented row is worse than a missing row.
  The full rule list (R1-R16) is printed on the "Rules" sheet of every Excel file.
"""
import importlib.util
import subprocess
import sys


def _ensure_packages():
    need = [("pdfplumber", "pdfplumber"), ("openpyxl", "openpyxl"), ("pypdfium2", "pypdfium2")]
    missing = [pkg for mod, pkg in need if importlib.util.find_spec(mod) is None]
    if missing:
        print("Installing:", " ".join(missing))
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *missing])


_ensure_packages()

import re  # noqa: E402
from collections import Counter, OrderedDict, defaultdict  # noqa: E402

import pdfplumber  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402

# ===========================================================================
# PART A - CHECK AGENTS
# ===========================================================================

STRICT_RULES = [
    "R1  Every row comes from the PDF text. Nothing is generated, guessed or taken from general knowledge.",
    "R2  'Spec Language (verbatim)' must appear word-for-word on the cited page (or run onto the next "
    "page). A sentence interrupted by the page header/footer is matched against the same page text "
    "with that page furniture removed - never against anything outside the cited pages.",
    "R3  The cited Spec Section must exist in the document and must be the section printed on that page.",
    "R4  Qty and Unit must be read from the quote itself. A number that is not in the quote is an error.",
    "R5  Qty is empty only for 'Quantity Not Specified', and that type always has an empty Qty.",
    "R6  No duplicate rows and no repeated quotes beyond the distinct items they contain (no padding).",
    "R7  There is no target row count. The document decides how many rows there are.",
    "R8  Quantities stated 'for each / per / of each' are NOT multiplied - the equipment count must come "
    "from the drawings or schedules and is flagged for the estimator.",
    "R9  Labor hours are only calculated from hours, days, persons and visits stated in the quote. "
    "Missing factors are shown as 'Needs input', never assumed.",
    "R10 Conflicting requirements for the same item are flagged on both rows, never silently resolved.",
    "R11 Pages that mention closeout items but produced no row, and pages without readable text, "
    "are listed for manual review.",
    "R12 The Excel file is re-opened and checked against the verified data. If any check fails, "
    "the file is not delivered.",
    "R13 Scanned pages are read by OCR and every row from them is marked. Rows from pages with OCR "
    "confidence below 75% are removed and the page is listed for manual review.",
    "R14 Per-unit quantities are totalled only from equipment tags/schedules found on the drawings or from "
    "an estimator's counts file, and the source of every count is written next to the total. "
    "'Each type and size' is counted only from schedule columns (model/size/HP), never assumed.",
    "R15 The delivered file is entirely in English. Spec quotes are the original English text and are never "
    "translated or reworded. Any non-English text blocks delivery.",
    "R16 Every HVAC and Electrical section in the document (Divisions 23 and 26 in MasterFormat 2004, "
    "Divisions 15 and 16 in CSI 1995) is listed with its closeout "
    "subsections and row count. A section with closeout text but no extracted row is flagged CHECK; "
    "MasterFormat 2004 section numbers outside the Division 23/26 structure are flagged; a CSI 1995 "
    "five-digit number is listed but has no equivalent structure to be checked against.",
]

ALLOWED_TYPES = {"Attic Stock", "Spare Part", "Special Tool", "O&M Deliverable", "Training",
                 "Extended Warranty", "Maintenance Service", "Quantity Not Specified"}
ALLOWED_UNITS = {"YR", "HR", "DAY", "MO", "SF", "BOX", "GAL", "SET", "EA", "PCT", ""}
COLUMNS = ["Spec Section", "Section Title", "Type", "Item Required", "Qty", "Unit", "Basis", "Page",
           "Spec Language (verbatim)"]


def _n(text):
    return re.sub(r"\s+", " ", (text or "").replace("’", "'")).strip()


def _key(text):
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


class Finding:
    def __init__(self, agent, level, row_id, message):
        self.agent, self.level, self.row_id, self.message = agent, level, row_id, message

    def as_list(self):
        return [self.agent, self.level, self.row_id if self.row_id is not None else "-", self.message]


# ---------------------------------------------------------------------------
class PrecisionAgent:
    """Agent 1: numbers, quotes, pages, sections, drawing-dependent quantities."""
    name = "1 Precision"

    def __init__(self, page_text, sec_of_page, known_sections, quantities_fn, body_text=None):
        self.page_text, self.sec_of_page = page_text, sec_of_page
        self.known_sections, self.quantities = known_sections, quantities_fn
        self.body_text = body_text or page_text

    def run(self, rows):
        out = []
        for r in rows:
            rid, quote, page = r["_id"], _n(r["Spec Language (verbatim)"]), r["Page"]
            # R2 verbatim quote on page
            if not isinstance(page, int) or not 1 <= page <= len(self.page_text):
                out.append(Finding(self.name, "ERROR", rid, f"R2 page {page} is outside the PDF"))
                continue
            def pair(texts):
                return texts[page - 1] + " " + (texts[page] if page < len(texts) else "")
            # the quote must be on the page word-for-word; a sentence interrupted by the page
            # header/footer is matched against the same page with that furniture removed
            if not quote or (quote not in pair(self.page_text) and quote not in pair(self.body_text)):
                out.append(Finding(self.name, "ERROR", rid, f"R2 quote not found on page {page}"))
            # R3 section exists and matches the page
            sec = r["Spec Section"]
            if sec not in self.known_sections:
                out.append(Finding(self.name, "ERROR", rid, f"R3 section {sec} does not exist in the document"))
            elif self.sec_of_page[page - 1] != sec:
                out.append(Finding(self.name, "ERROR", rid,
                                   f"R3 page {page} belongs to section {self.sec_of_page[page - 1]}, not {sec}"))
            # R4 / R5 numbers
            qty, unit, kind = r["Qty"], r["Unit"], r["Type"]
            if unit not in ALLOWED_UNITS:
                out.append(Finding(self.name, "ERROR", rid, f"R4 unknown unit '{unit}'"))
            if kind == "Quantity Not Specified":
                if qty not in (None, ""):
                    out.append(Finding(self.name, "ERROR", rid, "R5 'Quantity Not Specified' row has a Qty"))
            else:
                if qty in (None, ""):
                    out.append(Finding(self.name, "ERROR", rid, "R5 Qty is empty but type is not 'Quantity Not Specified'"))
                else:
                    found = {(q, u) for q, u, _ in self.quantities(quote)}
                    if (qty, unit) not in found and not (qty == 1 and unit == "EA" and re.search(r"for each", quote, re.I)):
                        out.append(Finding(self.name, "ERROR", rid,
                                           f"R4 Qty {qty} {unit} cannot be read from the quote (quote gives {sorted(found) or 'no number'})"))
            # R8 drawing-dependent totals
            if qty not in (None, "") and re.search(r"\b(for each|for every|of each|per(?! year| month| week))\b",
                                                   (r["Basis"] or "") + " " + quote, re.I) \
                    and unit not in ("YR", "HR", "DAY", "MO") and kind != "Training":
                out.append(Finding(self.name, "WARN", rid,
                                   "R8 quantity is per unit/size/type - total needs the count from drawings/equipment schedules"))
        return out


# ---------------------------------------------------------------------------
class QualityAgent:
    """Agent 2: duplicates, padding, conflicts, coverage and counts."""
    name = "2 Quality"

    def __init__(self, log, n_pages, empty_pages, blank_pages=0):
        self.log, self.n_pages, self.empty_pages, self.blank_pages = log, n_pages, empty_pages, blank_pages

    def run(self, rows):
        out = []
        seen = {}
        quote_use = defaultdict(list)
        for r in rows:
            rid = r["_id"]
            if r["Type"] not in ALLOWED_TYPES:
                out.append(Finding(self.name, "ERROR", rid, f"type '{r['Type']}' is not an allowed type"))
            for col in ("Spec Section", "Type", "Item Required", "Page", "Spec Language (verbatim)"):
                if r[col] in (None, ""):
                    out.append(Finding(self.name, "ERROR", rid, f"required column '{col}' is empty"))
            k = (r["Spec Section"], _key(r["Spec Language (verbatim)"]), _key(r["Item Required"]), r["Qty"], r["Unit"])
            if k in seen:
                out.append(Finding(self.name, "ERROR", rid, f"R6 duplicate of row {seen[k]}"))
            else:
                seen[k] = rid
            quote_use[(r["Spec Section"], _key(r["Spec Language (verbatim)"]))].append(r)
        # R6 padding: one quote used more often than it has distinct items
        for (_, _), group in quote_use.items():
            items = {_key(g["Item Required"]) for g in group}
            if len(group) > len(items):
                for g in group[len(items):]:
                    out.append(Finding(self.name, "ERROR", g["_id"], "R6 quote repeated without a distinct item (padding)"))
            if len(group) > 4:
                for g in group:
                    out.append(Finding(self.name, "WARN", g["_id"], f"same quote used {len(group)} times - check"))
        # R10 conflicts: same section, same service noun (visits / inspections / calls),
        # but a different number or frequency
        FREQ = r"(bi-?monthly|monthly|quarterly|weekly|annually|per year|every \d+ months|\w+ month interval)"
        groups = defaultdict(list)
        for r in rows:
            q = (r["Spec Language (verbatim)"] or "").lower()
            noun = re.search(r"\b(visits?|inspections?|service calls?)\b", q)
            if noun and "report" not in q:
                groups[(r["Spec Section"], noun.group(1).rstrip("s"))].append(r)
        for (sec, noun), group in groups.items():
            def sig(g):
                q = (g["Spec Language (verbatim)"] or "").lower()
                f = re.search(FREQ, q)
                return (f.group(1).replace("-", "") if f else "", g["Qty"])
            sigs = [sig(g) for g in group]
            freqs = {f for f, _ in sigs if f}
            qtys = {q for _, q in sigs if q not in (None, "")}
            if len(freqs) > 1 or len(qtys) > 1:
                for g in group:
                    others = ", ".join(f"p.{o['Page']}" for o in group if o is not g)
                    out.append(Finding(self.name, "WARN", g["_id"],
                                       f"R10 CONFLICT: {noun}s for this section are stated differently elsewhere ({others}) - raise an RFI"))
        # R11 coverage
        for page in self.empty_pages:
            out.append(Finding(self.name, "WARN", None, f"R11 page {page} has no readable text (scanned?) - needs OCR/manual review"))
        for entry in self.log:
            if entry[1].startswith("Review"):
                out.append(Finding(self.name, "WARN", None, f"R11 page {entry[0]}: closeout keywords but no row - review manually"))
        if self.blank_pages:
            out.append(Finding(self.name, "INFO", None, f"{self.blank_pages} intentionally blank pages skipped"))
        counts = Counter(r["Type"] for r in rows)
        out.append(Finding(self.name, "INFO", None,
                           f"{len(rows)} candidate rows from {self.n_pages} pages: " +
                           ", ".join(f"{t} {n}" for t, n in counts.most_common())))
        return out


# ---------------------------------------------------------------------------
class LaborAgent:
    """Agent 3: labor stated in the spec. Calculates only from stated numbers."""
    name = "3 Labor"
    WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
             "nine": 9, "ten": 10, "twelve": 12}

    def _num(self, s):
        s = s.lower()
        return int(s) if s.isdigit() else self.WORDS.get(s)

    def run(self, rows):
        findings, labor = [], []
        for r in rows:
            # a row whose Qty the spec never stated is still a labor obligation: it is priced
            # from the obligation behind it, and reported as "Needs input"
            if r.get("_obligation", r["Type"]) not in ("Training", "Maintenance Service"):
                continue
            q = _n(r["Spec Language (verbatim)"])
            if re.search(r"\bcop(y|ies)\b|\breports?\b", q, re.I) and r["Type"] == "Maintenance Service" \
                    and not re.search(r"inspect|visit|service and maintenance", q, re.I):
                continue
            persons = re.search(r"for (\d+|one|two|three|four|five|six|eight|ten) (?:persons?|people|attendees?)", q, re.I)
            hours = re.search(r"(\d+|one|two|three|four|five|six|eight|ten)\s*(?:\(\d+\)\s*)?hours?", q, re.I)
            days = re.search(r"(\d+|one|two|three|four|five|six|eight|ten)\s*(?:\(\d+\)\s*)?days?", q, re.I)
            visits = re.search(r"(\d+|one|two|three|four|five|six|eight|ten|twelve)\s*(?:\(\d+\)\s*)?(?:complete |normal |routine )*"
                               r"(inspections?|visits?|calls?)", q, re.I)
            freq = re.search(r"\b(bi-?monthly|monthly|quarterly|per year|three month interval)\b", q, re.I)
            period = re.search(r"for (\d+|one|two|three|\[\d\])\s*years?", q, re.I)
            row = {"Row": r["_id"], "Spec Section": r["Spec Section"], "Page": r["Page"], "Item": r["Item Required"],
                   "Labor Type": "Owner training" if r.get("_obligation", r["Type"]) == "Training"
                                 else "Post-completion service",
                   "Stated in spec": "", "Hours": None, "Status": "", "How": ""}
            stated = []
            h = self._num(hours.group(1)) if hours else None
            d = self._num(days.group(1)) if days else None
            p = self._num(persons.group(1)) if persons else None
            v = self._num(visits.group(1)) if visits else None
            if h is not None: stated.append(f"{h} h")
            if d is not None: stated.append(f"{d} day(s)")
            if p is not None: stated.append(f"{p} person(s)")
            if v is not None: stated.append(f"{v} {visits.group(2)}")
            if freq: stated.append(freq.group(1))
            if period: stated.append(f"{period.group(1).strip('[]')} year period")
            row["Stated in spec"] = "; ".join(stated) or "-"
            if v is not None and h is not None:
                row["Hours"], row["How"], row["Status"] = v * h, f"{v} x {h} h stated", "Computed from spec"
            elif h is not None:
                row["Hours"], row["How"], row["Status"] = h, "hours stated", "Computed from spec"
                if p is not None:
                    row["How"] += f" (instructor hours; {p} trainees = {h * p} trainee-hours)"
            elif d is not None:
                row["Status"] = "Needs input"
                row["How"] = f"{d} day(s) stated - hours per day not stated in spec"
            else:
                row["Status"] = "Needs input"
                row["How"] = "spec states the obligation but not the hours - estimator must price it"
            labor.append(row)
            if row["Status"] == "Needs input":
                findings.append(Finding(self.name, "WARN", r["_id"], f"R9 labor hours not stated: {row['How']}"))
        total = sum(x["Hours"] for x in labor if x["Hours"])
        findings.append(Finding(self.name, "INFO", None,
                                f"{len(labor)} labor items; {sum(1 for x in labor if x['Hours'])} computed from spec "
                                f"({total} h stated), {sum(1 for x in labor if not x['Hours'])} need estimator input"))
        return findings, labor


# ---------------------------------------------------------------------------
class DeliveryAgent:
    """Agent 4: re-opens the written Excel file and proves it is correct."""
    name = "4 Delivery"

    def run(self, path, rows, labor):
        from openpyxl import load_workbook
        out = []
        try:
            wb = load_workbook(path)
        except Exception as e:  # noqa: BLE001
            return [Finding(self.name, "ERROR", None, f"R12 Excel file cannot be opened: {e}")]
        need = ["Closeout Schedule", "Summary", "Labor", "Checks", "Rules"]  # noqa
        for s in need:
            if s not in wb.sheetnames:
                out.append(Finding(self.name, "ERROR", None, f"R12 sheet '{s}' missing"))
        if out:
            return out
        ws = wb["Closeout Schedule"]
        header = [c.value for c in ws[2]][:len(COLUMNS)]
        if header != COLUMNS:
            out.append(Finding(self.name, "ERROR", None, f"R12 header wrong: {header}"))
        data = [r for r in ws.iter_rows(min_row=3, values_only=True) if any(v not in (None, "") for v in r)]
        if len(data) != len(rows):
            out.append(Finding(self.name, "ERROR", None, f"R12 file has {len(data)} rows, verified data has {len(rows)}"))
        for i, (cells, r) in enumerate(zip(data, rows), 3):
            for j, col in enumerate(COLUMNS):
                want = r[col] if r[col] not in ("", None) else None
                got = cells[j] if cells[j] not in ("", None) else None
                if want != got:
                    out.append(Finding(self.name, "ERROR", r["_id"], f"R12 Excel row {i} column '{col}' differs from verified data"))
                    break
            if "ERROR" in str(cells[9] or ""):
                out.append(Finding(self.name, "ERROR", r["_id"], f"R12 Excel row {i} contains a row that failed checks"))
        summ = {a: b for a, b in wb["Summary"].iter_rows(min_row=2, values_only=True) if a and a != "Total"}
        if sum(v for v in summ.values() if isinstance(v, int)) != len(rows):
            out.append(Finding(self.name, "ERROR", None, "R12 Summary totals do not match the schedule"))
        lab = [r for r in wb["Labor"].iter_rows(min_row=2, values_only=True) if r[0] is not None]
        if len(lab) != len(labor):
            out.append(Finding(self.name, "ERROR", None, "R12 Labor sheet row count does not match"))
        for i, (cells, r) in enumerate(zip(data, rows), 3):
            for j, col in enumerate(("Unit Count", "Total Qty", "Count Source"), 11):
                want = r.get(col) if r.get(col) not in ("", None) else None
                got = cells[j] if len(cells) > j and cells[j] not in ("", None) else None
                if want != got:
                    out.append(Finding(self.name, "ERROR", r["_id"], f"R12 Excel row {i} column '{col}' differs"))
                    break
        if not out:
            out.append(Finding(self.name, "INFO", None, f"R12 file re-opened and matches verified data ({len(rows)} rows)"))
        return out


# ---------------------------------------------------------------------------
# Agent 5: OCR for scanned (image-only) pages
# ---------------------------------------------------------------------------

def _ocr_page(args):
    """Render one PDF page to an image and read it with Tesseract.
    Returns (page_index, text, mean_word_confidence)."""
    import os
    import subprocess
    import tempfile
    import pypdfium2 as pdfium
    pdf_path, idx, dpi = args
    doc = pdfium.PdfDocument(pdf_path)
    img = doc[idx].render(scale=dpi / 72).to_pil().convert("L")
    doc.close()
    fd, png = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        img.save(png)
        tsv = subprocess.run(["tesseract", png, "stdout", "--psm", "6", "tsv"],
                             capture_output=True, text=True, timeout=180,
                             env={**os.environ, "OMP_THREAD_LIMIT": "1"}).stdout   # one thread per worker
    finally:
        os.remove(png)
    lines, confs = {}, []
    for row in tsv.splitlines()[1:]:
        f = row.split("\t")
        if len(f) < 12 or not f[11].strip():
            continue
        conf = float(f[10])
        if conf < 0:
            continue
        confs.append(conf)
        key = (int(f[2]), int(f[3]), int(f[4]))           # block, paragraph, line
        lines.setdefault(key, []).append(f[11])
    text = "\n".join(" ".join(w) for _, w in sorted(lines.items()))
    return idx, text, (sum(confs) / len(confs)) if confs else 0.0


class OcrAgent:
    """Agent 5: reads image-only pages with Tesseract OCR.
    Text read by OCR is marked; rows from low-confidence pages are blocked."""
    name = "5 OCR"
    MIN_CONF = 75.0

    def __init__(self, dpi=300, workers=None):
        import os
        self.dpi, self.workers = dpi, workers or max(1, min(os.cpu_count() or 1, 8))

    @staticmethod
    def available():
        import os
        import shutil
        import subprocess
        if shutil.which("tesseract") is None and shutil.which("apt-get") and hasattr(os, "geteuid") and os.geteuid() == 0:
            subprocess.run(["apt-get", "install", "-y", "-qq", "tesseract-ocr"], capture_output=True)   # Colab / Linux
        return shutil.which("tesseract") is not None

    def run(self, pdf_path, page_indexes):
        """Returns ({page_no: text}, {page_no: confidence}, findings)."""
        findings, texts, confs = [], {}, {}
        if not page_indexes:
            return texts, confs, findings
        if not self.available():
            findings.append(Finding(self.name, "WARN", None,
                                    f"R13 Tesseract OCR is not installed - {len(page_indexes)} scanned pages NOT read: "
                                    + ", ".join(str(i + 1) for i in page_indexes)))
            return texts, confs, findings
        from multiprocessing import Pool
        jobs = [(pdf_path, i, self.dpi) for i in page_indexes]
        if self.workers > 1 and len(jobs) > 1:
            with Pool(self.workers) as pool:
                results = pool.map(_ocr_page, jobs)
        else:
            results = [_ocr_page(j) for j in jobs]
        for idx, text, conf in results:
            texts[idx + 1], confs[idx + 1] = text, conf
            level = "INFO" if conf >= self.MIN_CONF else "WARN"
            findings.append(Finding(self.name, level, None, f"R13 page {idx + 1} read by OCR, confidence {conf:.0f}%"))
        return texts, confs, findings

    def check_rows(self, rows, confs):
        out = []
        for r in rows:
            c = confs.get(r["Page"])
            if c is None:
                continue
            if c < self.MIN_CONF:
                out.append(Finding(self.name, "ERROR", r["_id"],
                                   f"R13 page {r['Page']} OCR confidence {c:.0f}% is below {self.MIN_CONF:.0f}% - row not trusted"))
            else:
                out.append(Finding(self.name, "WARN", r["_id"],
                                   f"R13 read by OCR ({c:.0f}% confidence) - compare numbers with the PDF page image"))
        return out


# ---------------------------------------------------------------------------
# Agent 6: drawings - equipment counts and per-unit totals
# ---------------------------------------------------------------------------

TAG_RE = re.compile(r"(?<![A-Z0-9-])(AHU|RTU|CHWP|CWP|HWP|CH|P|EJ|PV|FCU|CUH|UH|EF|CT|VAV)[- ]?(\d{1,3}[A-Z]?)(?![A-Za-z0-9])")

# which spec rows depend on which equipment tags
EQUIPMENT = [
    {"name": "pumps", "row": r"\bpumps?\b", "section": r"", "tags": ("P", "CHWP", "CWP", "HWP")},
    {"name": "air-handling / rooftop units", "row": r"each unit", "section": r"^23 73", "tags": ("AHU", "RTU")},
    {"name": "packed expansion joints", "row": r"expansion joint", "section": r"", "tags": ("EJ",)},
    {"name": "plug valves", "row": r"plug valves?", "section": r"", "tags": ("PV",)},
    {"name": "terminal units", "row": r"each (?:terminal )?unit", "section": r"^23 81", "tags": ("FCU", "CUH", "UH")},
]
GROUP_COLS = re.compile(r"MODEL|SIZE|\bHP\b|GPM|TYPE|MANUFACTURER|MFR|RPM|HEAD", re.I)


class DrawingAgent:
    """Agent 6: reads drawing PDFs, counts equipment tags and equipment schedules,
    and multiplies per-unit spec quantities. Counts come only from the drawings
    or from a counts file supplied by the estimator - never assumed."""
    name = "6 Drawings"

    def __init__(self, drawing_pdfs=(), counts_csv=None, ocr=None):
        self.drawing_pdfs, self.counts_csv, self.ocr = list(drawing_pdfs or []), counts_csv, ocr
        self.tags = defaultdict(lambda: defaultdict(set))   # prefix -> tag -> {"file p.N"}
        self.schedules = {}                                 # tag -> {column: value}
        self.findings = []

    # -- reading ------------------------------------------------------------
    def load(self):
        import os
        import pdfplumber
        for path in self.drawing_pdfs:
            fname = os.path.basename(path)
            scanned = []
            with pdfplumber.open(path) as pdf:
                for no, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    if not text.strip():
                        scanned.append(no - 1)
                        continue
                    self._tags_from_text(text, f"{fname} p.{no}")
                    for table in page.extract_tables() or []:
                        self._schedule_from_table(table)
            if scanned and self.ocr is not None:
                texts, confs, f = self.ocr.run(path, scanned)
                self.findings += f
                for no, text in texts.items():
                    if confs[no] >= OcrAgent.MIN_CONF:
                        self._tags_from_text(text, f"{fname} p.{no} (OCR)")
            elif scanned:
                self.findings.append(Finding(self.name, "WARN", None,
                                             f"{fname}: {len(scanned)} scanned drawing pages not read (no OCR)"))
        n_tags = sum(len(v) for v in self.tags.values())
        self.findings.append(Finding(self.name, "INFO", None,
                                     f"{len(self.drawing_pdfs)} drawing file(s) read: {n_tags} equipment tags, "
                                     f"{len(self.schedules)} schedule rows"))

    def _tags_from_text(self, text, where):
        for prefix, num in TAG_RE.findall(text):
            self.tags[prefix][f"{prefix}-{num}"].add(where)

    def _schedule_from_table(self, table):
        if not table or len(table) < 2:
            return
        header = [(c or "").replace("\n", " ").strip().upper() for c in table[0]]
        for row in table[1:]:
            cells = [(c or "").replace("\n", " ").strip() for c in row]
            if not cells:
                continue
            m = TAG_RE.fullmatch(cells[0].upper().replace(" ", "-")) or TAG_RE.fullmatch(cells[0].upper())
            if not m:
                continue
            tag = f"{m.group(1)}-{m.group(2)}"
            self.schedules[tag] = {h: v for h, v in zip(header, cells) if h}
            self.tags[m.group(1)][tag].add("schedule")

    def _load_counts(self):
        import csv
        rules = []
        if not self.counts_csv:
            return rules
        with open(self.counts_csv, newline="", encoding="utf-8-sig") as fh:
            for rec in csv.DictReader(fh):
                try:
                    rules.append((rec["Spec Section"].strip(), rec["Match"].strip().lower(), int(rec["Count"]),
                                  rec.get("Source", "").strip() or "counts file"))
                except (KeyError, ValueError):
                    self.findings.append(Finding(self.name, "ERROR", None, f"counts file row not usable: {rec}"))
        return rules

    # -- applying -----------------------------------------------------------
    def run(self, rows):
        """Adds 'Unit Count', 'Total Qty', 'Count Source' to rows it can complete."""
        import math
        if self.drawing_pdfs:
            self.load()
        counts = self._load_counts()
        out = list(self.findings)
        for r in rows:
            r.setdefault("Unit Count", None)
            r.setdefault("Total Qty", None)
            r.setdefault("Count Source", "")
            q = r["Qty"]
            text = f"{r['Spec Language (verbatim)']} {r['Basis']}"
            if q in (None, "") or not re.search(r"\b(for each|for every|of each|each unit)\b", text, re.I):
                continue
            count, source, per_type = None, "", bool(re.search(r"each type and size|each size and type", text, re.I))
            # 1) estimator-supplied counts file
            for sec, match, n, src in counts:
                if sec == r["Spec Section"] and match and match in text.lower() + " " + (r["Item Required"] or "").lower():
                    count, source = n, f"{src} (estimator input)"
                    break
            # 2) drawings
            if count is None:
                for eq in EQUIPMENT:
                    if not re.search(eq["row"], text, re.I) or not re.search(eq["section"], r["Spec Section"]):
                        continue
                    tags = sorted({t for p in eq["tags"] for t in self.tags.get(p, {})})
                    if not tags:
                        break
                    if per_type:
                        sched = [self.schedules[t] for t in tags if t in self.schedules]
                        if len(sched) != len(tags):
                            out.append(Finding(self.name, "WARN", r["_id"],
                                               f"R14 {len(tags)} {eq['name']} on drawings ({', '.join(tags)}) but not all are in a "
                                               "schedule - types/sizes cannot be counted; total not calculated"))
                            break
                        keys = {tuple(v for k, v in s.items() if GROUP_COLS.search(k)) for s in sched}
                        if not keys or keys == {()}:
                            out.append(Finding(self.name, "WARN", r["_id"],
                                               f"R14 schedule has no model/size columns - types/sizes cannot be counted"))
                            break
                        count = len(keys)
                        source = f"Drawings: {len(tags)} {eq['name']} ({', '.join(tags)}) = {count} distinct type/size in schedule"
                    else:
                        count = len(tags)
                        where = sorted({w for p in eq["tags"] for t in self.tags.get(p, {}) for w in self.tags[p][t]})
                        source = f"Drawings: {', '.join(tags)} [{'; '.join(where[:6])}{' ...' if len(where) > 6 else ''}]"
                    break
            if count is None:
                continue
            every = re.search(r"for every (\d+|ten|five|twenty)\b", text, re.I)
            if every:
                k = {"ten": 10, "five": 5, "twenty": 20}.get(every.group(1).lower()) or int(every.group(1))
                total = q * max(1, math.ceil(count / k))
                calc = f"{q} x ceil({count}/{k}), minimum one"
            else:
                total = q * count
                calc = f"{q} x {count}"
            r["Unit Count"], r["Total Qty"], r["Count Source"] = count, total, f"{source}; {calc}"
            out.append(Finding(self.name, "INFO", r["_id"], f"R14 total {total} {r['Unit']} = {calc} ({source})"))
        done = sum(1 for r in rows if r.get("Total Qty") is not None)
        need = sum(1 for r in rows if r.get("Total Qty") is None and r["Qty"] not in (None, "") and
                   re.search(r"\b(for each|for every|of each|each unit)\b",
                             f"{r['Spec Language (verbatim)']} {r['Basis']}", re.I))
        out.append(Finding(self.name, "INFO", None, f"{done} per-unit rows totalled from drawings/counts, {need} still need a count"))
        return out


# ---------------------------------------------------------------------------
# Agent 7: language - the delivered file must be entirely in English
# ---------------------------------------------------------------------------

class LanguageAgent:
    """Agent 7: opens the written Excel file and checks that every sheet, header and
    cell is English, and that spec quotes are the original English text (never translated).
    Any non-English text blocks delivery."""
    name = "7 Language"
    NON_ENGLISH_LETTERS = re.compile(r"[Ā-ſƀ-ɏͰ-ϿЀ-ӿ֐-ۿ一-鿿]")
    # distinctive words of Latvian, German, Spanish, French, Russian-latin that never appear in US specs
    FOREIGN_WORDS = re.compile(
        r"\b(un|ir|nav|vai|kas|lapa|lapas|rinda|rindas|daudzums|garantija|apkope|apm[a-z]*ba|rezerves|"
        r"gads|gadi|stundas|dienas|kop[a-z]|p[a-z]rbaud[a-z]*|und|nicht|mit|f[uü]r|der|die|das|"
        r"para|con|los|las|del|garant[ií]a|avec|pour|les|des|est)\b", re.I)
    ENGLISH_FUNCTION_WORDS = re.compile(r"\b(the|of|and|for|to|in|with|each|shall|provide|furnish|one|two)\b", re.I)
    ALLOWED_SHEETS = {"Closeout Schedule", "Summary", "Labor", "Checks", "Rules",
                      "Div 23-26 Coverage", "Div 15-16 Coverage", "HVAC-Electrical Coverage"}

    def run(self, path, rows):
        from openpyxl import load_workbook
        out = []
        wb = load_workbook(path)
        for s in wb.sheetnames:
            if s not in self.ALLOWED_SHEETS:
                out.append(Finding(self.name, "ERROR", None, f"R15 sheet name '{s}' is not an approved English name"))
        quote_col = COLUMNS.index("Spec Language (verbatim)")
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    if not isinstance(c.value, str) or not c.value.strip():
                        continue
                    v = c.value
                    if self.NON_ENGLISH_LETTERS.search(v):
                        out.append(Finding(self.name, "ERROR", None,
                                           f"R15 non-English characters in {ws.title}!{c.coordinate}: '{v[:60]}'"))
                        continue
                    is_quote = ws.title == "Closeout Schedule" and c.column == quote_col + 1 and c.row > 2
                    if not is_quote and self.FOREIGN_WORDS.search(v):
                        out.append(Finding(self.name, "ERROR", None,
                                           f"R15 non-English word '{self.FOREIGN_WORDS.search(v).group(0)}' in "
                                           f"{ws.title}!{c.coordinate}: '{v[:60]}'"))
        # quotes must be the original English spec text, not translated or rewritten
        ws = wb["Closeout Schedule"]
        for cells, r in zip(ws.iter_rows(min_row=3, values_only=True), rows):
            q = cells[quote_col] or ""
            if q != r["Spec Language (verbatim)"]:
                out.append(Finding(self.name, "ERROR", r["_id"], "R15 quote in file differs from the verified spec text"))
            elif len(q.split()) > 5 and not self.ENGLISH_FUNCTION_WORDS.search(q):
                out.append(Finding(self.name, "WARN", r["_id"], "R15 quote has no common English words - check source"))
        if not any(f.level == "ERROR" for f in out):
            out.append(Finding(self.name, "INFO", None, "R15 all sheets, headers and cells are English; quotes are original spec text"))
        return out


# ---------------------------------------------------------------------------
# Agent 8: Division 23 (HVAC) and Division 26 (Electrical) coverage
# ---------------------------------------------------------------------------

# MasterFormat level-2 numbers used in Division 23 and Division 26
MF_LEVEL2 = {
    "23": {"00", "01", "05", "06", "07", "08", "09", "11", "12", "13", "21", "22", "23", "25", "29", "31", "33", "34",
           "35", "36", "37", "38", "40", "41", "42", "43", "51", "52", "53", "54", "55", "56", "57", "61", "62", "63",
           "64", "65", "70", "71", "72", "73", "74", "75", "76", "77", "78", "81", "82", "83", "84"},
    "26": {"00", "01", "05", "06", "08", "09", "10", "11", "12", "13", "18", "20", "21", "22", "23", "24", "25", "26",
           "27", "28", "29", "30", "31", "32", "33", "35", "36", "40", "41", "42", "43", "50", "51", "52", "53", "54",
           "55", "56", "61"},
}


# the HVAC and Electrical divisions of each numbering system, and the digit shape that identifies
# one: a MasterFormat 2004 number is canonicalised with spaces ("23 64 23"), a CSI 1995 one is not
HVAC_ELEC = {"2004": (("23", "Division 23 HVAC"), ("26", "Division 26 Electrical")),
             "1995": (("15", "Division 15 Mechanical/HVAC"), ("16", "Division 16 Electrical"))}
COVERAGE_SHEETS = {("2004",): "Div 23-26 Coverage", ("1995",): "Div 15-16 Coverage",
                   ("1995", "2004"): "HVAC-Electrical Coverage"}


class CoverageAgent:
    """Agent 8: lists every HVAC and Electrical section of the document, which closeout
    subsections it has and how many rows were extracted. Flags sections whose closeout text
    produced no row. Divisions 23/26 in MasterFormat 2004 documents, 15/16 in CSI 1995 ones."""
    name = "8 Div 23/26"
    sheet_name = "Div 23-26 Coverage"
    CROSS_REF = re.compile(r"^\s*(See|Refer to)\s+Section", re.I)
    VERB = re.compile(r"\b(provide|furnish|supply|submit|perform|deliver|warrant\w*|guarantee|train)\b", re.I)
    EMPTY_LIST = re.compile(r"furnish the following for owner'?s use", re.I)

    @staticmethod
    def schemes(sec_info):
        """Every numbering system this document uses for HVAC and Electrical. A manual that
        carries both (a transitional project manual) is covered under both - never one only."""
        found = set()
        for sec in sec_info:
            if not sec:
                continue
            scheme = "2004" if " " in sec else "1995"
            if sec[:2] in {d for d, _ in HVAC_ELEC[scheme]}:
                found.add(scheme)
        return tuple(sorted(found)) or ("2004",)

    def run(self, rows, sec_info, titles):
        findings, table = [], []
        per_sec = Counter(r["Spec Section"] for r in rows)
        schemes = self.schemes(sec_info)
        divisions = [d for scheme in schemes for d in HVAC_ELEC[scheme]]
        wanted = {d for d, _ in divisions}
        self.sheet_name = COVERAGE_SHEETS[schemes]
        self.name = "8 Div " + "/".join(d for d, _ in divisions)
        stats = {d: Counter() for d, _ in divisions}
        for sec in sorted(s for s in sec_info if s[:2] in wanted):
            div, level2 = sec[:2], sec[3:5]
            info = sec_info[sec]
            heads = sorted(info["closeout"])
            texts = [t for ts in info["closeout"].values() for t in ts]
            own = [t for t in texts if not self.CROSS_REF.match(t) and self.VERB.search(t)
                   and not self.EMPTY_LIST.search(t)]
            empty_list = [t for t in texts if self.EMPTY_LIST.search(t)]
            n = per_sec.get(sec, 0)
            if n:
                status = f"OK - {n} requirement row(s)"
            elif empty_list and not own:
                status = ("CHECK - section says 'furnish the following' maintenance materials but lists none "
                          "(possible spec omission - consider an RFI)")
                findings.append(Finding(self.name, "WARN", None,
                                        f"R16 {sec} {titles.get(sec, '')}: calls for maintenance materials but lists none - RFI"))
            elif own:
                status = "CHECK - closeout text present but no row extracted: review manually"
                findings.append(Finding(self.name, "WARN", None,
                                        f"R16 {sec} {titles.get(sec, '')}: closeout text in {', '.join(heads)} but no row - review"))
            elif heads:
                status = "No own closeout requirements (lists or cross-references only)"
            else:
                status = "No closeout requirements in this section"
            # the level-2 list is the MasterFormat 2004 structure; it does not apply to
            # five-digit CSI 1995 numbers, which are not flagged against it
            if " " in sec and level2 not in MF_LEVEL2.get(div, ()):
                status += " | nonstandard MasterFormat number"
                findings.append(Finding(self.name, "WARN", None, f"R16 {sec} is not a standard Division {div} number"))
            pages = sorted(info["pages"])
            table.append({"Spec Section": sec, "Section Title": (titles.get(sec, "") or "").upper(),
                          "Pages": f"{pages[0]}-{pages[-1]}" if pages else "",
                          "Closeout subsections found": "; ".join(heads) or "-", "Rows": n, "Status": status})
            stats[div]["sections"] += 1
            stats[div]["with rows"] += 1 if n else 0
            stats[div]["check"] += 1 if status.startswith("CHECK") else 0
        for div, label in divisions:
            s = stats[div]
            findings.append(Finding(self.name, "INFO", None,
                                    f"R16 {label}: {s['sections']} sections, {s['with rows']} with requirements, "
                                    f"{s['check']} flagged CHECK"))
        return findings, table


# ===========================================================================
# PART B - EXTRACTION, EXCEL OUTPUT AND RUN
# ===========================================================================

# ---------------------------------------------------------------------------
# 1. Reading the PDF
# ---------------------------------------------------------------------------

def _read_range(args):
    pdf_path, start, stop = args
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[start:stop]:
            sizes = sorted(round(c["size"], 1) for c in page.chars)
            body = sizes[len(sizes) // 2] if sizes else 10
            limit = max(body * 2.5, 20)
            clean = page.filter(lambda o: o.get("object_type") != "char" or o["size"] <= limit)
            # the default x_tolerance of 3 pt silently drops a real word space in these fonts
            # (a space glyph measures ~2.8 pt), which broke the word-for-word promise in R2
            text = clean.extract_text(x_tolerance=2) or ""
            if not text.strip() and page.images:
                text = "\x00SCANNED"          # image-only page: needs OCR, never guessed
            out.append(text)
            page.flush_cache()
    return out


def read_pages(pdf_path, workers=None):
    """Return the text of every page, reading chunks of pages in parallel on
    all CPU cores. Oversized characters (diagonal "FOR BIDDING" style
    watermarks) are removed before text extraction."""
    import os
    from multiprocessing import Pool
    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
    workers = workers or max(1, min(os.cpu_count() or 1, 8))
    chunk = max(10, -(-n // (workers * 3)))
    jobs = [(pdf_path, s, min(s + chunk, n)) for s in range(0, n, chunk)]
    if workers == 1 or len(jobs) == 1:
        parts = [_read_range(j) for j in jobs]
    else:
        with Pool(workers) as pool:
            parts = pool.map(_read_range, jobs)
    return [t for part in parts for t in part]


def norm(text):
    text = (text or "").replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# 2. Page furniture: headers, footers, section numbers and titles
# ---------------------------------------------------------------------------

# Section numbers are written many ways. Two numbering systems are in use in US project manuals:
#   MasterFormat 2004, six digits: "23 64 23", "236423", "23 6423", "23-64-23", "23 64 23.13"
#   CSI 1995, five digits:         "15625", "15010", "09911"  (Division 15 Mechanical, 16 Electrical)
# Six-digit numbers are normalised to "23 64 23" / "23 64 23.13"; five-digit numbers keep the
# form printed in the document ("15625"). The two are never converted into each other - the
# section cited on a row is always the number printed on that page (R3).
SEC6 = r"([0-4]\d)[ -]?(\d{2})[ -]?(\d{2})(?:\.(\d{1,2}))?"
SEC5 = r"(\d{2})(\d{3})(?:\.(\d{1,2}))?"
SEC_ANY = r"(?<![\d.])(?:" + SEC6 + r"|" + SEC5 + r")(?![\d])"   # six digits are tried first
SEC_ONE_RE = re.compile(SEC_ANY)
_TITLE = r"(?P<title>[A-Z][A-Z0-9 ,&'/\-()]*)"
# a section start is "SECTION" in capitals, optionally followed by the title in capitals;
# cross-references in body text ("Section 23 09 13 - Instrumentation ...") are not starts
SECTION_START_RE = re.compile(r"^SECTION\s+" + SEC_ANY + r"(?:\s*[-\u2013:]?\s*" + _TITLE + r")?$")
# page footers: "23 64 23 - 2", "236423-2", "Section 236423 Page 2", "VALVES 15110 - 15",
# "15181 - Hydronic Piping Page 2 of 14", and a bare "Page 2 of 12"
FOOTER_RE = re.compile(SEC_ANY + r"\s*[-\u2013]\s*(?:page\s*)?\d{1,3}(?!\d)|"
                       r"section\s+" + SEC_ANY + r"\s*(?:[-\u2013,]\s*)?page\s*\d{1,3}|"
                       + SEC_ANY + r"\s*[-\u2013]\s*[A-Za-z][\w ,&'/()-]{0,60}?\s*page\s*\d{1,3}\s*of\s*\d{1,3}|"
                       r"^\s*page\s*\d{1,3}\s*of\s*\d{1,3}\s*$", re.I)
TOC_RE = re.compile(r"^(?:SECTION\s+)?" + SEC_ANY + r"\s*[-\u2013:]?\s+(?P<title>[A-Z][A-Z0-9 ,&'/\-()]{3,})$")


def canon(groups):
    """Normalise a matched section number to the form printed in the document:
    six-digit MasterFormat 2004 as "23 64 23" / "23 64 23.13", five-digit CSI 1995 as "15625"."""
    a, b, c, d, e, f, g = (list(groups) + [None] * 7)[:7]
    if a:
        return f"{a} {b} {c}" + (f".{d}" if d else "")
    return f"{e}{f}" + (f".{g}" if g else "")


def _footer_sections(text):
    out = []
    for m in FOOTER_RE.finditer(text):
        one = SEC_ONE_RE.search(m.group(0))
        if one:                                    # a bare "Page 2 of 12" carries no section number
            out.append(canon(one.groups()))
    return out


def shingles(line):
    w = re.sub(r"\d+", "#", line).split()
    return {" ".join(w[i:i + 3]) for i in range(max(1, len(w) - 2))}


def furniture_lines(pages):
    """Word sequences repeated on many pages (project name, architect, dates)
    are page furniture, not specification text."""
    counts = Counter()
    for p in pages:
        seen = set()
        for l in p.splitlines():
            seen |= shingles(norm(l))
        counts.update(seen)
    threshold = max(5, int(len(pages) * 0.10))
    return {k for k, v in counts.items() if v >= threshold}


def section_titles(pages):
    titles = {}
    for p in pages:
        lines = [norm(l) for l in p.splitlines() if norm(l)]
        for i, line in enumerate(lines):
            m = SECTION_START_RE.match(line)
            if m:
                sec = canon(m.groups())
                title = (m.group("title") or "").strip()
                if not title and i + 1 < len(lines):
                    title = lines[i + 1]
                if title:
                    titles.setdefault(sec, title)
                continue
            m = TOC_RE.match(line)
            if m:
                titles.setdefault(canon(m.groups()), m.group("title").strip())
    return titles


def page_sections(pages, toc_sections=()):
    """Section number for every page: from 'SECTION xx xx xx' starts and from page
    footers/headers ('23 64 23 - 2', '236423-2', 'Section 236423 Page 2'). Footer numbers
    are accepted only if that section starts somewhere in the document or is listed in the
    table of contents."""
    starts = set(toc_sections)
    for p in pages:
        for line in p.splitlines():
            m = SECTION_START_RE.match(norm(line))
            if m:
                starts.add(canon(m.groups()))
    result, current = [], ""
    for p in pages:
        start_here = None
        for line in p.splitlines():
            m = SECTION_START_RE.match(norm(line))
            if m:
                start_here = canon(m.groups())
        found = [f for f in _footer_sections(p) if f in starts or not starts]
        if start_here:
            current = start_here
        elif found:
            current = found[-1]
        result.append(current)
    return result


def body_lines(pages, furniture):
    """All specification lines in reading order as (page_no, text)."""
    out = []
    for no, p in enumerate(pages, 1):
        lines = [norm(l) for l in p.splitlines()]
        lines = [l for l in lines if len(l) > 3]
        for i, t in enumerate(lines):
            edge = i < 6 or i >= len(lines) - 4
            if edge:
                keep_upper = t.startswith(("SECTION ", "PART ", "END OF")) or HEADING_RE.match(t) or ITEM_RE.match(t)
                if (shingles(t) & furniture) or FOOTER_RE.search(t) or (t.upper() == t and not keep_upper):
                    continue
            out.append((no, t))
    return out


# ---------------------------------------------------------------------------
# 3. Splitting the text into subsections and paragraphs
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"^(\d{1,2}\.\d{1,2})\s+([A-Z][A-Z0-9 ,&'/\-\(\)\.]{2,})$")
ITEM_RE = re.compile(r"^(?:[A-Z]\.|\d{1,2}\.|[a-z]\.|\d{1,2}\.\d{1,2}\.\d{1,2}|\d{1,2}\.\d{1,2}(?=\s+[A-Z][a-z])|\d{1,2}\)|\([a-z]\))\s+")
RELEVANT_HEADING = re.compile(
    r"WARRANT|GUARANT|EXTRA MATERIAL|MAINTENANCE MATERIAL|SPARE|MAINTENANCE|"
    r"DEMONSTRATION|TRAINING|INSTRUCTION|CLOSEOUT|FIELD SERVICE|WARRANTIES AND BONDS|"
    r"RECORD DOCUMENT")
RELEVANT_LABEL = re.compile(
    r"^[^:]{0,20}?\b(Maintenance Materials|Extra Materials|Spare Parts|Extra Stock|Special Tools|"
    r"Warrant\w*|Training\w*|Demonstration|Project Record Submittals|Closeout|Operation and Maintenance Data|"
    r"Spare \w+|Keys|Owner'?s Keys|Lamps|Software License\w*)\b[^:]{0,60}:", re.I)


def build_items(lines):
    """Group lines into numbered items (A., B., 1., 2. ...) and remember the
    subsection heading each item belongs to."""
    items, heading, cur, parent, part = [], "", None, "", 0
    for page, text in lines:
        if text.startswith("SECTION ") or text.startswith("END OF SECTION"):
            heading, cur, parent, part = "", None, "", 0
            continue
        if text.startswith("PART "):
            m = re.match(r"PART (\d)", text)
            part = int(m.group(1)) if m else part
            heading, cur, parent = "", None, ""
            continue
        h = HEADING_RE.match(text)
        if h and not text.endswith(".") and sum(c.isupper() for c in h.group(2)) >= 0.7 * sum(c.isalpha() for c in h.group(2)):
            heading, cur, parent = h.group(1) + " " + h.group(2), None, ""
            continue
        if ITEM_RE.match(text) or cur is None:
            body = ITEM_RE.sub("", text, count=1)
            if re.match(r"^[A-Z]\.\s", text):
                parent = body
            cur = {"heading": heading, "page": page, "part": part,
                   "parent": parent if re.match(r"^\d{1,2}\.\s", text) else "",
                   "parts": [(page, body)]}
            items.append(cur)
        else:
            cur["parts"].append((page, text))
    for it in items:
        it["text"] = norm(" ".join(t for _, t in it["parts"]))
    return items


def sentences(item):
    """Split an item into sentences, keeping the page each sentence starts on."""
    text = item["text"]
    offsets, pos = [], 0
    for page, t in item["parts"]:
        offsets.append((pos, page))
        pos += len(t) + 1
    out = []
    for m in re.finditer(r".+?(?:[.;](?=\s+[A-Z(\[])|$)", text):
        s = m.group(0).strip()
        if len(s) < 8:
            continue
        page = item["page"]
        for start, p in offsets:
            if start <= m.start():
                page = p
        out.append((page, s))
    return out


# ---------------------------------------------------------------------------
# 4. Reading quantities, units and type
# ---------------------------------------------------------------------------

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
         "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100}
NUM = r"(?:\d+(?:\.\d+)?|\[\d+\]|(?:" + "|".join(WORDS) + r")(?![a-z]))(?:\s*\(\d+\))?"

# unit nouns -> Unit code; order matters (most specific first)
UNITS = [
    (r"years?|yr\b", "YR"),
    (r"hours?|hrs?\b", "HR"),
    (r"days?", "DAY"),
    (r"months?", "MO"),
    (r"SF\b|square feet", "SF"),
    (r"box(?:es)?", "BOX"),
    (r"gallons?|gal\b", "GAL"),
    (r"sets?", "SET"),
    (r"containers?", "EA"),
    (r"(?:bound )?(?:hard ?copies|copies|copy|prints?)", "EA"),
    (r"(?:bound )?volumes?", "EA"),
    (r"(?:archival-grade \(gold foil\) )?DVDs?", "EA"),
    (r"(?:complete )?inspections?", "EA"),
    (r"(?:technical )?service visits?|visits?|calls?", "EA"),
    (r"(?:filter|fan belt|belt) replacements?", "EA"),
    (r"(?:fuse )?pullers?|wrench(?:es)?|keys?", "EA"),
    (r"percent", "PCT"),
    (r"(?:spare )?(?:circuit )?breakers?|lamps?|fuses?|cartridges?|(?:wall )?plates?|licenses?|"
     r"(?:filter )?media|motors?|drives?|contactors?|relays?|thermostats?|sensors?", "EA"),
    (r"of each", "EA"),
]
# the number may be joined to the unit noun by a hyphen ("1-year warranty", "10-year")
UNIT_RE = re.compile(r"(?<![\w-])(" + NUM + r")[\s-]*(?:(?:extra|spare|minimum|additional|final|complete|normal|plug|valve|replacement)[\s-]+){0,2}(" +
                     "|".join(u for u, _ in UNITS) + r")", re.I)
DEADLINE_RE = re.compile(r"(within|after|prior|before|not less than|no later than|at least)\s+" + NUM +
                         r"[\s-]*(days?|weeks?|months?)(?!\s+interval)"
                         r"|" + NUM + r"[\s-]*(days?|weeks?|months?)\s+(after|before|prior)\b"
                         r"|" + NUM + r"[\s-]*(days?|weeks?|months?)'?\s*(?:advance\s+|written\s+){0,2}notice", re.I)


def to_number(token):
    token = token.lower().strip()
    m = re.search(r"\((\d+)\)", token)
    if m:
        return int(m.group(1))
    token = token.strip("[]")
    if token in WORDS:
        return WORDS[token]
    try:
        v = float(token)
        return int(v) if v.is_integer() else v
    except ValueError:
        return None


def unit_code(noun):
    for pattern, code in UNITS:
        if re.fullmatch(pattern, noun, re.I):
            return code
    return "EA"


def quantities(sentence):
    """All (qty, unit, noun) pairs in a sentence, ignoring deadlines such as
    'within 10 days after acceptance'."""
    s = DEADLINE_RE.sub(lambda m: " " * len(m.group(0)), sentence)
    pairs = []
    for m in UNIT_RE.finditer(s):
        q = to_number(m.group(1))
        if q is not None:
            pairs.append((q, unit_code(m.group(2)), m.group(2)))
    if not pairs:
        m = re.search(r"\b(duplicate|triplicate)\b", s, re.I)
        if m:
            pairs.append((2 if m.group(1).lower() == "duplicate" else 3, "EA", "copies"))
    # A frequency ("monthly", "quarterly") states HOW OFTEN, never how many. The count is the
    # frequency times the service period, and the period is stated in a different sentence - so
    # the count is not readable from this quote and no number may be put in Qty (R4).
    return pairs


# how often a recurring service happens, and the gap between visits: both are stated as text and
# neither is a quantity. They are recorded in Basis so the estimator can work the count out.
FREQ_BASIS = re.compile(r"\b(bi-?monthly|monthly|quarterly|semiannual(?:ly)?|semi-annual(?:ly)?|weekly|"
                        r"annual(?:ly)?|every \d+ months?|\w+[- ]month interval|"
                        r"\d+ (?:complete |normal |routine )*inspections? per year)\b", re.I)


def basis(sentence):
    m = re.search(r"\b((?:for|of) (?:each|every)\b[^,.;]*|per [^,.;]*|from (?:the )?Date of Substantial Completion|"
                  r"after Acceptance by the Owner|minimum)", sentence, re.I)
    out = m.group(1).strip() if m else ""
    f = FREQ_BASIS.search(sentence)
    if f:
        note = f"{f.group(1)} - count not stated in this sentence, estimator must compute it"
        out = f"{out}; {note}" if out else note
    return out


SKIP_RE = re.compile(r"^\s*(See|Refer to) Section|\bdraft\b|preliminary|reviewed and returned|"
                     r"Submit manufacturer'?s warranty and ensure forms|segments\b|take precedence|"
                     r"other guarantees required|longer than|\u00a7|User Notes|"
                     r"\bwaives? the right|\bfails to notify\b|\bclaim for breach\b|"
                     r"\bquote\b[^.]{0,80}\bwarrant|"
                     r"\bwill be subject to\b|\bcause for Owner to charge\b|\bBe prepared to\b|"
                     r"\bif unable to\b|\bre-?schedule\b|\bshall be accomplished by\b|"
                     r"\brequire (?:material|product) (?:or product )?suppliers\b|"
                     r"\bmaintain\b[^.]{0,40}\b(?:cop(?:y|ies)|sets?|records?|documents?|prints?)\b"
                     r"[^.]{0,40}\bduring (?:the )?construction period\b", re.I)
WARRANTY_RE = re.compile(r"warrant|guarant", re.I)
MAINT_RE = re.compile(r"service and maintenance|maintenance service|maintenance contract|maintenance period|"
                      r"(?:quarterly|semi-?annual|annual|monthly|bi-?monthly)[^.]{0,40}maintenance|"
                      r"(?:infrared|thermographic) (?:scan|survey|inspection)|"
                      r"service visits|inspections per year|service calls?|time period between calls|"
                      r"filter replacements|fan belt replacement", re.I)
TRAIN_RE = re.compile(r"train|instruct|demonstrat", re.I)
TOOL_RE = re.compile(r"\btools?\b|wrench|puller|\bkeys?\b", re.I)
SPARE_RE = re.compile(r"\bextra\b|\bspare\b|seals?\b|belts?\b|fuses?\b|refrigerant|lubricating oil|packing|"
                      r"breakers?\b|lamps?\b|contactors?\b|relays?\b", re.I)
INFRARED_RE = re.compile(r"(infrared|thermographic)\s+(scan|survey|inspection|testing)", re.I)
ATTIC_RE = re.compile(r"owner'?s use in maintenance|store where directed|acoustical|paint|gallon|wall plate|filters?\b", re.I)
OM_RE = re.compile(r"operation and maintenance|operating and maintenance|O&M|as-built|record|manuals?|DVD|"
                   r"copies|prints|reports?|documents|warranties and bonds|training manual", re.I)
QNS_RE = re.compile(r"\bsufficient\b|\bfinal copies\b|\ball (?:spare|extra)\b|\badditional copies\b", re.I)


def classify(sentence, heading):
    if (WARRANTY_RE.search(sentence) or "WARRANT" in heading) and re.search(r"year|yr\b", sentence, re.I) \
            and not MAINT_RE.search(sentence):
        return "Extended Warranty"
    if MAINT_RE.search(sentence) or (re.search(r"MAINTENANCE SERVICE|^\d\.\d+ MAINTENANCE$", heading)
                                     and re.search(r"\bservice\b|inspect", sentence, re.I)):
        return "Maintenance Service"
    if re.search(r"\bmanuals?\b|as-built|DVD|\bcop(?:y|ies)\b|\bprints\b|\breports?\b|record drawings", sentence, re.I):
        return "O&M Deliverable"
    if TOOL_RE.search(sentence) and not OM_RE.search(sentence):
        return "Special Tool"
    if TRAIN_RE.search(sentence) and not re.search(r"training manual|copy of each training", sentence, re.I):
        return "Training"
    if re.search(r"EXTRA MATERIAL|MAINTENANCE MATERIAL", heading) or RELEVANT_LABEL.match(sentence) or SPARE_RE.search(sentence):
        if SPARE_RE.search(sentence) and not re.search(r"^Provide one \(1\) set of filters", sentence):
            return "Spare Part"
        if ATTIC_RE.search(sentence) or re.search(r"EXTRA MATERIAL|MAINTENANCE MATERIAL", heading):
            return "Attic Stock"
    if OM_RE.search(sentence):
        return "O&M Deliverable"
    return None


def item_name(sentence, noun, multi):
    """Short description: the label before ':' if there is one, otherwise the
    sentence trimmed of its leading verb."""
    m = re.match(r"^([A-Z][^:]{2,60}):\s", sentence)
    if m and not multi:
        return m.group(1)
    s = re.sub(r"^(Provide|Furnish|Supply|Submit|Include|Obtain|Correct)\s+(?:a |an |the |minimum of |minimum )?", "", sentence)
    s = s.rstrip(".;")
    if multi:
        return f"{noun} - {s[:90]}".rstrip()
    return s[:110].rstrip()


# ---------------------------------------------------------------------------
# 5. Extraction
# ---------------------------------------------------------------------------

def extract(pdf_path, ocr=None):
    pages = read_pages(pdf_path)
    scanned = [i for i, p in enumerate(pages) if p == "\x00SCANNED"]
    ocr_confs, ocr_findings = {}, []
    if scanned and ocr is not None:
        texts, ocr_confs, ocr_findings = ocr.run(pdf_path, scanned)
        for no, text in texts.items():
            pages[no - 1] = text
    furniture = furniture_lines(pages)
    titles = section_titles(pages)
    sec_of_page = page_sections(pages, titles)
    lines = body_lines(pages, furniture)
    items = build_items(lines)
    page_text = [norm(" ".join(l for l in p.splitlines() if len(l.strip()) > 3)) for p in pages]
    per_page = defaultdict(list)
    for _no, _t in lines:
        per_page[_no].append(_t)
    body_text = [norm(" ".join(per_page.get(i, []))) for i in range(1, len(pages) + 1)]

    sec_info = {}
    for it in items:
        sec = sec_of_page[it["page"] - 1]
        info = sec_info.setdefault(sec, {"pages": set(), "closeout": {}})
        info["pages"].add(it["page"])
        label = RELEVANT_LABEL.match(it["text"]) or RELEVANT_LABEL.match(it["parent"])
        if RELEVANT_HEADING.search(it["heading"]) or label or INFRARED_RE.search(it["text"]):
            key = it["heading"] or (label.group(1) if label else "Infrared scan")
            info["closeout"].setdefault(key, []).append(it["text"])
    rows, log = [], []
    GLOBAL_OM = re.compile(r"operation and maintenance|operating and maintenance|O&M|as-built|record drawings|"
                           r"record (?:prints|specifications|product data|documents)|instruction(?:al)? program|"
                           r"\bmanuals?\b|DVD|training manual", re.I)
    VERB = re.compile(r"\b(provide|furnish|supply|submit|attach|deliver|turn over)\b", re.I)
    TEMPORARY = re.compile(r"\bTEMPORARY\b")
    for it in items:
        # Temporary Facilities and Controls is removed at the end of the job; nothing in it is
        # handed over to the Owner, so its keys and materials are not closeout items
        if TEMPORARY.search((titles.get(sec_of_page[it["page"] - 1], "") or "").upper()):
            continue
        relevant = (bool(RELEVANT_HEADING.search(it["heading"])) or bool(RELEVANT_LABEL.match(it["text"]))
                    or bool(RELEVANT_LABEL.match(it["parent"])))
        sents = sentences(it)
        for idx, (page, sent) in enumerate(sents):
            nxt = sents[idx + 1][1] if idx + 1 < len(sents) else ""
            if SKIP_RE.search(sent) or re.search(r"reviewed and returned|will be reviewed", nxt, re.I):
                continue
            if len(sent) > 400:
                continue
            body_part = it["part"] != 2           # Part 2 = product descriptions
            g_warranty = (body_part and WARRANTY_RE.search(sent) and re.search(r"\byears?\b", sent, re.I)
                          and re.search(r"provide|warrant|guarantee|bond", sent, re.I))
            g_om = (GLOBAL_OM.search(sent) and VERB.search(sent)
                    and (quantities(sent) or QNS_RE.search(sent) or re.search(r"final copies", sent, re.I)))
            g_tool = re.search(r"wrench|puller|special tools?|\bkeys\b", sent, re.I) and quantities(sent) and \
                     re.search(r"for (?:each|every)|furnish|provide|supply|operator|per lock", sent, re.I)
            # the closeout clause that hands the stock itself over, and the one that owes the
            # Owner's own people instruction - both are obligations even with no number stated
            g_handover = bool(re.search(r"\b(deliver|turn over|hand over)\b[^.]{0,120}"
                                        r"\b(tools?|spare parts?|extra materials?|attic stock|keys?)\b", sent, re.I)
                              and re.search(r"\bOwner\b", sent, re.I))
            # the Owner's OWN people must be the ones being instructed - "as instructed by the
            # Owner" is the opposite direction and is not a training obligation
            g_instruct = bool(re.search(r"\b(?:instruct|train)\w*\s+(?:the\s+)?Owner'?s?\s+"
                                        r"(?:own\s+|operating\s+|maintenance\s+)?"
                                        r"(?:personnel|representatives?|staff|employees|operators?)\b",
                                        sent, re.I))
            # Division 26: follow-up infrared scan of electrical gear before warranty ends
            g_ir = body_part and INFRARED_RE.search(sent) and re.search(r"months? after|before (?:the )?(?:end|expiration)|"
                                                                       r"warranty period|substantial completion", sent, re.I)
            if not (relevant or g_warranty or g_om or g_tool or g_ir or g_handover or g_instruct):
                continue
            kind = classify(sent, it["heading"])
            if not kind:
                continue
            pairs = quantities(sent)
            if kind == "Extended Warranty":
                pairs = [p for p in pairs if p[1] == "YR"][:1]
            # an unquantified material ("sufficient chemicals ... for one year") states a period,
            # not an amount - the period must never be reported as the quantity supplied
            if pairs and QNS_RE.search(sent) and kind in ("Attic Stock", "Spare Part", "Special Tool") \
                    and all(u in ("YR", "MO", "DAY", "HR") for _, u, _ in pairs):
                pairs, kind = [(None, "", "")], "Quantity Not Specified"
            if not pairs and kind == "Training" and re.search(r"demonstration for (?:the )?other season", sent, re.I):
                pairs, kind = [(None, "", "")], "Quantity Not Specified"   # real requirement, no number stated
            if not pairs:
                if re.search(r"\bfor each\b", sent, re.I) and kind == "O&M Deliverable" \
                        and re.search(r"\b(provide|furnish|supply|submit|attach|deliver|turn over)\b", sent, re.I):
                    pairs = [(1, "EA", "")]
                elif QNS_RE.search(sent) or re.search(r"final copies", sent, re.I) or INFRARED_RE.search(sent):
                    pairs, kind = [(None, "", "")], "Quantity Not Specified"
                elif kind == "Maintenance Service" and FREQ_BASIS.search(sent):
                    # a recurring service whose frequency is stated but whose count is not: the
                    # obligation is real, the number of visits is not in the spec text
                    pairs, kind = [(None, "", "")], "Quantity Not Specified"
                elif g_handover or g_instruct:
                    pairs, kind = [(None, "", "")], "Quantity Not Specified"
                elif kind == "Training" and re.search(r"\b(provide|furnish|perform|engage|schedule)\b", sent, re.I) \
                        and re.search(r"\bOwner'?s?\b|\battendees?\b|\bparticipants?\b|\bpersonnel\b|"
                                      r"\beach season\b", sent, re.I):
                    # training owed to the Owner's personnel with no hours stated: the obligation is
                    # reported with an empty Qty, and agent 3 asks the estimator for the hours
                    pairs, kind = [(None, "", "")], "Quantity Not Specified"
                else:
                    continue
            # several different counted things in one sentence -> one row each
            counted = [p for p in pairs if p[1] in ("EA", "SET")]
            distinct = OrderedDict()
            for q, u, n in counted:
                distinct.setdefault(re.sub(r"s$", "", n.lower()), (q, u, n))
            if kind in ("O&M Deliverable", "Maintenance Service") and len(distinct) > 1:
                pairs = list(distinct.values())
            else:
                pairs = pairs[:1]
            sec = sec_of_page[page - 1]
            obligation = classify(sent, it["heading"]) or kind
            for q, u, n in pairs:
                rows.append({
                    "_obligation": obligation,          # the kind before an empty Qty made it "Quantity Not Specified"
                    "Spec Section": sec, "Section Title": titles.get(sec, "").upper(), "Type": kind,
                    "Item Required": item_name(sent, n, len(pairs) > 1), "Qty": q, "Unit": u,
                    "Basis": basis(sent), "Page": page, "Spec Language (verbatim)": sent,
                })

    # coverage: pages that talk about closeout items but produced no rows
    hit_pages = {r["Page"] for r in rows}
    for no, t in enumerate(page_text, 1):
        if no in hit_pages:
            continue
        if re.search(r"(extra materials|maintenance materials|spare parts|attic stock|maintenance service|"
                     r"\d+[- ]years? warranty|warranty for \w+ years|\d+[- ]year \w+ warranty|training)", t, re.I) and \
           re.search(r"\b(provide|furnish|supply)\b", t, re.I):
            log.append((no, "Review manually - closeout keywords but no row", ""))
    rows.sort(key=lambda r: (r["Spec Section"], r["Page"]))
    for i, r in enumerate(rows, 1):
        r["_id"] = i
    known = set(titles) | set(sec_of_page)
    empty = [i for i, p in enumerate(pages, 1) if p == "\x00SCANNED"]   # scanned and not OCR-read
    pages = [("" if p == "\x00SCANNED" else p) for p in pages]
    blank = sum(1 for p in pages if not p.strip() and p != "\x00SCANNED")
    return {"rows": rows, "log": log, "pages": len(pages), "page_text": page_text, "body_text": body_text,
            "sec_of_page": sec_of_page, "known_sections": known, "empty_pages": empty, "blank_pages": blank,
            "ocr_confs": ocr_confs, "ocr_findings": ocr_findings, "sec_info": sec_info, "titles": titles}


# ---------------------------------------------------------------------------
# 6. Excel output
# ---------------------------------------------------------------------------

COLUMNS = ["Spec Section", "Section Title", "Type", "Item Required", "Qty", "Unit", "Basis", "Page",
           "Spec Language (verbatim)"]
LABOR_COLS = ["Row", "Spec Section", "Page", "Item", "Labor Type", "Stated in spec", "Hours", "Status", "How"]


def _style(ws, header_row, widths):
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for c in ws[header_row]:
        c.font = Font(name="Arial", bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3864")
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = border
    for row in ws.iter_rows(min_row=header_row + 1):
        for c in row:
            c.font = Font(name="Arial", size=10)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = border
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)


COVERAGE_COLS = ["Spec Section", "Section Title", "Pages", "Closeout subsections found", "Rows", "Status"]


def write_excel(path, data, rows, labor, findings, notes, seconds, coverage=(), coverage_sheet="Div 23-26 Coverage"):
    wb = Workbook()
    ws = wb.active
    ws.title = "Closeout Schedule"
    ws.append([f"Source: {data['source']} ({data['pages']} pages) - {len(rows)} requirements. "
               "Every quote verified word-for-word against the cited page."])
    ws["A1"].font = Font(name="Arial", bold=True, size=11)
    ws.append(COLUMNS + ["Checks", "Notes", "Unit Count", "Total Qty", "Count Source"])
    warn_fill = PatternFill("solid", fgColor="FFF2CC")
    for r in rows:
        n = notes.get(r["_id"], [])
        ws.append([r[c] for c in COLUMNS] + ["WARN" if n else "PASS", " | ".join(n),
                                              r.get("Unit Count"), r.get("Total Qty"), r.get("Count Source") or None])
    _style(ws, 2, [11, 30, 20, 42, 7, 7, 26, 7, 80, 8, 50, 8, 8, 60])
    for row in ws.iter_rows(min_row=3):
        if row[9].value == "WARN":
            for c in row:
                c.fill = warn_fill
    ws.auto_filter.ref = f"A2:N{ws.max_row}"

    ws2 = wb.create_sheet("Summary")
    ws2.append(["Type", "Rows"])
    for t, n in Counter(r["Type"] for r in rows).most_common():
        ws2.append([t, n])
    ws2.append(["Total", len(rows)])
    _style(ws2, 1, [28, 10])

    ws3 = wb.create_sheet("Labor")
    ws3.append(LABOR_COLS)
    for x in labor:
        ws3.append([x[c] for c in LABOR_COLS])
    _style(ws3, 1, [6, 11, 6, 40, 22, 30, 8, 18, 60])

    ws4 = wb.create_sheet("Checks")
    ws4.append(["Agent", "Level", "Row", "Finding"])
    for f in findings:
        ws4.append(f.as_list())
    ws4.append(["Run", "INFO", "-", f"Extraction and checks took {seconds:.0f} seconds"])
    _style(ws4, 1, [14, 8, 6, 110])

    ws6 = wb.create_sheet(coverage_sheet)
    ws6.append(COVERAGE_COLS)
    for c in coverage:
        ws6.append([c[k] for k in COVERAGE_COLS])
    _style(ws6, 1, [11, 40, 14, 50, 7, 70])
    for row in ws6.iter_rows(min_row=2):
        if str(row[5].value).startswith("CHECK"):
            for c in row:
                c.fill = warn_fill

    ws5 = wb.create_sheet("Rules")
    ws5.append(["Strict rules applied to this schedule"])
    for rule in STRICT_RULES:
        ws5.append([rule])
    _style(ws5, 1, [140])
    wb.save(path)


# ---------------------------------------------------------------------------
# 7. Run: extract -> 4 agents -> write -> delivery check
# ---------------------------------------------------------------------------

TIME_LIMIT = 300  # seconds


def run(pdf_path, out_path, drawings=(), counts=None, use_ocr=True):
    import os
    import time
    t0 = time.time()
    ocr = OcrAgent() if use_ocr else None
    data = extract(pdf_path, ocr)
    data["source"] = os.path.basename(pdf_path)
    rows = data["rows"]
    print(f"[extract]  {data['pages']} pages read, {len(data['ocr_confs'])} by OCR, "
          f"{len(rows)} candidate rows  ({time.time() - t0:.0f}s)")

    findings = list(data["ocr_findings"])
    a1 = PrecisionAgent(data["page_text"], data["sec_of_page"], data["known_sections"], quantities,
                        data["body_text"]).run(rows)
    a2 = QualityAgent(data["log"], data["pages"], data["empty_pages"], data["blank_pages"]).run(rows)
    a5 = (ocr or OcrAgent()).check_rows(rows, data["ocr_confs"])
    findings += a1 + a2 + a5
    blocked = {f.row_id for f in findings if f.level == "ERROR" and f.row_id is not None}
    rows = [r for r in rows if r["_id"] not in blocked]
    a6 = DrawingAgent(drawings, counts, ocr).run(rows)
    a3, labor = LaborAgent().run(rows)
    agent8 = CoverageAgent()
    a8, coverage = agent8.run(rows, data["sec_info"], data["titles"])
    totalled = {r["_id"] for r in rows if r.get("Total Qty") is not None}
    a1 = [f for f in a1 if not (f.message.startswith("R8") and f.row_id in totalled)]
    findings = list(data["ocr_findings"]) + a1 + a2 + a5 + a6 + a3 + a8
    for name, fs in (("1 Precision", a1), ("2 Quality", a2), ("3 Labor", a3), ("5 OCR", data["ocr_findings"] + a5),
                     ("6 Drawings", a6), (agent8.name, a8)):
        e = sum(f.level == "ERROR" for f in fs)
        w = sum(f.level == "WARN" for f in fs)
        print(f"[agent {name}]  {e} errors, {w} warnings")

    notes = {}
    for f in findings:
        if f.level == "WARN" and f.row_id is not None:
            notes.setdefault(f.row_id, []).append(f.message)
    write_excel(out_path, data, rows, labor, findings, notes, time.time() - t0, coverage, agent8.sheet_name)

    a4 = DeliveryAgent().run(out_path, rows, labor)
    a7 = LanguageAgent().run(out_path, rows)
    findings += a4 + a7
    errors = [f for f in a4 + a7 if f.level == "ERROR"]
    seconds = time.time() - t0
    if errors:
        os.remove(out_path)
        for f in errors:
            print(f"[agent {f.agent}]  ERROR", f.message)
        print("FAILED - Excel file was NOT delivered.")
        return 2
    write_excel(out_path, data, rows, labor, findings, notes, seconds, coverage,
                agent8.sheet_name)   # final file includes delivery result
    print("[agent 4 Delivery]  file re-opened and verified")
    print("[agent 7 Language]  file is entirely English, quotes are original spec text")
    if seconds > TIME_LIMIT:
        print(f"WARNING: run took {seconds:.0f}s, over the {TIME_LIMIT}s target")
    print(f"DONE in {seconds:.0f}s - {len(rows)} verified rows -> {out_path}")
    return 0


def main():
    import argparse
    import glob
    import os
    ap = argparse.ArgumentParser(description="SpecTakeoff closeout requirements extractor")
    ap.add_argument("spec", nargs="?", help="specification PDF (default: every PDF in this folder and /content)")
    ap.add_argument("-o", "--out", help="output .xlsx (default: <pdf name>_Closeout_Schedule.xlsx)")
    ap.add_argument("-d", "--drawings", nargs="*", default=[], help="drawing PDF(s) for equipment counts")
    ap.add_argument("-c", "--counts", help="CSV with columns: Spec Section, Match, Count, Source")
    ap.add_argument("--no-ocr", action="store_true", help="do not OCR scanned pages")
    a = ap.parse_args()
    if a.spec:
        specs = [a.spec]
    else:
        drawings = {os.path.abspath(d) for d in a.drawings}
        specs = sorted({os.path.abspath(p) for p in glob.glob("*.pdf") + glob.glob("/content/*.pdf")} - drawings)
        if not specs:
            print("No PDF found. Put the specification PDF in this folder (Colab: /content) or give its path.")
            sys.exit(1)
        print("Specification PDF(s) found:", ", ".join(os.path.basename(p) for p in specs))
    status = 0
    for spec in specs:
        out = a.out if (a.out and len(specs) == 1) else re.sub(r"\.pdf$", "", spec, flags=re.I) + "_Closeout_Schedule.xlsx"
        print(f"\n=== {os.path.basename(spec)} ===")
        status = max(status, run(spec, out, a.drawings, a.counts, not a.no_ocr))
    sys.exit(status)


if __name__ == "__main__":
    main()
