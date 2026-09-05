"""Thin FastAPI service exposing the parser: a field checklist (for the
frontend to render "found / estimated / missing" per field), parse
endpoints for text and PDF uploads, offer listing with filters, and the
offer-comparison endpoint used by the multi-offer comparison feature.

Run with:  uvicorn parser.api:app --reload --port 8100
(see README.md — this is a separate service from the main Offer Decoder
backend in ../backend, on its own port, so the two can be developed and
demoed independently.)
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import schema, storage
from .compare import compare_offers
from .parser_engine import OfferLetterParser

app = FastAPI(title="Offer Letter Data Parser", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_parser = OfferLetterParser()


@app.get("/checklist")
def get_checklist() -> dict[str, Any]:
    """Categorized list of every field this parser looks for, plus the
    label variants/acronyms it recognizes — for a frontend "what did we
    find vs. still need to check" checklist UI."""
    checklist: dict[str, list[dict[str, Any]]] = {}
    for field_key, meta in schema.FIELDS.items():
        checklist.setdefault(meta["category"], []).append({
            "field": field_key,
            "label": meta["label"],
            "unit": meta["unit"],
            "known_aliases": schema.ALIASES.get(field_key, []),
        })
    return checklist


class ParseTextRequest(BaseModel):
    text: str
    source_filename: str | None = None


@app.post("/parse/text")
def parse_text(req: ParseTextRequest) -> dict[str, Any]:
    result = _parser.parse_text(req.text)
    offer_id = storage.save_offer(result, source_filename=req.source_filename)
    result["offer_id"] = offer_id
    return result


@app.post("/parse/pdf")
async def parse_pdf(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Expected a .pdf file")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        result = _parser.parse_pdf(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    offer_id = storage.save_offer(result, source_filename=file.filename)
    result["offer_id"] = offer_id
    return result


@app.get("/offers")
def get_offers(company_name: str | None = None, min_ctc: float | None = None,
                max_ctc: float | None = None, missing_field: str | None = None,
                category: str | None = None) -> list[dict[str, Any]]:
    return storage.list_offers(company_name=company_name, min_ctc=min_ctc, max_ctc=max_ctc,
                                missing_field=missing_field, category=category)


@app.get("/offers/{offer_id}")
def get_offer(offer_id: str) -> dict[str, Any]:
    result = storage.get_offer(offer_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No stored offer with id '{offer_id}'")
    return result


class CompareRequest(BaseModel):
    offer_id_a: str
    offer_id_b: str
    label_a: str = "Offer A"
    label_b: str = "Offer B"


@app.post("/compare")
def compare(req: CompareRequest) -> dict[str, Any]:
    result_a = storage.get_offer(req.offer_id_a)
    result_b = storage.get_offer(req.offer_id_b)
    if result_a is None:
        raise HTTPException(status_code=404, detail=f"No stored offer with id '{req.offer_id_a}'")
    if result_b is None:
        raise HTTPException(status_code=404, detail=f"No stored offer with id '{req.offer_id_b}'")
    return compare_offers(result_a, result_b, req.label_a, req.label_b)
