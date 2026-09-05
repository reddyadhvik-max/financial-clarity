"""Strict normalization helpers.

Money values are always cast to a plain float, with every currency symbol,
thousands separator, and stray whitespace stripped first — no downstream
code should ever try to parse "₹8,00,000" itself.
"""
from __future__ import annotations

import re

from . import schema

_MONEY_JUNK_RE = re.compile(r"[₹$,\s]")
_MONEY_TOKEN_RE = re.compile(r"[₹$]?\s*[\d,]+(?:\.\d+)?")
_LAKH_CRORE_RE = re.compile(r"(?P<num>[\d.]+)\s*(?P<unit>lakh|lac|crore|cr)\b", re.IGNORECASE)

_UNIT_MULTIPLIERS = {"lakh": 100_000, "lac": 100_000, "crore": 10_000_000, "cr": 10_000_000}


def parse_money(raw: str) -> float | None:
    """Cast a raw monetary string to a float, stripping symbols/commas and
    resolving lakh/crore shorthand (e.g. "8.5 lakh" -> 850000.0). Returns
    None if no numeric value can be recovered — callers must treat that as
    "missing", never coerce it to 0.
    """
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None

    lakh_match = _LAKH_CRORE_RE.search(raw)
    if lakh_match:
        try:
            value = float(lakh_match.group("num"))
        except ValueError:
            return None
        return value * _UNIT_MULTIPLIERS[lakh_match.group("unit").lower()]

    match = _MONEY_TOKEN_RE.search(raw)
    if not match:
        return None
    cleaned = _MONEY_JUNK_RE.sub("", match.group())
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_months(raw: str) -> int | None:
    """Extract a duration in months from free text like "12 months",
    "1 year", or "18-month". Returns None if unparseable.
    """
    if not raw:
        return None
    m = re.search(r"(\d+)\s*(month|yr|year)", raw, re.IGNORECASE)
    if not m:
        return None
    value = int(m.group(1))
    if m.group(2).lower().startswith("year") or m.group(2).lower() == "yr":
        value *= 12
    return value


def resolve_alias(label: str) -> str | None:
    """Map a raw label string (as found in a document, e.g. "Employer's PF
    Contribution") to its canonical schema field key, or None if no alias
    matches. Case-insensitive substring match, checked longest-alias-first
    so a specific alias like "employer pf" wins over a broader one.
    """
    label_lower = label.strip().lower()
    all_aliases = [
        (field_key, alias)
        for field_key, aliases in schema.ALIASES.items()
        for alias in aliases
    ]
    all_aliases.sort(key=lambda pair: len(pair[1]), reverse=True)
    for field_key, alias in all_aliases:
        if alias in label_lower:
            return field_key
    return None
