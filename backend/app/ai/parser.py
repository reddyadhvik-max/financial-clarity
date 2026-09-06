"""Offer-letter document understanding: raw text (or a PDF/image document) in,
structured + confidence-scored fields out. This is a pure I/O boundary — it
does no arithmetic. Anything the model can't determine confidently is
surfaced in `ambiguities` for the caller to ask the user about, rather than
guessed. `contradictions` is filled in afterward by a deterministic Python
check (app/ai/consistency.py), never by the model.

One Gemini call per document — no second "self-check" LLM call, since
app/ai/consistency.py already covers arithmetic consistency for free.
"""
from __future__ import annotations

from google.genai import types

from app.ai.consistency import detect_contradictions
from app.ai.gemini_client import DEFAULT_MODEL, get_client, translate_quota_errors
from app.ai.prompts import PARSE_SYSTEM_PROMPT
from app.ai.schemas import ParsedOfferAI

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_DOCUMENT_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}


class DocumentTooLargeError(ValueError):
    pass


class UnsupportedDocumentTypeError(ValueError):
    pass


def _finalize(response_text: str) -> ParsedOfferAI:
    parsed = ParsedOfferAI.model_validate_json(response_text)
    parsed.contradictions = detect_contradictions(parsed)
    if parsed.contradictions:
        parsed.needs_user_input = True
    return parsed


def parse_offer_letter(offer_text: str) -> ParsedOfferAI:
    """Parse plain extracted/pasted offer-letter text."""
    client = get_client()
    try:
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=offer_text,
            config=types.GenerateContentConfig(
                system_instruction=PARSE_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_json_schema=ParsedOfferAI.model_json_schema(),
            ),
        )
    except Exception as e:
        raise translate_quota_errors(e) from e
    return _finalize(response.text)


def parse_offer_document(data: bytes, mime_type: str) -> ParsedOfferAI:
    """Parse a PDF or image offer letter via Gemini's native document/vision
    understanding — no separate OCR pipeline. Handles multi-page PDFs and
    scanned images in one call."""
    if len(data) > MAX_DOCUMENT_BYTES:
        raise DocumentTooLargeError(
            f"Document is {len(data) / 1_048_576:.1f} MB, over the {MAX_DOCUMENT_BYTES // 1_048_576} MB limit."
        )
    if mime_type not in ALLOWED_DOCUMENT_MIME_TYPES:
        raise UnsupportedDocumentTypeError(
            f"Unsupported file type '{mime_type}'. Allowed: {', '.join(sorted(ALLOWED_DOCUMENT_MIME_TYPES))}."
        )

    client = get_client()
    document_part = types.Part.from_bytes(data=data, mime_type=mime_type)
    try:
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=[document_part, "Extract the compensation and employment fields from this offer letter."],
            config=types.GenerateContentConfig(
                system_instruction=PARSE_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_json_schema=ParsedOfferAI.model_json_schema(),
            ),
        )
    except Exception as e:
        raise translate_quota_errors(e) from e
    return _finalize(response.text)
