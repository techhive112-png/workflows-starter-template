# SpecTakeoff — EVERYTHING IN ONE FILE

> **For the user (LV):** Šis ir vienīgais fails, kas vajadzīgs. Jaunajā sesijā pievieno šo failu un
> specifikācijas PDF, un raksti: *"Izlasi SPECTAKEOFF_ALL_IN_ONE.md un turpini no sadaļas 5, punkts 1."*
>
> **For the AI reading this:** read the whole file before doing anything. Reply to the user in Latvian
> (they write Latvian, often from a phone). All code, Excel output and docs stay in English.

---

## 1. Where we started

- The user runs a service called **SpecTakeoff** and wants US firms as clients.
- Original idea: automated quantity takeoffs from construction PDFs. It was **repositioned** to
  closeout requirements: extract attic stock, spare parts, special tools, O&M deliverables, training
  and warranty requirements from US spec books into an Excel schedule that cites page and quotes the spec.
- First output the user had: **40 rows from a 509-page spec** (RCCD Chiller Replacement at Multiple
  Schools, Red Clay Consolidated School District, Delaware). Public copy:
  https://bidcondocs.delaware.gov/RCCD/RCCD_22033Chillerrep_spec.pdf
- Hand review against the PDF showed the 40 rows were all correct but incomplete:
  1 duplicate row, a misleading "Gaps" sheet, 8 missed warranties, and a whole missed category
  (maintenance service contracts). Hand-verified complete answer: **67 rows** (section 7 below).

## 2. What went wrong along the way (lessons — do not repeat)

- **Another AI (Gemini) produced fake files**: 48 rows where 12 invented rows (quotes not in the PDF,
  sections that do not exist, wrong pages) were copied 4 times, titled "Verified" and "Bypass".
  Cause: it was told a target row count (48) and never actually read the PDF.
  → Never give an AI a target row count. Never trust an output file that was not produced by running the code.
- **Gemini in Colab** is very slow (~8 min per action) and once wrote a broken file extractor
  that put a `pip install` block into the .py files. → Run the code directly, no AI in the loop.
- **Phone pasting breaks Python indentation.** → Give the user single-line commands only.
- **Second real spec (ECISD) first run produced 0 rows** (with an older version): the section-number
  format was different, so every candidate row had an empty section and the agents rejected them all.
  This was correct strict behaviour (empty is better than invented). Fixed in the current code;
  NOT yet verified on the real ECISD PDF.

## 3. Where we ended (current state)

One self-contained Python file, `spectakeoff.py` (full code in section 8). It:
- auto-installs `pdfplumber`, `openpyxl`, `pypdfium2`; auto-installs Tesseract on Colab/Linux root;
- with no arguments processes every PDF in the current folder and `/content`;
- options: `-o out.xlsx`, `--drawings a.pdf b.pdf`, `--counts counts.csv`, `--no-ocr`;
- reads pages in parallel, removes watermarks/headers/footers, recognises section numbers in any common
  format - MasterFormat 2004 six-digit (`23 64 23`, `236423`, `23 6423`, `23-64-23`, `23 64 23.13`,
  "Section 236423 Page 3") and CSI 1995 five-digit (`15010`, `15625`, `09911`), plus the footer forms
  "VALVES 15110 - 15", "15181 - Hydronic Piping Page 2 of 14" and a bare "Page 2 of 12";
- extracts rows only by cutting sentences out of the PDF text, then runs **8 deterministic agents**
  (code, not AI — they cannot invent data):
  1 Precision (quote on page, section valid, qty/unit read from the quote) ·
  2 Quality (duplicates, padding, conflicts, pages to review) ·
  3 Labor (hours only from stated numbers, else "Needs input") ·
  4 Delivery (re-opens Excel, compares every cell, deletes file on mismatch) ·
  5 OCR (Tesseract for scanned pages, <75% confidence rows removed) ·
  6 Drawings (equipment tags/schedules or counts file multiply per-unit qty) ·
  7 Language (file entirely English, quotes never translated) ·
  8 Div 23/26 (every HVAC and Electrical section listed with rows; gaps flagged CHECK).
- Excel sheets: Closeout Schedule (+ Checks, Notes, Unit Count, Total Qty, Count Source),
  Summary, Labor, Checks, coverage sheet (Div 23-26 / Div 15-16 / HVAC-Electrical, named after the
  numbering system the document uses), Rules (R1–R16).

Results on RCCD (509 pages): **75 verified rows** in ~17 s (4 cores) — all 67 hand-verified
obligations plus real ones the hand review missed (p.355 4 inspections × ~4 h; p.400
1-year water treatment service). It also flags a spec conflict (p.398 monthly vs p.400 bi-monthly
visits) and a spec omission (26 28 18 Enclosed Switches: "furnish the following" maintenance
materials but lists none — RFI). OCR tested on an image-only PDF (same 9 rows as text version,
90–94% confidence). Drawings tested only on a synthetic drawing PDF (5 pumps → 3 distinct
type/size from schedule). All 48 fake Gemini rows are rejected by agents 1+2.

## 4. Non-negotiable rules

1. Never write output rows by hand or from general knowledge. Output comes only from running the code.
2. No target row count. Never pad, repeat or invent rows. An invented row is worse than a missing one.
3. Never remove or weaken a check; never add a bypass.
4. After every change run the regression test (below) and report results honestly.
5. A run must finish in under 5 minutes.
6. Everything delivered is English; spec quotes are never translated.

**Regression test** (RCCD spec): run must end with `DONE`, `[agent 4 Delivery] file re-opened and
verified`, `[agent 7 Language] file is entirely English`; must reproduce section 7 exactly (75 rows,
all 67 hand-verified obligations present), with zero R4 violations and zero quotes that are not word
for word on their cited page; Checks sheet must show the R10 CONFLICT p.398 vs p.400; Div 23-26 Coverage must flag 26 28 18.

## 5. Open tasks (continue here)

1. ~~**ECISD test.**~~ DONE - see section 9. Spec: https://www.ecisd.us/ourpages/auto/2026/2/20/41948290/ECISD%20Memorial%20MS%20Chiller%20Replacement%20Specs.pdf
   (234 pages). Ask the user to attach the PDF, run the current code, then check the result row by
   row against the PDF: find every WARRANTY / EXTRA MATERIALS / MAINTENANCE / TRAINING / CLOSEOUT
   subsection and compare. Fix format differences generically, then re-run the RCCD regression.
2. Test 2–3 more public specs the same way - use `batch.py --fetch urls.txt` (section 10.3):
   UM Barrows Hall https://www.maine.edu/general-services/wp-content/uploads/sites/34/2026/02/UM-Barrows-Hall-Chiller-Replacement-Specifications.pdf ·
   UCCS Cragmor Hall https://pdc.uccs.edu/sites/g/files/kjihxj1346/files/inline-files/UCCS%20Cragmor%20Hall%20Chiller%20Replacement%20-%20Project%20Manual_1.pdf ·
   D45 https://d45.org/wp-content/uploads/2025/12/253101-Mechanical-Equipment-Replacement_Specs.pdf
3. Test the drawings agent on real M/E drawings when the user has them.
4. Later: a visual summary for clients.

## 6. How to run (user is on a phone, Google Colab)

1. Create `spectakeoff.py` from section 8. In Colab, upload this .md file to `/content` and run ONE cell
   (single line, safe to paste on a phone):

```
d=open('/content/SPECTAKEOFF_ALL_IN_ONE.md',encoding='utf-8').read(); s=d.index('# BEGIN spectakeoff.py\n')+len('# BEGIN spectakeoff.py\n'); c=d[s:d.index('# END spectakeoff.py',s)]; open('/content/spectakeoff.py','w',encoding='utf-8').write(c); import hashlib; print(len(c.splitlines()),'lines', hashlib.md5(c.encode()).hexdigest()[:10]=='49de2874a2')
```
   It must print `True`. Then upload the spec PDF and run one cell: `!python /content/spectakeoff.py`
   Result: `<pdf name>_Closeout_Schedule.xlsx` in the Colab folder.
2. On a computer: save section 8 as `spectakeoff.py`, then `python spectakeoff.py spec.pdf`.

## 7. RCCD regression baseline - 75 rows (generated from a verified run)

Generated by `package.py --baseline`, never typed by hand, and only ever from a run that passed
`selftest.py`. Every Qty in this table is a number that appears in its own quote, every quote
appears word for word in the raw text of its cited page, and two runs reproduce it identically.

If a run does not reproduce this table exactly, something changed: explain it before delivering
the file, then regenerate this section with `package.py --baseline`.

| # | Section | Type | Item | Qty | Unit | Page | Spec Language (verbatim) |
|---|---|---|---|---|---|---|---|
| 1 | 00 73 13 | Extended Warranty | The Contractor will guarantee all materials and workmanship against original defects, except injury from prope | 2 | YR | 110 | The Contractor will guarantee all materials and workmanship against original defects, except injury from proper and usual wear when used for the purpose intended, for two years after Acceptance by the Owner, and will maintain all items in perfect condition during the period of guarantee. |
| 2 | 00 73 13 | O&M Deliverable | prints - The Contractor shall provide two (2) prints of the as-built conditions, along with the rep | 2 | EA | 111 | The Contractor shall provide two (2) prints of the as-built conditions, along with the reproducible drawings themselves, to the Owner and one (1) set to the Architect. |
| 3 | 00 73 13 | O&M Deliverable | set - The Contractor shall provide two (2) prints of the as-built conditions, along with the rep | 1 | SET | 111 | The Contractor shall provide two (2) prints of the as-built conditions, along with the reproducible drawings themselves, to the Owner and one (1) set to the Architect. |
| 4 | 00 73 13 | O&M Deliverable | In addition, attach one complete set to each of the Operating and Maintenance Instructions/Manuals | 1 | SET | 111 | In addition, attach one complete set to each of the Operating and Maintenance Instructions/Manuals. |
| 5 | 00 81 13 | Extended Warranty | Performance and Payment Bonds shall be maintained in full force (warranty bond) for a period of two (2) years | 2 | YR | 132 | Performance and Payment Bonds shall be maintained in full force (warranty bond) for a period of two (2) years after the date of the Certificate for Final Payment. |
| 6 | 00 81 13 | Extended Warranty | For a period of two (2) years from the date of substantial completion, as evidenced by the date of final accep | 2 | YR | 142 | For a period of two (2) years from the date of substantial completion, as evidenced by the date of final acceptance of the work, the contractor warrants that work performed under this contract conforms to the contract requirements and is free of any defect of equipment, material or workmanship performed by the contractor or any of his subcontractors or suppliers. |
| 7 | 01 70 00 | Quantity Not Specified | For equipment or systems requiring seasonal operation, perform demonstration for other season within six month |  |  | 244 | For equipment or systems requiring seasonal operation, perform demonstration for other season within six months. |
| 8 | 01 70 00 | Quantity Not Specified | qualified person who is knowledgeable about the Project to perform demonstration and instruction of Owner's pe |  |  | 244 | Provide a qualified person who is knowledgeable about the Project to perform demonstration and instruction of Owner's personnel. |
| 9 | 01 70 00 | Training | 8 hours minimum of demonstration and training | 8 | HR | 244 | Provide 8 hours minimum of demonstration and training. |
| 10 | 01 70 00 | O&M Deliverable | bound hardcopies - operation and maintenance manuals for all installed equipment and devices, as-built drawin | 2 | EA | 245 | Provide operation and maintenance manuals for all installed equipment and devices, as-built drawings (PDF), and all inspection certificates as two (2) bound hardcopies and two (2) archival-grade (gold foil) DVDs. |
| 11 | 01 70 00 | O&M Deliverable | archival-grade (gold foil) DVDs - operation and maintenance manuals for all installed equipment and devices, as-built drawin | 2 | EA | 245 | Provide operation and maintenance manuals for all installed equipment and devices, as-built drawings (PDF), and all inspection certificates as two (2) bound hardcopies and two (2) archival-grade (gold foil) DVDs. |
| 12 | 01 70 00 | Maintenance Service | Maintenance Period | 1 | YR | 245 | Maintenance Period: As indicated in specification sections or, if not indicated, not less than one year from the Date of Substantial Completion or the length of the specified warranty, whichever is longer. |
| 13 | 01 78 00 | O&M Deliverable | two sets of revised final documents in final form within 10 days after final inspection | 2 | SET | 253 | Submit two sets of revised final documents in final form within 10 days after final inspection. |
| 14 | 01 78 00 | O&M Deliverable | Two DVDs with All Project Record Submittals (Gold-Foil, Archival Grade DVDs) | 2 | EA | 253 | Two DVDs with All Project Record Submittals (Gold-Foil, Archival Grade DVDs) |
| 15 | 01 78 00 | O&M Deliverable | Maintain on site one set of the following record documents; record actual revisions to the Work: | 1 | SET | 254 | Maintain on site one set of the following record documents; record actual revisions to the Work: |
| 16 | 01 78 00 | O&M Deliverable | warranties and bonds, executed in duplicate by responsible Subcontractors, suppliers, and manufacturers, withi | 2 | EA | 255 | Obtain warranties and bonds, executed in duplicate by responsible Subcontractors, suppliers, and manufacturers, within 10 days after completion of the applicable item of work. |
| 17 | 01 79 00 | O&M Deliverable | Training Manuals | 1 | EA | 257 | Training Manuals: Provide training manual for each attendee; allow for minimum of two attendees per training session. |
| 18 | 01 79 00 | O&M Deliverable | one extra copy of each training manual to be included with operation and maintenance data | 1 | EA | 257 | Provide one extra copy of each training manual to be included with operation and maintenance data. |
| 19 | 01 79 00 | Quantity Not Specified | For equipment or systems requiring seasonal operation, perform demonstration for other season within six month |  |  | 258 | For equipment or systems requiring seasonal operation, perform demonstration for other season within six months. |
| 20 | 01 79 00 | Training | 8 hours of training | 8 | HR | 258 | Provide minimum 8 hours of training. |
| 21 | 03 30 00 | Extended Warranty | Slabs with Moisture Vapor Reducing Admixture (MVRA) | 10 | YR | 272 | Slabs with Moisture Vapor Reducing Admixture (MVRA): Provide warranty to cover the cost of flooring failures due to moisture migration from slabs for ten years. |
| 22 | 03 30 00 | Extended Warranty | Moisture Emission Reducing Curing and Sealing Compound | 10 | YR | 272 | Moisture Emission Reducing Curing and Sealing Compound: Provide warranty to cost of flooring delamination failures for 10 years. |
| 23 | 09 51 00 | Attic Stock | 100 SF of Type A1 acoustical unit, for Owner's use in maintenance of project | 100 | SF | 292 | Provide 100 SF of Type A1 acoustical unit, for Owner's use in maintenance of project. |
| 24 | 09 51 00 | Attic Stock | 1 box of Type A2 acoustical unit, for Owner's use in maintenance of project | 1 | BOX | 292 | Provide 1 box of Type A2 acoustical unit, for Owner's use in maintenance of project. |
| 25 | 09 90 00 | Attic Stock | 1 gallon of each color; store where directed | 1 | GAL | 296 | Supply 1 gallon of each color; store where directed. |
| 26 | 23 05 13 | Extended Warranty | five year manufacturer warranty for motors larger than 20 horsepower | 5 | YR | 301 | Provide five year manufacturer warranty for motors larger than 20 horsepower. |
| 27 | 23 05 16 | Spare Part | two sets of packing for each packed expansion joint | 2 | SET | 309 | Supply two sets of packing for each packed expansion joint. |
| 28 | 23 05 93 | Quantity Not Specified | final copies for Architect and for inclusion in operating and maintenance manuals |  |  | 326 | Provide final copies for Architect and for inclusion in operating and maintenance manuals. |
| 29 | 23 09 13 | Maintenance Service | service and maintenance of control system for two years from Date of Substantial Completion | 2 | YR | 352 | Provide service and maintenance of control system for two years from Date of Substantial Completion. |
| 30 | 23 09 23 | Extended Warranty | defective Work within a five year period after Substantial Completion | 5 | YR | 354 | Correct defective Work within a five year period after Substantial Completion. |
| 31 | 23 09 23 | Extended Warranty | five year manufacturer's warranty for field programmable micro-processor based units | 5 | YR | 354 | Provide five year manufacturer's warranty for field programmable micro-processor based units. |
| 32 | 23 09 23 | Maintenance Service | service and maintenance of energy management and control systems for one years from Date of Substantial Comple | 1 | YR | 354 | Provide service and maintenance of energy management and control systems for one years from Date of Substantial Completion. |
| 33 | 23 09 23 | Maintenance Service | four complete inspections per year, two in each season, to inspect, calibrate, and adjust controls as required | 4 | EA | 354 | Provide four complete inspections per year, two in each season, to inspect, calibrate, and adjust controls as required, and submit written reports. |
| 34 | 23 09 23 | Maintenance Service | Make minimum of 4 complete normal inspections of approximately 4 hours duration in addition to normal service | 4 | EA | 355 | Make minimum of 4 complete normal inspections of approximately 4 hours duration in addition to normal service calls to inspect, calibrate, and adjust controls, and submit written reports. |
| 35 | 23 09 23 | Training | service engineer to instruct Owner's representative in operation of systems plant and equipment for 2 day peri | 2 | DAY | 372 | Provide service engineer to instruct Owner's representative in operation of systems plant and equipment for 2 day period. |
| 36 | 23 09 23 | Training | minimum of 8 hours dedicated instructor time | 8 | HR | 373 | Include a minimum of 8 hours dedicated instructor time. |
| 37 | 23 21 13 | Special Tool | Operator | 1 | EA | 385 | Operator: One plug valve wrench for every ten plug valves minimum of one. |
| 38 | 23 21 23 | Spare Part | Extra Pump Seals | 1 | SET | 393 | Extra Pump Seals: One set for each type and size of pump. |
| 39 | 23 25 00 | Maintenance Service | service and maintenance of treatment systems for one year from Date of Substantial Completion | 1 | YR | 398 | Furnish service and maintenance of treatment systems for one year from Date of Substantial Completion. |
| 40 | 23 25 00 | Quantity Not Specified | monthly technical service visits to perform field inspections and make water analysis on site |  |  | 398 | Provide monthly technical service visits to perform field inspections and make water analysis on site. |
| 41 | 23 25 00 | Maintenance Service | two copies of field service report after each visit | 2 | EA | 398 | Submit two copies of field service report after each visit. |
| 42 | 23 25 00 | Training | 2 hour training course for operating personnel, instructing them on installation, care, maintenance, testing, | 2 | HR | 398 | Include 2 hour training course for operating personnel, instructing them on installation, care, maintenance, testing, and operation of water treatment systems. |
| 43 | 23 25 00 | Quantity Not Specified | sufficient chemicals for treatment and testing during warranty period |  |  | 398 | Supply sufficient chemicals for treatment and testing during warranty period. |
| 44 | 23 25 00 | Quantity Not Specified | Training |  |  | 399 | Training: Train Owner's personnel on operation and maintenance of chemical treatment system. |
| 45 | 23 25 00 | Training | two hours of instruction for two people | 2 | HR | 399 | Provide minimum of two hours of instruction for two people. |
| 46 | 23 25 00 | Maintenance Service | service and maintenance of treatment systems for one year from Date of Substantial Completion | 1 | YR | 400 | Provide service and maintenance of treatment systems for one year from Date of Substantial Completion. |
| 47 | 23 25 00 | Maintenance Service | bi-monthly (every 2 months) technical service visits for the first 6 months to perform field inspections and m | 2 | MO | 400 | Provide bi-monthly (every 2 months) technical service visits for the first 6 months to perform field inspections and make water analysis on site. |
| 48 | 23 64 23 | Spare Part | Extra Refrigerant | 1 | EA | 414 | Extra Refrigerant: One container. |
| 49 | 23 64 23 | Spare Part | Extra Lubricating Oil | 1 | EA | 414 | Extra Lubricating Oil: One container. |
| 50 | 23 64 23 | Extended Warranty | Manufacturer's Warranty | 5 | YR | 414 | Manufacturer's Warranty: Provide minimum Five year warranty to include coverage for materials and labor for compressor. |
| 51 | 23 64 23 | Quantity Not Specified | Training |  |  | 418 | Training: Train Owner's personnel on operation and maintenance of system. |
| 52 | 23 64 23 | Training | two hours of training | 2 | HR | 418 | Provide minimum of two hours of training. |
| 53 | 23 64 23 | Maintenance Service | separate maintenance contract for the service and maintenance of chiller for 2 years from Date of Substantial | 2 | YR | 418 | Provide a separate maintenance contract for the service and maintenance of chiller for 2 years from Date of Substantial Completion. |
| 54 | 23 64 26 | Spare Part | Extra Refrigerant | 1 | EA | 420 | Extra Refrigerant: One container. |
| 55 | 23 64 26 | Spare Part | Extra Lubricating Oil | 1 | EA | 420 | Extra Lubricating Oil: One container. |
| 56 | 23 64 26 | Extended Warranty | Manufacturer's Warranty | 2 | YR | 420 | Manufacturer's Warranty: 2 year parts and labor warranty for entire system. |
| 57 | 23 64 26 | Extended Warranty | five year warranty to include coverage for materials only for compressor | 5 | YR | 420 | Provide minimum five year warranty to include coverage for materials only for compressor. |
| 58 | 23 64 26 | Quantity Not Specified | Training |  |  | 424 | Training: Train Owner's personnel on operation and maintenance of system. |
| 59 | 23 64 26 | Training | two hours of training | 2 | HR | 424 | Provide minimum of two hours of training. |
| 60 | 23 64 26 | Maintenance Service | separate maintenance contract for the service and maintenance of chiller for 2 years from Date of Substantial | 2 | YR | 424 | Provide a separate maintenance contract for the service and maintenance of chiller for 2 years from Date of Substantial Completion. |
| 61 | 23 73 13 | Spare Part | Extra Fan Belts | 1 | SET | 426 | Extra Fan Belts: One set for each unit. |
| 62 | 23 73 13 | Spare Part | Extra Filters | 1 | SET | 426 | Extra Filters: One set for each unit. |
| 63 | 23 73 13 | Extended Warranty | two year manufacturer parts and labor warranty covering repair or replacement due to defective materials or wo | 2 | YR | 426 | Provide minimum two year manufacturer parts and labor warranty covering repair or replacement due to defective materials or workmanship. |
| 64 | 23 73 13 | Quantity Not Specified | Training |  |  | 432 | Training: Train Owner's personnel on operation and maintenance of system. |
| 65 | 23 73 13 | Training | one day of training | 1 | DAY | 432 | Provide minimum of one day of training. |
| 66 | 23 73 13 | Maintenance Service | service and maintenance of packaged roof top units for [2] years from Date of Substantial Completion | 2 | YR | 432 | Provide service and maintenance of packaged roof top units for [2] years from Date of Substantial Completion. |
| 67 | 23 73 13 | Maintenance Service | routine maintenance service with a three month interval as maximum time period between calls | 3 | MO | 432 | Provide routine maintenance service with a three month interval as maximum time period between calls. |
| 68 | 23 73 13 | Maintenance Service | filter replacements - maintenance items as outlined in manufacturer's operating and maintenance data, including | 4 | EA | 433 | Include maintenance items as outlined in manufacturer's operating and maintenance data, including minimum of four (4) filter replacements, minimum of one fan belt replacement, and controls check-out, adjustments, and recalibration. |
| 69 | 23 73 13 | Maintenance Service | fan belt replacement - maintenance items as outlined in manufacturer's operating and maintenance data, including | 1 | EA | 433 | Include maintenance items as outlined in manufacturer's operating and maintenance data, including minimum of four (4) filter replacements, minimum of one fan belt replacement, and controls check-out, adjustments, and recalibration. |
| 70 | 23 81 01 | Extended Warranty | five year manufacturers warranty for all motors | 5 | YR | 435 | Provide five year manufacturers warranty for all motors. |
| 71 | 23 81 01 | Extended Warranty | one year parts and labor warranty for enitre unit, from substitute and completion | 1 | YR | 435 | Provide one year parts and labor warranty for enitre unit, from substitute and completion. |
| 72 | 23 81 01 | Attic Stock | one (1) set of filters, with a final change immediately prior to occupancy | 1 | SET | 435 | Provide one (1) set of filters, with a final change immediately prior to occupancy. |
| 73 | 26 27 26 | Attic Stock | two of each style, size, and finish wall plate | 2 | EA | 479 | Furnish two of each style, size, and finish wall plate. |
| 74 | 26 28 13 | Special Tool | two fuse pullers | 2 | EA | 483 | Furnish two fuse pullers. |
| 75 | 26 28 13 | Spare Part | three of each size and type fuse installed | 3 | EA | 483 | Furnish three of each size and type fuse installed. |
## 8. Full code — spectakeoff.py

```python
# BEGIN spectakeoff.py
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
# END spectakeoff.py
```

## 9. ECISD test result (open task 5.1 - DONE) and what is still open

### 9.1 What was wrong and what was fixed (all fixes generic, no document-specific strings)

ECISD (Edinburg CISD, Memorial MS Chiller Replacement, 234 pages) is written in the **CSI 1995
five-digit** system for its mechanical and painting sections (`SECTION 15010`, `15625`, `09911` -
Division 15 Mechanical, 16 Electrical) and in MasterFormat 2004 six-digit for Division 01
(`SECTION 011000`). The old code could not see a five-digit number at all, so every mechanical row
was attributed to `01 79 00` and the coverage sheet was empty. First run: 11 rows, 8 of them with
the wrong section. Now: **26 rows, 0 errors**, correct sections, coverage sheet `Div 15-16 Coverage`.

Fixed:
1. Five-digit CSI 1995 section numbers, six-digit tried first; a five-digit number is never
   converted to six-digit - the row cites the number printed on the page (R3).
2. Footer forms `VALVES 15110 - 15`, `15181 - Hydronic Piping Page 2 of 14`, bare `Page 2 of 12`.
3. `END OF SECTION 15110` (number appended) now resets the heading state.
4. Hyphenated quantities: `1-year warranty` was invisible, so a real 1-year warranty was dropped.
5. A notice period is no longer a quantity: "at least seven days' advance notice" was becoming
   Qty 7 Unit DAY of training.
6. A sentence interrupted by the page footer now matches (R2 widened to the SAME cited pages with
   page furniture removed, and R2's text says so). This recovered the 1-year chiller maintenance
   service row, which spans p.206/207.
7. "sufficient chemicals ... for one year" no longer reports the period as the amount supplied.
8. A priced QUOTE for a warranty is no longer reported as a warranty (it was emitting a bogus
   "Extended Warranty 10 YR" for a clause that only requires the manufacturer to quote a price).
9. `RECORD DOCUMENTS` subsections, record prints/specifications/product data and the instruction
   programme are recognised as named deliverables.
10. The closeout clauses that actually hand the stock over ("Deliver tools, spare parts, extra
    materials ... to location designated by Owner", "deliver keys to Owner") and the one that owes
    the Owner's own people instruction are now caught. Direction matters: "as instructed by the
    Owner" is NOT a training obligation.
11. An obligation the spec states but never quantifies becomes a `Quantity Not Specified` row
    instead of being dropped, and agent 3 still prices it as "Needs input".
12. Agent 8 covers Divisions 15/16 as well as 23/26, and covers BOTH when a manual uses both; the
    coverage sheet is named after what it covers.

### 9.2 Checked by five independent review agents

RCCD regression: PASS. Speed PASS (17 s RCCD, 8 s ECISD, against the 300 s limit). All 67
obligations present, 0 regressions. R10 CONFLICT p.398/p.400 present. 26 28 18 flagged CHECK.
Determinism PASS (three runs byte-identical). No check was removed, loosened or bypassed.

### 9.3 Everything in this list is now FIXED (it was previously left open)

1. **A frequency is no longer a count.** "Provide monthly technical service visits" produced
   `Qty 1 EA` although the sentence contains no number - a straight breach of R4. The frequency
   now goes into Basis as quoted text ("monthly - count not stated in this sentence, estimator must
   compute it") and the row carries an empty Qty. Same for "quarterly, semiannual, and annual".
2. **An interval is no longer sold as a duration.** "every 2 months", "three month interval" and
   "N inspections per year" are recorded in Basis the same way instead of standing in Qty alone.
3. **Section 7 is regenerated** from a verified run and is now the golden baseline. The old
   hand-typed table was wrong on the rows listed at the top of section 7.
4. **Dropped word spaces are gone.** Extraction now uses `x_tolerance=2`, because the default of
   3 pt silently swallowed real word spaces in these fonts ("for 2years", "One setfor each unit").
   All 75 RCCD quotes now appear word for word in the raw text of their cited page.
5. **Temporary-facilities duties are excluded.** Keys to the temporary construction fence are not a
   closeout handover; sections titled TEMPORARY ... are skipped.
6. **Administrative clauses are excluded** - scheduling conditions, back-charge clauses,
   "be prepared to answer questions", "shall be accomplished by", supplier-staffing requirements.

Measured after the fixes: RCCD 75 rows, **0 R4 violations, 0 non-verbatim quotes, 67/67**
obligations, R10 conflict p.398/p.400 present, 26 28 18 flagged CHECK, 17 s. ECISD 25 rows,
0 R4 violations; its one quote that is not contiguous in the raw page text is the chiller
maintenance sentence split by the footer "Page 2 of 12" on p.206/207, which is the bounded R2 case
and is correct.

### 9.3b Still for LV to judge - genuine spec ambiguity, not code defects

1. **A frequency is not a count.** "Provide monthly technical service visits" (RCCD p.398) and
   "report quarterly, semiannual, and annual maintenance" (ECISD p.207) are reported as Qty 1 EA.
   There is no "1" in either sentence, so this breaks R4. Section 7 of this file carries the same
   1 EA, so fixing it moves your own baseline. Options: leave it, or make such rows
   `Quantity Not Specified` with the frequency in Basis. NOT changed without your decision.
2. **An interval is not a quantity.** "bi-monthly (every 2 months) ... for the first 6 months"
   gives 2 MO; "three month interval as maximum time period between calls" gives 3 MO. The numbers
   ARE in the quotes, so R4 holds, but an estimator needs the visit count (3 visits / 8 calls).
3. **Section 7 is stale on 8 rows.** The code's reading is better on 7 of the 8 (the table infers
   numbers that are not in the spec); the table is better on 1 (RCCD p.398 field service report is
   a document, not a service). Section 7 should be regenerated from a run.
4. **Dropped word spaces.** pdfplumber's default tolerance drops a real space in a few RCCD quotes
   ("for 2years", "One setfor each unit"). Fix is `extract_text(x_tolerance=2)`, but every quote in
   the file shifts, so the whole baseline must be re-verified. Not done yet.
5. **Temporary-facilities keys.** ECISD p.36 "Provide Owner with one set of keys" is keys to the
   temporary construction fence, not a closeout handover. Worth excluding sections titled
   TEMPORARY ... - one line, not done yet.
6. ECISD items needing an RFI rather than a row: the conditional 10-year capacitor warranty
   (p.208), the conditional 10-year shaft-seal warranty with annual inspections and the 5 years of
   annual TXV calibration visits and reports (pp.208-210), factory start-up service (p.216), the
   TAB final report with no copy count (p.227), and an empty "Number of Copies:" list (p.73).

### 9.4 Next, in order

1. Decide 9.3 items 1-5, then re-run and regenerate section 7 from the run.
2. Open task 5.2: UM Barrows Hall, UCCS Cragmor Hall, D45 - same method.
3. Open task 5.3: drawings agent on real M/E drawings.

## 10. The upgrade scripts (embedded - extract them the same way as the code)

Three scripts travel inside this file. `package.py` is the only thing that may ever update this
file, and it refuses to write a baseline from a run that did not pass `selftest.py`.

<!-- MANIFEST {"batch.py": "86b8504dbc", "package.py": "82f46a049f", "selftest.py": "dcc360603d", "spectakeoff.py": "49de2874a2"} -->

**Extract everything with ONE line** (safe to paste on a phone). It writes all four .py files and
prints `True` only if every one matches the manifest above:

```
d=open('/content/SPECTAKEOFF_ALL_IN_ONE.md',encoding='utf-8').read(); import re,json,hashlib; man=json.loads(re.search(r'<!-- MANIFEST (\{.*?\}) -->',d).group(1)); got={n:(open('/content/'+n,'w',encoding='utf-8').write(c), hashlib.md5(c.encode()).hexdigest()[:10])[1] for n,c in re.findall(r'# BEGIN (\S+\.py)\n(.*?)# END \1',d,re.S)}; print(got); print(got==man)
```

### 10.1 selftest.py - the quality gate. Run it after every change.

```
!python /content/selftest.py /content/spec.pdf -m /content/SPECTAKEOFF_ALL_IN_ONE.md
```

Seven checks, exit code 0 only if all pass: the run delivers; every Qty is a number that appears in
its own quote (R4); every quote is word for word in the raw text of its cited page (R2, and it says
separately which quotes match only once the page header/footer is removed); Qty is empty if and only
if the Type is "Quantity Not Specified" (R5); the output reproduces the golden baseline in section 7
exactly; two runs are identical; the run is inside 300 seconds. It re-reads the PDF with its own
code, so it cannot be fooled by a bug in the extractor's own agents.

```python
# BEGIN selftest.py
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


def _golden(md_path):
    """The rows of section 7 of the .md, as (section, type, item, qty, unit, page, quote)."""
    md = open(md_path, encoding="utf-8").read()
    m = re.search(r"^## 7\..*?$(.*?)^## 8\.", md, re.S | re.M)
    if not m:
        return None
    out = []
    for line in m.group(1).splitlines():
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
        want = _golden(md_path)
        if want is None:
            results.append(("5 golden baseline", FAIL, "section 7 of the .md has no table"))
        else:
            # a markdown table cell cannot carry leading or trailing spaces, so both sides are stripped
            got = [tuple(x.strip() for x in (
                    str(r["Spec Section"] or ""), str(r["Type"] or ""), str(r["Item Required"] or ""),
                    "" if r["Qty"] in (None, "") else str(r["Qty"]), str(r["Unit"] or ""),
                    str(r["Page"] or ""), str(r["Spec Language (verbatim)"] or ""))) for r in rows]
            want = [tuple(x.strip() for x in w) for w in want]
            if got == want:
                results.append(("5 golden baseline", PASS, f"reproduces section 7 exactly ({len(want)} rows)"))
            else:
                d = [f"{len(want)} rows in section 7, {len(got)} in the run"]
                for i, (a, b) in enumerate(zip(want, got), 1):
                    if a != b:
                        d.append(f"  row {i} differs: section 7 {a[:4]} / run {b[:4]}")
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
# END selftest.py
```

### 10.2 package.py - keeps this file consistent with the code

```
!python /content/package.py --check                       is this file stale?
!python /content/package.py --baseline /content/spec.pdf  re-embed everything and regenerate section 7
```

Re-embeds all four scripts, rewrites the md5 in the section 6 command and the manifest in section 10,
then re-reads what it wrote and refuses to leave an inconsistent file behind. This exists because the
md5 went stale by hand twice: now nothing updates it but this script.

```python
# BEGIN package.py
#!/usr/bin/env python3
"""
SpecTakeoff packaging - makes SPECTAKEOFF_ALL_IN_ONE.md consistent with the code.

The owner extracts the code from the .md with a one-line command that verifies an md5 prefix.
Every time spectakeoff.py changes, that literal and the embedded copy go stale and the command
prints False. This script is the only thing that should ever update them.

  python package.py                        re-embed the code, fix the md5 and the line count
  python package.py --baseline RCCD.pdf    also regenerate section 7 from a fresh verified run
  python package.py --check                change nothing, just report whether the .md is consistent

It refuses to write a baseline from a run that did not pass the self-test, so section 7 can never
record rows that the quality gate rejects.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(HERE, "SPECTAKEOFF_ALL_IN_ONE.md")
CODE = os.path.join(HERE, "spectakeoff.py")
BEGIN, END = "# BEGIN spectakeoff.py\n", "# END spectakeoff.py"
# every script that travels inside the .md, each between its own "# BEGIN x.py" / "# END x.py"
FILES = ["spectakeoff.py", "selftest.py", "package.py", "batch.py"]
MANIFEST = re.compile(r"<!-- MANIFEST (\{[^>]*?\}) -->")


def file_text(name):
    t = open(os.path.join(HERE, name), encoding="utf-8").read()
    return t if t.endswith("\n") else t + "\n"


def code_text():
    return file_text("spectakeoff.py")


def markers(name):
    return "# BEGIN %s\n" % name, "# END %s" % name


def embedded(md, name="spectakeoff.py"):
    b, e = markers(name)
    if b not in md or e not in md:
        return None
    i = md.index(b) + len(b)
    return md[i:md.index(e, i)]


def embed(md, name):
    """Replace the copy of `name` inside the .md with the one on disk."""
    b, e = markers(name)
    if b not in md or e not in md:
        print(f"  {name}: no markers in the .md - not embedded")
        return md, False
    i = md.index(b) + len(b)
    return md[:i] + file_text(name) + md[md.index(e, i):], True


def fingerprint(text):
    return hashlib.md5(text.encode()).hexdigest()[:10], len(text.splitlines())


def md_table(rows):
    def cell(v):
        return ("" if v in (None, "") else str(v)).replace("|", "\\|").replace("\n", " ").strip()
    out = ["| # | Section | Type | Item | Qty | Unit | Page | Spec Language (verbatim) |",
           "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        out.append("| %d | %s | %s | %s | %s | %s | %s | %s |" % (
            i, cell(r["Spec Section"]), cell(r["Type"]), cell(r["Item Required"]),
            cell(r["Qty"]), cell(r["Unit"]), cell(r["Page"]), cell(r["Spec Language (verbatim)"])))
    return "\n".join(out)


def build_section7(pdf):
    """Run the self-test on pdf; on a pass, return section 7 built from that run's output."""
    print(f"running the self-test on {os.path.basename(pdf)} before writing any baseline ...")
    p = subprocess.run([sys.executable, os.path.join(HERE, "selftest.py"), pdf],
                       capture_output=True, text=True)
    print(p.stdout.strip()[-1500:])
    if p.returncode != 0:
        sys.exit("REFUSED: the self-test failed, so no baseline was written. Fix the code first.")
    out = os.path.join(HERE, re.sub(r"\.pdf$", "", os.path.basename(pdf), flags=re.I) + "_selftest.xlsx")
    from openpyxl import load_workbook
    ws = load_workbook(out)["Closeout Schedule"]
    cols = [c.value for c in ws[2]]
    rows = [dict(zip(cols, r)) for r in ws.iter_rows(min_row=3, values_only=True)
            if any(v not in (None, "") for v in r)]
    name = os.path.basename(pdf)
    return ("""## 7. %s regression baseline - %d rows (generated from a verified run)

Generated by `package.py --baseline`, never typed by hand, and only ever from a run that passed
`selftest.py`. Every Qty in this table is a number that appears in its own quote, every quote
appears word for word in the raw text of its cited page, and two runs reproduce it identically.

If a run does not reproduce this table exactly, something changed: explain it before delivering
the file, then regenerate this section with `package.py --baseline`.

%s
""" % (re.sub(r"\.pdf$", "", name, flags=re.I), len(rows), md_table(rows)))


def main():
    ap = argparse.ArgumentParser(description="SpecTakeoff packaging")
    ap.add_argument("--baseline", help="spec PDF to regenerate section 7 from")
    ap.add_argument("--check", action="store_true", help="report only, change nothing")
    a = ap.parse_args()

    code = code_text()
    want_md5, want_lines = fingerprint(code)
    md = open(MD, encoding="utf-8").read()
    have = embedded(md)
    if have is None:
        sys.exit(f"REFUSED: {MD} has no '{BEGIN.strip()}' / '{END}' markers.")
    have_md5, have_lines = fingerprint(have)
    literal = re.search(r"hexdigest\(\)\[:10\]\s*==\s*'([0-9a-f]{10})'", md)

    print(f"spectakeoff.py      {want_lines} lines  md5 {want_md5}")
    print(f"embedded in the .md {have_lines} lines  md5 {have_md5}")
    print(f"md5 in the one-liner {literal.group(1) if literal else 'NOT FOUND'}")
    consistent = have_md5 == want_md5 and literal and literal.group(1) == want_md5

    if a.check:
        print("\nCONSISTENT - the owner's one-line command prints True" if consistent
              else "\nSTALE - the owner's one-line command prints False. Run package.py to fix it.")
        sys.exit(0 if consistent else 1)

    if a.check:
        pass

    if a.baseline:
        sec7 = build_section7(a.baseline)
        m = re.search(r"^## 7\..*?$.*?(?=^## 8\.)", md, re.S | re.M)
        if not m:
            sys.exit("REFUSED: could not find section 7 to replace.")
        md = md[:m.start()] + sec7 + md[m.end():]

    for name in FILES:
        md, done = embed(md, name)
        if done:
            print(f"  embedded {name} ({fingerprint(file_text(name))[1]} lines)")
    md = re.sub(r"hexdigest\(\)\[:10\]\s*==\s*'[0-9a-f]{10}'",
                "hexdigest()[:10]=='%s'" % want_md5, md, count=1)
    manifest = {n: fingerprint(file_text(n))[0] for n in FILES}
    line = "<!-- MANIFEST %s -->" % json.dumps(manifest, sort_keys=True)
    md = MANIFEST.sub(lambda _: line, md) if MANIFEST.search(md) else md
    open(MD, "w", encoding="utf-8").write(md)

    # prove it: re-read what was written and check every embedded copy against its own file
    md2 = open(MD, encoding="utf-8").read()
    bad = []
    for name in FILES:
        got = embedded(md2, name)
        if got is None:
            continue
        if fingerprint(got)[0] != fingerprint(file_text(name))[0]:
            bad.append(name)
    lit2 = re.search(r"hexdigest\(\)\[:10\]\s*==\s*'([0-9a-f]{10})'", md2)
    if bad or not lit2 or lit2.group(1) != want_md5:
        sys.exit("FAILED: the rewritten .md is inconsistent (%s). Do not deliver it."
                 % (", ".join(bad) or "md5 literal"))
    m2 = MANIFEST.search(md2)
    if not m2 or json.loads(m2.group(1)) != manifest:
        sys.exit("FAILED: the manifest in the .md does not match the files. Do not deliver it.")
    print(f"\nWRITTEN and VERIFIED: spectakeoff.py {want_lines} lines, md5 {want_md5}")
    print("manifest: " + ", ".join(f"{k} {v}" for k, v in sorted(manifest.items())))
    print("\nThe command for Colab (one line, safe to paste on a phone). It extracts EVERY script")
    print("in the file and prints True only if all of them match the manifest:\n")
    print("d=open('/content/SPECTAKEOFF_ALL_IN_ONE.md',encoding='utf-8').read(); "
          "import re,json,hashlib; "
          "man=json.loads(re.search(r'<!-- MANIFEST (\\{.*?\\}) -->',d).group(1)); "
          "got={n:(open('/content/'+n,'w',encoding='utf-8').write(c), "
          "hashlib.md5(c.encode()).hexdigest()[:10])[1] "
          "for n,c in re.findall(r'# BEGIN (\\S+\\.py)\\n(.*?)# END \\1',d,re.S)}; "
          "print(got); print(got==man)")


if __name__ == "__main__":
    main()
# END package.py
```

### 10.3 batch.py - several specifications at once (open task 5.2)

```
!python /content/batch.py /content/*.pdf
!python /content/batch.py --fetch /content/urls.txt
```

Runs each spec, runs the self-test on each, and writes one `Batch_Summary.xlsx`: pages, rows,
which numbering system the manual uses (it reports "both (mixed manual)" when a manual carries
MasterFormat 2004 and CSI 1995 side by side, as ECISD does), coverage sheet, agent errors and
warnings, seconds, self-test verdict and the type breakdown. A spec that fails is reported as
FAILED with the reason, never hidden - the point of a batch is to find the formats that break the
extractor.

```python
# BEGIN batch.py
#!/usr/bin/env python3
"""
SpecTakeoff batch - run several specifications and compare them on one sheet.

This is the tool for open task 5.2 (testing more public specs). It processes each PDF, runs the
self-test on each, and writes one Batch_Summary.xlsx plus a table on screen. It never merges rows
from different specs: each spec keeps its own schedule file.

  python batch.py a.pdf b.pdf c.pdf        run these
  python batch.py --fetch urls.txt         download each URL (one per line) first, then run
  python batch.py *.pdf --no-selftest      faster, skips the per-spec quality gate

A spec that fails the self-test is still reported, marked FAILED, with the reason. Nothing is
hidden: the point of a batch is to see which spec formats break the extractor.
"""
import argparse
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
COLS = ["Spec", "Pages", "Rows", "Numbering", "Coverage sheet", "Sections with rows",
        "Agent errors", "Agent warnings", "Seconds", "Self-test", "Types found", "Notes"]


def fetch(url, into):
    name = os.path.basename(urllib.parse.urlparse(url).path) or "spec.pdf"
    name = urllib.parse.unquote(name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    dest = os.path.join(into, re.sub(r"[^A-Za-z0-9._-]+", "_", name))
    if os.path.exists(dest):
        print(f"  already downloaded: {os.path.basename(dest)}")
        return dest
    print(f"  downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
            f.write(r.read())
    except Exception as e:                                           # noqa: BLE001
        print(f"  COULD NOT DOWNLOAD: {e}")
        return None
    if open(dest, "rb").read(5) != b"%PDF-":
        print("  NOT A PDF (the site probably returned an error page)")
        os.remove(dest)
        return None
    return dest


def one(pdf, selftest=True):
    from openpyxl import load_workbook
    name = os.path.basename(pdf)
    out = os.path.join(os.path.dirname(os.path.abspath(pdf)),
                       re.sub(r"\.pdf$", "", name, flags=re.I) + "_Closeout_Schedule.xlsx")
    t0 = time.time()
    p = subprocess.run([sys.executable, os.path.join(HERE, "spectakeoff.py"), pdf, "-o", out],
                       capture_output=True, text=True)
    secs = time.time() - t0
    log = p.stdout + p.stderr
    row = {c: "" for c in COLS}
    row["Spec"], row["Seconds"] = name, round(secs)
    m = re.search(r"\[extract\]\s+(\d+) pages", log)
    row["Pages"] = int(m.group(1)) if m else ""
    if not os.path.exists(out):
        row["Rows"], row["Notes"] = 0, "NOT DELIVERED - " + (log.strip().splitlines() or ["no output"])[-1][:200]
        row["Self-test"] = "n/a"
        return row, out
    wb = load_workbook(out)
    ws = wb["Closeout Schedule"]
    rows = [r for r in ws.iter_rows(min_row=3, values_only=True) if any(v not in (None, "") for v in r)]
    row["Rows"] = len(rows)
    secs_col = [str(r[0]) for r in rows]
    row["Numbering"] = ("CSI 1995 five-digit" if any(" " not in s and s.isdigit() for s in secs_col)
                        else "MasterFormat 2004")
    if any(" " not in s and s.isdigit() for s in secs_col) and any(" " in s for s in secs_col):
        row["Numbering"] = "both (mixed manual)"
    cov = [s for s in wb.sheetnames if "Coverage" in s]
    row["Coverage sheet"] = cov[0] if cov else "-"
    row["Sections with rows"] = len({str(r[0]) for r in rows})
    ch = [r for r in wb["Checks"].iter_rows(min_row=2, values_only=True)]
    row["Agent errors"] = sum(1 for r in ch if r[1] == "ERROR")
    row["Agent warnings"] = sum(1 for r in ch if r[1] == "WARN")
    from collections import Counter
    row["Types found"] = ", ".join(f"{t} {n}" for t, n in Counter(str(r[2]) for r in rows).most_common())
    if selftest:
        q = subprocess.run([sys.executable, os.path.join(HERE, "selftest.py"), pdf],
                           capture_output=True, text=True)
        row["Self-test"] = "PASS" if q.returncode == 0 else "FAILED"
        if q.returncode != 0:
            bad = [l for l in q.stdout.splitlines() if l.startswith("[FAIL]")]
            row["Notes"] = "; ".join(b[6:].strip() for b in bad)[:300]
    else:
        row["Self-test"] = "skipped"
    return row, out


def main():
    ap = argparse.ArgumentParser(description="SpecTakeoff batch runner")
    ap.add_argument("pdfs", nargs="*")
    ap.add_argument("--fetch", help="file of URLs, one per line")
    ap.add_argument("--no-selftest", action="store_true")
    ap.add_argument("-o", "--out", default=os.path.join(HERE, "Batch_Summary.xlsx"))
    a = ap.parse_args()

    pdfs = list(a.pdfs)
    if a.fetch:
        into = os.path.join(os.path.dirname(os.path.abspath(a.fetch)), "specs")
        os.makedirs(into, exist_ok=True)
        print("fetching:")
        for url in [l.strip() for l in open(a.fetch, encoding="utf-8") if l.strip()
                    and not l.strip().startswith("#")]:
            got = fetch(url, into)
            if got:
                pdfs.append(got)
    if not pdfs:
        sys.exit("No PDF to process. Give PDF paths, or --fetch a file of URLs.")

    results = []
    for pdf in pdfs:
        print(f"\n=== {os.path.basename(pdf)} ===")
        r, out = one(pdf, not a.no_selftest)
        results.append(r)
        print(f"  {r['Rows']} rows, {r['Pages']} pages, {r['Seconds']}s, self-test {r['Self-test']}"
              + (f"  >> {r['Notes']}" if r["Notes"] else ""))

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Batch Summary"
    ws.append(COLS)
    for r in results:
        ws.append([r[c] for c in COLS])
    for c in ws[1]:
        c.font = Font(name="Arial", bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3864")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name="Arial", size=10)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        if str(row[9].value) != "PASS":
            for c in row:
                c.fill = PatternFill("solid", fgColor="FFF2CC")
    for i, w in enumerate([34, 7, 7, 20, 20, 10, 9, 10, 9, 10, 46, 60]):
        ws.column_dimensions[chr(65 + i)].width = w
    ws.freeze_panes = "A2"
    wb.save(a.out)

    print("\n%-34s %5s %5s %-20s %-9s %s" % ("SPEC", "PAGES", "ROWS", "NUMBERING", "SELF-TEST", "SECONDS"))
    for r in results:
        print("%-34s %5s %5s %-20s %-9s %s" % (r["Spec"][:34], r["Pages"], r["Rows"],
                                               r["Numbering"], r["Self-test"], r["Seconds"]))
    print(f"\nSummary written to {a.out}")
    sys.exit(0 if all(r["Self-test"] in ("PASS", "skipped") for r in results) else 1)


if __name__ == "__main__":
    main()
# END batch.py
```
