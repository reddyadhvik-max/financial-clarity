"""Anomaly / red-flag detection over a fully parsed offer.

Runs after extraction + confidence scoring + checksum validation, over the
final field dict — never over raw text. Every flag names the exact field(s)
and threshold it tripped, so a human reviewer (or the frontend) doesn't have
to reverse-engineer why something was flagged.
"""
from __future__ import annotations

from typing import Any

VARIABLE_PAY_PCT_THRESHOLD = 0.20
ONE_TIME_CLIFF_PCT_THRESHOLD = 0.15
HIGH_VALUE_CTC_THRESHOLD = 1_000_000  # INR 10 LPA — above this, missing gratuity is notable


def _value(fields: dict[str, dict[str, Any]], key: str) -> float | None:
    entry = fields.get(key)
    return entry["value"] if entry else None


def run_red_flag_checks(fields: dict[str, dict[str, Any]], derived: dict[str, dict[str, Any]],
                         checksum: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []

    total_ctc = _value(fields, "total_ctc")
    variable_total = _value(derived, "variable_total")
    one_time_total = _value(derived, "one_time_total")
    gratuity = _value(fields, "gratuity")
    employer_pf = _value(fields, "employer_pf")
    basic_pay = _value(fields, "basic_pay")

    if total_ctc:
        if variable_total is not None:
            variable_pct = variable_total / total_ctc
            if variable_pct > VARIABLE_PAY_PCT_THRESHOLD:
                flags.append({
                    "flag_id": "HIGH_VARIABLE_PAY",
                    "severity": "warning",
                    "field": "variable_total",
                    "message": (f"Variable pay is {variable_pct:.0%} of CTC, above the "
                                f"{VARIABLE_PAY_PCT_THRESHOLD:.0%} threshold — a significant share of "
                                "this offer is not guaranteed."),
                })

        if one_time_total is not None:
            one_time_pct = one_time_total / total_ctc
            if one_time_pct > ONE_TIME_CLIFF_PCT_THRESHOLD:
                flags.append({
                    "flag_id": "ONE_TIME_PAYMENT_CLIFF",
                    "severity": "warning",
                    "field": "one_time_total",
                    "message": (f"One-time payments (joining/retention bonus, relocation, equity) make up "
                                f"{one_time_pct:.0%} of CTC, above the {ONE_TIME_CLIFF_PCT_THRESHOLD:.0%} "
                                "threshold — expect a significant drop in year-two total compensation "
                                "once these don't repeat."),
                })

        if total_ctc > HIGH_VALUE_CTC_THRESHOLD and not gratuity:
            flags.append({
                "flag_id": "MISSING_GRATUITY_HIGH_VALUE",
                "severity": "critical",
                "field": "gratuity",
                "message": (f"No gratuity found on an offer above ₹{HIGH_VALUE_CTC_THRESHOLD:,.0f} CTC. "
                            "Gratuity is a statutory benefit after 5 years of service regardless of "
                            "whether the letter itemizes it — confirm this wasn't omitted."),
            })

    if basic_pay and not employer_pf:
        flags.append({
            "flag_id": "MISSING_EMPLOYER_PF",
            "severity": "critical",
            "field": "employer_pf",
            "message": "Basic pay is stated but no employer PF contribution was found. EPF is mandatory "
                       "for eligible employees under the EPF & MP Act.",
        })

    if checksum.get("checked") and not checksum.get("within_tolerance"):
        flags.append({
            "flag_id": "CTC_CHECKSUM_MISMATCH",
            "severity": "info",
            "field": "total_ctc",
            "message": (f"Extracted components sum to ₹{checksum['component_sum']:,.0f}, "
                        f"{checksum['difference_pct']}% off the stated Total CTC of "
                        f"₹{checksum['total_ctc']:,.0f} — the letter may bundle a component this parser "
                        "doesn't itemize, or a field may have been mis-extracted. Worth a manual check."),
        })

    return flags
