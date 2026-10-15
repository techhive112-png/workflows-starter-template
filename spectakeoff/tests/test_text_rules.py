from spectakeoff.patterns import (BOLT, COUNT_NOTE, DETAIL_REF, DIMENSION, EQUIPMENT_TAG, STEEL_SHAPE,
                                  find_tokens)
from spectakeoff.quality import judge_line
from spectakeoff.specs import (SectionState, classify, detect_section, division_of, extract_requirements,
                               quantity, split_spans)


def kinds(s):
    return [(t.kind, t.text) for t in find_tokens(s)]


def test_steel_bolt_tag_dimension_tokens():
    assert kinds("W12x26 BEAM") == [(STEEL_SHAPE, "W12x26")]
    assert kinds("HSS6x6x1/4") == [(STEEL_SHAPE, "HSS6x6x1/4")]
    assert kinds("IPE 200") == [(STEEL_SHAPE, "IPE 200")]
    assert kinds('(4) 3/4" A325 BOLTS') == [(BOLT, '(4) 3/4" A325 BOLTS')]
    assert kinds("M20x60 8.8") == [(BOLT, "M20x60 8.8")]
    assert kinds("M12x11.8") == [(STEEL_SHAPE, "M12x11.8")]       # AISC M-shape, not a bolt
    assert kinds("AHU-1") == [(EQUIPMENT_TAG, "AHU-1")]
    assert kinds("2'-6\"") == [(DIMENSION, "2'-6\"")]
    assert kinds("1200 mm") == [(DIMENSION, "1200 mm")]
    assert kinds("SEE 3/A501") == [(DETAIL_REF, "3/A501")]
    assert kinds("4 PLACES") == [(COUNT_NOTE, "4 PLACES")]
    assert find_tokens("ABSTRACT WIDSOUY") == []


def test_equipment_tag_value_is_normalised():
    (t,) = find_tokens("RTU 2")
    assert t.value == "RTU-2"


def test_hatch_noise_rejected_real_words_kept():
    assert not judge_line([("SS", 80), ("SS", 70)]).keep
    assert not judge_line([("'eA", 48)]).keep
    assert not judge_line([("5", 65), ("4", 70)]).keep
    assert not judge_line([("wonawiocs", 0), ("ae", 50)]).keep
    v = judge_line([("GYPSUM", 96), ("BOARD", 96)])
    assert v.keep and v.text == "GYPSUM BOARD" and not v.needs_review


def test_multiword_tokens_survive_line_judging():
    v = judge_line([("(4)", 96), ('3/4"', 94), ("A325", 96), ("BOLTS", 96)])
    assert v.text == '(4) 3/4" A325 BOLTS'
    v = judge_line([("T.O.S.", 90), ("EL.", 91), ("102'-6\"", 60)])
    assert v.text == "T.O.S. EL. 102'-6\""


def test_unreadable_word_is_marked_not_guessed():
    v = judge_line([("INSULATION", 88), ("YaCROUY", 30)])
    assert v.keep and v.text == "INSULATION" and v.needs_review
    # a lone unverifiable word beside garbage is not trusted -> becomes an unreadable label
    assert not judge_line([("ABSTRACT", 88), ("YaCROUY", 30)]).keep
    v = judge_line([("RIGID", 95), ("xqzt", 20), ("INSULATION", 95)])
    assert v.text == "RIGID [?] INSULATION"


def test_quantity_parsing_incl_percent_fix():
    assert quantity("Submit three copies of the manual.") == ("three", "COPIES")
    assert quantity("Provide manuals as required by the Owner.") == ("", "")
    assert quantity("Furnish extra materials equal to 2% of each type.") == ("2", "PERCENT")
    assert quantity("Provide 10 percent spare parts.") == ("10", "PERCENT")
    assert quantity("Warranty period of two (2) years.") == ("two", "YEARS")


def test_classification_and_division():
    assert classify("Provide attic stock for the project.") == "Attic Stock"
    assert classify("Warranty shall be two years") == "Warranty"
    assert division_of("23 05 00") == "23"
    assert division_of("105") == ""


def test_section_detection_is_strict():
    st = SectionState()
    assert detect_section("2000 square feet of floor area\nmore text", st).section == ""
    assert detect_section("SECTION 23 05 00 - COMMON WORK RESULTS FOR HVAC", st).section == "23 05 00"
    assert detect_section("Item P-401 Asphalt Mix Pavement", st).section == "P-401"
    assert detect_section("SECTION 01 78 23 OPERATION AND MAINTENANCE ........ 12", st).section == ""


def test_split_spans_joins_wrapped_lines():
    spans = split_spans("Provide two copies of the\nfinal report. Submit warranty.")
    assert "Provide two copies of the final report." in spans


def test_requirements_extracted_with_evidence_and_flags():
    text = "SECTION 23 05 00 - HVAC\nProvide one spare filter set for each air handling unit.\nThe sky is blue."
    st = detect_section(text, SectionState())
    found, hits = extract_requirements(text, "spec.pdf", 3, st, "sha", "PDF text layer", None)
    assert hits == 1 and len(found) == 1
    f = found[0]
    assert f.text == "Provide one spare filter set for each air handling unit."
    assert (f.page, f.section, f.division, f.category) == (3, "23 05 00", "23", "Spare Part / Extra Material")
    assert f.value == "one" and f.unit == "SET"
