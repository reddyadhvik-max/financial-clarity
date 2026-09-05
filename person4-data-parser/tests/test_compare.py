"""Multi-offer comparison: field-by-field diff, with a field present in one
offer but absent in the other rendered as the literal "NA" (not null/0)."""
from parser.compare import compare_offers
from parser.parser_engine import OfferLetterParser

OFFER_A_TEXT = """
Company Name: Alpha Corp
Dear Asha Rao,
We are thrilled to extend an offer of employment to you at Alpha Corp for the position of Data Analyst.
Your Total Compensation (CTC) for the year will be Rs. 12,00,000.
Basic Pay: Rs. 6,00,000 per annum
House Rent Allowance (HRA): Rs. 2,40,000 per annum
Employer PF: Rs. 72,000 per annum
Gratuity: Rs. 28,846 per annum
"""

OFFER_B_TEXT = """
Company Name: Beta Systems
Dear Asha Rao,
We are thrilled to extend an offer of employment to you at Beta Systems for the position of Data Analyst.
Your Total Compensation (CTC) for the year will be Rs. 14,00,000.
Basic Pay: Rs. 5,00,000 per annum
House Rent Allowance (HRA): Rs. 2,00,000 per annum
"""


def _compare():
    parser = OfferLetterParser()
    result_a = parser.parse_text(OFFER_A_TEXT)
    result_b = parser.parse_text(OFFER_B_TEXT)
    return compare_offers(result_a, result_b, "Alpha Corp", "Beta Systems")


def _row(comparison, field_key):
    return next(r for r in comparison["rows"] if r["field"] == field_key)


def test_both_present_fields_compare_numerically():
    comparison = _compare()
    row = _row(comparison, "total_ctc")
    assert row["Alpha Corp"] == 1200000.0
    assert row["Beta Systems"] == 1400000.0
    assert row["difference"] == -200000.0
    assert row["higher_offer"] == "Beta Systems"


def test_field_missing_in_one_offer_is_marked_na():
    comparison = _compare()
    row = _row(comparison, "gratuity")
    assert row["Alpha Corp"] == 28846.0
    assert row["Beta Systems"] == "NA"
    assert row["difference"] is None
    assert row["higher_offer"] is None


def test_field_missing_in_both_is_na_on_both_sides():
    comparison = _compare()
    row = _row(comparison, "lta")
    assert row["Alpha Corp"] == "NA"
    assert row["Beta Systems"] == "NA"


def test_summary_flags_fields_only_one_side_disclosed():
    comparison = _compare()
    only_in = comparison["summary"]["fields_only_disclosed_by"]
    assert "employer_pf" in only_in["Alpha Corp"]
    assert "gratuity" in only_in["Alpha Corp"]


def test_summary_total_ctc_delta():
    comparison = _compare()
    assert comparison["summary"]["total_ctc_difference"] == -200000.0
    assert comparison["summary"]["total_ctc_higher_offer"] == "Beta Systems"
