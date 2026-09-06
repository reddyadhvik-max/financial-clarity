"""Provider-agnostic LLM client.

The rest of the AI layer (parsing.py, explanation.py) only ever calls
`.generate(system, prompt)` on whatever `get_llm_client()` returns — swapping
providers never touches calling code.

Provider is selected via the LLM_PROVIDER env var (default "mock"). Mock mode
needs no API key and is the default specifically so this whole layer is
buildable, runnable, and testable today, before a real key exists. When a
free-tier key is available, set LLM_PROVIDER=gemini and GEMINI_API_KEY.
"""
from __future__ import annotations

import os
from typing import Protocol


class LLMClient(Protocol):
    def generate(self, system: str, prompt: str) -> str: ...


class MockLLMClient:
    """Keyless stand-in. Returns the prompt unchanged.

    explanation.py always builds a complete, correct, template-based string
    itself before handing it to the LLM client — the client's only job is to
    optionally *rephrase* that string in a warmer tone. A mock that can't
    rephrase anything still returns a fully correct explanation; a real
    provider only ever improves phrasing, never the numbers or facts, since
    those are fixed by the template before this call happens.
    """

    def generate(self, system: str, prompt: str) -> str:
        return prompt


class GeminiClient:
    """Google Gemini — has a free API tier as of writing. Only imported when
    LLM_PROVIDER=gemini, so `google-generativeai` is an optional dependency
    for anyone running in mock mode (which is everyone until a key exists).
    """

    def __init__(self, model: str = "gemini-1.5-flash"):
        import google.generativeai as genai  # optional dependency, see docstring

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model)

    def generate(self, system: str, prompt: str) -> str:
        response = self._model.generate_content(f"{system}\n\n{prompt}")
        return response.text


def get_llm_client() -> LLMClient:
    provider = os.environ.get("LLM_PROVIDER", "mock").lower()
    if provider == "mock":
        return MockLLMClient()
    if provider == "gemini":
        return GeminiClient()
    raise ValueError(f"Unknown LLM_PROVIDER '{provider}' (expected 'mock' or 'gemini')")
