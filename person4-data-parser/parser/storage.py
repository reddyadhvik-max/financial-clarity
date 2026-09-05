"""Local persistence for parsed offers — a plain SQLite database (no server,
no extra dependency) so parsed offers survive between runs and can be
listed/filtered/compared later (e.g. by the multi-offer comparison feature).

Filtering by "does this offer have a missing field" is done in Python after
loading candidate rows rather than via SQLite JSON functions, since JSON1
availability varies across Python/SQLite builds — this trades a little
efficiency for working identically everywhere, which matters more for a
dataset this small (a handful of offers per user, not millions of rows).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "offers.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    source_filename TEXT,
    company_name TEXT,
    employee_name TEXT,
    total_ctc REAL,
    result_json TEXT NOT NULL
);
"""


def _connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(_SCHEMA)
    return conn


def save_offer(result: dict[str, Any], source_filename: str | None = None,
               db_path: str | Path = DEFAULT_DB_PATH) -> str:
    """Persists a parsed offer (the dict returned by OfferLetterParser) and
    returns its generated offer_id."""
    offer_id = str(uuid.uuid4())
    metadata = result.get("metadata", {})
    total_ctc = result.get("fields", {}).get("top_line", {}).get("total_ctc", {}).get("value")

    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO offers (id, created_at, source_filename, company_name, employee_name, "
            "total_ctc, result_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                offer_id,
                datetime.now(timezone.utc).isoformat(),
                source_filename,
                metadata.get("company_name"),
                metadata.get("employee_name"),
                total_ctc,
                json.dumps(result),
            ),
        )
    return offer_id


def get_offer(offer_id: str, db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT result_json FROM offers WHERE id = ?", (offer_id,)).fetchone()
    if row is None:
        return None
    result = json.loads(row[0])
    result["offer_id"] = offer_id
    return result


def list_offers(db_path: str | Path = DEFAULT_DB_PATH, company_name: str | None = None,
                 min_ctc: float | None = None, max_ctc: float | None = None,
                 missing_field: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    """Lists stored offer summaries, optionally filtered by:
      - company_name (substring match, case-insensitive)
      - min_ctc / max_ctc (inclusive range on total_ctc)
      - missing_field (a canonical field key that must be 'missing' on this offer)
      - category (only consider missing_field within this category when both are given)
    """
    query = "SELECT id, created_at, source_filename, company_name, employee_name, total_ctc, result_json FROM offers"
    clauses: list[str] = []
    params: list[Any] = []

    if company_name:
        clauses.append("LOWER(company_name) LIKE ?")
        params.append(f"%{company_name.lower()}%")
    if min_ctc is not None:
        clauses.append("total_ctc >= ?")
        params.append(min_ctc)
    if max_ctc is not None:
        clauses.append("total_ctc <= ?")
        params.append(max_ctc)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"

    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()

    summaries = []
    for offer_id, created_at, source_filename, company, employee, total_ctc, result_json in rows:
        result = json.loads(result_json)
        if missing_field:
            field_entry = _find_field(result, missing_field, category)
            if field_entry is None or field_entry.get("confidence_tier") != "missing":
                continue
        summaries.append({
            "offer_id": offer_id,
            "created_at": created_at,
            "source_filename": source_filename,
            "company_name": company,
            "employee_name": employee,
            "total_ctc": total_ctc,
            "red_flag_count": len(result.get("red_flags", [])),
        })
    return summaries


def _find_field(result: dict[str, Any], field_key: str, category: str | None) -> dict[str, Any] | None:
    fields = result.get("fields", {})
    if category:
        return fields.get(category, {}).get(field_key)
    for cat_fields in fields.values():
        if field_key in cat_fields:
            return cat_fields[field_key]
    return None
