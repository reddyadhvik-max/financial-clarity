"""Confidence tagging, payroll-rule estimation, and checksum validation.

Every field in the final output is tagged exactly one of:
  "found"     — an exact label/table match.
  "estimated" — not found directly, but derived via a stated, auditable
                payroll rule or an arithmetic remainder (never a guess).
  "missing"   — genuinely absent. Always output as `null`, never coerced to
                0 — a missing employer PF is not the same fact as a stated
                zero employer PF, and treating them the same would hide a
                real red flag (see redflags.py).
"""
from __future__ import annotations

from typing import Any

from . import schema
from . import tabular as tabular_module
from .patterns import extract_field_regex

CHECKSUM_TOLERANCE_PCT = 0.05  # 5% slack for rounding / unlisted minor components
STATUTORY_PF_RATE = 0.12  # matches backend/data/rules.json's PF_EMPLOYEE_RATE convention


def extract_all_fields(text: str, tables: list[list[list[str | None]]]) -> dict[str, dict[str, Any]]:
    """Runs Layer 1 (tabular) then Layer 2/3 (regex, patterns.py) for every
    schema field, tabular taking priority, then applies Layer-4 estimation
    rules for a handful of fields with a well-defined payroll relationship.
    Returns {field_key: {"value", "confidence_tier", "evidence"}}.
    """
    table_hits = tabular_module.extract_from_tables(tables)

    fields: dict[str, dict[str, Any]] = {}
    for field_key in schema.FIELDS:
        if field_key in table_hits:
            fields[field_key] = table_hits[field_key]
        else:
            fields[field_key] = extract_field_regex(text, field_key)

    _apply_estimation_rules(fields)
    return fields


def _apply_estimation_rules(fields: dict[str, dict[str, Any]]) -> None:
    """Fills in a small set of fields via explicit, auditable formulas when
    they weren't found directly — never a blind guess, and never invented
    when the inputs it depends on are themselves missing.
    """
    # basic_pay from a stated employer PF (statutory 12% of basic, standard
    # case — doesn't apply if the letter caps PF at the wage ceiling, but
    # that's a rarer case a human reviewer should catch via the "estimated"
    # tag rather than this rule silently getting it wrong).
    if fields["basic_pay"]["value"] is None and fields["employer_pf"]["value"] is not None:
        estimated_basic = fields["employer_pf"]["value"] / STATUTORY_PF_RATE
        fields["basic_pay"] = {
            "value": round(estimated_basic, 2),
            "confidence_tier": "estimated",
            "evidence": "derived: employer_pf / 12% statutory PF rate",
        }

    # total_gross_pay as CTC minus retiral components, when both are known
    # and gross wasn't stated directly.
    if fields["total_gross_pay"]["value"] is None and fields["total_ctc"]["value"] is not None:
        retiral_fields = ("employer_pf", "gratuity", "superannuation_nps")
        retiral_values = [fields[f]["value"] for f in retiral_fields if fields[f]["value"] is not None]
        if retiral_values:
            estimated_gross = fields["total_ctc"]["value"] - sum(retiral_values)
            fields["total_gross_pay"] = {
                "value": round(estimated_gross, 2),
                "confidence_tier": "estimated",
                "evidence": f"derived: total_ctc - ({' + '.join(retiral_fields)})",
            }


def compute_derived_totals(fields: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Category subtotals. Tagged 'estimated' (they're computed, not
    extracted) whenever at least one contributing field was found/estimated;
    'missing' only if every contributing field is missing.
    """
    category_fields: dict[str, list[str]] = {}
    for key, meta in schema.FIELDS.items():
        if meta["unit"] != "currency":
            continue
        category_fields.setdefault(meta["category"], []).append(key)

    derived: dict[str, dict[str, Any]] = {}
    for category, field_keys in category_fields.items():
        values = [fields[k]["value"] for k in field_keys if fields[k]["value"] is not None]
        total_key = f"{category}_total"
        if values:
            derived[total_key] = {"value": round(sum(values), 2), "confidence_tier": "estimated",
                                   "evidence": f"sum of {category} category fields"}
        else:
            derived[total_key] = {"value": None, "confidence_tier": "missing", "evidence": None}

    return derived


def run_checksum_validation(fields: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Sanity-check: sum of the fixed + retiral + variable components should
    equal the stated Total CTC, within a small tolerance. A mismatch doesn't
    invalidate the parse — real letters often bundle a component this
    schema doesn't itemize — but it's a signal worth surfacing to a human
    reviewer rather than silently trusting either number.
    """
    total_ctc = fields["total_ctc"]["value"]
    component_values = [fields[f]["value"] for f in schema.CTC_COMPONENT_FIELDS
                         if fields[f]["value"] is not None]

    if total_ctc is None or not component_values:
        return {"checked": False, "reason": "insufficient data (missing total_ctc or all components)"}

    component_sum = round(sum(component_values), 2)
    diff = round(component_sum - total_ctc, 2)
    diff_pct = abs(diff) / total_ctc if total_ctc else 0.0

    return {
        "checked": True,
        "total_ctc": total_ctc,
        "component_sum": component_sum,
        "difference": diff,
        "difference_pct": round(diff_pct * 100, 2),
        "within_tolerance": diff_pct <= CHECKSUM_TOLERANCE_PCT,
    }
