"""Input sanitization — the first pass every extracted text goes through,
regardless of whether it came from raw text, a PDF, or OCR.

Real offer letters (especially PDF-exported ones) carry zero-width
characters, non-breaking spaces, smart quotes, and inconsistent line
breaks/hyphenation from justified text layout. Every downstream regex and
label-match depends on this being cleaned up first.
"""
from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH = "".join(["​", "‌", "‍", "﻿"])
_ZERO_WIDTH_RE = re.compile(f"[{_ZERO_WIDTH}]")
_MULTI_SPACE_RE = re.compile(r"[ \t ]+")
_MULTI_BLANK_LINE_RE = re.compile(r"\n{3,}")
_HYPHEN_LINEBREAK_RE = re.compile(r"(\w)-\n(\w)")  # "de-\nductions" -> "deductions"

_QUOTE_MAP = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", " ": " ",
}


def sanitize_text(raw: str) -> str:
    """Normalize a raw text extraction into a clean, consistently-spaced
    string safe for regex/label matching. Idempotent — safe to call more
    than once on the same text.
    """
    if not raw:
        return ""

    text = unicodedata.normalize("NFKC", raw)
    text = _ZERO_WIDTH_RE.sub("", text)
    for smart, plain in _QUOTE_MAP.items():
        text = text.replace(smart, plain)

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHEN_LINEBREAK_RE.sub(r"\1\2", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_BLANK_LINE_RE.sub("\n\n", text)

    return "\n".join(line.strip() for line in text.split("\n")).strip()
