"""Validation of agent-parsed structured fields, before anything hits the
calculation engine. A partial CTC breakup must never silently produce a
wrong number — it must be rejected with a structured error the parsing
agent can act on (e.g. to ask the user a clarifying question).
"""
from __future__ import annotations

from typing import Any

REQUIRED_CTC_FIELDS = ("basic", "hra")
NUMERIC_CTC_FIELDS = ("basic", "hra", "special_allowance", "bonus", "employer_pf",
                      "gratuity", "professional_tax", "rent_paid")


class ValidationResult:
    def __init__(self, valid: bool, missing_fields: list[str] | None = None,
                 malformed_fields: dict[str, str] | None = None):
        self.valid = valid
        self.missing_fields = missing_fields or []
        self.malformed_fields = malformed_fields or {}

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"valid": self.valid}
        if self.missing_fields:
            out["missing_fields"] = self.missing_fields
        if self.malformed_fields:
            out["malformed_fields"] = self.malformed_fields
        return out


def validate_ctc_breakup(data: dict[str, Any]) -> ValidationResult:
    missing = [f for f in REQUIRED_CTC_FIELDS if data.get(f) is None]

    malformed: dict[str, str] = {}
    for field in NUMERIC_CTC_FIELDS:
        value = data.get(field)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            malformed[field] = "expected a number"
        elif value < 0:
            malformed[field] = "must be non-negative"

    other_allowances = data.get("other_allowances")
    if other_allowances is not None:
        if not isinstance(other_allowances, dict):
            malformed["other_allowances"] = "expected an object of {name: amount}"
        else:
            for k, v in other_allowances.items():
                if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
                    malformed[f"other_allowances.{k}"] = "expected a non-negative number"

    deductions_claimed = data.get("deductions_claimed")
    if deductions_claimed is not None and not isinstance(deductions_claimed, dict):
        malformed["deductions_claimed"] = "expected an object, e.g. {\"80C\": 150000, \"80D\": 25000}"

    valid = not missing and not malformed
    return ValidationResult(valid, missing, malformed)
