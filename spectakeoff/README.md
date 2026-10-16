# SpecTakeoff 4.0

Auditējama būvniecības specifikāciju, rasējumu un attēlu apstrāde ar rezultātu Excel failā.
Katrai atrastajai vērtībai ir avota fails, lapa, apgabals lapā un oriģinālais citāts.
**Nekas netiek sertificēts kā pareizs** — visi atradumi nonāk cilvēka pārbaudes rindā.

## Kas jauns 4.0 versijā

| Joma | 3.1 | 4.0 |
|---|---|---|
| Struktūra | viens 340 rindu skripts | Python pakotne (`src/spectakeoff`), CLI, 41 automātiskais tests |
| Ievade | tikai PDF | PDF + attēli (PNG, JPG, TIFF ar vairākām lapām, WEBP, BMP) |
| Lapas tipa noteikšana | nav | specifikācijas teksts / vektoru rasējums / rastra rasējums / skenēts teksts / foto / tukša |
| Vektoru PDF rasējumi | apstrādāti kā teksts | precīzs teksts ar koordinātām tieši no PDF, bez OCR |
| Rastra rasējumi | pilnas lapas OCR → līnijas nolasītas kā burti | teksta augstuma noteikšana, palielināšana, līniju (arī izometrisko) noņemšana, teksta rindu meklēšana, OCR 0° un 90°, trokšņa filtrs |
| Nesalasāmi marķējumi | pazuda vai kļuva par "atkritumu" tekstu | tiek atrasti un uzrādīti kā "nesalasāms marķējums U1…" ar atrašanās vietu pārbaudei |
| Marķējumi | nav | tērauda profili (W, HSS, L, IPE, HEB, PL…), skrūves (A325, M20…), metinājumi, iekārtu marķējumi (AHU-1…), izmēri, augstuma atzīmes, atsauces (3/A501), skaita piezīmes ((4), 4 PLACES, 6 GAB.) |
| Tabulas | nav | tabulu/grafiku rindas ar galveni, daudzumu un marķējumu |
| Aprēķini (R8) | nav | `Aprēķini` lapa: daudzums uz vienību × **pārbaudīts** skaits (Excel formula); rasējumu skaits tiek rādīts tikai kā nepārbaudīts pierādījums |
| Pretrunas (R10) | nav | vienā sadaļā+kategorijā dažādi daudzumi → `CONFLICT` |
| Pārbaudes attēli | nav | katrai rastra/rasējuma lapai PNG ar iekrāsotiem apgabaliem (zaļš = kandidāts, oranžs = pārbaudīt, sarkans = nesalasāms) |
| Excel validācija | tikai kandidātu lapa | katra datu lapa, katra šūna; teksts, kas sākas ar `=`, netiek pārvērsts par formulu |
| Lokalizācija | nav | `--lang lv` / `en` (lapas, galvenes, statusi); citāti nekad netiek tulkoti |
| Precizitātes mērīšana | nav | `spectakeoff eval` — recall/precision pret cilvēka pārbaudītu etalonu |

Laboti 3.1 defekti: `%` daudzums nekad netika atrasts; jebkura rinda, kas sākas ar 3–4 cipariem,
tika uzskatīta par sadaļu; Excel kļūda ar vadības rakstzīmēm; Tesseract rindas no dažādām
rindkopām tika savienotas; daudzums "one spare filter **set**" netika atrasts.

## Instalēšana

```bash
cd spectakeoff
python -m pip install -e .            # vai: pip install -r requirements.txt
# OCR programma un valodas (Ubuntu/Debian):
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-lav
```

Windows: instalē Tesseract (UB Mannheim instalators) un pievieno to `PATH`.

## Lietošana

```bash
# viens fails -> fails_SpecTakeoff_v4.xlsx blakus avotam
spectakeoff projekts.pdf

# viss projekts vienā darbgrāmatā (specifikācija + rasējumi + foto), latviski
spectakeoff spec.pdf rasejumi.pdf foto.jpg -o projekts.xlsx --lang lv

# OCR vairākās valodās
spectakeoff skenejums.pdf --ocr-lang eng+lav

# R8 aprēķini ar tāmētāja pārbaudītu skaitu
spectakeoff spec.pdf -o projekts.xlsx --counts skaits.csv
```

`skaits.csv`:

```csv
item,count,verified_by,source
air handling unit,4,J. Bērziņš,M-101 grafiks
pump,6,J. Bērziņš,P-201
```

Rindas bez `verified_by` tiek ignorētas — nepārbaudīts skaits nekad netiek reizināts.

### Valodas modeļa pārbaude (`--llm`, pēc izvēles)

```bash
pip install -e .[llm]  # vienreiz: Anthropic SDK
spectakeoff key        # vienreiz: ielīmē atslēgu (sk-ant-api03-…), tā tiek pārbaudīta un saglabāta
                       # ~/.config/spectakeoff/api_key (tikai tev lasāma); --status, --remove
spectakeoff projekts.pdf --llm                              # claude-opus-5-5
spectakeoff projekts.pdf --llm --llm-model claude-haiku-5-5 # ~40x lētāk
```

Palielina pārklājumu: modelim tiek sūtīti **tikai** teikumi, kurus noteikumi neatrada, bet kuros ir
pienākuma vārds/saraksta punkts un dokumenta lietvārds (ne veselas lapas). 80 teikumi vienā
pieprasījumā, atbilde ir tikai "jā" rindu numuri; atbildes tiek kešotas
(`~/.cache/spectakeoff/llm_cache.json`), atkārtota palaišana ir bez maksas. Citāts vienmēr ir
oriģinālais teikums. Modeļa atradumi ir statusā PĀRBAUDĪT ar piezīmi. Aptuveni FAA 727 lapām:
~95k ievades tokenu (≈ $0,6 ar Opus 5.5, ≈ $0,02 ar Haiku 5.5). **Teksts tiek nosūtīts Anthropic** —
konfidenciāliem dokumentiem tikai ar klienta atļauju. Tokenu patēriņš ir `*.run_report.json` laukā `llm`.
Šajā vidē API atslēgas nebija, tāpēc reālais pārklājuma pieaugums vēl nav izmērīts — izmēri ar
`spectakeoff label` / `eval`.

### Izvade

* `projekts.xlsx` — lapas: Kopsavilkums, Prasības, Rasējumu teksts, Rasējumu marķējumi, Tabulas,
  Aprēķini, Pārbaudes rinda, Lapu audits, Sadaļu pārklājums, Noteikumi, Metodika un ierobežojumi
* `projekts_review/` — pārbaudes attēli katrai rasējuma/attēla lapai
* `projekts.findings.json` — visi atradumi mašīnlasāmā formā (integrācijām, `eval`)
* `projekts.run_report.json` — izpildes atskaite

### Precizitātes mērīšana uz saviem dokumentiem (etalons)

Precizitāti var godīgi izmērīt tikai tad, ja cilvēks atzīmē **visas** prasības dažās lapās —
ne tikai programmas atrastās. Tam ir divas komandas:

```bash
# 1) izveido Excel ar katru teikumu/saraksta punktu 20 nejaušās lapās
spectakeoff label projekts.pdf --sample 20 -o etalons.xlsx
#    (vai konkrētas lapas: --pages 3,7-9)

# 2) atver etalons.xlsx, kolonnā "Prasība?" izvēlies Jā / Nē / ? katrai rindai, saglabā

# 3) izmēra (programma pati atkārtoti apstrādā tos pašus PDF; tiem jābūt tajā pašā mapē)
spectakeoff eval etalons.xlsx
```

Rezultāts: recall (cik no īstajām prasībām atrastas) un precision (cik no atrastajām ir pareizas)
ar 95% ticamības intervālu, un `etalons_eval.xlsx` ar lapām *Palaistas garām* un
*Kļūdaini atrastas*. Lapas, kur kaut viena rinda nav atzīmēta, netiek vērtētas. Lapā *Instrukcija*
ir definīcija, kas skaitās "Jā". 20 lapas ≈ 400–500 rindas ≈ 1–1,5 h darba.

Vecais formāts (CSV ar `source,page,kind,text`) joprojām darbojas:
`spectakeoff eval projekts.findings.json etalons.csv`.

## Precizitātes mērījumi (publiskas specifikācijas)

### Pilnībā atzīmētas lapas (recall + precision) — godīgākais mērījums

Katrā kopā **katrs** teikums izvēlētajās lapās atzīmēts Jā/Nē. Kopas "neredzēts" tika izveidotas
pēc noteikumu iesaldēšanas, un rezultāts pierakstīts **pirms** jebkādiem labojumiem.

| Kārta | Lapas | Noteikumi | Recall (atrastas īstās) | Precision (pareizas atrastās) |
|---|---|---|---|---|
| 1. FAA izlase | 20 | pirms labojumiem | **44%** (4/9) | 100% (4/4) |
| 2. FAA + jauni UFGS (neredzēts) | 30 | iesaldēti `c69ad0c` | **40%** (6/15) | 86% (6/7) |
| 3. FAA + jauni UFGS (neredzēts) | 30 | iesaldēti `6befdab` | **60%** (3/5) | 100% (3/3) |

Pēc katras kārtas kļūdas tika labotas pēc **veida** (nevis rindas), un tagad visas 5 atzīmētās kopas
(95 lapas, 29 īstās prasības) dod 28/29 atrastas, 0 kļūdainu — bet tas ir **pēc** noregulēšanas uz
tām pašām lapām, tāpēc tas nav neatkarīgs skaitlis. Neatkarīgie skaitļi ir tabulā augstāk: pārklājums
uz jaunām lapām līdz šim bijis 40–60%, precizitāte 86–100%; paraugi ir mazi (5–15 prasības kārtā),
tāpēc ticamības intervāli ir plaši.

Galvenais secinājums: **precizitāte ir augsta, pārklājums ir vājā vieta.** Noteikumu pieeja katrā
jaunā dokumentā atrod jaunus formulējumus, ko tā nepazīst. Pirms klientam sola konkrētu skaitli,
jāizmēra ar `spectakeoff label` / `eval` uz klienta paša dokumentu tipa.

### Izvilkto rindu pārbaude (tikai precision)

Katra izvilktā rinda pārbaudīta (pareiza / kļūdaina / apšaubāma; apšaubāmās nevērtē):

| Kopa | Lapas | Pareizas | Zināmas kļūdainas, kas vēl tiek izvilktas |
|---|---|---|---|
| FAA AC 150/5370-10H | 727 | 246 | 0 no 58 |
| UFGS 01 78 00, 23 05 93, 26 20 00 | 168 | 121 | 0 no 37 |
| UFGS 22 00 00, 08 71 00 | 152 | 21 | 0 no 1 |

Atkārtot visu: `python benchmarks/run_benchmarks.py` (PDF tiek lejupielādēti no faa.gov un wbdg.org).
Marķējumu veicis Claude (AI), nevis tāmētājs; vairākas paša marķējuma kļūdas pārbaudes gaitā atrastas
un atklāti izlabotas.

Labotie kļūdu veidi (visiem ir regresijas testi):

| Kļūda | Piemērs |
|---|---|
| Atslēgvārds vārda iekšienē (bija arī v3) | "air-en**training** admixtures" → "training" |
| Atslēgvārds citā nozīmē | "bank certificates of deposit", "bid guarantee", "spare conduits", "one spare auxiliary contact" |
| Noliegumi / skaidrojumi | "…shall **not** be interpreted as a basis for final acceptance", "makes **no guarantee**" |
| Uzstādīšanas instrukcijas nav nodošanas dokuments | "…in (strict) accordance with the manufacturer's instructions" |
| Redaktora piezīmes | UFGS `NOTE:` un FAA "Notes to the Engineer" blokos starp `****` rindām (arī pāri lapām, `****.`, `] ****`) |
| Atsauces uz citām sadaļām | "…in accordance with ⏎ Section 01 33 00 SUBMITTAL PROCEDURES" vairs nemaina sadaļu |
| Virsraksti kā prasības | "90-10 Construction warranty.", "20-10 Bid guarantee." |
| UFGS iesniegumu saraksti netika lasīti | SD-06/07/09/10/11 vienumi (As-Built Drawings, O&M Manuals, testu atskaites) tagad ir prasības |
| Citāts nebija burtisks | "[_____]" beigu iekava tika nogriezta |
| Tabulas kā rasējumi, tukšas lapas OCR | FAA PWL tabula (93.–94. lpp.), "Page Intentionally Blank" |

Ātrums: FAA 727 lapas ~32 s; UFGS 168 lapas ~33 s.

## Kā darbojas rasējumu skenēšana

1. Lapa tiek klasificēta (balto pikseļu daļa, piesātinājums, garo līniju attiecība pret tinti).
2. Vektoru PDF rasējumiem teksts tiek nolasīts tieši no PDF — precīzi, ar koordinātām.
3. Rastra rasējumiem: tiek novērtēts burtu augstums un attēls palielināts līdz ~30 px burtiem;
   horizontālās, vertikālās un slīpās (izometriskās) līnijas tiek noņemtas; tiek atrastas teksta
   rindas; visas rindas tiek nolasītas vienā Tesseract izsaukumā (mozaīka, ~6× ātrāk);
   tas pats tiek atkārtots 90° pagriezienā vertikālajiem izmēriem.
4. Katrs vārds iziet filtru: konstrukciju marķējumu šabloni, vārdnīca (EN + LV), pārliecība.
   Šraffējums ("SS", "///") un līniju atliekas tiek noraidīti.
5. Apgabali, kas izskatās pēc teksta rindas, bet nav droši nolasāmi, tiek uzrādīti kā
   `nesalasāms marķējums U…` ar koordinātām — nevis uzminēti.

## Zināmās robežas (godīgi)

* **Foto**: 4.0 neskaita objektus (skrūves, sijas) no fotogrāfijām. Tika izmērīts, ka klasiskā
  attēlu apstrāde (Hough apļi, blob detektori, šablonu salīdzināšana) uz dotā tērauda mezgla foto
  atrod ~18 no ~40 skrūvēm ar daudz kļūdainiem trāpījumiem — tas nav lietojams. Foto tiek
  nosūtīts vizuālai pārbaudei. Uzticamai skaitīšanai nepieciešams apmācīts modelis un etalona dati.
* Pievienotā izometriskā rasējuma uzraksti nav īsti vārdi (piem. "ABSTRACT WIDSOUY") un ir
  ~6 px augsti — tie tiek atrasti un atzīmēti kā nesalasāmi (17 apgabali), bez izdomāta teksta.
* Simboli bez teksta (metinājumu simboli, iekārtu ikonas) netiek atpazīti.
* R9 (darbaspēka aprēķini) nav ieviests. R16 Division 23/26 pārbaude ir daļēja.
* OCR pārliecība ir Tesseract vārdu pārliecība, nevis pareizības procents.
* Prasību izvilkšana joprojām balstās uz noteikumiem (atslēgvārdi + teikuma struktūra), ne
  valodas modeli: neparasti formulējumi var tikt palaisti garām. Jauniem dokumentu tipiem
  (citas valstis, citas valodas) precizitāte jāmēra no jauna ar `spectakeoff eval`.
* Tulkošana (`--translate`) nosūta tekstu ārējam pakalpojumam; konfidenciāliem dokumentiem
  neizmantot bez atļaujas.

## Izstrāde

```bash
pip install -e .[dev]
pytest
```

Testi izmanto sintētisku rasējumu ar zināmiem pareizajiem uzrakstiem (`tests/synthetic.py`),
ģenerētu PDF ar specifikāciju, vektoru rasējumu, tabulu un skenētu lapu, kā arī abus
`examples/` attēlus.
