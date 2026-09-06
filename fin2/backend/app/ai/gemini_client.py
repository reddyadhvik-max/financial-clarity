"""Thin, lazy wrapper around the Gemini client.

Lazy so importing app.ai.* doesn't require GEMINI_API_KEY to be set until the
AI layer is actually invoked (keeps the deterministic engine and its tests
fully independent of any LLM credentials).

Free tier only, by design (see app/ai/prompts.py and consistency.py for the
matching cost-discipline rules): gemini-2.5-flash's free tier caps at 20
requests/day, so this project is built to spend that budget carefully rather
than to assume it can pay its way out of the limit — no billing dependency
anywhere in this codebase.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
LITE_MODEL = os.environ.get("GEMINI_LITE_MODEL", "gemini-2.5-flash-lite")
REQUEST_TIMEOUT_MS = 30_000

# Caps the tool-calling agent's worst-case round trips per question — each
# round trip is a separate free-tier request, so an unbounded loop could
# burn the whole daily quota on one chat message.
MAX_AGENT_TOOL_ROUNDS = 5

_client: genai.Client | None = None


class MissingCredentialsError(RuntimeError):
    pass


class QuotaExhaustedError(RuntimeError):
    """Raised when Gemini's free-tier rate limit (429 RESOURCE_EXHAUSTED) is
    hit, so callers can show a clear "try again later" message instead of a
    raw Google error payload."""


def get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise MissingCredentialsError(
                "No Gemini credentials found. Set GEMINI_API_KEY (or GOOGLE_API_KEY)."
            )
        _client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS)
        )
    return _client


def translate_quota_errors(exc: Exception) -> Exception:
    """Turns Gemini's 429 RESOURCE_EXHAUSTED into a QuotaExhaustedError with a
    plain-language message; passes everything else through unchanged."""
    message = str(exc)
    if "RESOURCE_EXHAUSTED" in message or "429" in message:
        return QuotaExhaustedError(
            "Gemini's free-tier request limit has been reached for now. Please try again "
            "in a few minutes, or later today once the daily quota resets."
        )
    return exc
