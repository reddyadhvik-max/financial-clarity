"""Canonical field schema for the compensation data parser.

Every field the parser can extract has exactly one canonical key here. Every
raw label variant a real offer letter might use for that field (including
the acronyms/shortforms companies actually use) is registered in
``ALIASES`` so ``normalize.py`` can map free-text labels onto the canonical
key regardless of how a given company phrases it.

This file is deliberately data, not logic — extractors, normalizers, and the
comparison/checklist code all read from here so the field list only has to
be maintained in one place.
"""
from __future__ import annotations

from typing import Literal

Category = Literal[
    "top_line", "fixed", "retirals", "variable", "one_time", "deductions", "derived"
]

# ---------------------------------------------------------------------------
# Canonical fields, grouped by category. `unit` is "currency" (annual INR
# unless noted), "text" (categorical/free text), "months" (a duration), or
# "count" (a unit count, e.g. equity units).
# ---------------------------------------------------------------------------

FIELDS: dict[str, dict[str, str]] = {
    # --- Top-Line Metrics ---
    "total_ctc": {"category": "top_line", "unit": "currency",
                  "label": "Total CTC (Cost to Company)"},
    "total_gross_pay": {"category": "top_line", "unit": "currency",
                         "label": "Total Gross Pay (pre-tax cash)"},
    "target_net_pay": {"category": "top_line", "unit": "currency",
                        "label": "Target Net Pay (in-hand take-home)"},

    # --- Fixed Components ---
    "basic_pay": {"category": "fixed", "unit": "currency", "label": "Basic Pay"},
    "hra": {"category": "fixed", "unit": "currency", "label": "House Rent Allowance"},
    "special_allowance": {"category": "fixed", "unit": "currency",
                           "label": "Special / Flexible Allowance"},
    "lta": {"category": "fixed", "unit": "currency", "label": "Leave Travel Allowance"},
    "da": {"category": "fixed", "unit": "currency", "label": "Dearness Allowance"},

    # --- Retirals ---
    "employer_pf": {"category": "retirals", "unit": "currency", "label": "Employer Provident Fund"},
    "gratuity": {"category": "retirals", "unit": "currency", "label": "Gratuity"},
    "superannuation_nps": {"category": "retirals", "unit": "currency",
                            "label": "Superannuation / NPS"},

    # --- Variable Pay ---
    "target_bonus": {"category": "variable", "unit": "currency",
                      "label": "Target Bonus / Performance Pay"},
    "variable_pay_frequency": {"category": "variable", "unit": "text",
                                "label": "Variable Pay Frequency"},
    "sales_commission": {"category": "variable", "unit": "currency",
                          "label": "Sales Commission / Incentives"},

    # --- One-Time Payments ---
    "joining_bonus": {"category": "one_time", "unit": "currency", "label": "Joining / Sign-on Bonus"},
    "joining_bonus_clawback_months": {"category": "one_time", "unit": "months",
                                       "label": "Joining Bonus Clawback Period"},
    "relocation_allowance": {"category": "one_time", "unit": "currency", "label": "Relocation Allowance"},
    "retention_bonus": {"category": "one_time", "unit": "currency", "label": "Retention Bonus"},
    "equity_type": {"category": "one_time", "unit": "text", "label": "Equity Type (ESOP/RSU/ESPP)"},
    "equity_grant_value": {"category": "one_time", "unit": "currency",
                            "label": "Total Equity Grant Value"},
    "equity_unit_count": {"category": "one_time", "unit": "count", "label": "Equity Unit Count"},
    "equity_vesting_schedule": {"category": "one_time", "unit": "text", "label": "Equity Vesting Schedule"},
    "equity_cliff_months": {"category": "one_time", "unit": "months", "label": "Equity Cliff Period"},

    # --- Deductions / benefit costs ---
    "health_insurance_premium": {"category": "deductions", "unit": "currency",
                                  "label": "Health Insurance Premium"},
    "food_meal_allowance": {"category": "deductions", "unit": "currency",
                             "label": "Food / Meal Allowance (Sodexo/Zeta)"},
    "internet_phone_reimbursement": {"category": "deductions", "unit": "currency",
                                      "label": "Internet / Phone Reimbursement"},
    "cab_transport_deduction": {"category": "deductions", "unit": "currency",
                                 "label": "Cab / Transport Deduction"},
}

# Fields summed to sanity-check against total_ctc in confidence.py's checksum pass.
CTC_COMPONENT_FIELDS: tuple[str, ...] = (
    "basic_pay", "hra", "special_allowance", "lta", "da",
    "employer_pf", "gratuity", "superannuation_nps",
    "target_bonus", "sales_commission",
)

# Purely informational metadata pulled from the letter — not compensation
# numbers, not subject to confidence scoring or the CTC checksum.
METADATA_FIELDS: tuple[str, ...] = ("company_name", "employee_name", "designation", "joining_date")

# ---------------------------------------------------------------------------
# Label aliases, including the acronyms/shortforms Indian offer letters
# commonly use. Matching is case-insensitive; ordered longest-first per field
# so "Employer PF" doesn't get shadowed by a bare "PF" alias, etc.
# ---------------------------------------------------------------------------

ALIASES: dict[str, list[str]] = {
    "total_ctc": ["total ctc", "ctc", "tctc", "cost to company", "total compensation",
                  "annual ctc"],
    "total_gross_pay": ["gross pay", "gross salary", "total gross", "gmp",
                         "guaranteed monthly pay"],
    "target_net_pay": ["net pay", "take-home", "take home", "in-hand", "in hand salary"],

    "basic_pay": ["basic pay", "basic salary", "basic"],
    "hra": ["hra", "house rent allowance"],
    "special_allowance": ["special allowance", "flexible allowance", "special pay",
                           "flexi pay", "spl. allowance"],
    "lta": ["lta", "leave travel allowance", "leave travel assistance"],
    "da": ["da", "dearness allowance"],

    "employer_pf": ["employer pf", "employer's pf", "employer contribution to pf",
                     "epf", "provident fund (employer)", "pf (employer)"],
    "gratuity": ["gratuity"],
    "superannuation_nps": ["superannuation", "nps", "national pension scheme",
                            "super annuation"],

    "target_bonus": ["target bonus", "performance bonus", "performance pay",
                      "variable component", "variable pay", "vp", "annual bonus"],
    "variable_pay_frequency": ["variable pay frequency", "bonus frequency",
                                "payout frequency"],
    # deliberately excludes bare "incentive"/"incentives" — too generic, collides
    # with equity/retention "incentive plan" language that isn't sales commission
    "sales_commission": ["sales commission", "sales incentive", "commission"],

    "joining_bonus": ["joining bonus", "sign-on bonus", "signing bonus", "sign on bonus"],
    "joining_bonus_clawback_months": ["clawback period", "clawback", "recovery period"],
    "relocation_allowance": ["relocation allowance", "relocation bonus", "relocation"],
    "retention_bonus": ["retention bonus", "retention pay"],
    "equity_type": ["esop", "rsu", "espp", "equity type", "stock options"],
    "equity_grant_value": ["equity grant value", "grant value", "total grant value",
                            "esop value", "rsu value"],
    "equity_unit_count": ["number of units", "unit count", "no. of options",
                           "no. of shares", "units granted"],
    "equity_vesting_schedule": ["vesting schedule", "vesting"],
    "equity_cliff_months": ["cliff period", "cliff"],

    "health_insurance_premium": ["health insurance", "medical insurance", "gmc",
                                  "group mediclaim", "insurance premium"],
    "food_meal_allowance": ["food allowance", "meal allowance", "sodexo", "zeta",
                             "meal card"],
    "internet_phone_reimbursement": ["internet reimbursement", "phone reimbursement",
                                      "mobile reimbursement", "internet & phone",
                                      "communication reimbursement"],
    "cab_transport_deduction": ["cab deduction", "transport deduction",
                                 "conveyance deduction", "cab charges"],
}
