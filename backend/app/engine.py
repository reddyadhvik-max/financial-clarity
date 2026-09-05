"""Pure calculation engine. No LLM, no I/O beyond reading versioned rule data.

Every number these functions produce is traceable to a rule_id, so the API
layer and frontend can show "this figure came from rule X" without ever
inventing a description themselves.

All monetary inputs/outputs are annual INR unless a field name says
otherwise. All functions are pure: same input -> same output, always.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from app import rules

Regime = Literal["old", "new"]

REQUIRED_CTC_FIELDS = ("basic", "hra")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _round2(x: float) -> float:
    return round(x + 1e-9, 2)


def slab_tax(taxable_income: float, slabs_rule_id: str, fy: str | None = None) -> dict[str, Any]:
    """Apply a progressive slab table to taxable_income.

    Returns the tax before cess/rebate, plus a per-bracket breakdown so
    callers (e.g. compute_regime_comparison) can attribute rupees of tax
    to a specific bracket of a specific rule.
    """
    taxable_income = max(0.0, taxable_income)
    slabs = rules.get_value(slabs_rule_id, fy)
    brackets: list[dict[str, Any]] = []
    tax = 0.0
    for bracket in slabs:
        lo = bracket["min"]
        hi = bracket["max"]
        if taxable_income <= lo:
            continue
        upper = taxable_income if hi is None else min(taxable_income, hi)
        span = max(0.0, upper - lo)
        bracket_tax = span * bracket["rate"]
        if span > 0:
            brackets.append({
                "rule_id": slabs_rule_id,
                "min": lo,
                "max": hi,
                "rate": bracket["rate"],
                "taxable_amount_in_bracket": _round2(span),
                "tax_in_bracket": _round2(bracket_tax),
            })
        tax += bracket_tax
    return {"tax_before_rebate": _round2(tax), "brackets": brackets}


def apply_rebate_87a(tax_before_rebate: float, taxable_income: float, rebate_rule_id: str,
                      fy: str | None = None) -> dict[str, Any]:
    rebate_rule = rules.get_value(rebate_rule_id, fy)
    threshold = rebate_rule["taxable_income_threshold"]
    max_rebate = rebate_rule["max_rebate"]
    if taxable_income <= threshold:
        rebate = min(tax_before_rebate, max_rebate)
    else:
        rebate = 0.0
    return {
        "rule_id": rebate_rule_id,
        "rebate_amount": _round2(rebate),
        "tax_after_rebate": _round2(max(0.0, tax_before_rebate - rebate)),
    }


def compute_tax_for_regime(taxable_income: float, regime: Regime, fy: str | None = None) -> dict[str, Any]:
    """Full tax computation (slabs -> rebate -> cess) for one regime."""
    slabs_rule_id = "OLD_REGIME_SLABS" if regime == "old" else "NEW_REGIME_SLABS"
    rebate_rule_id = "OLD_REGIME_REBATE_87A" if regime == "old" else "NEW_REGIME_REBATE_87A"

    slab_result = slab_tax(taxable_income, slabs_rule_id, fy)
    rebate_result = apply_rebate_87a(slab_result["tax_before_rebate"], taxable_income, rebate_rule_id, fy)

    cess_rate = rules.get_value("CESS_RATE", fy)
    cess = rebate_result["tax_after_rebate"] * cess_rate
    total_tax = rebate_result["tax_after_rebate"] + cess

    return {
        "regime": regime,
        "taxable_income": _round2(taxable_income),
        "tax_before_rebate": slab_result["tax_before_rebate"],
        "brackets": slab_result["brackets"],
        "rebate_rule_id": rebate_rule_id,
        "rebate_amount": rebate_result["rebate_amount"],
        "tax_after_rebate": rebate_result["tax_after_rebate"],
        "cess_rule_id": "CESS_RATE",
        "cess_amount": _round2(cess),
        "total_tax": _round2(total_tax),
    }


def compute_hra_exemption(basic: float, hra_received: float, rent_paid: float, is_metro: bool,
                           fy: str | None = None) -> dict[str, Any]:
    """Least of the three HRA exemption limbs (old regime only)."""
    metro_pct_rule = "HRA_METRO_PCT" if is_metro else "HRA_NONMETRO_PCT"
    metro_pct = rules.get_value(metro_pct_rule, fy)
    offset_pct = rules.get_value("HRA_RENT_OFFSET_PCT", fy)

    limb_actual_hra = hra_received
    limb_rent_minus_offset = max(0.0, rent_paid - offset_pct * basic)
    limb_pct_of_basic = metro_pct * basic

    exempt = min(limb_actual_hra, limb_rent_minus_offset, limb_pct_of_basic)
    exempt = max(0.0, exempt)

    return {
        "exempt_amount": _round2(exempt),
        "limbs": [
            {"rule_id": "HRA_ACTUAL_RECEIVED", "label": "Actual HRA received", "amount": _round2(limb_actual_hra)},
            {"rule_id": "HRA_RENT_OFFSET_PCT", "label": "Rent paid minus 10% of Basic",
             "amount": _round2(limb_rent_minus_offset)},
            {"rule_id": metro_pct_rule, "label": f"{int(metro_pct * 100)}% of Basic ({'metro' if is_metro else 'non-metro'})",
             "amount": _round2(limb_pct_of_basic)},
        ],
    }


# ---------------------------------------------------------------------------
# 1. compute_in_hand
# ---------------------------------------------------------------------------

def compute_in_hand(ctc_breakup: dict[str, Any], regime: Regime = "new", fy: str | None = None) -> dict[str, Any]:
    """Compute annual/monthly in-hand pay from a validated CTC breakup.

    Expected ctc_breakup fields (all annual INR unless noted):
      basic (required), hra (required), special_allowance (default 0),
      other_allowances (dict[str, float], default {}), bonus (default 0),
      employer_pf (optional, else computed), pf_on_full_basic (bool, default True),
      professional_tax (optional annual, default 0),
      deductions_claimed (dict, for old regime: 80C, 80D),
      rent_paid (optional, for HRA exemption under old regime),
      is_metro (bool, default False).

    Callers (the API layer) are expected to have already run
    validate_ctc_breakup() so required fields are guaranteed present;
    this function still raises ValueError defensively if they are not.
    """
    missing = [f for f in REQUIRED_CTC_FIELDS if ctc_breakup.get(f) is None]
    if missing:
        raise ValueError(f"compute_in_hand: missing required fields {missing}")

    basic = float(ctc_breakup["basic"])
    hra = float(ctc_breakup["hra"])
    special_allowance = float(ctc_breakup.get("special_allowance", 0) or 0)
    other_allowances = ctc_breakup.get("other_allowances") or {}
    other_allowances_total = float(sum(other_allowances.values()))
    bonus = float(ctc_breakup.get("bonus", 0) or 0)
    retention_bonus = float(ctc_breakup.get("retention_bonus", 0) or 0)
    sales_commission = float(ctc_breakup.get("sales_commission", 0) or 0)
    pf_on_full_basic = bool(ctc_breakup.get("pf_on_full_basic", True))
    professional_tax = float(ctc_breakup.get("professional_tax", 0) or 0)
    transport_deduction = float(ctc_breakup.get("transport_deduction", 0) or 0)
    deductions_claimed = ctc_breakup.get("deductions_claimed") or {}
    rent_paid = ctc_breakup.get("rent_paid")
    is_metro = bool(ctc_breakup.get("is_metro", False))
    da = float(ctc_breakup.get("dearness_allowance", 0) or 0)
    basic_plus_da = basic + da
    lta_received = float(ctc_breakup.get("lta_received", 0) or 0)
    lta_exemption_claimed = min(float(ctc_breakup.get("lta_exemption_claimed", 0) or 0), lta_received)

    deductions: list[dict[str, Any]] = []

    # --- Employee PF (statutory base is Basic + DA, not Basic alone) ---
    pf_ceiling_monthly = rules.get_value("PF_WAGE_CEILING", fy)
    pf_base_annual = basic_plus_da if pf_on_full_basic else min(basic_plus_da, pf_ceiling_monthly * 12)
    employee_pf_rate = rules.get_value("PF_EMPLOYEE_RATE", fy)
    employee_pf = employee_pf_rate * pf_base_annual
    deductions.append({
        "name": "Employee PF (EPF)",
        "rule_id": "PF_EMPLOYEE_RATE",
        "amount": _round2(employee_pf),
        "frequency": "annual",
    })

    # --- Employer PF (informational, not a deduction from gross-to-employee, but part of CTC) ---
    if ctc_breakup.get("employer_pf") is not None:
        employer_pf = float(ctc_breakup["employer_pf"])
        employer_pf_rule_id = "CTC_INPUT_OVERRIDE"
    else:
        employer_pf_rate = rules.get_value("PF_EMPLOYER_RATE", fy)
        employer_pf = employer_pf_rate * pf_base_annual
        employer_pf_rule_id = "PF_EMPLOYER_RATE"

    # --- Gross cash salary paid to the employee (excludes employer-side CTC components) ---
    gross_salary = (basic + da + hra + special_allowance + other_allowances_total
                    + bonus + retention_bonus + sales_commission + lta_received)
    gross_monthly = gross_salary / 12.0

    # --- ESI (employee + employer), only if gross monthly wage is within threshold ---
    esi_threshold = rules.get_value("ESI_WAGE_THRESHOLD", fy)
    esi_eligible = gross_monthly <= esi_threshold
    employee_esi = 0.0
    employer_esi = 0.0
    if esi_eligible:
        employee_esi = rules.get_value("ESI_EMPLOYEE_RATE", fy) * gross_salary
        employer_esi = rules.get_value("ESI_EMPLOYER_RATE", fy) * gross_salary
        deductions.append({
            "name": "Employee ESI",
            "rule_id": "ESI_EMPLOYEE_RATE",
            "amount": _round2(employee_esi),
            "frequency": "annual",
        })

    # --- Gratuity (employer-side CTC provision, informational only, not a cash deduction) ---
    if ctc_breakup.get("gratuity") is not None:
        gratuity_provision = float(ctc_breakup["gratuity"])
        gratuity_rule_id = "CTC_INPUT_OVERRIDE"
    else:
        gratuity_factor = rules.get_value("GRATUITY_FACTOR", fy)
        gratuity_provision = (basic_plus_da / 12.0) * gratuity_factor
        gratuity_rule_id = "GRATUITY_FACTOR"

    # --- Employer NPS/Superannuation (Section 80CCD(2)): a CTC cost paid to
    # the NPS fund, never part of gross cash salary, deductible from taxable
    # income under BOTH regimes, capped as a % of Basic+DA ---
    employer_nps = float(ctc_breakup.get("employer_nps") or 0)
    nps_cap_pct = rules.get_value("NPS_80CCD2_CAP_PCT", fy)
    nps_deduction = min(employer_nps, nps_cap_pct * basic_plus_da) if employer_nps > 0 else 0.0

    # --- Employer-paid health insurance premium: a CTC cost, not cash paid
    # to the employee, so it never touches gross salary or taxable income ---
    health_insurance_premium = float(ctc_breakup.get("health_insurance_premium", 0) or 0)

    # --- Professional tax (state-specific; not modelled, pass-through if supplied) ---
    if professional_tax > 0:
        deductions.append({
            "name": "Professional Tax",
            "rule_id": "PROFESSIONAL_TAX_STATE_SPECIFIC",
            "amount": _round2(professional_tax),
            "frequency": "annual",
        })

    # --- Cab/transport facility cost recovered from pay: a cash deduction,
    # not a tax rule (no rule_id) ---
    if transport_deduction > 0:
        deductions.append({
            "name": "Cab / Transport Deduction",
            "rule_id": None,
            "amount": _round2(transport_deduction),
            "frequency": "annual",
        })

    # --- HRA exemption (old regime only; base is Basic + DA) ---
    hra_exemption_amount = 0.0
    if regime == "old" and rent_paid is not None:
        hra_result = compute_hra_exemption(basic_plus_da, hra, float(rent_paid), is_metro, fy)
        hra_exemption_amount = hra_result["exempt_amount"]

    # --- Taxable income & income tax ---
    std_deduction_rule_id = "STD_DEDUCTION_OLD" if regime == "old" else "STD_DEDUCTION_NEW"
    std_deduction = rules.get_value(std_deduction_rule_id, fy)

    taxable_income = gross_salary - hra_exemption_amount - std_deduction - nps_deduction
    if regime == "old":
        cap_80c = rules.get_value("CAP_80C", fy)
        cap_80d = rules.get_value("CAP_80D_SELF", fy)
        claimed_80c = min(float(deductions_claimed.get("80C", 0) or 0), cap_80c)
        claimed_80d = min(float(deductions_claimed.get("80D", 0) or 0), cap_80d)
        # Professional tax and LTA exemption are deductible from salary income
        # under the old regime (Sections 16(iii) and 10(5)) but not under the new.
        taxable_income -= (claimed_80c + claimed_80d + professional_tax + lta_exemption_claimed)

    tax_result = compute_tax_for_regime(max(0.0, taxable_income), regime, fy)
    deductions.append({
        "name": "Income Tax (TDS)",
        "rule_id": "OLD_REGIME_SLABS" if regime == "old" else "NEW_REGIME_SLABS",
        "amount": tax_result["total_tax"],
        "frequency": "annual",
    })

    total_deductions = sum(d["amount"] for d in deductions)
    in_hand_annual = _round2(gross_salary - total_deductions)
    ctc_total = _round2(gross_salary + employer_pf + employer_esi + gratuity_provision
                         + employer_nps + health_insurance_premium)

    variable_pay_frequency = ctc_breakup.get("variable_pay_frequency")
    variable_pay_note = None
    if variable_pay_frequency and variable_pay_frequency != "monthly" and (bonus or retention_bonus or sales_commission):
        variable_pay_note = (f"Variable pay is paid {variable_pay_frequency}, as a lump sum — not spread evenly "
                              "across each month. The monthly in-hand figure above is the annual total divided "
                              "by 12, which won't match what actually lands in any single month.")

    equity = None
    if any(ctc_breakup.get(f) is not None for f in
           ("equity_type", "equity_grant_value", "equity_unit_count", "equity_vesting_schedule",
            "equity_cliff_period_months")):
        equity = {
            "equity_type": ctc_breakup.get("equity_type"),
            "grant_value": ctc_breakup.get("equity_grant_value"),
            "unit_count": ctc_breakup.get("equity_unit_count"),
            "vesting_schedule": ctc_breakup.get("equity_vesting_schedule"),
            "cliff_period_months": ctc_breakup.get("equity_cliff_period_months"),
            "note": "Equity is displayed as provided only — not valued, vested, or taxed by this engine.",
        }

    return {
        "regime": regime,
        "ctc_total": ctc_total,
        "gross_salary_annual": _round2(gross_salary),
        "gross_salary_monthly": _round2(gross_monthly),
        "taxable_income": tax_result["taxable_income"],
        "std_deduction_rule_id": std_deduction_rule_id,
        "std_deduction_amount": std_deduction,
        "hra_exemption_amount": hra_exemption_amount,
        "lta_exemption_amount": lta_exemption_claimed if regime == "old" else 0.0,
        "nps_deduction_amount": _round2(nps_deduction),
        "deductions": deductions,
        "total_deductions_annual": _round2(total_deductions),
        "in_hand_annual": in_hand_annual,
        "in_hand_monthly": _round2(in_hand_annual / 12.0),
        "employer_side": {
            "employer_pf": {"amount": _round2(employer_pf), "rule_id": employer_pf_rule_id},
            "employer_esi": {"amount": _round2(employer_esi), "rule_id": "ESI_EMPLOYER_RATE" if esi_eligible else None},
            "gratuity_provision": {"amount": _round2(gratuity_provision), "rule_id": gratuity_rule_id},
            "employer_nps": {"amount": _round2(employer_nps), "rule_id": "NPS_80CCD2_CAP_PCT" if employer_nps else None},
            "health_insurance": {"amount": _round2(health_insurance_premium), "rule_id": None},
        },
        "esi_eligible": esi_eligible,
        "tax_breakdown": tax_result,
        "variable_pay_frequency": variable_pay_frequency,
        "variable_pay_note": variable_pay_note,
        "equity": equity,
    }


# ---------------------------------------------------------------------------
# 2. compute_regime_comparison
# ---------------------------------------------------------------------------

def compute_regime_comparison(gross_salary: float, deductions_claimed: dict[str, Any] | None = None,
                               hra_exemption: float = 0.0, fy: str | None = None) -> dict[str, Any]:
    """Compare old vs new regime tax liability for a given gross salary.

    deductions_claimed (old regime only): {"80C": float, "80D": float}.
    hra_exemption: pre-computed HRA exemption amount (old regime only) —
    callers should use compute_hra_exemption() to derive this.
    """
    deductions_claimed = deductions_claimed or {}
    cap_80c = rules.get_value("CAP_80C", fy)
    cap_80d = rules.get_value("CAP_80D_SELF", fy)
    claimed_80c = min(float(deductions_claimed.get("80C", 0) or 0), cap_80c)
    claimed_80d = min(float(deductions_claimed.get("80D", 0) or 0), cap_80d)

    std_old = rules.get_value("STD_DEDUCTION_OLD", fy)
    std_new = rules.get_value("STD_DEDUCTION_NEW", fy)

    old_taxable = max(0.0, gross_salary - hra_exemption - std_old - claimed_80c - claimed_80d)
    new_taxable = max(0.0, gross_salary - std_new)

    old_result = compute_tax_for_regime(old_taxable, "old", fy)
    new_result = compute_tax_for_regime(new_taxable, "new", fy)

    recommended: Regime = "old" if old_result["total_tax"] < new_result["total_tax"] else "new"
    savings = abs(old_result["total_tax"] - new_result["total_tax"])

    # Per-deduction impact: tax saved by each old-regime-only deduction,
    # computed as the marginal difference in old-regime tax with vs. without it.
    per_deduction_impact = []

    def _old_tax_without(exclude: dict[str, float]) -> float:
        taxable = max(0.0, gross_salary
                      - (0.0 if exclude.get("hra") else hra_exemption)
                      - std_old
                      - (0.0 if exclude.get("80C") else claimed_80c)
                      - (0.0 if exclude.get("80D") else claimed_80d))
        return compute_tax_for_regime(taxable, "old", fy)["total_tax"]

    baseline_old_tax = old_result["total_tax"]

    if hra_exemption > 0:
        tax_without = _old_tax_without({"hra": True})
        per_deduction_impact.append({
            "name": "HRA Exemption",
            "rule_id": "HRA_METRO_PCT",
            "claimed_amount": _round2(hra_exemption),
            "tax_saved": _round2(tax_without - baseline_old_tax),
            "applies_to": "old_regime",
        })
    if claimed_80c > 0:
        tax_without = _old_tax_without({"80C": True})
        per_deduction_impact.append({
            "name": "Section 80C",
            "rule_id": "CAP_80C",
            "claimed_amount": _round2(claimed_80c),
            "tax_saved": _round2(tax_without - baseline_old_tax),
            "applies_to": "old_regime",
        })
    if claimed_80d > 0:
        tax_without = _old_tax_without({"80D": True})
        per_deduction_impact.append({
            "name": "Section 80D",
            "rule_id": "CAP_80D_SELF",
            "claimed_amount": _round2(claimed_80d),
            "tax_saved": _round2(tax_without - baseline_old_tax),
            "applies_to": "old_regime",
        })

    return {
        "gross_salary": _round2(gross_salary),
        "old_regime_tax": old_result,
        "new_regime_tax": new_result,
        "recommended": recommended,
        "annual_savings_with_recommended": _round2(savings),
        "per_deduction_impact": per_deduction_impact,
    }


# ---------------------------------------------------------------------------
# 3. detect_red_flags
# ---------------------------------------------------------------------------

def detect_red_flags(offer_data: dict[str, Any], fy: str | None = None) -> list[dict[str, Any]]:
    """Simple threshold checks over an offer's structured fields.

    Expected offer_data fields (superset of ctc_breakup):
      basic, hra, bonus (all annual), ctc_total (optional, else summed),
      employer_pf (optional; None/0 with basic>0 flags missing PF),
      gratuity_clause_present (bool, default True),
      notice_period_days (optional),
      has_service_bond (bool, default False),
      joining_bonus_has_clawback (bool, default False).
    """
    flags: list[dict[str, Any]] = []

    basic = float(offer_data.get("basic", 0) or 0)
    hra = float(offer_data.get("hra", 0) or 0)
    bonus = float(offer_data.get("bonus", 0) or 0)
    retention_bonus = float(offer_data.get("retention_bonus", 0) or 0)
    sales_commission = float(offer_data.get("sales_commission", 0) or 0)
    variable_total = bonus + retention_bonus + sales_commission
    special_allowance = float(offer_data.get("special_allowance", 0) or 0)
    dearness_allowance = float(offer_data.get("dearness_allowance", 0) or 0)
    lta_received = float(offer_data.get("lta_received", 0) or 0)
    other_allowances = offer_data.get("other_allowances") or {}
    other_allowances_total = float(sum(other_allowances.values()))

    ctc_total = offer_data.get("ctc_total")
    if ctc_total is None:
        ctc_total = (basic + hra + dearness_allowance + variable_total + special_allowance
                     + lta_received + other_allowances_total)
    ctc_total = float(ctc_total)

    if ctc_total > 0:
        variable_pct = variable_total / ctc_total
        threshold = rules.get_value("RED_FLAG_VARIABLE_PAY_PCT", fy)
        if variable_pct > threshold:
            flags.append({
                "flag_id": "HIGH_VARIABLE_PAY",
                "severity": "warning",
                "rule_id": "RED_FLAG_VARIABLE_PAY_PCT",
                "field": "bonus",
                "message": (f"Variable pay (bonus, retention bonus, commission) is {variable_pct:.0%} of CTC, "
                            f"above the {threshold:.0%} threshold — a significant portion of this offer is "
                            "not guaranteed."),
            })

        basic_pct = basic / ctc_total
        min_basic_threshold = rules.get_value("RED_FLAG_BASIC_PCT_MIN", fy)
        if basic_pct < min_basic_threshold:
            flags.append({
                "flag_id": "LOW_BASIC_SALARY",
                "severity": "warning",
                "rule_id": "RED_FLAG_BASIC_PCT_MIN",
                "field": "basic",
                "message": (f"Basic salary is only {basic_pct:.0%} of CTC, below the {min_basic_threshold:.0%} "
                            "benchmark — this lowers your PF contribution, gratuity and HRA exemption, "
                            "since all three are calculated on Basic."),
            })

    employer_pf = offer_data.get("employer_pf")
    if basic > 0 and (employer_pf is None or float(employer_pf) == 0):
        flags.append({
            "flag_id": "MISSING_PF",
            "severity": "critical",
            "rule_id": "PF_EMPLOYER_RATE",
            "field": "employer_pf",
            "message": "No employer PF contribution found in the offer. EPF is mandatory for eligible "
                       "employees under the EPF & MP Act — confirm this wasn't omitted from the breakup.",
        })

    if offer_data.get("gratuity_clause_present", True) is False:
        flags.append({
            "flag_id": "MISSING_GRATUITY_CLAUSE",
            "severity": "info",
            "rule_id": "GRATUITY_FACTOR",
            "field": "gratuity_clause_present",
            "message": "No gratuity clause found. Gratuity is a statutory benefit payable after 5 years "
                       "of continuous service, regardless of whether the offer letter mentions it.",
        })

    notice_period_days = offer_data.get("notice_period_days")
    if notice_period_days is not None:
        notice_threshold = rules.get_value("RED_FLAG_NOTICE_PERIOD_DAYS", fy)
        if float(notice_period_days) > notice_threshold:
            flags.append({
                "flag_id": "LONG_NOTICE_PERIOD",
                "severity": "info",
                "rule_id": "RED_FLAG_NOTICE_PERIOD_DAYS",
                "field": "notice_period_days",
                "message": (f"Notice period is {int(notice_period_days)} days, longer than the "
                            f"{notice_threshold}-day benchmark — factor this into how quickly you "
                            "could join a future employer."),
            })

    if offer_data.get("has_service_bond"):
        flags.append({
            "flag_id": "SERVICE_BOND",
            "severity": "warning",
            "rule_id": None,
            "field": "has_service_bond",
            "message": "This offer includes a service bond. Check the lock-in period and the exact "
                       "penalty for leaving early before accepting.",
        })

    if offer_data.get("joining_bonus_has_clawback"):
        clawback_months = offer_data.get("joining_bonus_clawback_period_months")
        if clawback_months:
            message = (f"The joining bonus must be repaid if you leave within {int(clawback_months)} months — "
                       "confirm whether the repayment is pro-rated.")
        else:
            message = ("The joining bonus is subject to clawback if you leave within a certain period — "
                       "confirm the clawback window and whether it's pro-rated.")
        flags.append({
            "flag_id": "JOINING_BONUS_CLAWBACK",
            "severity": "info",
            "rule_id": None,
            "field": "joining_bonus_has_clawback",
            "message": message,
        })

    return flags


# ---------------------------------------------------------------------------
# 4. classify_compensation_components
# ---------------------------------------------------------------------------

def classify_compensation_components(ctc_breakup: dict[str, Any], regime: Regime = "new",
                                      fy: str | None = None) -> dict[str, Any]:
    """Bucket a raw CTC breakup into Fixed / Employer Contributions / Variable /
    One-time, so the frontend can show "your CTC is not all cash compensation"
    without re-deriving anything compute_in_hand already owns.

    Calls compute_in_hand() internally to source Employer PF/gratuity amounts
    even when the caller didn't supply explicit overrides for them (the
    common case), so `recurring_ctc_total` here always matches
    compute_in_hand()'s `ctc_total` for the same input.

    This is a structural regrouping, not a computed legal figure, so line
    items don't carry a rule_id the way tax/PF numbers do — the bucket
    definitions themselves are the "rule". `one_time_components` (e.g.
    joining bonus, relocation) are NOT part of the recurring `ctc_total`,
    since they are typically one-off payments outside the annual CTC figure;
    they are kept in a separate bucket for that reason.
    """
    in_hand = compute_in_hand(ctc_breakup, regime=regime, fy=fy)

    def _item(label: str, amount: float) -> dict[str, Any]:
        return {"label": label, "amount": _round2(amount)}

    fixed_items = [_item("Basic", float(ctc_breakup.get("basic", 0) or 0))]
    hra = float(ctc_breakup.get("hra", 0) or 0)
    if hra:
        fixed_items.append(_item("HRA", hra))
    da = float(ctc_breakup.get("dearness_allowance", 0) or 0)
    if da:
        fixed_items.append(_item("Dearness Allowance", da))
    special_allowance = float(ctc_breakup.get("special_allowance", 0) or 0)
    if special_allowance:
        fixed_items.append(_item("Special Allowance", special_allowance))
    lta_received = float(ctc_breakup.get("lta_received", 0) or 0)
    if lta_received:
        fixed_items.append(_item("Leave Travel Allowance (LTA)", lta_received))
    for name, amount in (ctc_breakup.get("other_allowances") or {}).items():
        fixed_items.append(_item(name, float(amount)))

    employer_items: list[dict[str, Any]] = []
    employer_pf_amount = in_hand["employer_side"]["employer_pf"]["amount"]
    if employer_pf_amount:
        employer_items.append(_item("Employer PF", employer_pf_amount))
    employer_esi_amount = in_hand["employer_side"]["employer_esi"]["amount"]
    if employer_esi_amount:
        employer_items.append(_item("Employer ESI", employer_esi_amount))
    employer_nps_amount = in_hand["employer_side"]["employer_nps"]["amount"]
    if employer_nps_amount:
        employer_items.append(_item("Employer NPS / Superannuation", employer_nps_amount))
    health_insurance_amount = in_hand["employer_side"]["health_insurance"]["amount"]
    if health_insurance_amount:
        employer_items.append(_item("Health Insurance Premium", health_insurance_amount))
    gratuity_amount = in_hand["employer_side"]["gratuity_provision"]["amount"]
    if gratuity_amount:
        employer_items.append(_item("Gratuity Provision", gratuity_amount))

    variable_items: list[dict[str, Any]] = []
    bonus = float(ctc_breakup.get("bonus", 0) or 0)
    if bonus:
        variable_items.append(_item("Bonus / Variable Pay", bonus))
    retention_bonus = float(ctc_breakup.get("retention_bonus", 0) or 0)
    if retention_bonus:
        variable_items.append(_item("Retention Bonus", retention_bonus))
    sales_commission = float(ctc_breakup.get("sales_commission", 0) or 0)
    if sales_commission:
        variable_items.append(_item("Sales Commission / Incentives", sales_commission))

    one_time_items = [_item(name, float(amount))
                       for name, amount in (ctc_breakup.get("one_time_components") or {}).items()]

    fixed_total = sum(i["amount"] for i in fixed_items)
    employer_total = sum(i["amount"] for i in employer_items)
    variable_total = sum(i["amount"] for i in variable_items)
    one_time_total = sum(i["amount"] for i in one_time_items)
    recurring_ctc_total = fixed_total + employer_total + variable_total

    def _bucket(bucket_id: str, label: str, items: list[dict[str, Any]], total: float,
                pct_of_ctc: float | None) -> dict[str, Any]:
        return {
            "bucket": bucket_id, "label": label, "items": items, "total": _round2(total),
            "pct_of_ctc": _round2(pct_of_ctc) if pct_of_ctc is not None else None,
        }

    pct = (lambda x: x / recurring_ctc_total) if recurring_ctc_total > 0 else (lambda x: None)

    buckets = [
        _bucket("fixed_compensation", "Fixed Compensation", fixed_items, fixed_total, pct(fixed_total)),
        _bucket("employer_contributions", "Employer Contributions", employer_items, employer_total,
                pct(employer_total)),
        _bucket("variable", "Variable", variable_items, variable_total, pct(variable_total)),
        _bucket("one_time", "One-time (not part of annual CTC)", one_time_items, one_time_total, None),
    ]

    if in_hand.get("equity"):
        equity = in_hand["equity"]
        equity_label = equity["equity_type"] or "Equity"
        equity_amount = equity["grant_value"] or 0
        buckets.append(_bucket("equity", "Equity (not valued/vested by this engine)",
                                [_item(equity_label, float(equity_amount))], equity_amount, None))

    return {
        "recurring_ctc_total": _round2(recurring_ctc_total),
        "one_time_total": _round2(one_time_total),
        "buckets": buckets,
    }


# ---------------------------------------------------------------------------
# 5. compute_ctc_waterfall
# ---------------------------------------------------------------------------

def compute_ctc_waterfall(ctc_breakup: dict[str, Any], regime: Regime = "new",
                           fy: str | None = None) -> dict[str, Any]:
    """Reshape a compute_in_hand() result into an ordered CTC -> in-hand
    waterfall (CTC, minus each employer-side and employee-side deduction, in
    order, down to monthly in-hand). Every subtracted step carries the same
    rule_id the underlying deduction/employer_side entry already has —
    this function invents no new numbers, only an ordering.
    """
    result = compute_in_hand(ctc_breakup, regime=regime, fy=fy)
    steps: list[dict[str, Any]] = []

    running = result["ctc_total"]
    steps.append({"label": "CTC (Total Cost to Company)", "amount": running,
                   "running_balance": running, "kind": "start", "rule_id": None})

    for label, key in (("Employer PF", "employer_pf"), ("Employer ESI", "employer_esi"),
                        ("Employer NPS / Superannuation", "employer_nps"),
                        ("Health Insurance Premium", "health_insurance"),
                        ("Gratuity Provision", "gratuity_provision")):
        item = result["employer_side"][key]
        if item["amount"]:
            running = _round2(running - item["amount"])
            steps.append({"label": label, "amount": -item["amount"], "running_balance": running,
                           "kind": "employer_side_deduction", "rule_id": item["rule_id"]})

    steps.append({"label": "Gross Salary (paid to you annually)", "amount": result["gross_salary_annual"],
                   "running_balance": result["gross_salary_annual"], "kind": "subtotal", "rule_id": None})

    running = result["gross_salary_annual"]
    for d in result["deductions"]:
        running = _round2(running - d["amount"])
        steps.append({"label": d["name"], "amount": -d["amount"], "running_balance": running,
                       "kind": "employee_deduction", "rule_id": d["rule_id"]})

    steps.append({"label": "Annual In-Hand", "amount": result["in_hand_annual"],
                   "running_balance": result["in_hand_annual"], "kind": "end", "rule_id": None})
    steps.append({"label": "Monthly In-Hand", "amount": result["in_hand_monthly"],
                   "running_balance": result["in_hand_monthly"], "kind": "end_monthly", "rule_id": None})

    return {
        "steps": steps,
        "ctc_total": result["ctc_total"],
        "in_hand_annual": result["in_hand_annual"],
        "in_hand_monthly": result["in_hand_monthly"],
    }


# ---------------------------------------------------------------------------
# 6. compute_offer_quality_score
# ---------------------------------------------------------------------------

def compute_offer_quality_score(ctc_breakup: dict[str, Any], regime: Regime = "new",
                                 fy: str | None = None) -> dict[str, Any]:
    """A transparent 0-100 Compensation Quality Score. Every sub-score has an
    explicit formula grounded in a versioned rule (weights, benchmarks, and
    point allocations all live in data/rules.json, never inline here) —
    nothing here is an opaque "AI opinion" of offer quality.
    """
    in_hand = compute_in_hand(ctc_breakup, regime=regime, fy=fy)
    classification = classify_compensation_components(ctc_breakup, regime=regime, fy=fy)
    ctc_total = in_hand["ctc_total"]

    weights = rules.get_value("QUALITY_SCORE_WEIGHTS", fy)
    fixed_benchmark = rules.get_value("QUALITY_FIXED_RATIO_BENCHMARK", fy)
    take_home_benchmark = rules.get_value("QUALITY_TAKE_HOME_RATIO_BENCHMARK", fy)
    variable_threshold = rules.get_value("RED_FLAG_VARIABLE_PAY_PCT", fy)
    benefits_points = rules.get_value("QUALITY_BENEFITS_POINTS", fy)

    def _clamp(x: float) -> float:
        return max(0.0, min(100.0, x))

    fixed_bucket = next(b for b in classification["buckets"] if b["bucket"] == "fixed_compensation")
    variable_bucket = next(b for b in classification["buckets"] if b["bucket"] == "variable")

    fixed_ratio = (fixed_bucket["total"] / ctc_total) if ctc_total > 0 else 0.0
    variable_ratio = (variable_bucket["total"] / ctc_total) if ctc_total > 0 else 0.0
    take_home_ratio = (in_hand["in_hand_annual"] / ctc_total) if ctc_total > 0 else 0.0

    fixed_ratio_score = _clamp(100 * fixed_ratio / fixed_benchmark) if fixed_benchmark > 0 else 0.0
    variable_dependence_score = _clamp(100 * (1 - variable_ratio / variable_threshold)) \
        if variable_threshold > 0 else 0.0
    take_home_ratio_score = _clamp(100 * take_home_ratio / take_home_benchmark) if take_home_benchmark > 0 else 0.0

    esi_eligible = in_hand["esi_eligible"]
    employer_esi_amount = in_hand["employer_side"]["employer_esi"]["amount"]
    esi_handled = (not esi_eligible) or employer_esi_amount > 0

    benefits_score = 0.0
    if float(ctc_breakup.get("employer_pf") or 0) > 0 or in_hand["employer_side"]["employer_pf"]["amount"] > 0:
        benefits_score += benefits_points["employer_pf"]
    if in_hand["employer_side"]["gratuity_provision"]["amount"] > 0 and \
            ctc_breakup.get("gratuity_clause_present", True) is not False:
        benefits_score += benefits_points["gratuity"]
    if esi_handled:
        benefits_score += benefits_points["esi_handled"]
    benefits_score = _clamp(benefits_score)

    sub_scores = {
        "fixed_ratio": {"score": _round2(fixed_ratio_score), "value": _round2(fixed_ratio),
                         "benchmark": fixed_benchmark, "rule_id": "QUALITY_FIXED_RATIO_BENCHMARK",
                         "weight": weights["fixed_ratio"]},
        "variable_dependence": {"score": _round2(variable_dependence_score), "value": _round2(variable_ratio),
                                 "benchmark": variable_threshold, "rule_id": "RED_FLAG_VARIABLE_PAY_PCT",
                                 "weight": weights["variable_dependence"]},
        "take_home_ratio": {"score": _round2(take_home_ratio_score), "value": _round2(take_home_ratio),
                             "benchmark": take_home_benchmark, "rule_id": "QUALITY_TAKE_HOME_RATIO_BENCHMARK",
                             "weight": weights["take_home_ratio"]},
        "benefits": {"score": _round2(benefits_score), "value": None, "benchmark": None,
                     "rule_id": "QUALITY_BENEFITS_POINTS", "weight": weights["benefits"]},
    }

    overall = sum(s["score"] * s["weight"] for s in sub_scores.values())

    return {
        "overall_score": round(overall),
        "weights_rule_id": "QUALITY_SCORE_WEIGHTS",
        "sub_scores": sub_scores,
    }


# ---------------------------------------------------------------------------
# 7. compare_offers
# ---------------------------------------------------------------------------

def compare_offers(offer_a: dict[str, Any], offer_b: dict[str, Any], fy: str | None = None) -> dict[str, Any]:
    """Side-by-side comparison of two offers. Each of offer_a/offer_b is
    {"label": str, "ctc_breakup": {...}, "regime": "old"|"new"}. Reuses
    compute_in_hand/compute_offer_quality_score per offer, then reports the
    deltas a candidate actually cares about (cashflow vs. total comp) —
    no LLM judgement, just arithmetic differences between two already-computed
    results.
    """
    def _evaluate(offer: dict[str, Any]) -> dict[str, Any]:
        breakup = offer["ctc_breakup"]
        regime: Regime = offer.get("regime", "new")
        in_hand = compute_in_hand(breakup, regime=regime, fy=fy)
        classification = classify_compensation_components(breakup, regime=regime, fy=fy)
        quality = compute_offer_quality_score(breakup, regime=regime, fy=fy)
        return {
            "label": offer.get("label", "Offer"),
            "regime": regime,
            "in_hand": in_hand,
            "classification": classification,
            "quality_score": quality,
        }

    a = _evaluate(offer_a)
    b = _evaluate(offer_b)

    ctc_diff = _round2(b["in_hand"]["ctc_total"] - a["in_hand"]["ctc_total"])
    monthly_diff = _round2(b["in_hand"]["in_hand_monthly"] - a["in_hand"]["in_hand_monthly"])
    annual_diff = _round2(b["in_hand"]["in_hand_annual"] - a["in_hand"]["in_hand_annual"])
    quality_diff = b["quality_score"]["overall_score"] - a["quality_score"]["overall_score"]

    best_for_cashflow = "offer_a" if monthly_diff < 0 else ("offer_b" if monthly_diff > 0 else "tie")
    best_for_total_comp = "offer_a" if ctc_diff < 0 else ("offer_b" if ctc_diff > 0 else "tie")

    return {
        "offer_a": a,
        "offer_b": b,
        "diff": {
            "ctc_total": ctc_diff,
            "in_hand_monthly": monthly_diff,
            "in_hand_annual": annual_diff,
            "quality_score": quality_diff,
        },
        "best_for_cashflow": best_for_cashflow,
        "best_for_total_comp": best_for_total_comp,
    }


# ---------------------------------------------------------------------------
# 8. compute_epf_gratuity_timeline
# ---------------------------------------------------------------------------

def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        # joining date was Feb 29 on a leap year; land on Feb 28 instead
        return d.replace(year=d.year + years, day=28)


def compute_epf_gratuity_timeline(joining_date: str, as_of_date: str | None = None,
                                   separation_date: str | None = None, fy: str | None = None) -> dict[str, Any]:
    """Gratuity vesting and EPF continuity timeline from a joining date.

    Every threshold (5-year gratuity vesting, 5-year EPF tax-free withdrawal,
    10-year EPS pension eligibility) is a versioned rule, not a hardcoded
    number, so this is explanation grounded in `rule_id`s like everything
    else — no LLM judgement about whether gratuity is forfeited or an EPF
    withdrawal is taxable, only date arithmetic against those rules.

    If `separation_date` is given, evaluates the outcome AT exit (gratuity
    payable vs. forfeited). Otherwise evaluates tenure as of `as_of_date`
    (default: today) for an employee still employed.
    """
    joining = date.fromisoformat(joining_date)
    evaluation_date = date.fromisoformat(separation_date) if separation_date else (
        date.fromisoformat(as_of_date) if as_of_date else date.today()
    )
    tenure_years = (evaluation_date - joining).days / 365.25

    vesting_years = rules.get_value("GRATUITY_VESTING_YEARS", fy)
    epf_tax_free_years = rules.get_value("EPF_TAX_FREE_WITHDRAWAL_YEARS", fy)
    eps_pension_years = rules.get_value("EPS_PENSION_MIN_SERVICE_YEARS", fy)

    gratuity_vested = tenure_years >= vesting_years
    vesting_date = _add_years(joining, vesting_years)
    if separation_date:
        gratuity = {
            "vested": gratuity_vested,
            "outcome": "payable" if gratuity_vested else "forfeited",
            "rule_id": "GRATUITY_VESTING_YEARS",
            "note": ("Gratuity is payable — service at separation meets the "
                     f"{vesting_years}-year vesting requirement.") if gratuity_vested else
                    ("Gratuity is forfeited — service ended before the "
                     f"{vesting_years}-year vesting requirement, unless the exit was due to "
                     "death or permanent disablement (not evaluated here)."),
        }
    else:
        gratuity = {
            "vested": gratuity_vested,
            "vesting_date": vesting_date.isoformat(),
            "days_to_vesting": None if gratuity_vested else (vesting_date - evaluation_date).days,
            "rule_id": "GRATUITY_VESTING_YEARS",
            "note": "Gratuity has vested." if gratuity_vested else
                    (f"Gratuity vests on {vesting_date.isoformat()}; leaving before then forfeits it "
                     "unless the exit is due to death or permanent disablement."),
        }

    epf_tax_free = tenure_years >= epf_tax_free_years
    epf = {
        "continuous_service_years": _round2(tenure_years),
        "tax_free_withdrawal_eligible": epf_tax_free,
        "rule_id": "EPF_TAX_FREE_WITHDRAWAL_YEARS",
        "withdrawal_note": ("Withdrawing the full EPF balance now is tax-free — "
                             f"continuous service ({_round2(tenure_years)} yrs) meets the "
                             f"{epf_tax_free_years}-year threshold.") if epf_tax_free else
                            (f"Withdrawing now, at {_round2(tenure_years)} yrs of service, would make the "
                             "employer's contribution and interest taxable as income "
                             f"— the tax-free threshold is {epf_tax_free_years} years."),
        "transfer_note": ("Transferring the EPF balance to a new employer via UAN (instead of withdrawing) "
                           "preserves continuity of service for this threshold and for the "
                           f"{eps_pension_years}-year EPS pension eligibility below."),
    }

    milestones = [
        {"label": "Joining", "date": joining.isoformat(), "rule_id": None,
         "status": "past" if joining <= evaluation_date else "upcoming"},
        {"label": f"Gratuity Vesting ({vesting_years} yrs)", "date": vesting_date.isoformat(),
         "rule_id": "GRATUITY_VESTING_YEARS",
         "status": "past" if vesting_date <= evaluation_date else "upcoming"},
        {"label": f"EPF Withdrawal Tax-Free ({epf_tax_free_years} yrs)",
         "date": _add_years(joining, epf_tax_free_years).isoformat(), "rule_id": "EPF_TAX_FREE_WITHDRAWAL_YEARS",
         "status": "past" if epf_tax_free else "upcoming"},
        {"label": f"EPS Pension Eligibility ({eps_pension_years} yrs, if continuously transferred)",
         "date": _add_years(joining, eps_pension_years).isoformat(), "rule_id": "EPS_PENSION_MIN_SERVICE_YEARS",
         "status": "past" if tenure_years >= eps_pension_years else "upcoming"},
    ]

    return {
        "joining_date": joining.isoformat(),
        "evaluation_date": evaluation_date.isoformat(),
        "tenure_years": _round2(tenure_years),
        "gratuity": gratuity,
        "epf": epf,
        "milestones": milestones,
    }
