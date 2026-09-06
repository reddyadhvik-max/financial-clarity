"""Tests for the deterministic (non-LLM) consistency checks in
app/ai/consistency.py — these never touch Gemini."""
from __future__ import annotations

from app.ai.consistency import detect_contradictions
from app.ai.schemas import ExtractedField, ParsedOfferAI


def _field(value):
    return ExtractedField(value=value, confidence=0.9, source_text="x")


def test_no_contradiction_when_components_sum_to_ctc():
    parsed = ParsedOfferAI(
        ctc_total=_field(1_000_000),
        basic=_field(600_000),
        hra=_field(240_000),
        special_allowance=_field(160_000),
        needs_user_input=False,
    )
    assert detect_contradictions(parsed) == []


def test_flags_ctc_mismatch_beyond_tolerance():
    parsed = ParsedOfferAI(
        ctc_total=_field(1_500_000),
        basic=_field(600_000),
        hra=_field(240_000),
        needs_user_input=False,
    )
    findings = detect_contradictions(parsed)
    assert len(findings) == 1
    assert "ctc_total" in findings[0].fields_involved
    assert "1,500,000" in findings[0].description or "1500000" in findings[0].description.replace(",", "")


def test_flags_implausible_notice_period():
    parsed = ParsedOfferAI(notice_period_days=_field(9000), needs_user_input=False)
    findings = detect_contradictions(parsed)
    assert any("notice_period_days" in f.fields_involved for f in findings)


def test_flags_clawback_without_period():
    parsed = ParsedOfferAI(
        joining_bonus_has_clawback=_field(True),
        joining_bonus_clawback_period_months=None,
        needs_user_input=False,
    )
    findings = detect_contradictions(parsed)
    assert any("joining_bonus_clawback_period_months" in f.fields_involved for f in findings)


def test_no_findings_on_empty_offer():
    parsed = ParsedOfferAI(needs_user_input=False)
    assert detect_contradictions(parsed) == []
