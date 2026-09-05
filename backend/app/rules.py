"""Versioned rule data access.

Rule data lives in data/rules.json, never inline in code, so every number
the calculation engine produces can be traced back to a rule_id + FY that
the frontend/audit-trail can look up via GET /rule/:rule_id.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "rules.json"


class RuleNotFoundError(KeyError):
    def __init__(self, rule_id: str, fy: str):
        self.rule_id = rule_id
        self.fy = fy
        super().__init__(f"No rule '{rule_id}' found for FY {fy}")


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _index() -> dict[tuple[str, str], dict[str, Any]]:
    raw = _load_raw()
    return {(r["rule_id"], r["fy"]): r for r in raw["rules"]}


def current_fy() -> str:
    return _load_raw()["current_fy"]


def get_rule(rule_id: str, fy: str | None = None) -> dict[str, Any]:
    """Return the full rule record for rule_id at the given FY (default: current FY)."""
    fy = fy or current_fy()
    rule = _index().get((rule_id, fy))
    if rule is None:
        raise RuleNotFoundError(rule_id, fy)
    return rule


def get_value(rule_id: str, fy: str | None = None) -> Any:
    """Convenience accessor for just the rule's `value`."""
    return get_rule(rule_id, fy)["value"]


def get_rules_by_category(category: str, fy: str | None = None) -> list[dict[str, Any]]:
    fy = fy or current_fy()
    return [r for r in _load_raw()["rules"] if r["category"] == category and r["fy"] == fy]


def list_rule_ids(fy: str | None = None) -> list[str]:
    fy = fy or current_fy()
    return sorted({r["rule_id"] for r in _load_raw()["rules"] if r["fy"] == fy})
