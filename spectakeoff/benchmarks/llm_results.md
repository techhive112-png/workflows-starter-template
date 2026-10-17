# `--llm` salīdzinājums (Haiku 5.5)

Mērīts 2026-10-17 ar SpecTakeoff 4.0.0 un `claude-haiku-5-5`. Bāzes mērījums (tikai noteikumi) ir `baseline_results.md`. Tas pats OCR (Tesseract, eng), tie paši PDF avoti un tā pati vērtēšana.

Komanda:

```
python benchmarks/run_benchmarks.py --cache <scratch> --llm --llm-model claude-haiku-5-5
```

Mērītas divas prompta versijas (`PROMPT_VERSION` failā `src/spectakeoff/llm.py`):

- **v1** — sākotnējais prompts.
- **v2** — prompts saskaņots ar marķēšanas instrukciju (`labeling.py`): „Jā“ tikai nodošanas/closeout dokumentiem; apstiprināšanas iesniegumi (rasējumi, maisījumu receptes, kvalifikācijas), testu veikšana bez atskaites, virsraksti un ievadrindas ir „Nē“; šaubu gadījumā „Nē“.

## Pilnībā marķētās lapas (`gold_*.xlsx`) — recall un precision

| Etalons | Lapas | Īstās prasības | Recall: rules / v1 / v2 | Precision: rules / v1 / v2 | Kļūdainās rindas v1 → v2 |
|---|---|---|---|---|---|
| gold_faa_15pages_holdout | 15 | 3 | 66,7% / 100% / **100%** | 100% / 50,0% / **75,0%** (30,1–95,4%) | 3 → 1 |
| gold_faa_15pages_holdout3 | 15 | 3 | 100% / 100% / **100%** | 100% / 30,0% / **75,0%** (30,1–95,4%) | 7 → 1 |
| gold_faa_20pages | 20 | 9 | 100% / 100% / **100%** | 100% / 75,0% / **100%** (70,1–100%) | 3 → 0 |
| gold_ufgs_15pages_holdout | 15 | 12 | 100% / 100% / **100%** | 100% / 85,7% / **100%** (75,8–100%) | 2 → 0 |
| gold_ufgs_15pages_holdout3 | 15 | 2 | 100% / 100% / **100%** | 100% / 66,7% / **100%** (34,2–100%) | 1 → 0 |
| **Kopā** | 80 | 29 | 96,6% / 100% / **100%** | 100% / 64,4% / **93,5%** (29 / 31 rindas) | 16 → **2** |

LLM atrod vienīgo prasību, ko noteikumi palaiž garām (ASTM C1840, gold_faa_15pages_holdout).

Atlikušās 2 kļūdainās rindas (v2) ir tieši tie gadījumi, ko prompts jau liek noraidīt — Haiku ar `effort: low` tos tomēr pieņem:

- „The specimens shall be compacted and tested in accordance with ASTM D698 …“ (testa veikšana, nav atskaites);
- „Paper copies of design cross sections … will be issued to the successful bidder“ (pasūtītājs dod darbuzņēmējam).

## Marķētās izvilktās rindas (CSV) — precision

| Etalons | Rindas: rules / v1 / v2 | Īstās atrastas | Kļūdainās palikušas: rules / v1 / v2 | Precision v2 (marķētajām) |
|---|---|---|---|---|
| faa_150-5370-10H_requirement_labels.csv | 278 / 507 / 417 | 246/246 | 0 / 5 / **6** no 58 | 97,6% |
| ufgs_requirement_labels.csv | 145 / 307 / 274 | 121/121 | 0 / 4 / **0** no 37 | 100% |
| ufgs_heldout_requirement_labels.csv | 24 / 74 / 49 | 21/21 | 0 / 0 / **0** no 1 | 100% |

FAA dokumentā v2 joprojām atstāj 6 kļūdainas marķētas rindas (v1: 5). Papildu rindas, ko pievieno LLM, lielākoties CSV etalonā nav marķētas un nav vērtētas.

## Izmaksas (v2)

- 39 pieprasījumi; ~157 000 ievades un ~20 000 izvades tokenu visos etalonos kopā (v1: ~151 000 / ~33 000).
- Kļūdu nebija. Cena dolāros nav aprēķināta.

## Secinājums

- v2 prompts samazina kļūdainās rindas gold lapās no 16 uz 2 (precision 64,4% → 93,5%), recall paliek 100%.
- Bez `--llm` precision gold lapās ir 100%, bet recall 96,6%. Ar `--llm` (v2) recall ir 100%, bet precision 93,5%. Visas LLM rindas Excel failā ir atzīmētas „Found by the language model … verify against the page“, tāpēc tās jāpārbauda cilvēkam.
- `--llm` joprojām nav ieteicams ieslēgt pēc noklusējuma, ja kļūdaina rinda ir sliktāka par palaistu garām.
- Atlikušās kļūdas ir modeļa spriešanas kļūdas, nevis prompta nepilnības. Spēcīgāks modelis (`claude-opus-5-5`, noklusējums kodā) varētu tās novērst, bet tas nav izmērīts.

## Godīgi par ierobežojumiem

- **v2 nav neatkarīgs tests.** Prompts tika pārrakstīts pēc tam, kad bija redzamas v1 kļūdas šajos pašos etalonos. Izmaiņas atbilst marķēšanas instrukcijai, nevis konkrētiem teikumiem, bet rezultāts, visticamāk, ir optimistisks. Neatkarīgai pārbaudei vajag jaunu, iepriekš neredzētu marķētu etalonu.
- Etaloni ir mazi (2–12 prasību katrā), ticamības intervāli ir plaši.
- Mērīts tikai ar Haiku.
