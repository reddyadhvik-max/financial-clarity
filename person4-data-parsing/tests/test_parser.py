"""End-to-end test of OfferLetterParser against a realistic filled offer
letter (tests/sample_offer_letter.txt), which follows the exact template
format the team is standardizing test offer letters on.

Expected values here were derived by hand from the fixture text, then
cross-checked against an actual parser run — not guessed after the fact.
"""
from pathlib import Path

from parser.parser_engine import OfferLetterParser

FIXTURE_PATH = Path(__file__).parent / "sample_offer_letter.txt"


def _parse_fixture():
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    return OfferLetterParser().parse_text(text)


def test_metadata_extraction():
    result = _parse_fixture()
    assert result["metadata"]["company_name"] == "BrightPath Technologies Pvt Ltd"
    assert result["metadata"]["employee_name"] == "Rohan Mehta"
    assert result["metadata"]["designation"] == "Senior Software Engineer"
    assert result["metadata"]["joining_date"] == "01/10/2026"


def test_top_line_and_fixed_components_found():
    result = _parse_fixture()
    top_line = result["fields"]["top_line"]
    fixed = result["fields"]["fixed"]

    assert top_line["total_ctc"] == {
        "value": 1800000.0, "confidence_tier": "found",
        "evidence": "Total Compensation (CTC) for the year will be Rs. 18,00,000",
    }
    assert fixed["basic_pay"]["value"] == 720000.0
    assert fixed["basic_pay"]["confidence_tier"] == "found"
    assert fixed["hra"]["value"] == 360000.0
    assert fixed["special_allowance"]["value"] == 360000.0


def test_missing_fields_are_null_not_zero():
    result = _parse_fixture()
    fixed = result["fields"]["fixed"]
    variable = result["fields"]["variable"]

    # Dearness Allowance and Sales Commission are genuinely absent from the
    # letter — must be null + "missing", never silently coerced to 0.
    assert fixed["da"] == {"value": None, "confidence_tier": "missing", "evidence": None}
    assert variable["sales_commission"] == {"value": None, "confidence_tier": "missing", "evidence": None}


def test_da_does_not_false_match_inside_date():
    """Regression test: "DA" is a substring of "Date" — without word-boundary
    matching, the letter's "Date: 2026-09-01" line used to be misread as a
    Dearness Allowance of 2026."""
    result = _parse_fixture()
    da_field = result["fields"]["fixed"]["da"]
    assert da_field["value"] != 2026.0
    assert da_field["confidence_tier"] == "missing"


def test_sales_commission_does_not_false_match_incentive_plan_prose():
    """Regression test: a generic "incentive" alias used to match the
    equity paragraph's "long-term incentive plan" wording and grab the
    equity grant value as a bogus sales commission figure."""
    result = _parse_fixture()
    assert result["fields"]["variable"]["sales_commission"]["value"] is None


def test_duration_fields_parsed_as_months_not_bare_numbers():
    result = _parse_fixture()
    one_time = result["fields"]["one_time"]
    assert one_time["joining_bonus_clawback_months"] == {
        "value": 12, "confidence_tier": "found", "evidence": "Clawback Period of 12 months",
    }
    assert one_time["equity_cliff_months"]["value"] == 12


def test_equity_and_text_fields():
    result = _parse_fixture()
    one_time = result["fields"]["one_time"]
    variable = result["fields"]["variable"]

    assert one_time["equity_type"]["value"] == "RSUs"
    assert one_time["equity_grant_value"]["value"] == 500000.0
    assert variable["variable_pay_frequency"]["value"] == "Annually"
    # Not directly labeled "Vesting Schedule:" -> estimated tier, clause-trimmed
    assert one_time["equity_vesting_schedule"]["confidence_tier"] == "estimated"
    assert "vesting over 4 years" in one_time["equity_vesting_schedule"]["value"]


def test_derived_totals():
    result = _parse_fixture()
    derived = result["derived"]
    assert derived["fixed_total"]["value"] == 1440000.0       # basic + hra + special
    assert derived["retirals_total"]["value"] == 121015.0     # employer_pf + gratuity
    assert derived["variable_total"]["value"] == 180000.0     # target_bonus only
    assert derived["one_time_total"]["value"] == 600000.0     # joining_bonus + equity_grant_value


def test_checksum_within_tolerance():
    result = _parse_fixture()
    checksum = result["checksum"]
    assert checksum["checked"] is True
    assert checksum["total_ctc"] == 1800000.0
    assert checksum["component_sum"] == 1741015.0
    assert checksum["within_tolerance"] is True


def test_one_time_payment_cliff_red_flag_fires():
    result = _parse_fixture()
    flag_ids = [f["flag_id"] for f in result["red_flags"]]
    assert "ONE_TIME_PAYMENT_CLIFF" in flag_ids
    # These conditions are NOT met by the fixture, so must not fire:
    assert "HIGH_VARIABLE_PAY" not in flag_ids            # target_bonus is only 10% of CTC
    assert "MISSING_GRATUITY_HIGH_VALUE" not in flag_ids  # gratuity is stated
    assert "MISSING_EMPLOYER_PF" not in flag_ids          # employer_pf is stated
    assert "CTC_CHECKSUM_MISMATCH" not in flag_ids        # within tolerance


def test_never_fails_on_empty_input():
    result = OfferLetterParser().parse_text("")
    assert result["fields"]["top_line"]["total_ctc"]["confidence_tier"] == "missing"
    assert result["checksum"]["checked"] is False
    assert result["red_flags"] == []
