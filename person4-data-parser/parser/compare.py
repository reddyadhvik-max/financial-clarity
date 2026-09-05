"""Multi-offer comparison.

Compares two already-parsed offers (as returned by OfferLetterParser / read
back from storage.py) field by field. Per the product requirement: if one
offer letter states a field the other lacks, the missing side is rendered as
the literal string "NA" — not null, not 0 — since this comparison view is
UI-facing, not an internal confidence-scoring pass (that distinction is
still preserved in each offer's own `fields[...]["confidence_tier"]`, which
this module passes through rather than discarding).
"""
from __future__ import annotations

from typing import Any

from . import schema

NA = "NA"


def _flat_fields(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    flat: dict[str, dict[str, Any]] = {}
    for category_fields in result.get("fields", {}).values():
        flat.update(category_fields)
    return flat


def compare_offers(result_a: dict[str, Any], result_b: dict[str, Any],
                    label_a: str = "Offer A", label_b: str = "Offer B") -> dict[str, Any]:
    fields_a = _flat_fields(result_a)
    fields_b = _flat_fields(result_b)

    rows: list[dict[str, Any]] = []
    for field_key, meta in schema.FIELDS.items():
        entry_a = fields_a.get(field_key, {"value": None, "confidence_tier": "missing"})
        entry_b = fields_b.get(field_key, {"value": None, "confidence_tier": "missing"})

        value_a = entry_a["value"] if entry_a["value"] is not None else NA
        value_b = entry_b["value"] if entry_b["value"] is not None else NA

        row: dict[str, Any] = {
            "field": field_key,
            "label": meta["label"],
            "category": meta["category"],
            "unit": meta["unit"],
            label_a: value_a,
            label_b: value_b,
            f"{label_a}_confidence": entry_a["confidence_tier"],
            f"{label_b}_confidence": entry_b["confidence_tier"],
        }

        if meta["unit"] == "currency" and value_a != NA and value_b != NA:
            row["difference"] = round(value_a - value_b, 2)
            row["higher_offer"] = label_a if value_a > value_b else (
                label_b if value_b > value_a else None)
        else:
            row["difference"] = None
            row["higher_offer"] = None

        rows.append(row)

    return {
        "offers_compared": [label_a, label_b],
        "rows": rows,
        "summary": _summarize(rows, label_a, label_b),
    }


def _summarize(rows: list[dict[str, Any]], label_a: str, label_b: str) -> dict[str, Any]:
    wins_a = sum(1 for r in rows if r["higher_offer"] == label_a)
    wins_b = sum(1 for r in rows if r["higher_offer"] == label_b)
    only_in_a = [r["field"] for r in rows if r[label_a] != NA and r[label_b] == NA]
    only_in_b = [r["field"] for r in rows if r[label_b] != NA and r[label_a] == NA]

    top_line_ctc_row = next((r for r in rows if r["field"] == "total_ctc"), None)

    return {
        "fields_higher_in": {label_a: wins_a, label_b: wins_b},
        "fields_only_disclosed_by": {label_a: only_in_a, label_b: only_in_b},
        "total_ctc_difference": top_line_ctc_row["difference"] if top_line_ctc_row else None,
        "total_ctc_higher_offer": top_line_ctc_row["higher_offer"] if top_line_ctc_row else None,
    }
