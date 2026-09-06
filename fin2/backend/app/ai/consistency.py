"""Deterministic, Python-only consistency checks on a parsed offer — the
"AI self-validation" pass, implemented as plain arithmetic rather than a
second LLM call, so it can never itself hallucinate a contradiction. Gemini
extracts; this module only checks whether the extracted numbers add up.
"""
from __future__ import annotations

from app.ai.schemas import Contradiction, ParsedOfferAI

CTC_MISMATCH_RELATIVE_TOLERANCE = 0.12


def _num(field) -> float:
    if field is None or field.value is None or not isinstance(field.value, (int, float)):
        return 0.0
    return float(field.value)


def detect_contradictions(parsed: ParsedOfferAI) -> list[Contradiction]:
    """Cross-checks the fields Gemini extracted against each other. Runs
    after parsing, never during it — this is arithmetic, not judgement."""
    findings: list[Contradiction] = []

    ctc_total = parsed.ctc_total
    if ctc_total is not None and isinstance(ctc_total.value, (int, float)) and ctc_total.value > 0:
        recurring_components = (
            _num(parsed.basic) + _num(parsed.hra) + _num(parsed.special_allowance)
            + _num(parsed.dearness_allowance) + _num(parsed.bonus) + _num(parsed.retention_bonus)
            + _num(parsed.sales_commission) + _num(parsed.employer_pf) + _num(parsed.employer_nps)
            + _num(parsed.gratuity) + _num(parsed.health_insurance_premium)
        )
        if recurring_components > 0:
            stated = float(ctc_total.value)
            diff_ratio = abs(recurring_components - stated) / stated
            if diff_ratio > CTC_MISMATCH_RELATIVE_TOLERANCE:
                findings.append(Contradiction(
                    description=(
                        f"The extracted components sum to approximately ₹{recurring_components:,.0f}, "
                        f"but the offer states a total CTC of ₹{stated:,.0f} — a "
                        f"{diff_ratio * 100:.0f}% difference. Either a component was missed, or the "
                        "letter's stated CTC includes items not itemized here (e.g. one-time bonuses)."
                    ),
                    fields_involved=["ctc_total", "basic", "hra", "special_allowance", "bonus", "employer_pf"],
                ))

    notice = parsed.notice_period_days
    if notice is not None and isinstance(notice.value, (int, float)):
        if notice.value < 0 or notice.value > 365:
            findings.append(Contradiction(
                description=f"Notice period was read as {notice.value:g} days, which is outside a plausible "
                            "range (0-365) — likely a misread (e.g. months mistaken for days).",
                fields_involved=["notice_period_days"],
            ))

    clawback_period = parsed.joining_bonus_clawback_period_months
    has_clawback = parsed.joining_bonus_has_clawback
    if (has_clawback is not None and has_clawback.value is True
            and (clawback_period is None or clawback_period.value is None)):
        findings.append(Contradiction(
            description="A joining-bonus clawback clause was detected, but no repayment period was found — "
                        "the letter may state it in a way the parser couldn't isolate.",
            fields_involved=["joining_bonus_has_clawback", "joining_bonus_clawback_period_months"],
        ))

    return findings
