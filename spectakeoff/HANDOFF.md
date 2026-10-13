# SpecTakeoff — session handoff

## To resume in a NEW session, paste this

> Read `spectakeoff/SPECTAKEOFF_ALL_IN_ONE.md` (the whole file, including section 9) and
> `spectakeoff/HANDOFF.md`. Continue from section 9.4.

Everything needed is in this folder. The container that produced it is gone; these files are the state.

## Files

| File | What it is |
|---|---|
| `SPECTAKEOFF_ALL_IN_ONE.md` | The single source of truth. Code embedded in section 8, ECISD result + open decisions in section 9. |
| `spectakeoff.py` | The code, 1497 lines, md5 `8363f6918c`. Identical to what is embedded in the .md. |
| `verify_rccd.py` | Matches a run's output against the 67 hand-verified RCCD rows in section 7. |
| `RCCD_Closeout_Schedule.xlsx` | Current RCCD output, 78 rows. |
| `ECISD_Closeout_Schedule.xlsx` | Current ECISD output, 26 rows. |

## The Colab one-liner now verifies

Section 6's command prints `True` again — the md5 literal was updated to `8363f6918c` and the
code in section 8 was re-embedded. Do not edit `spectakeoff.py` without re-embedding it and
recomputing that md5, or the owner's command prints `False`.

## State

- Open task 5.1 (ECISD) is DONE. 11 rows with 8 wrong sections → 26 rows, 0 errors, correct sections.
- RCCD regression PASSES: all 67 obligations present, 0 regressions, R10 conflict p.398/p.400,
  26 28 18 flagged CHECK, three runs byte-identical, 17 s against the 300 s limit.
- No check was removed, loosened or bypassed. Verified finding-by-finding against the pre-change code.
- RCCD is 78 rows, not 69: new rows come from the record-document, handover and unquantified-obligation
  catches. There is no target row count, so this is not a failure — but a few of them are weak
  (procedural sentences rather than deliverables) and are listed in section 9.3.

## Unfinished, and deliberately not decided alone

Section 9.3 lists six items that need the owner's call before the baseline moves again. The two
that matter most: a frequency ("monthly") and an interval ("every 2 months") are currently reported
as quantities, and section 7 of the .md is stale on 8 rows.

## Review agents used

Five independent agents checked this work: a verifier (re-verified every row straight from the
PDFs with its own code), a completeness agent (found what was missing from ECISD), a
regression + speed agent (67-row baseline, determinism, no weakened checks), a fixer, and a guard
(package consistency, rule compliance, scope). Their findings are folded into section 9.
