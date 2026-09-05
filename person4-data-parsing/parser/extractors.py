"""Input-tolerance layer: turns any supported input (raw text, a structured
PDF, or a scanned/image-based PDF) into plain text, before sanitize.py and
the extraction strategies ever see it.

Routing logic:
  1. Raw text in                -> returned as-is (after sanitize.py).
  2. PDF path in                -> try pdfplumber (works for text-layer PDFs
     and also pulls table cells for tabular.py to use).
  3. PDF produced ~no text      -> assume it's a scanned/image PDF, fall back
     to OCR via pytesseract (requires the Tesseract binary to be installed
     separately — see the package README).

OCR is a genuinely optional dependency: if pytesseract or the Tesseract
binary isn't available, `extract_text_from_pdf` still returns whatever
pdfplumber found (possibly empty) instead of crashing the whole pipeline —
per the "never fail silently, don't block the rest of the system" principle,
a page that can't be OCR'd should surface as missing fields downstream, not
as an unhandled exception.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .sanitize import sanitize_text

MIN_CHARS_TO_SKIP_OCR = 40  # a text-layer PDF page yields far more than this


@dataclass
class ExtractionResult:
    text: str
    tables: list[list[list[str | None]]] = field(default_factory=list)
    used_ocr: bool = False
    warnings: list[str] = field(default_factory=list)


def extract_from_text(raw_text: str) -> ExtractionResult:
    return ExtractionResult(text=sanitize_text(raw_text))


def extract_from_pdf(pdf_path: str | Path) -> ExtractionResult:
    warnings: list[str] = []
    text_parts: list[str] = []
    tables: list[list[list[str | None]]] = []

    try:
        import pdfplumber
    except ImportError:
        warnings.append("pdfplumber not installed — cannot read PDF text layer or tables")
        return ExtractionResult(text="", warnings=warnings)

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
            for table in page.extract_tables() or []:
                tables.append(table)

    combined = "\n".join(text_parts)

    if len(combined.strip()) < MIN_CHARS_TO_SKIP_OCR:
        ocr_result = _try_ocr_pdf(pdf_path, warnings)
        if ocr_result is not None:
            return ExtractionResult(text=sanitize_text(ocr_result), tables=tables,
                                     used_ocr=True, warnings=warnings)
        warnings.append("PDF text layer near-empty and OCR unavailable/failed — "
                         "treat this document as a scanned image with no usable text")

    return ExtractionResult(text=sanitize_text(combined), tables=tables, warnings=warnings)


def _try_ocr_pdf(pdf_path: str | Path, warnings: list[str]) -> str | None:
    """Best-effort OCR fallback for scanned/image-only PDFs.

    Requires `pytesseract` (Python package) AND the Tesseract OCR binary on
    PATH, plus `pdf2image` (Python package) AND the Poppler binaries on
    PATH to rasterize PDF pages. Any missing piece degrades to `None` rather
    than raising, so the caller can surface "missing" fields instead of a
    hard failure.
    """
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as e:
        warnings.append(f"OCR dependency not installed ({e.name}) — skipping OCR fallback")
        return None

    try:
        pages = convert_from_path(str(pdf_path))
    except Exception as e:  # poppler missing, corrupt file, etc.
        warnings.append(f"Could not rasterize PDF for OCR ({e}) — skipping OCR fallback")
        return None

    try:
        return "\n".join(pytesseract.image_to_string(page) for page in pages)
    except Exception as e:  # tesseract binary missing/misconfigured
        warnings.append(f"Tesseract OCR failed ({e}) — skipping OCR fallback")
        return None


def extract_from_image(image_path: str | Path) -> ExtractionResult:
    """OCR a single scanned image (not a PDF) directly."""
    warnings: list[str] = []
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        warnings.append(f"OCR dependency not installed ({e.name})")
        return ExtractionResult(text="", warnings=warnings)

    try:
        text = pytesseract.image_to_string(Image.open(image_path))
    except Exception as e:
        warnings.append(f"Tesseract OCR failed ({e})")
        return ExtractionResult(text="", warnings=warnings)

    return ExtractionResult(text=sanitize_text(text), used_ocr=True, warnings=warnings)
