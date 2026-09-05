"""Layer 2 (strict label:value regex) and Layer 3 (loose same-line fallback)
extraction over the plain-text body of a document.

Layer 1 (spatial/tabular — reading an Annexure table's Annual/Monthly
columns) lives in tabular.py and takes priority over both of these when it
finds a value, since a table cell is a stronger signal than a text regex.

Every alias is matched on a word boundary (`\\b`), never a bare substring —
without that, a two-letter acronym like "DA" would happily match inside
"Date" or "commission" fields would trip on unrelated prose. This one rule
eliminates a whole class of false positives.
"""
from __future__ import annotations

import re

from . import schema
from .normalize import parse_money, parse_months

MONEY_TOKEN = r"[₹$]?\s*[\d][\d,]*(?:\.\d+)?\s*(?:lakh|lac|crore|cr)?"
DURATION_TOKEN = r"\d+\s*(?:months?|years?|yrs?)"
COUNT_TOKEN = r"\d[\d,]*"

_VALUE_TOKENS = {"currency": MONEY_TOKEN, "months": DURATION_TOKEN, "count": COUNT_TOKEN}
_MAX_FILLER_CHARS = 40  # how much unrelated prose we tolerate between a label and its value

METADATA_PATTERNS: dict[str, re.Pattern] = {
    "company_name": re.compile(r"(?:^|\n)Company Name\s*[:\-]\s*(.+)", re.IGNORECASE),
    "employee_name": re.compile(r"^Dear\s+([A-Za-z.\s]+?)[,\n]", re.IGNORECASE | re.MULTILINE),
    "designation": re.compile(r"position of\s+([A-Za-z0-9 /&,'\-]+?)[.\n]", re.IGNORECASE),
    "joining_date": re.compile(r"joining date is (?:on or before\s+)?([\d/\-A-Za-z]+)", re.IGNORECASE),
}

# Fields whose value is a short classification token rather than a number,
# matched directly anywhere in the document rather than via a label:value line.
KEYWORD_TOKEN_PATTERNS: dict[str, re.Pattern] = {
    "variable_pay_frequency": re.compile(r"\b(monthly|quarterly|annually|annual|yearly)\b", re.IGNORECASE),
    "equity_type": re.compile(r"\b(ESOPs?|RSUs?|ESPPs?)\b", re.IGNORECASE),
}

# variable_pay_frequency's keyword pattern matches common words ("Monthly",
# "Annual") that show up all over a document for unrelated reasons (a table's
# "Monthly (Rs.)" column header, an unrelated "per annum" clause elsewhere).
# For fields listed here, a keyword match only counts if one of these anchor
# terms also appears within CONTEXT_WINDOW characters of it.
CONTEXT_WINDOW = 80
CONTEXT_ANCHORS: dict[str, list[str]] = {
    "variable_pay_frequency": [*schema.ALIASES["target_bonus"], "bonus", "variable"],
}


def _clean_evidence(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_metadata(text: str) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for key, pattern in METADATA_PATTERNS.items():
        match = pattern.search(text)
        result[key] = match.group(1).strip().rstrip(".,") if match else None
    return result


def _alias_boundary(alias: str) -> str:
    return rf"\b{re.escape(alias)}\b"


def _sorted_aliases(field_key: str) -> list[str]:
    return sorted(schema.ALIASES.get(field_key, []), key=len, reverse=True)


def _strict_label_match(text: str, field_key: str, value_token: str, unit: str) -> tuple[str, str] | None:
    """Two passes per alias, both anchored on a word boundary:

    (a) tight/adjacent — alias, an optional parenthetical aside, an optional
        ':'/'-' separator, an optional "of", an optional currency marker,
        then the value. No free-text filler allowed.
    (b) tolerant-with-marker (currency fields only) — allows up to
        `_MAX_FILLER_CHARS` of arbitrary prose between the alias and an
        *explicit* Rs./INR/₹ marker, so a sentence like "Total Compensation
        ... for the year will be Rs. 18,00,000" still counts as a direct
        label match rather than falling to the loose fallback tier. Requiring
        the explicit marker (rather than allowing filler before a bare
        number) keeps this from grabbing an unrelated number elsewhere in
        a long sentence.
    """
    for alias in _sorted_aliases(field_key):
        boundary_alias = _alias_boundary(alias)

        tight = re.compile(
            rf"{boundary_alias}\s*(?:\([^)]*\))?\s*[:\-]?\s*(?:of\s+)?(?:Rs\.?|INR|₹)?\s*({value_token})",
            re.IGNORECASE,
        )
        match = tight.search(text)
        if match and match.group(1).strip():
            return match.group(1), match.group(0)

        if unit == "currency":
            widened = re.compile(
                rf"{boundary_alias}[^.\n₹$]{{0,{_MAX_FILLER_CHARS}}}?(?:Rs\.?|INR|₹)\s*({value_token})",
                re.IGNORECASE,
            )
            match = widened.search(text)
            if match and match.group(1).strip():
                return match.group(1), match.group(0)

    return None


def _fallback_same_line_match(text: str, field_key: str, value_token: str) -> tuple[str, str] | None:
    """Loosest tier: alias appears (as a whole word) anywhere in a line that
    also contains a value token of the expected kind, even without a direct
    label:value adjacency."""
    value_re = re.compile(value_token, re.IGNORECASE)
    for line in text.split("\n"):
        if any(re.search(_alias_boundary(alias), line, re.IGNORECASE)
               for alias in schema.ALIASES.get(field_key, [])):
            value_match = value_re.search(line)
            if value_match:
                return value_match.group(), line.strip()
    return None


def _clause_around(line: str, alias: str) -> str:
    """For the free-text fallback: instead of returning an entire
    (possibly multi-sentence) line, trim to just the clause containing the
    alias — from just after the previous '.'/',' up to the next '.'."""
    match = re.search(_alias_boundary(alias), line, re.IGNORECASE)
    if not match:
        return line.strip()
    idx = match.start()
    start = max(line.rfind(".", 0, idx), line.rfind(",", 0, idx)) + 1
    end_dot = line.find(".", idx)
    end = end_dot + 1 if end_dot != -1 else len(line)
    return line[start:end].strip()


def _text_field_match(text: str, field_key: str) -> tuple[str, str, str] | None:
    """For 'text'-unit fields: try a dedicated keyword pattern first (found),
    then a direct 'alias: value' label (found), then a clause-trimmed
    same-line fallback (estimated). Returns (value, evidence, confidence_tier).
    """
    if field_key in KEYWORD_TOKEN_PATTERNS:
        anchors = CONTEXT_ANCHORS.get(field_key)
        for match in KEYWORD_TOKEN_PATTERNS[field_key].finditer(text):
            if anchors is None:
                return match.group(1), match.group(0), "found"
            window = text[max(0, match.start() - CONTEXT_WINDOW):match.end() + CONTEXT_WINDOW].lower()
            if any(re.search(_alias_boundary(a), window) for a in anchors):
                return match.group(1), match.group(0), "found"

    for alias in schema.ALIASES.get(field_key, []):
        pattern = re.compile(rf"{_alias_boundary(alias)}\s*[:\-]\s*(.+)", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            value = match.group(1).strip().rstrip(".")
            if value:
                return value, match.group(0), "found"

    for line in text.split("\n"):
        for alias in schema.ALIASES.get(field_key, []):
            if re.search(_alias_boundary(alias), line, re.IGNORECASE):
                snippet = _clause_around(line, alias)
                return snippet, snippet, "estimated"

    return None


def extract_field_regex(text: str, field_key: str) -> dict:
    """Runs Layer 2 then Layer 3 for one field. Returns
    {"value": ..., "confidence_tier": "found"|"estimated"|"missing", "evidence": str|None}.
    Never returns 0 for a genuinely absent value — an unmatched field is
    always {"value": None, "confidence_tier": "missing"}.
    """
    unit = schema.FIELDS[field_key]["unit"]

    if unit == "text":
        result = _text_field_match(text, field_key)
        if result:
            value, evidence, tier = result
            return {"value": value, "confidence_tier": tier, "evidence": evidence}
        return {"value": None, "confidence_tier": "missing", "evidence": None}

    value_token = _VALUE_TOKENS[unit]
    if unit == "months":
        cast = parse_months
    elif unit == "count":
        cast = lambda raw: int(parse_money(raw)) if parse_money(raw) is not None else None
    else:
        cast = parse_money

    strict = _strict_label_match(text, field_key, value_token, unit)
    if strict:
        raw_value, evidence = strict
        value = cast(raw_value)
        if value is not None:
            return {"value": value, "confidence_tier": "found", "evidence": _clean_evidence(evidence)}

    fallback = _fallback_same_line_match(text, field_key, value_token)
    if fallback:
        raw_value, evidence = fallback
        value = cast(raw_value)
        if value is not None:
            return {"value": value, "confidence_tier": "estimated", "evidence": _clean_evidence(evidence)}

    return {"value": None, "confidence_tier": "missing", "evidence": None}
