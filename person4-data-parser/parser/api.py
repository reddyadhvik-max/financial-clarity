"""Thin FastAPI service exposing the parser: a field checklist (for the
frontend to render "found / estimated / missing" per field), parse
endpoints for text and PDF uploads, offer listing with filters, and the
offer-comparison endpoint used by the multi-offer comparison feature.

Every parsed offer is stored in an **in-memory, per-session** SQLite
database (see sessions.py) — nothing is ever written to disk. Pass the
`X-Session-Id` header (returned by any response once a session exists) to
keep using the same session across requests; omit it and a new session is
created automatically. Call `DELETE /session` when the upload flow is done
to wipe that session's data immediately rather than waiting for the idle
timeout.

Run with:  uvicorn parser.api:app --reload --port 8100
(see README.md — this is a separate service from the main Offer Decoder
backend in ../backend, on its own port, so the two can be developed and
demoed independently.)
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import schema, storage
from .compare import compare_offers
from .parser_engine import OfferLetterParser
from .sessions import store

app = FastAPI(title="Offer Letter Data Parser", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    expose_headers=["X-Session-Id"],  # so browser JS can read the session id back
)

_parser = OfferLetterParser()


def resolve_session(response: Response, x_session_id: str | None = Header(default=None)) -> str:
    """Reuses the caller's session if it's still alive; otherwise silently
    starts a new one (e.g. first request, or the old one idle-timed-out).
    Either way, the effective session id is echoed back in the response
    header so the client always knows which session it's now talking to.
    """
    session_id = x_session_id
    if session_id is None or store.get_conn(session_id) is None:
        session_id = store.create()
    response.headers["X-Session-Id"] = session_id
    return session_id


@app.post("/session")
def start_session(response: Response) -> dict[str, Any]:
    """Explicitly starts a fresh session (optional — any parse/list/compare
    call will auto-create one if you don't). Useful for a UI that wants to
    show/copy the session id before the first upload."""
    session_id = store.create()
    response.headers["X-Session-Id"] = session_id
    return {"session_id": session_id}


@app.delete("/session")
def end_session(x_session_id: str = Header(...)) -> dict[str, Any]:
    """Ends a session immediately, discarding every offer parsed in it.
    Call this when the user finishes their comparison/upload flow rather
    than relying on the idle timeout."""
    closed = store.close(x_session_id)
    if not closed:
        raise HTTPException(status_code=404, detail=f"No active session '{x_session_id}'")
    return {"closed": True}


@app.get("/checklist")
def get_checklist() -> dict[str, Any]:
    """Categorized list of every field this parser looks for, plus the
    label variants/acronyms it recognizes — for a frontend "what did we
    find vs. still need to check" checklist UI. Not session-scoped — this
    is static schema data, not offer data."""
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
def parse_text(req: ParseTextRequest, session_id: str = Depends(resolve_session)) -> dict[str, Any]:
    result = _parser.parse_text(req.text)
    conn = store.get_conn(session_id)
    offer_id = storage.save_offer(conn, result, source_filename=req.source_filename)
    result["offer_id"] = offer_id
    result["session_id"] = session_id
    return result


@app.post("/parse/pdf")
async def parse_pdf(file: UploadFile = File(...), session_id: str = Depends(resolve_session)) -> dict[str, Any]:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Expected a .pdf file")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        result = _parser.parse_pdf(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)  # the uploaded PDF itself never touches persistent storage either

    conn = store.get_conn(session_id)
    offer_id = storage.save_offer(conn, result, source_filename=file.filename)
    result["offer_id"] = offer_id
    result["session_id"] = session_id
    return result


@app.get("/offers")
def get_offers(session_id: str = Depends(resolve_session), company_name: str | None = None,
                min_ctc: float | None = None, max_ctc: float | None = None,
                missing_field: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    conn = store.get_conn(session_id)
    return storage.list_offers(conn, company_name=company_name, min_ctc=min_ctc, max_ctc=max_ctc,
                                missing_field=missing_field, category=category)


@app.get("/offers/{offer_id}")
def get_offer(offer_id: str, session_id: str = Depends(resolve_session)) -> dict[str, Any]:
    conn = store.get_conn(session_id)
    result = storage.get_offer(conn, offer_id)
    if result is None:
        raise HTTPException(status_code=404,
                             detail=f"No offer '{offer_id}' in this session (offers never outlive their session)")
    return result


class CompareRequest(BaseModel):
    offer_id_a: str
    offer_id_b: str
    label_a: str = "Offer A"
    label_b: str = "Offer B"


@app.post("/compare")
def compare(req: CompareRequest, session_id: str = Depends(resolve_session)) -> dict[str, Any]:
    conn = store.get_conn(session_id)
    result_a = storage.get_offer(conn, req.offer_id_a)
    result_b = storage.get_offer(conn, req.offer_id_b)
    if result_a is None:
        raise HTTPException(status_code=404, detail=f"No offer '{req.offer_id_a}' in this session")
    if result_b is None:
        raise HTTPException(status_code=404, detail=f"No offer '{req.offer_id_b}' in this session")
    return compare_offers(result_a, result_b, req.label_a, req.label_b)
