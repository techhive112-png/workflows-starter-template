# SpecTakeoff — operating manual

Everything you need, in order. Nothing here is optional reading.

---

## 1. What this is

You give it a US construction specification PDF (a project manual). It gives you an Excel
schedule of everything the contractor must hand over to the Owner at closeout: attic stock,
spare parts, special tools, O&M documentation, training, extended warranties, maintenance
service contracts.

Every row cites the spec section, the PDF page, and quotes the spec word for word. That is the
whole point: the client can check any row against the PDF in ten seconds.

Proven on five real specifications, four states, both CSI numbering systems.

---

## 2. The files

| File | What it is | Do you edit it? |
|---|---|---|
| `SPECTAKEOFF_ALL_IN_ONE.md` | **The project.** History, rules, the code itself, and a golden baseline per spec. | Only via `package.py` |
| `spectakeoff.py` | The extractor. 8 check agents + Excel output. | Yes, this is the code |
| `selftest.py` | The quality gate. 7 checks. | Rarely |
| `package.py` | Keeps the `.md` consistent with the code. | Rarely |
| `batch.py` | Several specs at once. | Rarely |
| `MANUAL.md` | This file. | — |
| `urls.txt` | The public specs used for testing. | Add URLs freely |
| `verify_rccd.py` | Legacy. Checks against the ORIGINAL hand-typed 67 rows. Superseded by `selftest.py`. | No |

The `.md` carries a copy of all four `.py` files inside it. **The `.md` alone is the whole
project** — upload only that file and you can recreate everything.

---

## 3. Install and run

### Google Colab (phone-friendly — every command is one line)

Upload `SPECTAKEOFF_ALL_IN_ONE.md` and your spec PDF to `/content`, then:

**Cell 1 — extract all four scripts. Must print `True`.**
```
d=open('/content/SPECTAKEOFF_ALL_IN_ONE.md',encoding='utf-8').read(); import re,json,hashlib; man=json.loads(re.search(r'<!-- MANIFEST (\{.*?\}) -->',d).group(1)); got={n:(open('/content/'+n,'w',encoding='utf-8').write(c), hashlib.md5(c.encode()).hexdigest()[:10])[1] for n,c in re.findall(r'# BEGIN (\S+\.py)\n(.*?)# END \1',d,re.S)}; print(got); print(got==man)
```

**Cell 2 — run it.**
```
!python /content/spectakeoff.py /content/spec.pdf
```

**Cell 3 — run it and prove the result.**
```
!python /content/selftest.py /content/spec.pdf -m /content/SPECTAKEOFF_ALL_IN_ONE.md
```

### A computer

```
pip install pdfplumber openpyxl pypdfium2
python spectakeoff.py spec.pdf
```

Tesseract is only needed for scanned PDFs. On Colab and Linux as root it installs itself.

---

## 4. Every command

### `spectakeoff.py` — produce the schedule

```
python spectakeoff.py                          every PDF in this folder and in /content
python spectakeoff.py spec.pdf                 one spec
python spectakeoff.py spec.pdf -o result.xlsx  name the output
python spectakeoff.py spec.pdf --drawings M-101.pdf E-601.pdf
python spectakeoff.py spec.pdf --counts counts.csv
python spectakeoff.py spec.pdf --no-ocr        skip scanned pages instead of OCR-ing them
```

Output: `<pdf name>_Closeout_Schedule.xlsx` next to the PDF.

`counts.csv` is how you feed equipment counts by hand when there are no drawings:

```
Spec Section,Match,Count,Source
26 28 13,fuse,12,E-601 panel schedules
23 21 23,pump,4,M-201 pump schedule
```

### `selftest.py` — the quality gate. Run it after EVERY change to the code.

```
python selftest.py spec.pdf                        the universal checks
python selftest.py spec.pdf -m ALL_IN_ONE.md       also check the golden baseline
python selftest.py *.pdf                           every spec in turn
```

Seven checks. Exit code 0 only if all pass:

1. **run** — the file is delivered, agents 4 and 7 pass
2. **R4** — every Qty is a number that appears in that row's own quote
3. **R2** — every quote is word for word in the raw text of its cited page
4. **R5** — Qty is empty if and only if Type is "Quantity Not Specified"
5. **golden** — the output reproduces the baseline in the `.md` exactly
6. **repeat** — two runs are identical
7. **time** — inside 300 seconds

It re-reads the PDF with its own code, so a bug in the extractor's own agents cannot hide from it.

### `package.py` — the only thing allowed to change the `.md`

```
python package.py                        re-embed all four scripts, fix the md5 and the manifest
python package.py --baseline spec.pdf    also regenerate that spec's golden baseline
python package.py --check                report only: is the .md stale?
```

It refuses to write a baseline from a run that failed `selftest.py`, and it re-reads what it wrote
rather than leave an inconsistent file behind.

**Never hand-edit the md5 or the embedded code.** That went stale twice when done by hand.

### `batch.py` — several specs at once

```
python batch.py a.pdf b.pdf c.pdf
python batch.py --fetch urls.txt         download each URL first, then run
python batch.py *.pdf --no-selftest      faster, skips the per-spec gate
```

Writes `Batch_Summary.xlsx`: pages, rows, numbering system, coverage sheet, agent errors and
warnings, seconds, self-test verdict, type breakdown. A spec that fails is reported FAILED with
the reason, never hidden.

---

## 5. The working loop — follow it in this order

```
1. change spectakeoff.py
2. python selftest.py <each spec> -m SPECTAKEOFF_ALL_IN_ONE.md
3. if a baseline moved: understand WHY before accepting it
4. python package.py --baseline <each spec>
5. python package.py --check            must say CONSISTENT
6. git commit && git push
```

Skipping step 2 is how a silent defect reaches a client.

---

## 6. The rules

Four non-negotiables. These are not style preferences:

1. **Output rows come only from running the code.** Never written by hand, never from general
   knowledge. An invented row is worse than a missing one.
2. **There is no target row count.** Never pad, repeat or invent rows. The document decides how
   many rows there are. Never tell an AI a row count to hit — that is exactly how another AI
   produced 12 fake rows with quotes that were not in the PDF.
3. **Never remove or weaken a check, never add a bypass.**
4. **A run finishes in under 5 minutes, and everything delivered is English.** Spec quotes are the
   original English text and are never translated.

The full list, R1–R16, is printed on the **Rules** sheet of every Excel file the program produces.
The ones you will meet in practice:

| Rule | What it means |
|---|---|
| R2 | The quote must be word for word on the cited page. A sentence interrupted by the page header/footer is matched against the same page with that furniture removed — never against another page. |
| R3 | The cited section must be the section printed on that page. Six-digit MasterFormat 2004 numbers are normalised to `23 64 23`; five-digit CSI 1995 numbers keep their printed form `15625`. The two are never converted into each other. |
| R4 | Qty and Unit are read from the quote itself. A number not in the quote is an error. A deadline, a notice period, a frequency and years of experience are not quantities. |
| R5 | Qty is empty only for "Quantity Not Specified", and that type always has an empty Qty. |
| R8 | "for each / per / of each" quantities are NOT multiplied. The equipment count must come from drawings or a counts file. |
| R9 | Labor hours are computed only from hours, days, persons and visits stated in the quote. Missing factors are "Needs input", never assumed. |
| R10 | Conflicting requirements for the same item are flagged on both rows, never silently resolved. |
| R12 | The Excel file is re-opened and checked. If any check fails, **the file is deleted and not delivered.** |
| R16 | Every HVAC and Electrical section is listed with its closeout subsections and row count (Divisions 23/26 in MasterFormat 2004, 15/16 in CSI 1995, both when a manual uses both). |

---

## 7. The 8 agents inside `spectakeoff.py`

Deterministic code, not AI. They cannot invent data.

| # | Agent | What it does |
|---|---|---|
| 1 | Precision | quote on the cited page, section valid, Qty/Unit read from the quote |
| 2 | Quality | duplicates, padding, conflicts, pages needing manual review |
| 3 | Labor | hours only from stated numbers, otherwise "Needs input" |
| 4 | Delivery | re-opens the finished Excel, compares every cell, **deletes the file on any mismatch** |
| 5 | OCR | Tesseract for scanned pages; rows from pages under 75% confidence are removed |
| 6 | Drawings | equipment tags and schedules multiply per-unit quantities |
| 7 | Language | the delivered file is entirely English; quotes never translated |
| 8 | Div coverage | every HVAC/Electrical section listed; closeout text with no row is flagged CHECK |

---

## 8. The Excel you get

| Sheet | What it holds |
|---|---|
| **Closeout Schedule** | The rows. Section, Title, Type, Item, Qty, Unit, Basis, Page, verbatim quote, Checks, Notes, Unit Count, Total Qty, Count Source. Yellow = a warning worth reading. |
| Summary | Row count per type |
| Labor | Hours computed from the spec, or "Needs input" for the estimator |
| Checks | Every agent finding, with the rule number |
| Div 23-26 / 15-16 Coverage | Every HVAC/Electrical section, its closeout subsections, row count, and CHECK flags |
| Rules | R1–R16, so the client sees the standard the file was held to |

The eight types: Attic Stock · Spare Part · Special Tool · O&M Deliverable · Training ·
Extended Warranty · Maintenance Service · Quantity Not Specified.

"Quantity Not Specified" means the spec states the obligation but never says how many. That is a
real finding, not a gap in the program.

---

## 9. When something goes wrong

| What you see | What it means | What to do |
|---|---|---|
| Cell 1 prints `False` | The `.md` and the code disagree | `python package.py`, then re-run cell 1 |
| `FAILED - Excel file was NOT delivered` | Agent 4 or 7 rejected the file | Read the ERROR lines above it. The file is withheld on purpose |
| Very few rows for a big spec | Under-extraction, like UM Barrows at 14 rows from 290 pages | Open the PDF and read its WARRANTY / EXTRA MATERIALS / MAINTENANCE / TRAINING / CLOSEOUT subsections by eye. The self-test cannot see a row that never appeared |
| `0 rows` | Section numbers are in an unrecognised format | Check how the spec prints `SECTION ...` and its page footers |
| `golden baseline FAIL` | Your change moved a row | Understand why **before** regenerating the baseline |
| `R11 page N: closeout keywords but no row` | That page may hold an obligation | Read page N yourself |
| `CHECK - furnish the following ... but lists none` | The spec itself is incomplete | Send an RFI. This is a finding to sell, not a bug |

**The one blind spot:** the self-test proves that the rows present are correct. It cannot prove
that no row is missing. Every new specification must also be read by eye once.

---

## 10. What it cannot do yet

- **Price anything.** The Labor sheet gives hours only where the spec states them. No rates, no
  material costs.
- **Count equipment by itself.** Per-unit quantities ("one set for each pump") come out flagged for
  the estimator. The drawings agent has only ever been tested on a synthetic drawing — not on real
  M/E drawings.
- **Measure from a photo.** OCR can read text from a photo; perspective makes dimensions
  unreliable. Photos are for documenting condition, not for takeoff.
- **Decide conditional requirements.** "If capacitor backup is used, an additional 10-year warranty
  must be carried" is reported; a human decides it with an RFI.
- **Electrical depth.** All five test specs are mechanical projects, so Division 26/16 coverage is
  thin.

Next, in order: real M/E drawings → spec-versus-drawings conflict detection and RFI generation →
submittal register and closeout calendar → drawing measurement → a productivity database for hours.
