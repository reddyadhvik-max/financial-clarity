"""Pure calculation engine. No LLM, no I/O beyond reading versioned rule data.

Every number these functions produce is traceable to a rule_id, so the API
layer and frontend can show "this figure came from rule X" without ever
inventing a description themselves.

All monetary inputs/outputs are annual INR unless a field name says
otherwise. All functions are pure: same input -> same output, always.
"""
from __future__ import annotations

from dataclasses import dataclass, field
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
    pf_on_full_basic = bool(ctc_breakup.get("pf_on_full_basic", True))
    professional_tax = float(ctc_breakup.get("professional_tax", 0) or 0)
    deductions_claimed = ctc_breakup.get("deductions_claimed") or {}
    rent_paid = ctc_breakup.get("rent_paid")
    is_metro = bool(ctc_breakup.get("is_metro", False))

    deductions: list[dict[str, Any]] = []

    # --- Employee PF ---
    pf_ceiling_monthly = rules.get_value("PF_WAGE_CEILING", fy)
    pf_base_annual = basic if pf_on_full_basic else min(basic, pf_ceiling_monthly * 12)
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
    gross_salary = basic + hra + special_allowance + other_allowances_total + bonus
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
        gratuity_provision = (basic / 12.0) * gratuity_factor
        gratuity_rule_id = "GRATUITY_FACTOR"

    # --- Professional tax (state-specific; not modelled, pass-through if supplied) ---
    if professional_tax > 0:
        deductions.append({
            "name": "Professional Tax",
            "rule_id": "PROFESSIONAL_TAX_STATE_SPECIFIC",
            "amount": _round2(professional_tax),
            "frequency": "annual",
        })

    # --- HRA exemption (old regime only) ---
    hra_exemption_amount = 0.0
    if regime == "old" and rent_paid is not None:
        hra_result = compute_hra_exemption(basic, hra, float(rent_paid), is_metro, fy)
        hra_exemption_amount = hra_result["exempt_amount"]

    # --- Taxable income & income tax ---
    std_deduction_rule_id = "STD_DEDUCTION_OLD" if regime == "old" else "STD_DEDUCTION_NEW"
    std_deduction = rules.get_value(std_deduction_rule_id, fy)

    taxable_income = gross_salary - hra_exemption_amount - std_deduction
    if regime == "old":
        cap_80c = rules.get_value("CAP_80C", fy)
        cap_80d = rules.get_value("CAP_80D_SELF", fy)
        claimed_80c = min(float(deductions_claimed.get("80C", 0) or 0), cap_80c)
        claimed_80d = min(float(deductions_claimed.get("80D", 0) or 0), cap_80d)
        # Professional tax is deductible from salary income under the old regime
        # (Section 16(iii)) but not available under the new regime.
        taxable_income -= (claimed_80c + claimed_80d + professional_tax)

    tax_result = compute_tax_for_regime(max(0.0, taxable_income), regime, fy)
    deductions.append({
        "name": "Income Tax (TDS)",
        "rule_id": "OLD_REGIME_SLABS" if regime == "old" else "NEW_REGIME_SLABS",
        "amount": tax_result["total_tax"],
        "frequency": "annual",
    })

    total_deductions = sum(d["amount"] for d in deductions)
    in_hand_annual = _round2(gross_salary - total_deductions)
    ctc_total = _round2(gross_salary + employer_pf + employer_esi + gratuity_provision)

    return {
        "regime": regime,
        "ctc_total": ctc_total,
        "gross_salary_annual": _round2(gross_salary),
        "gross_salary_monthly": _round2(gross_monthly),
        "taxable_income": tax_result["taxable_income"],
        "std_deduction_rule_id": std_deduction_rule_id,
        "std_deduction_amount": std_deduction,
        "hra_exemption_amount": hra_exemption_amount,
        "deductions": deductions,
        "total_deductions_annual": _round2(total_deductions),
        "in_hand_annual": in_hand_annual,
        "in_hand_monthly": _round2(in_hand_annual / 12.0),
        "employer_side": {
            "employer_pf": {"amount": _round2(employer_pf), "rule_id": employer_pf_rule_id},
            "employer_esi": {"amount": _round2(employer_esi), "rule_id": "ESI_EMPLOYER_RATE" if esi_eligible else None},
            "gratuity_provision": {"amount": _round2(gratuity_provision), "rule_id": gratuity_rule_id},
        },
        "esi_eligible": esi_eligible,
        "tax_breakdown": tax_result,
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
    special_allowance = float(offer_data.get("special_allowance", 0) or 0)
    other_allowances = offer_data.get("other_allowances") or {}
    other_allowances_total = float(sum(other_allowances.values()))

    ctc_total = offer_data.get("ctc_total")
    if ctc_total is None:
        ctc_total = basic + hra + bonus + special_allowance + other_allowances_total
    ctc_total = float(ctc_total)

    if ctc_total > 0:
        variable_pct = bonus / ctc_total
        threshold = rules.get_value("RED_FLAG_VARIABLE_PAY_PCT", fy)
        if variable_pct > threshold:
            flags.append({
                "flag_id": "HIGH_VARIABLE_PAY",
                "severity": "warning",
                "rule_id": "RED_FLAG_VARIABLE_PAY_PCT",
                "field": "bonus",
                "message": (f"Variable/bonus pay is {variable_pct:.0%} of CTC, above the {threshold:.0%} "
                            "threshold — a significant portion of this offer is not guaranteed."),
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
        flags.append({
            "flag_id": "JOINING_BONUS_CLAWBACK",
            "severity": "info",
            "rule_id": None,
            "field": "joining_bonus_has_clawback",
            "message": "The joining bonus is subject to clawback if you leave within a certain period — "
                       "confirm the clawback window and whether it's pro-rated.",
        })

    return flags
