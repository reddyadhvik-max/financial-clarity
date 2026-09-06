"""Unit tests for the pure calculation engine, verified against hand-worked
numbers for FY 2025-26. These are the numbers that must be right before
anything else in this project matters.
"""
import pytest

from app import engine


def test_new_regime_no_tax_up_to_12l_taxable():
    result = engine.compute_tax_for_regime(1_000_000, "new")
    assert result["tax_before_rebate"] == 40000.0
    assert result["rebate_amount"] == 40000.0
    assert result["total_tax"] == 0.0


def test_new_regime_tax_above_12l_no_rebate():
    result = engine.compute_tax_for_regime(1_500_000, "new")
    assert result["tax_before_rebate"] == 105000.0
    assert result["rebate_amount"] == 0.0
    assert result["cess_amount"] == 4200.0
    assert result["total_tax"] == 109200.0


def test_old_regime_tax_above_5l_threshold():
    result = engine.compute_tax_for_regime(600_000, "old")
    assert result["tax_before_rebate"] == 32500.0
    assert result["rebate_amount"] == 0.0
    assert result["cess_amount"] == 1300.0
    assert result["total_tax"] == 33800.0


def test_old_regime_rebate_zeroes_tax_below_5l():
    result = engine.compute_tax_for_regime(480_000, "old")
    assert result["tax_before_rebate"] == 11500.0
    assert result["rebate_amount"] == 11500.0
    assert result["total_tax"] == 0.0


def test_hra_exemption_least_of_three():
    result = engine.compute_hra_exemption(
        basic=600_000, hra_received=300_000, rent_paid=240_000, is_metro=True
    )
    assert result["exempt_amount"] == 180_000.0


def test_hra_exemption_non_metro_lower_pct():
    result = engine.compute_hra_exemption(
        basic=600_000, hra_received=300_000, rent_paid=400_000, is_metro=False
    )
    assert result["exempt_amount"] == 240_000.0


def test_compute_in_hand_new_regime_full_scenario():
    ctc = {
        "basic": 600_000,
        "hra": 300_000,
        "special_allowance": 200_000,
        "bonus": 100_000,
        "pf_on_full_basic": True,
    }
    result = engine.compute_in_hand(ctc, regime="new")

    assert result["gross_salary_annual"] == 1_200_000.0
    assert result["esi_eligible"] is False

    employee_pf = next(d for d in result["deductions"] if d["name"] == "Employee PF (EPF)")
    assert employee_pf["amount"] == 72_000.0
    assert employee_pf["rule_id"] == "PF_EMPLOYEE_RATE"

    income_tax = next(d for d in result["deductions"] if d["name"] == "Income Tax (TDS)")
    assert income_tax["amount"] == 0.0

    assert result["total_deductions_annual"] == 72_000.0
    assert result["in_hand_annual"] == 1_128_000.0
    assert result["in_hand_monthly"] == pytest.approx(94_000.0)

    assert result["employer_side"]["gratuity_provision"]["amount"] == pytest.approx(28_846.15, abs=0.01)
    assert result["ctc_total"] == pytest.approx(1_300_846.15, abs=0.01)


def test_compute_in_hand_rejects_missing_required_fields():
    with pytest.raises(ValueError):
        engine.compute_in_hand({"basic": 500_000})


def test_compute_in_hand_esi_eligible_low_gross():
    ctc = {"basic": 150_000, "hra": 60_000, "pf_on_full_basic": True}
    result = engine.compute_in_hand(ctc, regime="new")
    assert result["esi_eligible"] is True
    esi = next(d for d in result["deductions"] if d["name"] == "Employee ESI")
    assert esi["amount"] == pytest.approx(0.0075 * 210_000, abs=0.01)


def test_compute_regime_comparison_matches_hand_worked_numbers():
    result = engine.compute_regime_comparison(
        gross_salary=1_200_000,
        deductions_claimed={"80C": 150_000, "80D": 25_000},
        hra_exemption=180_000,
    )

    assert result["old_regime_tax"]["total_tax"] == 74_360.0
    assert result["new_regime_tax"]["total_tax"] == 0.0
    assert result["recommended"] == "new"
    assert result["annual_savings_with_recommended"] == 74_360.0

    impacts = {i["name"]: i["tax_saved"] for i in result["per_deduction_impact"]}
    assert impacts["HRA Exemption"] == pytest.approx(37_440.0, abs=0.01)
    assert impacts["Section 80C"] == pytest.approx(31_200.0, abs=0.01)
    assert impacts["Section 80D"] == pytest.approx(5_200.0, abs=0.01)


def test_detect_red_flags_clean_offer_has_no_flags():
    offer = {
        "basic": 600_000, "hra": 300_000, "bonus": 100_000, "special_allowance": 200_000,
        "employer_pf": 72_000, "gratuity_clause_present": True,
    }
    assert engine.detect_red_flags(offer) == []


def test_detect_red_flags_bad_offer_flags_everything():
    offer = {
        "basic": 200_000, "hra": 100_000, "bonus": 400_000, "ctc_total": 1_000_000,
        "employer_pf": None, "gratuity_clause_present": False,
        "notice_period_days": 120, "has_service_bond": True,
        "joining_bonus_has_clawback": True,
    }
    flags = engine.detect_red_flags(offer)
    flag_ids = {f["flag_id"] for f in flags}
    assert flag_ids == {
        "HIGH_VARIABLE_PAY", "LOW_BASIC_SALARY", "MISSING_PF",
        "MISSING_GRATUITY_CLAUSE", "LONG_NOTICE_PERIOD", "SERVICE_BOND",
        "JOINING_BONUS_CLAWBACK",
    }
    for f in flags:
        assert f["message"]
