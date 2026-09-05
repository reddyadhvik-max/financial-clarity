"""OfferLetterParser — the single entry point for the data-parsing engine.

Usage:
    parser = OfferLetterParser()
    result = parser.parse_text(raw_text)          # raw/plain text input
    result = parser.parse_pdf("offer.pdf")         # structured or scanned PDF
    result = parser.parse_image("offer_page1.png") # scanned image, no PDF wrapper

`result` is a plain dict matching the schema documented in README.md:
top-level `metadata`, `fields` (categorized), `derived`, `checksum`,
`red_flags`, and `warnings` (non-fatal extraction issues, e.g. OCR unavailable).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import schema
from .confidence import compute_derived_totals, extract_all_fields, run_checksum_validation
from .extractors import ExtractionResult, extract_from_image, extract_from_pdf, extract_from_text
from .patterns import extract_metadata
from .redflags import run_red_flag_checks


class OfferLetterParser:
    def parse_text(self, raw_text: str) -> dict[str, Any]:
        return self._parse(extract_from_text(raw_text))

    def parse_pdf(self, pdf_path: str | Path) -> dict[str, Any]:
        return self._parse(extract_from_pdf(pdf_path))

    def parse_image(self, image_path: str | Path) -> dict[str, Any]:
        return self._parse(extract_from_image(image_path))

    def _parse(self, extraction: ExtractionResult) -> dict[str, Any]:
        text = extraction.text
        metadata = extract_metadata(text)
        fields = extract_all_fields(text, extraction.tables)
        derived = compute_derived_totals(fields)
        checksum = run_checksum_validation(fields)
        red_flags = run_red_flag_checks(fields, derived, checksum)

        return {
            "metadata": metadata,
            "fields": self._categorize(fields),
            "derived": derived,
            "checksum": checksum,
            "red_flags": red_flags,
            "used_ocr": extraction.used_ocr,
            "warnings": extraction.warnings,
        }

    @staticmethod
    def _categorize(fields: dict[str, dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
        """Groups the flat field dict into the categories the spec calls
        for: Top-Line Metrics, Fixed Components, Retirals, Variable Pay,
        One-Time Payments, Deductions.
        """
        categorized: dict[str, dict[str, dict[str, Any]]] = {
            "top_line": {}, "fixed": {}, "retirals": {},
            "variable": {}, "one_time": {}, "deductions": {},
        }
        for field_key, meta in schema.FIELDS.items():
            categorized[meta["category"]][field_key] = fields[field_key]
        return categorized
