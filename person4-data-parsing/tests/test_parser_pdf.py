"""End-to-end test against a real generated PDF (tests/sample_offer_letter.pdf)
containing both prose paragraphs and a genuine bordered table — exercising
the actual pdfplumber text + table extraction path (extractors.py + tabular.py),
not just regex matching over a plain-text string.

The fixture PDF was generated once with reportlab (see
tests/generate_sample_pdf.py) and is committed to the repo, so running these
tests does not require reportlab to be installed.
"""
from pathlib import Path

from parser.parser_engine import OfferLetterParser

FIXTURE_PDF = Path(__file__).parent / "sample_offer_letter.pdf"


def _parse_fixture_pdf():
    return OfferLetterParser().parse_pdf(FIXTURE_PDF)


def test_metadata_and_prose_fields_extracted_from_pdf_text_layer():
    result = _parse_fixture_pdf()
    assert result["used_ocr"] is False  # real text layer, no OCR fallback needed
    assert result["metadata"]["company_name"] == "Delta Analytics Pvt Ltd"
    assert result["metadata"]["employee_name"] == "Meera Iyer"
    assert result["fields"]["top_line"]["total_ctc"]["value"] == 2200000.0
    assert result["fields"]["top_line"]["total_ctc"]["confidence_tier"] == "found"


def test_annexure_table_fields_extracted_via_tabular_layer():
    """These five fields exist ONLY in the PDF's bordered table, not in the
    prose — proving Layer 1 (tabular.py) actually ran against a real
    pdfplumber table, not just text regex."""
    result = _parse_fixture_pdf()
    fixed = result["fields"]["fixed"]
    retirals = result["fields"]["retirals"]

    for field_entry, expected_value in [
        (fixed["basic_pay"], 960000.0),
        (fixed["hra"], 480000.0),
        (fixed["special_allowance"], 360000.0),
        (retirals["employer_pf"], 115200.0),
        (retirals["gratuity"], 46154.0),
    ]:
        assert field_entry["value"] == expected_value
        assert field_entry["confidence_tier"] == "found"
        assert "table row" in field_entry["evidence"]


def test_duration_field_evidence_has_no_embedded_pdf_linebreak():
    """Regression test: pdfplumber's text extraction preserves PDF line
    wrapping as literal '\\n' characters — evidence strings must be
    collapsed to single-line before being surfaced to a human reviewer."""
    result = _parse_fixture_pdf()
    clawback = result["fields"]["one_time"]["joining_bonus_clawback_months"]
    assert clawback["value"] == 6
    assert "\n" not in clawback["evidence"]


def test_variable_pay_frequency_does_not_false_match_table_column_header():
    """Regression test: the Annexure table's "Monthly (Rs.)" column header
    used to be misread as the variable-pay frequency, even though this
    letter never states a bonus payout frequency at all."""
    result = _parse_fixture_pdf()
    frequency = result["fields"]["variable"]["variable_pay_frequency"]
    assert frequency["value"] is None
    assert frequency["confidence_tier"] == "missing"


def test_checksum_mismatch_flag_on_this_fixture():
    """This fixture's table doesn't itemize every CTC component (no bonus,
    no LTA/DA), so the checksum is expected to be outside tolerance —
    this should surface as an info-level red flag, not silently pass."""
    result = _parse_fixture_pdf()
    assert result["checksum"]["within_tolerance"] is False
    assert "CTC_CHECKSUM_MISMATCH" in [f["flag_id"] for f in result["red_flags"]]
