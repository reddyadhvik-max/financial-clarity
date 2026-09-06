"""Tests for the advanced, still-deterministic engine features layered on
top of compute_in_hand: compensation classification, the CTC waterfall,
the offer quality score, and two-offer comparison. These reuse the same
FY 2025-26 scenario already hand-verified in test_engine.py
(test_compute_in_hand_new_regime_full_scenario) so the numbers below are
either copied from there or derived from it.
"""
import pytest

from app import engine

FULL_SCENARIO_CTC = {
    "basic": 600_000,
    "hra": 300_000,
    "special_allowance": 200_000,
    "bonus": 100_000,
    "pf_on_full_basic": True,
}


def test_classify_recurring_total_matches_compute_in_hand_ctc_total():
    in_hand = engine.compute_in_hand(FULL_SCENARIO_CTC, regime="new")
    classification = engine.classify_compensation_components(FULL_SCENARIO_CTC, regime="new")
    assert classification["recurring_ctc_total"] == pytest.approx(in_hand["ctc_total"], abs=0.01)


def test_classify_buckets_sum_to_recurring_total():
    classification = engine.classify_compensation_components(FULL_SCENARIO_CTC, regime="new")
    bucket_sum = sum(b["total"] for b in classification["buckets"] if b["bucket"] != "one_time")
    assert bucket_sum == pytest.approx(classification["recurring_ctc_total"], abs=0.01)

    fixed = next(b for b in classification["buckets"] if b["bucket"] == "fixed_compensation")
    assert fixed["total"] == 1_100_000.0
    variable = next(b for b in classification["buckets"] if b["bucket"] == "variable")
    assert variable["total"] == 100_000.0


def test_classify_one_time_components_excluded_from_recurring_total():
    ctc = dict(FULL_SCENARIO_CTC, one_time_components={"Joining Bonus": 100_000, "Relocation": 50_000})
    classification = engine.classify_compensation_components(ctc, regime="new")
    one_time = next(b for b in classification["buckets"] if b["bucket"] == "one_time")
    assert one_time["total"] == 150_000.0
    assert classification["one_time_total"] == 150_000.0
    baseline = engine.classify_compensation_components(FULL_SCENARIO_CTC, regime="new")
    assert classification["recurring_ctc_total"] == baseline["recurring_ctc_total"]


def test_waterfall_starts_at_ctc_and_ends_at_monthly_in_hand():
    in_hand = engine.compute_in_hand(FULL_SCENARIO_CTC, regime="new")
    waterfall = engine.compute_ctc_waterfall(FULL_SCENARIO_CTC, regime="new")

    assert waterfall["steps"][0]["label"] == "CTC (Total Cost to Company)"
    assert waterfall["steps"][0]["amount"] == in_hand["ctc_total"]
    assert waterfall["steps"][-1]["label"] == "Monthly In-Hand"
    assert waterfall["steps"][-1]["amount"] == in_hand["in_hand_monthly"]
    assert waterfall["in_hand_monthly"] == 94_000.0


def test_waterfall_running_balance_after_all_steps_matches_in_hand_annual():
    in_hand = engine.compute_in_hand(FULL_SCENARIO_CTC, regime="new")
    waterfall = engine.compute_ctc_waterfall(FULL_SCENARIO_CTC, regime="new")
    annual_step = next(s for s in waterfall["steps"] if s["label"] == "Annual In-Hand")
    assert annual_step["running_balance"] == in_hand["in_hand_annual"] == 1_128_000.0

    pf_step = next(s for s in waterfall["steps"] if s["label"] == "Employee PF (EPF)")
    assert pf_step["rule_id"] == "PF_EMPLOYEE_RATE"


def test_quality_score_hand_verified_full_scenario():
    result = engine.compute_offer_quality_score(FULL_SCENARIO_CTC, regime="new")
    assert result["sub_scores"]["fixed_ratio"]["score"] == 100.0
    assert result["sub_scores"]["take_home_ratio"]["score"] == 100.0
    assert result["sub_scores"]["benefits"]["score"] == 100.0
    assert result["sub_scores"]["variable_dependence"]["score"] == pytest.approx(74.38, abs=0.01)
    assert result["overall_score"] == 94


def test_quality_score_penalizes_missing_pf_and_high_variable_pay():
    risky_ctc = {"basic": 150_000, "hra": 50_000, "bonus": 500_000, "pf_on_full_basic": True}
    result = engine.compute_offer_quality_score(risky_ctc, regime="new")
    assert result["sub_scores"]["variable_dependence"]["score"] == 0.0
    assert result["overall_score"] < 60


def test_quality_score_always_in_0_100_range():
    for ctc in (FULL_SCENARIO_CTC, {"basic": 1, "hra": 1}, {"basic": 5_000_000, "hra": 100_000, "bonus": 5_000_000}):
        result = engine.compute_offer_quality_score(ctc, regime="new")
        assert 0 <= result["overall_score"] <= 100
        for sub in result["sub_scores"].values():
            assert 0 <= sub["score"] <= 100


def test_compare_offers_per_offer_results_match_direct_compute_in_hand():
    offer_a = {"label": "Offer A", "regime": "new", "ctc_breakup": FULL_SCENARIO_CTC}
    offer_b = {"label": "Offer B", "regime": "new",
               "ctc_breakup": {"basic": 500_000, "hra": 250_000, "special_allowance": 150_000, "bonus": 400_000}}

    result = engine.compare_offers(offer_a, offer_b)

    direct_a = engine.compute_in_hand(FULL_SCENARIO_CTC, regime="new")
    direct_b = engine.compute_in_hand(offer_b["ctc_breakup"], regime="new")

    assert result["offer_a"]["in_hand"]["in_hand_monthly"] == direct_a["in_hand_monthly"]
    assert result["offer_b"]["in_hand"]["in_hand_monthly"] == direct_b["in_hand_monthly"]
    assert result["diff"]["ctc_total"] == pytest.approx(
        direct_b["ctc_total"] - direct_a["ctc_total"], abs=0.01
    )


def test_compare_offers_best_for_cashflow_picks_higher_monthly_in_hand():
    lower = {"label": "Lower", "regime": "new", "ctc_breakup": {"basic": 300_000, "hra": 150_000}}
    higher = {"label": "Higher", "regime": "new", "ctc_breakup": {"basic": 900_000, "hra": 450_000}}

    result = engine.compare_offers(lower, higher)
    assert result["best_for_cashflow"] == "offer_b"
    assert result["best_for_total_comp"] == "offer_b"
    assert result["diff"]["in_hand_monthly"] > 0


def test_gratuity_vests_exactly_at_five_years():
    result = engine.compute_epf_gratuity_timeline("2019-06-15", as_of_date="2024-06-15")
    assert result["gratuity"]["vested"] is True
    assert result["gratuity"]["vesting_date"] == "2024-06-15"
    assert result["tenure_years"] == pytest.approx(5.0, abs=0.01)


def test_gratuity_not_vested_before_five_years():
    result = engine.compute_epf_gratuity_timeline("2019-06-15", as_of_date="2023-06-15")
    assert result["gratuity"]["vested"] is False
    assert result["gratuity"]["days_to_vesting"] == 366


def test_gratuity_forfeited_on_early_separation():
    result = engine.compute_epf_gratuity_timeline("2022-01-01", separation_date="2023-06-01")
    assert result["gratuity"]["outcome"] == "forfeited"
    assert result["gratuity"]["vested"] is False


def test_gratuity_payable_after_vesting():
    result = engine.compute_epf_gratuity_timeline("2018-01-01", separation_date="2024-01-01")
    assert result["gratuity"]["outcome"] == "payable"
    assert result["gratuity"]["vested"] is True


def test_epf_tax_free_threshold_matches_gratuity_vesting():
    result = engine.compute_epf_gratuity_timeline("2019-06-15", as_of_date="2024-06-15")
    assert result["epf"]["tax_free_withdrawal_eligible"] is True


def test_epf_not_tax_free_before_five_years():
    result = engine.compute_epf_gratuity_timeline("2022-01-01", as_of_date="2023-01-01")
    assert result["epf"]["tax_free_withdrawal_eligible"] is False


def test_timeline_milestones_cover_all_three_rules():
    result = engine.compute_epf_gratuity_timeline("2020-01-01", as_of_date="2023-01-01")
    assert len(result["milestones"]) == 4
    rule_ids = {m["rule_id"] for m in result["milestones"] if m["rule_id"]}
    assert rule_ids == {"GRATUITY_VESTING_YEARS", "EPF_TAX_FREE_WITHDRAWAL_YEARS", "EPS_PENSION_MIN_SERVICE_YEARS"}


def test_timeline_rejects_malformed_date():
    with pytest.raises(ValueError):
        engine.compute_epf_gratuity_timeline("15-06-2019")


def test_gratuity_vests_at_exactly_five_years_across_a_single_leap_day():
    # 2026-09-05 -> 2031-09-05 spans exactly one leap day (2028-02-29), so
    # the exact day count is 1826, and 1826 / 365.25 < 5.0 — a naive
    # days/365.25 approximation would wrongly call this "not yet vested" on
    # the employee's actual 5-year anniversary. Vesting must be judged by
    # exact calendar date, not by that approximation (regression test for a
    # bug found via manual browser testing: the eligibility boolean and the
    # milestone list disagreed with each other on this exact date range).
    result = engine.compute_epf_gratuity_timeline("2026-09-05", separation_date="2031-09-05")
    assert result["gratuity"]["vested"] is True
    assert result["gratuity"]["outcome"] == "payable"
    assert result["epf"]["tax_free_withdrawal_eligible"] is True

    vesting_milestone = next(m for m in result["milestones"] if m["rule_id"] == "GRATUITY_VESTING_YEARS")
    assert vesting_milestone["status"] == "past"


def test_schema_accepts_camelcase_field_names():
    from app.schemas import CTCBreakup

    parsed = CTCBreakup.model_validate({
        "basic": 600_000, "hra": 300_000, "specialAllowance": 200_000,
        "variablePay": 100_000, "employerPF": 72_000,
    })
    assert parsed.special_allowance == 200_000
    assert parsed.bonus == 100_000
    assert parsed.employer_pf == 72_000


def test_schema_still_accepts_snake_case_field_names():
    from app.schemas import CTCBreakup

    parsed = CTCBreakup.model_validate({
        "basic": 600_000, "hra": 300_000, "special_allowance": 200_000,
        "bonus": 100_000, "employer_pf": 72_000,
    })
    assert parsed.special_allowance == 200_000
    assert parsed.bonus == 100_000
    assert parsed.employer_pf == 72_000


def test_dearness_allowance_included_in_pf_and_gratuity_base():
    ctc = {"basic": 600_000, "hra": 300_000, "dearness_allowance": 200_000, "pf_on_full_basic": True}
    result = engine.compute_in_hand(ctc, regime="new")
    pf = next(d for d in result["deductions"] if d["name"] == "Employee PF (EPF)")
    assert pf["amount"] == 96_000.0
    assert result["gross_salary_annual"] == 1_100_000.0
    assert result["employer_side"]["gratuity_provision"]["amount"] == pytest.approx(38_461.54, abs=0.01)


def test_lta_exemption_reduces_taxable_income_old_regime_only():
    ctc = {"basic": 600_000, "hra": 300_000, "lta_received": 50_000, "lta_exemption_claimed": 40_000}
    old = engine.compute_in_hand(ctc, regime="old")
    new = engine.compute_in_hand(ctc, regime="new")

    assert old["taxable_income"] == 860_000.0
    assert old["lta_exemption_amount"] == 40_000.0
    assert new["lta_exemption_amount"] == 0.0
    assert old["gross_salary_annual"] == 950_000.0 == new["gross_salary_annual"]


def test_lta_exemption_claimed_is_capped_at_amount_received():
    ctc = {"basic": 600_000, "hra": 300_000, "lta_received": 20_000, "lta_exemption_claimed": 999_000}
    result = engine.compute_in_hand(ctc, regime="old")
    assert result["lta_exemption_amount"] == 20_000.0


def test_employer_nps_deductible_under_both_regimes():
    ctc = {"basic": 1_000_000, "hra": 300_000, "employer_nps": 80_000}
    old = engine.compute_in_hand(ctc, regime="old")
    new = engine.compute_in_hand(ctc, regime="new")

    assert new["taxable_income"] == 1_145_000.0
    assert new["nps_deduction_amount"] == 80_000.0
    assert old["nps_deduction_amount"] == 80_000.0
    assert new["employer_side"]["employer_nps"]["amount"] == 80_000.0
    assert new["employer_side"]["employer_nps"]["rule_id"] == "NPS_80CCD2_CAP_PCT"
    assert new["gross_salary_annual"] == 1_300_000.0


def test_employer_nps_deduction_capped_at_10pct_of_basic_but_ctc_shows_full_contribution():
    ctc = {"basic": 1_000_000, "hra": 300_000, "employer_nps": 150_000}
    result = engine.compute_in_hand(ctc, regime="new")
    assert result["nps_deduction_amount"] == 100_000.0
    assert result["employer_side"]["employer_nps"]["amount"] == 150_000.0


def test_health_insurance_and_transport_deduction():
    ctc = {"basic": 500_000, "hra": 250_000, "health_insurance_premium": 15_000, "transport_deduction": 6_000}
    result = engine.compute_in_hand(ctc, regime="new")

    transport = next(d for d in result["deductions"] if d["name"] == "Cab / Transport Deduction")
    assert transport["amount"] == 6_000.0
    assert transport["rule_id"] is None
    assert result["in_hand_annual"] == 684_000.0
    assert result["employer_side"]["health_insurance"]["amount"] == 15_000.0
    assert result["gross_salary_annual"] == 750_000.0


def test_retention_bonus_and_sales_commission_count_toward_gross_and_variable_pay():
    ctc = {"basic": 300_000, "hra": 150_000, "retention_bonus": 200_000, "sales_commission": 100_000}
    result = engine.compute_in_hand(ctc, regime="new")
    assert result["gross_salary_annual"] == 750_000.0

    flags = engine.detect_red_flags(ctc)
    assert any(f["flag_id"] == "HIGH_VARIABLE_PAY" for f in flags)

    classification = engine.classify_compensation_components(ctc, regime="new")
    variable = next(b for b in classification["buckets"] if b["bucket"] == "variable")
    assert variable["total"] == 300_000.0


def test_variable_pay_frequency_note_only_when_not_monthly():
    base = {"basic": 600_000, "hra": 300_000, "bonus": 100_000}
    quarterly = engine.compute_in_hand(dict(base, variable_pay_frequency="quarterly"), regime="new")
    monthly = engine.compute_in_hand(dict(base, variable_pay_frequency="monthly"), regime="new")
    unset = engine.compute_in_hand(base, regime="new")

    assert quarterly["variable_pay_note"] is not None and "quarterly" in quarterly["variable_pay_note"]
    assert monthly["variable_pay_note"] is None
    assert unset["variable_pay_note"] is None


def test_equity_is_passed_through_but_never_affects_ctc_math():
    base = {"basic": 600_000, "hra": 300_000}
    with_equity = dict(base, equity_type="RSU", equity_grant_value=500_000, equity_unit_count=100,
                        equity_vesting_schedule="25% per year over 4 years", equity_cliff_period_months=12)

    plain_result = engine.compute_in_hand(base, regime="new")
    equity_result = engine.compute_in_hand(with_equity, regime="new")

    assert plain_result["equity"] is None
    assert equity_result["equity"]["equity_type"] == "RSU"
    assert equity_result["equity"]["grant_value"] == 500_000
    assert equity_result["equity"]["cliff_period_months"] == 12
    assert equity_result["ctc_total"] == plain_result["ctc_total"]
    assert equity_result["in_hand_annual"] == plain_result["in_hand_annual"]

    classification = engine.classify_compensation_components(with_equity, regime="new")
    assert any(b["bucket"] == "equity" for b in classification["buckets"])
    plain_classification = engine.classify_compensation_components(base, regime="new")
    assert not any(b["bucket"] == "equity" for b in plain_classification["buckets"])


def test_joining_bonus_clawback_period_in_message():
    offer = {"basic": 600_000, "hra": 300_000, "joining_bonus_has_clawback": True,
              "joining_bonus_clawback_period_months": 18}
    flags = engine.detect_red_flags(offer)
    clawback = next(f for f in flags if f["flag_id"] == "JOINING_BONUS_CLAWBACK")
    assert "18 months" in clawback["message"]


def test_schema_accepts_new_camelcase_field_names():
    from app.schemas import CTCBreakup

    parsed = CTCBreakup.model_validate({
        "basic": 600_000, "hra": 300_000, "dearnessAllowance": 100_000,
        "employerNPS": 50_000, "healthInsurancePremium": 12_000,
        "transportDeduction": 3_000, "retentionBonus": 20_000, "incentives": 10_000,
    })
    assert parsed.dearness_allowance == 100_000
    assert parsed.employer_nps == 50_000
    assert parsed.health_insurance_premium == 12_000
    assert parsed.transport_deduction == 3_000
    assert parsed.retention_bonus == 20_000
    assert parsed.sales_commission == 10_000
