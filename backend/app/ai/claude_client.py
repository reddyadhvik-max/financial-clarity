"""Thin, lazy wrapper around the Anthropic client.

Lazy so importing app.ai.* doesn't require ANTHROPIC_API_KEY to be set until
the AI layer is actually invoked (keeps the deterministic engine and its
tests fully independent of any LLM credentials).
"""
from __future__ import annotations

import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")

_client: anthropic.Anthropic | None = None


class MissingCredentialsError(RuntimeError):
    pass


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise MissingCredentialsError(
                "No Anthropic credentials found. Set ANTHROPIC_API_KEY."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client
