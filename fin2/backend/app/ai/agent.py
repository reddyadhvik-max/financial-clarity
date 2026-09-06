"""The conversational agent: Gemini decides which engine analyses a question
needs, calls them as tools, and narrates the results. It never computes a
number itself — see app/ai/tools.py for the deterministic functions it can
call, and app/ai/prompts.py for the rule that binds it to their output.

Also hosts `narrate()`, used by endpoints that already know exactly which
engine calculation answers the question (explain / compare / negotiate) —
there Python computes first and Gemini only writes the summary, so no tool
loop is needed. That split is deliberate cost discipline on a free-tier
quota: one call per question, never a second LLM pass to "double-check" a
result the deterministic engine (or app/ai/consistency.py) already verifies.
"""
from __future__ import annotations

import json
from typing import Any

from google.genai import types

from app.ai.gemini_client import (
    DEFAULT_MODEL,
    MAX_AGENT_TOOL_ROUNDS,
    get_client,
    translate_quota_errors,
)
from app.ai.prompts import AGENT_SYSTEM_PROMPT, NARRATE_SYSTEM_PROMPT
from app.ai.schemas import AgentAnswer, ToolCallLog
from app.ai.tools import build_tools


def _summarize(result: Any, limit: int = 220) -> str:
    text = json.dumps(result, default=str)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def ask(
    ctc_breakup: dict[str, Any],
    question: str,
    fy: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> AgentAnswer:
    """Answer a free-form question about `ctc_breakup` using tool-calling.

    `history` is prior turns as [{"role": "user"|"assistant", "content": "..."}].
    """
    client = get_client()
    call_log: list[dict[str, Any]] = []
    tools = build_tools(ctc_breakup, fy, call_log)

    prior_turns: list[types.Content] = []
    for turn in history or []:
        role = "model" if turn["role"] in ("assistant", "model") else "user"
        prior_turns.append(types.Content(role=role, parts=[types.Part.from_text(text=turn["content"])]))

    system_instruction = AGENT_SYSTEM_PROMPT.format(
        offer_json=json.dumps(ctc_breakup, indent=2, default=str)
    )

    # Automatic function calling only reliably loops across multiple tool
    # calls via the Chat interface — the SDK itself warns that driving AFC
    # straight off models.generate_content can silently stop after one call.
    chat = client.chats.create(
        model=DEFAULT_MODEL,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                maximum_remote_calls=MAX_AGENT_TOOL_ROUNDS
            ),
        ),
        history=prior_turns,
    )
    try:
        response = chat.send_message(question)
    except Exception as e:
        raise translate_quota_errors(e) from e

    tool_calls = [
        ToolCallLog(tool=c["tool"], args=c["args"], result_summary=_summarize(c["result"]))
        for c in call_log
    ]
    return AgentAnswer(answer=response.text or "", tool_calls=tool_calls)


def narrate(instruction: str, computed: dict[str, Any]) -> str:
    """Ask Gemini to explain an already-computed engine result. `computed` is
    trusted, final JSON — Gemini is only allowed to describe it, per
    NARRATE_SYSTEM_PROMPT."""
    client = get_client()
    prompt = (
        f"{instruction}\n\n"
        "Verified calculation results (JSON, already computed — cite these numbers "
        "exactly, do not recompute or alter them):\n"
        f"{json.dumps(computed, indent=2, default=str)}"
    )
    try:
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=NARRATE_SYSTEM_PROMPT),
        )
    except Exception as e:
        raise translate_quota_errors(e) from e
    return response.text or ""
