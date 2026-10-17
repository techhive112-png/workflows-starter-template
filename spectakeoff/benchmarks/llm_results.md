# `--llm` salīdzinājums (Haiku 5.5)

Mērīts 2026-10-17 ar SpecTakeoff 4.0.0 un `--llm --llm-model claude-haiku-5-5`. Bāzes mērījums (tikai noteikumi) ir `baseline_results.md`. Tas pats OCR (Tesseract, eng), tie paši PDF avoti un tā pati vērtēšanas loģika (`evaluate` un `score` no `run_benchmarks.py`).

Palaišana: vienāda ar `run_benchmarks.py`, tikai ar `--llm --llm-model claude-haiku-5-5` katram izsaukumam. Repo skripts `run_benchmarks.py` pats `--llm` nepadod, tāpēc salīdzinājums tika palaists ar ārēju ietvara skriptu (nav iekļauts repo).

## Pilnībā marķētās lapas (`gold_*.xlsx`) — recall un precision

| Etalons | Lapas | Īstās prasības | Recall: rules → LLM | Precision: rules → LLM | Kļūdainās rindas (LLM) |
|---|---|---|---|---|---|
| gold_faa_15pages_holdout | 15 | 3 | 66,7% → **100%** (43,9–100%) | 100% → **50,0%** (18,8–81,2%) | 3 |
| gold_faa_15pages_holdout3 | 15 | 3 | 100% → 100% (43,9–100%) | 100% → **30,0%** (10,8–60,3%) | 7 |
| gold_faa_20pages | 20 | 9 | 100% → 100% (70,1–100%) | 100% → **75,0%** (46,8–91,1%) | 3 |
| gold_ufgs_15pages_holdout | 15 | 12 | 100% → 100% (75,8–100%) | 100% → **85,7%** (60,1–96,0%) | 2 |
| gold_ufgs_15pages_holdout3 | 15 | 2 | 100% → 100% (34,2–100%) | 100% → **66,7%** (20,8–93,9%) | 1 |
| **Kopā** | 80 | 29 | 96,6% → **100%** | 100% → **64,4%** (29 / 45 rindas) | **16** |

LLM atrada vienīgo prasību, ko noteikumi bija palaiduši garām (ASTM C1840, gold_faa_15pages_holdout). Visas pārējās 28 prasības bija atrastas arī bez LLM.

Kļūdainie LLM atradumi ir biežāk nekā prasības, piemēram: „Other sources shall be tested in accordance with ASTM C1602 prior to use.“ (atkārtoti), „The Contractor shall submit to the RPR…“ un UFGS iesniegumu saraksta virsraksti.

## Marķētās izvilktās rindas (CSV) — precision

| Etalons | Rindas: rules → LLM | Īstās atrastas | Kļūdainās palikušas: rules → LLM | Precision (marķētajām) |
|---|---|---|---|---|
| faa_150-5370-10H_requirement_labels.csv | 278 → 507 | 246/246 | 0/58 → **5/58** | 100% → 98,0% |
| ufgs_requirement_labels.csv | 145 → 307 | 121/121 | 0/37 → **4/37** | 100% → 96,8% |
| ufgs_heldout_requirement_labels.csv | 24 → 74 | 21/21 | 0/1 → 0/1 | 100% → 100% |

Rindu skaita palielināšanās nāk no LLM pārbaudes, kas FAA dokumentā pievienoja 230 atradumus. Lielākā daļa no tiem CSV etalonā nav marķēta, tāpēc tie nav vērtēti.

## Izmaksas un izpilde

- Izsaukumi: 39 pieprasījumi (Haiku), no tiem 2110 lēmumu keša ieraksti.
- Tokeni: ~151 000 ievades un ~33 000 izvades tokenu kopā visos avotos.
- Kļūdu nebija. Excel integritātes pārbaude izgāja, saturs nav sertificēts.
- Cena dolāros nav aprēķināta; atskaitē redzami tikai tokeni.

## Secinājums

- `--llm` ar Haiku nedaudz paaugstina recall (96,6% → 100% gold lapās), bet būtiski pazemina precision: gold lapās no 100% uz 64,4%, un marķētajos CSV parādās kļūdainas rindas, kas bāzes mērījumā nebija.
- Tā kā precision ir svarīgāka par recall (kļūdaina prasība ir sliktāka par palaistu garām), `--llm` **nevajadzētu** iespējot pēc noklusējuma. Ja to lieto, vajadzētu pārskatīt LLM atradumus pirms izmantošanas.
- Iespējams, labāks modelis (`claude-opus-5-5`) dotu augstāku precision, bet tas nav izmērīts un izmaksā vairāk.

## Godīgi par ierobežojumiem

- Etaloni ir mazi (2–12 prasību katrā), ticamības intervāli ir plaši, un 30–75% precision šajos izmēros nav droši.
- Ārējs skripts palaiž to pašu vērtēšanu ar `--llm`; tas nav iekļauts repo.
- LLM keša fails (`llm_cache.json`) ir ārpus repo.
