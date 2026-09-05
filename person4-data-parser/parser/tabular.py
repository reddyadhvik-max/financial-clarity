"""Layer 1: spatial/tabular extraction.

Many real offer letters put the actual compensation breakdown in an
"Annexure" table with columns like Component | Monthly | Annual, rather than
in prose. pdfplumber's `extract_tables()` (already run in extractors.py and
attached to `ExtractionResult.tables`) gives us that table as a grid of cell
strings — this module turns it into canonical field values.

A table hit is the strongest possible signal (a labeled cell in a labeled
column), so callers should treat it as "found" and let it take priority over
a regex match on the same field found elsewhere in the document body.
"""
from __future__ import annotations

from typing import Any

from .normalize import parse_money, resolve_alias

ANNUAL_HEADERS = ("annual", "yearly", "per annum", "p.a.")
MONTHLY_HEADERS = ("monthly", "per month", "p.m.")


def _find_column_index(header_row: list[str | None], headers_to_match: tuple[str, ...]) -> int | None:
    for i, cell in enumerate(header_row):
        if not cell:
            continue
        cell_lower = cell.strip().lower()
        if any(h in cell_lower for h in headers_to_match):
            return i
    return None


def extract_from_tables(tables: list[list[list[str | None]]]) -> dict[str, dict[str, Any]]:
    """Returns {field_key: {"value": float, "confidence_tier": "found",
    "evidence": "table row: <label> | <raw cell>"}} for every recognizable
    row across every table. Later tables/rows overwrite earlier ones for the
    same field (last-labeled-value-wins, matching how an Annexure usually
    supersedes a summary paragraph).
    """
    results: dict[str, dict[str, Any]] = {}

    for table in tables:
        if not table or len(table) < 2:
            continue

        header_row = table[0]
        annual_col = _find_column_index(header_row, ANNUAL_HEADERS)
        monthly_col = _find_column_index(header_row, MONTHLY_HEADERS)
        if annual_col is None and monthly_col is None:
            continue  # not a compensation table we recognize

        for row in table[1:]:
            if not row or not row[0]:
                continue
            field_key = resolve_alias(row[0])
            if field_key is None:
                continue

            value = None
            evidence_col = None
            if annual_col is not None and annual_col < len(row):
                value = parse_money(row[annual_col] or "")
                evidence_col = "annual"
            if value is None and monthly_col is not None and monthly_col < len(row):
                monthly_value = parse_money(row[monthly_col] or "")
                if monthly_value is not None:
                    value = monthly_value * 12
                    evidence_col = "monthly*12"

            if value is not None:
                results[field_key] = {
                    "value": value,
                    "confidence_tier": "found",
                    "evidence": f"table row: '{row[0].strip()}' ({evidence_col} column)",
                }

    return results
