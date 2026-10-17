# `--llm` salīdzinājums (Haiku 5.5 un Opus 5.5)

Mērīts 2026-10-17 ar SpecTakeoff 4.0.0 un `claude-haiku-5-5`; Opus mērījums ir sadaļā „Opus 5.5 ar v2 promptu“. Bāzes mērījums (tikai noteikumi) ir `baseline_results.md`. Tas pats OCR (Tesseract, eng), tie paši PDF avoti un tā pati vērtēšana.

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

## Izmaksas (v2, Haiku)

- 39 pieprasījumi; ~157 000 ievades un ~20 000 izvades tokenu visos etalonos kopā (v1: ~151 000 / ~33 000).
- Kļūdu nebija. Cena dolāros nav aprēķināta.

## Opus 5.5 ar v2 promptu

Tā pati komanda ar `--llm-model claude-opus-5-5`.

| Mērījums | Tikai noteikumi | Haiku v2 | Opus v2 |
|---|---|---|---|
| Gold recall (29 prasības) | 96,6% (28) | 100% (29) | **96,6% (28)** |
| Gold precision | 100% (0 kļūdu) | 93,5% (2 kļūdas) | **100% (0 kļūdu)** |
| faa CSV kļūdainās no 58 | 0 | 6 | **1** (precision 99,6%) |
| ufgs CSV kļūdainās no 37 | 0 | 0 | **0** |
| ufgs_heldout CSV kļūdainās no 1 | 0 | 0 | **0** |
| Tokeni (ievade / izvade) | 0 | ~157 000 / ~20 000 | ~157 000 / ~700 |

Opus noraida abas Haiku kļūdas, bet noraida arī ASTM C1840 prasību („… shall be inspected, evaluated, and reported on in accordance with ASTM C1840“) — to pašu, ko palaiž garām noteikumi. Tāpēc gold lapās Opus v2 rezultāts ir tieši tāds pats kā bez `--llm`, un FAA CSV tas pievieno 1 kļūdainu rindu. Kļūdu API izsaukumos nebija.

## Secinājums

- Neviens izmērītais variants nedod 100% recall un 100% precision vienlaikus:
  - bez `--llm`: recall 96,6%, precision 100%;
  - Haiku v2: recall 100%, precision 93,5%;
  - Opus v2: recall 96,6%, precision 100% gold lapās (FAA CSV 99,6%).
- v2 prompts Haiku kļūdainās rindas gold lapās samazina no 16 uz 2.
- Ar Opus `--llm` šajos etalonos neko nepievieno, salīdzinot ar noteikumiem bez LLM, bet maksā tokenus.
- Ja svarīgāk nepalaist garām nevienu prasību, Haiku v2 ir labākais variants; tā rindas Excel failā ir atzīmētas „Found by the language model … verify against the page“, un tās jāpārbauda cilvēkam. Ja svarīgāka ir precizitāte, labāk lietot programmu bez `--llm`.
- `--llm` joprojām nav ieteicams ieslēgt pēc noklusējuma.

## Godīgi par ierobežojumiem

- **v2 nav neatkarīgs tests.** Prompts tika pārrakstīts pēc tam, kad bija redzamas v1 kļūdas šajos pašos etalonos. Izmaiņas atbilst marķēšanas instrukcijai, nevis konkrētiem teikumiem, bet rezultāts, visticamāk, ir optimistisks. Neatkarīgai pārbaudei vajag jaunu, iepriekš neredzētu marķētu etalonu.
- Etaloni ir mazi (2–12 prasību katrā), ticamības intervāli ir plaši.
- Atšķirība starp variantiem ir viena vai divas rindas; ar šādiem etaloniem tā nav statistiski droša.
