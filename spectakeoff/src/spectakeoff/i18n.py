"""Workbook localisation. Evidence quotes are never translated (R15)."""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "sheet.summary": "Summary",
        "sheet.requirements": "Requirements",
        "sheet.drawing_text": "Drawing Text",
        "sheet.tokens": "Drawing Tokens",
        "sheet.schedules": "Schedules",
        "sheet.calc": "Calculations",
        "sheet.review": "Review Queue",
        "sheet.pages": "Page Audit",
        "sheet.coverage": "Section Coverage",
        "sheet.rules": "Rules & Gates",
        "sheet.method": "Method & Limitations",
        "col.id": "ID", "col.source": "Source file", "col.page": "Page", "col.region": "Region (x0,y0,x1,y1)",
        "col.kind": "Kind", "col.category": "Category", "col.text": "Verbatim evidence",
        "col.value": "Value / quantity", "col.unit": "Unit", "col.tag": "Tag", "col.section": "Spec section",
        "col.section_title": "Section title", "col.division": "Division", "col.method": "Evidence method",
        "col.confidence": "OCR confidence", "col.status": "Review status", "col.flags": "Review flags",
        "col.translated": "Translated (not authoritative)", "col.sha": "Page SHA-256", "col.priority": "Priority",
        "col.page_kind": "Page type", "col.chars": "Characters", "col.images": "Embedded images",
        "col.regions": "Text regions", "col.accepted": "Accepted lines", "col.rejected": "Rejected OCR noise",
        "col.findings": "Findings", "col.warnings": "Warnings", "col.overlay": "Review image",
        "col.metric": "Metric", "col.v": "Value",
        "col.pages": "Pages", "col.hits": "Closeout keyword hits", "col.coverage": "Coverage status",
        "col.rule": "Rule", "col.required": "Requirement", "col.impl": "Implementation status",
        "col.topic": "Topic", "col.details": "Details",
        "col.req_id": "Requirement ID", "col.per_unit": "Per-unit qty", "col.counted_item": "Counted item",
        "col.verified_count": "Verified count", "col.count_source": "Count source", "col.total": "Total (formula)",
        "col.drawing_evidence": "Drawing/schedule evidence (unverified)",
        "status.CANDIDATE": "CANDIDATE", "status.REVIEW": "REVIEW", "status.CONFLICT": "CONFLICT",
        "kind.requirement": "Requirement", "kind.drawing_text": "Drawing text", "kind.token": "Token",
        "kind.schedule_row": "Schedule row", "kind.visual_review": "Visual review",
        "page.spec_text": "Spec text", "page.drawing_vector": "Drawing (vector PDF)",
        "page.drawing_raster": "Drawing (raster)", "page.photo": "Photograph", "page.scan_text": "Scanned text",
        "page.blank": "Blank",
    },
    "lv": {
        "sheet.summary": "Kopsavilkums",
        "sheet.requirements": "Prasības",
        "sheet.drawing_text": "Rasējumu teksts",
        "sheet.tokens": "Rasējumu marķējumi",
        "sheet.schedules": "Tabulas",
        "sheet.calc": "Aprēķini",
        "sheet.review": "Pārbaudes rinda",
        "sheet.pages": "Lapu audits",
        "sheet.coverage": "Sadaļu pārklājums",
        "sheet.rules": "Noteikumi",
        "sheet.method": "Metodika un ierobežojumi",
        "col.id": "ID", "col.source": "Avota fails", "col.page": "Lapa", "col.region": "Apgabals (x0,y0,x1,y1)",
        "col.kind": "Veids", "col.category": "Kategorija", "col.text": "Oriģinālais citāts",
        "col.value": "Vērtība / daudzums", "col.unit": "Mērvienība", "col.tag": "Marķējums",
        "col.section": "Specifikācijas sadaļa", "col.section_title": "Sadaļas nosaukums", "col.division": "Divīzija",
        "col.method": "Pierādījuma metode", "col.confidence": "OCR pārliecība", "col.status": "Pārbaudes statuss",
        "col.flags": "Pārbaudes piezīmes", "col.translated": "Tulkojums (nav saistošs)", "col.sha": "Lapas SHA-256",
        "col.priority": "Prioritāte", "col.page_kind": "Lapas tips", "col.chars": "Rakstzīmes",
        "col.images": "Iegultie attēli", "col.regions": "Teksta apgabali", "col.accepted": "Pieņemtās rindas",
        "col.rejected": "Noraidītais OCR troksnis", "col.findings": "Atradumi", "col.warnings": "Brīdinājumi",
        "col.overlay": "Pārbaudes attēls", "col.metric": "Rādītājs", "col.v": "Vērtība",
        "col.pages": "Lapas", "col.hits": "Atslēgvārdu trāpījumi", "col.coverage": "Pārklājuma statuss",
        "col.rule": "Noteikums", "col.required": "Prasība", "col.impl": "Ieviešanas statuss",
        "col.topic": "Tēma", "col.details": "Apraksts",
        "col.req_id": "Prasības ID", "col.per_unit": "Daudzums uz vienību", "col.counted_item": "Skaitāmā vienība",
        "col.verified_count": "Pārbaudīts skaits", "col.count_source": "Skaita avots",
        "col.total": "Kopā (formula)", "col.drawing_evidence": "Rasējuma/tabulas pierādījums (nepārbaudīts)",
        "status.CANDIDATE": "KANDIDĀTS", "status.REVIEW": "PĀRBAUDĪT", "status.CONFLICT": "PRETRUNA",
        "kind.requirement": "Prasība", "kind.drawing_text": "Rasējuma teksts", "kind.token": "Marķējums",
        "kind.schedule_row": "Tabulas rinda", "kind.visual_review": "Vizuāla pārbaude",
        "page.spec_text": "Specifikācijas teksts", "page.drawing_vector": "Rasējums (vektoru PDF)",
        "page.drawing_raster": "Rasējums (rastra)", "page.photo": "Fotogrāfija", "page.scan_text": "Skenēts teksts",
        "page.blank": "Tukša",
    },
}

SUPPORTED = tuple(STRINGS)


class Localizer:
    def __init__(self, lang: str = "en"):
        self.lang = lang if lang in STRINGS else "en"

    def __call__(self, key: str) -> str:
        return STRINGS[self.lang].get(key) or STRINGS["en"].get(key) or key
