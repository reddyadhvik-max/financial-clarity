"""Tests for the app/ai/* layer. Never calls the real Gemini API — the
`google.genai` client is monkeypatched everywhere, so these run offline and
without GEMINI_API_KEY, exactly like the deterministic-engine tests.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import engine
from app.ai import agent as ai_agent
from app.ai.gemini_client import MissingCredentialsError
from app.ai.schemas import ParsedOfferAI
from app.ai.tools import build_tools
from app.main import app

client = TestClient(app)

SAMPLE_CTC = {"basic": 600_000, "hra": 300_000, "special_allowance": 200_000, "bonus": 100_000}


# --- tools.py: pure wiring around engine.py, no Gemini involved ---

def test_build_tools_logs_calls_and_matches_engine():
    call_log: list[dict] = []
    tools = build_tools(SAMPLE_CTC, fy=None, call_log=call_log)
    by_name = {t.__name__: t for t in tools}

    result = by_name["get_in_hand_breakdown"](regime="new")
    assert result == engine.compute_in_hand(SAMPLE_CTC, regime="new", fy=None)
    assert call_log[-1]["tool"] == "compute_in_hand"
    assert call_log[-1]["args"] == {"regime": "new"}

    by_name["get_red_flags"]()
    assert call_log[-1]["tool"] == "detect_red_flags"


# --- /ai/parse-offer ---

def test_ai_parse_offer_missing_credentials_returns_503(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr("app.ai.gemini_client._client", None)
    resp = client.post("/ai/parse-offer", json={"offer_text": "Basic: 6,00,000"})
    assert resp.status_code == 503


def test_ai_parse_offer_happy_path(monkeypatch):
    parsed = ParsedOfferAI(
        basic={"value": 600_000, "confidence": 0.97, "source_text": "Basic: Rs. 6,00,000 p.a."},
        needs_user_input=False,
    )
    monkeypatch.setattr("app.ai.parser.parse_offer_letter", lambda text: parsed)
    resp = client.post("/ai/parse-offer", json={"offer_text": "Basic: Rs. 6,00,000 p.a."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["basic"]["value"] == 600_000
    assert body["needs_user_input"] is False


# --- /ai/ask, /ai/explain, /ai/negotiate, /ai/compare-offers: mock the agent layer ---

def test_ai_ask_validates_ctc_before_calling_agent(monkeypatch):
    called = False

    def fake_ask(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("should not be reached — validation must fail first")

    monkeypatch.setattr(ai_agent, "ask", fake_ask)
    resp = client.post("/ai/ask", json={"ctc_breakup": {"basic": 600_000}, "question": "hi"})
    assert resp.status_code == 422
    assert not called


def test_ai_ask_happy_path(monkeypatch):
    from app.ai.schemas import AgentAnswer, ToolCallLog

    def fake_ask(ctc_breakup, question, fy=None, history=None):
        assert ctc_breakup["basic"] == 600_000
        assert question == "How much do I actually take home?"
        return AgentAnswer(
            answer="You take home about ₹94k/month.",
            tool_calls=[ToolCallLog(tool="compute_in_hand", args={"regime": "new"},
                                     result_summary="in_hand_monthly=94000")],
        )

    monkeypatch.setattr(ai_agent, "ask", fake_ask)
    resp = client.post("/ai/ask", json={
        "ctc_breakup": SAMPLE_CTC, "question": "How much do I actually take home?",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "94k" in body["answer"]
    assert body["tool_calls"][0]["tool"] == "compute_in_hand"


def test_ai_explain_computes_before_narrating(monkeypatch):
    captured = {}

    def fake_narrate(instruction, computed):
        captured["computed"] = computed
        return "In plain terms, your offer is solid."

    monkeypatch.setattr(ai_agent, "narrate", fake_narrate)
    resp = client.post("/ai/explain", json={"ctc_breakup": SAMPLE_CTC})
    assert resp.status_code == 200
    body = resp.json()
    assert body["explanation"] == "In plain terms, your offer is solid."
    # The numbers Gemini narrated are the real engine output, not invented.
    assert body["computed"]["in_hand"] == engine.compute_in_hand(SAMPLE_CTC, regime="new", fy=None)
    assert "red_flags" in captured["computed"]
    assert "quality_score" in captured["computed"]


def test_ai_negotiate_grounds_in_engine_output(monkeypatch):
    monkeypatch.setattr(ai_agent, "narrate", lambda instruction, computed: "Ask for more fixed pay.")
    resp = client.post("/ai/negotiate", json={"ctc_breakup": SAMPLE_CTC})
    assert resp.status_code == 200
    body = resp.json()
    assert body["negotiation_points"] == "Ask for more fixed pay."
    assert body["computed"]["classification"] == engine.classify_compensation_components(
        SAMPLE_CTC, regime="new", fy=None
    )


def test_ai_compare_offers_uses_engine_compare(monkeypatch):
    monkeypatch.setattr(ai_agent, "narrate", lambda instruction, computed: "Offer A is safer.")
    payload = {
        "offer_a": {"label": "Offer A", "ctc_breakup": SAMPLE_CTC},
        "offer_b": {"label": "Offer B", "ctc_breakup": {**SAMPLE_CTC, "bonus": 400_000}},
    }
    resp = client.post("/ai/compare-offers", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "Offer A is safer."
    assert "computed" in body


def test_ai_gemini_failure_returns_502(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("Gemini timed out")

    monkeypatch.setattr(ai_agent, "narrate", boom)
    resp = client.post("/ai/explain", json={"ctc_breakup": SAMPLE_CTC})
    assert resp.status_code == 502


def test_ai_quota_exhausted_returns_429(monkeypatch):
    from app.ai.gemini_client import QuotaExhaustedError

    def boom(*args, **kwargs):
        raise QuotaExhaustedError("Gemini's free-tier request limit has been reached for now.")

    monkeypatch.setattr(ai_agent, "narrate", boom)
    resp = client.post("/ai/explain", json={"ctc_breakup": SAMPLE_CTC})
    assert resp.status_code == 429


# --- /ai/negotiation-message ---

def test_ai_negotiation_message_recruiter_email(monkeypatch):
    monkeypatch.setattr(ai_agent, "narrate", lambda instruction, computed: "Dear recruiter, ...")
    resp = client.post("/ai/negotiation-message", json={
        "ctc_breakup": SAMPLE_CTC, "audience": "recruiter_email",
    })
    assert resp.status_code == 200
    assert resp.json()["message"] == "Dear recruiter, ..."


def test_ai_negotiation_message_hr_talking_points(monkeypatch):
    captured = {}

    def fake_narrate(instruction, computed):
        captured["instruction"] = instruction
        return "- Point one\n- Point two"

    monkeypatch.setattr(ai_agent, "narrate", fake_narrate)
    resp = client.post("/ai/negotiation-message", json={
        "ctc_breakup": SAMPLE_CTC, "audience": "hr_call_talking_points",
    })
    assert resp.status_code == 200
    assert "talking points" in captured["instruction"]


# --- /ai/parse-offer-document ---

def test_ai_parse_offer_document_rejects_oversized_file(monkeypatch):
    from app.ai import parser as ai_parser

    monkeypatch.setattr(ai_parser, "MAX_DOCUMENT_BYTES", 10)  # tiny, to trigger easily
    resp = client.post(
        "/ai/parse-offer-document",
        files={"file": ("offer.pdf", b"x" * 100, "application/pdf")},
    )
    assert resp.status_code == 413


def test_ai_parse_offer_document_rejects_unsupported_type():
    resp = client.post(
        "/ai/parse-offer-document",
        files={"file": ("offer.exe", b"not a real document", "application/x-msdownload")},
    )
    assert resp.status_code == 415


def test_ai_parse_offer_document_happy_path(monkeypatch):
    from app.ai import parser as ai_parser

    parsed = ParsedOfferAI(
        basic={"value": 700_000, "confidence": 0.9, "source_text": "Basic: 7,00,000", "page": 1},
        needs_user_input=False,
    )
    monkeypatch.setattr(ai_parser, "parse_offer_document", lambda data, mime_type: parsed)
    resp = client.post(
        "/ai/parse-offer-document",
        files={"file": ("offer.pdf", b"%PDF-1.4 fake pdf bytes", "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["basic"]["value"] == 700_000
    assert body["basic"]["page"] == 1


def test_ai_parse_offer_document_missing_credentials_returns_503(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr("app.ai.gemini_client._client", None)
    resp = client.post(
        "/ai/parse-offer-document",
        files={"file": ("offer.pdf", b"%PDF-1.4 fake pdf bytes", "application/pdf")},
    )
    assert resp.status_code == 503


# --- Free-tier quota handling (never crash the app on 429) ---

def test_translate_quota_errors_recognizes_resource_exhausted():
    from app.ai.gemini_client import QuotaExhaustedError, translate_quota_errors

    original = RuntimeError("429 RESOURCE_EXHAUSTED. Quota exceeded for metric: ...")
    translated = translate_quota_errors(original)
    assert isinstance(translated, QuotaExhaustedError)


def test_translate_quota_errors_passes_through_other_errors():
    from app.ai.gemini_client import translate_quota_errors

    original = ValueError("some unrelated failure")
    assert translate_quota_errors(original) is original


def test_ai_parse_offer_quota_exhausted_returns_429(monkeypatch):
    from app.ai import parser as ai_parser
    from app.ai.gemini_client import QuotaExhaustedError

    def boom(text):
        raise QuotaExhaustedError("Gemini's free-tier request limit has been reached for now.")

    monkeypatch.setattr(ai_parser, "parse_offer_letter", boom)
    resp = client.post("/ai/parse-offer", json={"offer_text": "Basic: 6,00,000"})
    assert resp.status_code == 429
