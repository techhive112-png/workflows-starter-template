# SpecTakeoff — session handoff

## To resume in a NEW session, paste this

> Read `spectakeoff/SPECTAKEOFF_ALL_IN_ONE.md` (the whole file, including section 9) and
> `spectakeoff/HANDOFF.md`. Continue from section 9.4.

Everything needed is in this folder. The container that produced it is gone; these files are the state.

## Files

| File | What it is |
|---|---|
| `SPECTAKEOFF_ALL_IN_ONE.md` | The single source of truth. Code embedded in section 8, ECISD result + open decisions in section 9. |
| `spectakeoff.py` | The code, 1524 lines, md5 `0943655ad0`. Identical to what is embedded in the .md. |
| `verify_rccd.py` | Matches a run's output against the 67 hand-verified RCCD rows in section 7. |
| `RCCD_Closeout_Schedule.xlsx` | Current RCCD output, 75 rows. |
| `ECISD_Closeout_Schedule.xlsx` | Current ECISD output, 25 rows. |

## The Colab one-liner now verifies

Section 6's command prints `True` again — the md5 literal was updated to `0943655ad0` and the
code in section 8 was re-embedded. Do not edit `spectakeoff.py` without re-embedding it and
recomputing that md5, or the owner's command prints `False`.

## State

- Open task 5.1 (ECISD) is DONE. 11 rows with 8 wrong sections → 25 rows, 0 errors, correct sections.
- RCCD regression PASSES: all 67 obligations present, 0 regressions, R10 conflict p.398/p.400,
  26 28 18 flagged CHECK, three runs byte-identical, 17 s against the 300 s limit.
- No check was removed, loosened or bypassed. Verified finding-by-finding against the pre-change code.
- RCCD is 75 rows, not 69: new rows come from the record-document, handover and unquantified-obligation
  catches. There is no target row count, so this is not a failure — but a few of them are weak
  (procedural sentences rather than deliverables) and are listed in section 9.3.

## Quality measured, not asserted

| Check | Result |
|---|---|
| All 67 hand-verified RCCD obligations present | **67 / 67** |
| Qty values not readable from their own quote (R4) | **0** |
| Quotes not word-for-word on their cited page | **0** of 75 |
| R10 conflict p.398 vs p.400 | present on both rows |
| Section 26 28 18 flagged CHECK | yes |
| Three runs byte-identical | yes |
| Runtime against the 300 s limit | 17 s RCCD, 7 s ECISD |
| Checks removed, loosened or bypassed | none |

Section 7 of the .md is now the golden baseline, generated from a verified run. A run that does not
reproduce it exactly means something changed and must be explained before delivery.

Section 9.3b lists what is left, and none of it is a code defect: genuine spec ambiguity in ECISD
(conditional warranties, a factory start-up obligation, a TAB report with no copy count, an empty
"Number of Copies:" list) that needs an RFI to the design team, not a row.

## Review agents used

Five independent agents checked this work: a verifier (re-verified every row straight from the
PDFs with its own code), a completeness agent (found what was missing from ECISD), a
regression + speed agent (67-row baseline, determinism, no weakened checks), a fixer, and a guard
(package consistency, rule compliance, scope). Their findings are folded into section 9.
