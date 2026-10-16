# Bāzes mērījums: tikai noteikumi (bez `--llm`)

Mērīts 2026-10-16 ar SpecTakeoff 4.0.0, komanda
`python benchmarks/run_benchmarks.py --cache <scratch>` (bez `--llm`, bez API izsaukumiem, izmaksas 0).
Ilgums ~4,5 min. OCR: Tesseract (eng).

## Pilnībā marķētās lapas (`gold_*.xlsx`) — recall un precision

| Etalons | Lapas | Īstās prasības | Atrastas | Recall (95% CI) | Precision (95% CI) |
|---|---|---|---|---|---|
| gold_faa_15pages_holdout | 15 | 3 | 2 | 66,7% (20,8–93,9%) | 100% (34,2–100%) |
| gold_faa_15pages_holdout3 | 15 | 3 | 3 | 100% (43,9–100%) | 100% (43,9–100%) |
| gold_faa_20pages | 20 | 9 | 9 | 100% (70,1–100%) | 100% (70,1–100%) |
| gold_ufgs_15pages_holdout | 15 | 12 | 12 | 100% (75,8–100%) | 100% (75,8–100%) |
| gold_ufgs_15pages_holdout3 | 15 | 2 | 2 | 100% (34,2–100%) | 100% (34,2–100%) |
| **Kopā** | 80 | 29 | 28 | **96,6%** | **100%** (0 kļūdainu rindu) |

Vienīgā palaistā garām prasība (gold_faa_15pages_holdout):
„Reinforced concrete pipe shall be inspected, evaluated, and reported on in accordance with ASTM C1840 …”

## Marķētās izvilktās rindas (CSV) — precision

| Etalons | Rindas | Īstās atrastas | Kļūdainās palikušas | Robežgadījumi (nevērtē) |
|---|---|---|---|---|
| faa_150-5370-10H_requirement_labels.csv | 278 | 246/246 | 0/58 | 32 |
| ufgs_requirement_labels.csv | 145 | 121/121 | 0/37 | 24 |
| ufgs_heldout_requirement_labels.csv | 24 | 21/21 | 0/1 | 3 |

CSV etaloni aptver tikai izvilktās rindas un ar roku atrastos izlaidumus, tāpēc tie nav pilns recall mērījums.

## Godīgi par ierobežojumiem

- Etaloni ir mazi (lielākajā daļā 2–12 prasību), ticamības intervāli ir plaši.
- Noteikumi tika pielāgoti, skatoties uz šiem pašiem etaloniem, tāpēc tie **nav neatkarīgs tests** — rezultāti, visticamāk, ir optimistiski.
- `--llm` salīdzinājums vēl nav izmērīts: sesijā nebija `ANTHROPIC_API_KEY`. Tas tiks pievienots `llm_results.md`.
  Palaist: `pip install -e .[llm]`, tad `python benchmarks/run_benchmarks.py --cache <scratch> --llm [--llm-model claude-haiku-5-5]` (~39 pieprasījumi, ~2 550 teikumi; rezultātos `llm_usage` rāda tokenus).
