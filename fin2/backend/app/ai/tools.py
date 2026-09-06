"""Function-calling tools for the conversational agent (app/ai/agent.py).

Every tool is a thin, closure-bound wrapper around one app/engine.py function —
Gemini decides *which* analysis a question needs, but the arithmetic always
runs in the deterministic engine. Tools take no compensation data as
arguments (the offer is fixed for the conversation); the only exposed
parameter is a regime override, so Gemini's automatic function calling only
ever has to invent a tax-regime string, never reconstruct financial figures.

Each call appends a plain-dict record to `call_log`, which the caller passed
in — this is how app/ai/agent.py gets a provenance trail (which engine
function backed each number in the final answer) without having to parse the
Gemini SDK's internal automatic-function-calling history.

Deliberately NOT using `from __future__ import annotations` here: Gemini's
automatic function calling does `isinstance(value, param.annotation)` on each
tool's real parameter type objects. PEP 563 postponed evaluation turns those
annotations into strings (e.g. `"str"` instead of `str`), which makes that
isinstance() check throw — every tool call would silently fail via Gemini's
broad except-and-stringify and the model would report a fake "technical
issue" instead of the real answer. (Found and fixed the hard way once
already — see the git history / session notes if this regresses.)
"""
from typing import Any, Callable

from app import engine


def build_tools(
    ctc_breakup: dict[str, Any], fy: str | None, call_log: list[dict[str, Any]]
) -> list[Callable[..., dict]]:
    def _log(tool: str, args: dict, result: Any) -> None:
        call_log.append({"tool": tool, "args": args, "result": result})

    def get_in_hand_breakdown(regime: str = "new") -> dict:
        """Compute the full in-hand pay breakdown for this offer under one tax regime:
        gross salary, employee PF/ESI deductions, gratuity provisioning, income tax, and
        annual/monthly take-home pay. Call this once per regime to compare old vs new.

        Args:
          regime: Tax regime to compute under — "old" or "new".
        """
        result = engine.compute_in_hand(ctc_breakup, regime=regime, fy=fy)
        _log("compute_in_hand", {"regime": regime}, result)
        return result

    def get_red_flags() -> dict:
        """Run the rule-based red-flag scan on this offer: variable-pay concentration,
        low basic salary, missing PF, missing gratuity clause, long notice period,
        service bonds, and joining-bonus clawback clauses. Regime-independent."""
        result = {"red_flags": engine.detect_red_flags(ctc_breakup, fy=fy)}
        _log("detect_red_flags", {}, result)
        return result

    def get_compensation_classification(regime: str = "new") -> dict:
        """Classify every compensation component of this offer as fixed/guaranteed vs.
        variable/at-risk, and total each bucket. Use this to answer questions like "how
        much of my CTC is actually guaranteed?".

        Args:
          regime: Tax regime — "old" or "new".
        """
        result = engine.classify_compensation_components(ctc_breakup, regime=regime, fy=fy)
        _log("classify_compensation_components", {"regime": regime}, result)
        return result

    def get_ctc_waterfall(regime: str = "new") -> dict:
        """Compute the step-by-step CTC-to-in-hand waterfall (each deduction/tax step
        and how much it removes from the headline CTC).

        Args:
          regime: Tax regime — "old" or "new".
        """
        result = engine.compute_ctc_waterfall(ctc_breakup, regime=regime, fy=fy)
        _log("compute_ctc_waterfall", {"regime": regime}, result)
        return result

    def get_offer_quality_score(regime: str = "new") -> dict:
        """Compute the overall offer-quality score (0-100) with its sub-component
        weights, based on fixed-pay ratio, red flags, and benefit completeness.

        Args:
          regime: Tax regime — "old" or "new".
        """
        result = engine.compute_offer_quality_score(ctc_breakup, regime=regime, fy=fy)
        _log("compute_offer_quality_score", {"regime": regime}, result)
        return result

    return [
        get_in_hand_breakdown,
        get_red_flags,
        get_compensation_classification,
        get_ctc_waterfall,
        get_offer_quality_score,
    ]
