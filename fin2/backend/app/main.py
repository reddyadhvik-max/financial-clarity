"""API layer. Thin wrappers around the pure engine functions in app/engine.py,
plus the AI orchestration endpoints under /ai/* (app/ai/*).

The /ai/* endpoints are the AI layer, hosted in this same service: Gemini
handles document understanding, ambiguity detection, conversational tool use,
and narration, but never arithmetic — every number they surface is computed
by the engine functions below and passed to Gemini as already-verified JSON.
See app/ai/README-equivalent docstrings in agent.py/parser.py/tools.py for
the boundary.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import engine, rules
from app.ai import agent as ai_agent
from app.ai import parser as ai_parser
from app.ai.gemini_client import MissingCredentialsError, QuotaExhaustedError
from app.ai.schemas import (
    AskRequest,
    ExplainRequest,
    NegotiateRequest,
    NegotiationMessageRequest,
    ParseOfferTextRequest,
)
from app.schemas import (
    BreakdownRequest,
    ClassifyRequest,
    CompareOffersRequest,
    ParseFieldsRequest,
    QualityScoreRequest,
    RegimeComparisonRequest,
    TimelineRequest,
    WaterfallRequest,
)
from app.validation import validate_ctc_breakup

app = FastAPI(title="Offer Decoder API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

COMPLETENESS_SCOPE = {
    "covered": [
        "Salaried income: Basic, Dearness Allowance, HRA, special allowance, other fixed allowances, "
        "bonus/variable pay, retention bonus, sales commission",
        "Employee & employer PF (EPF), computed on Basic + DA",
        "Employee & employer ESI",
        "Gratuity provisioning, Section 10(10) exemption cap, and 5-year vesting timeline "
        "(payable vs. forfeited on early exit)",
        "HRA exemption (old regime)",
        "Leave Travel Allowance (LTA): exemption on the claimed amount (old regime only — the "
        "twice-in-a-4-year-block restriction is not modelled)",
        "Employer NPS/Superannuation contribution under Section 80CCD(2) (both regimes)",
        "EPF continuity: tax-free withdrawal eligibility (5 years) and EPS pension eligibility "
        "(10 years, if continuously transferred rather than withdrawn)",
        "Standard deduction (old & new regime)",
        "Section 80C and 80D deductions (old regime)",
        "Old vs new regime tax slab comparison, incl. Section 87A rebate",
        "Health & Education Cess",
        "Basic offer red flags: variable pay concentration, low basic, missing PF, missing gratuity "
        "clause, long notice period, service bonds, joining bonus clawbacks (with period, if given)",
    ],
    "not_covered": [
        "Capital gains (mutual funds, property, ESOPs/RSUs/ESPP already vested/sold)",
        "Equity compensation (ESOPs/RSUs/ESPP): grant details are accepted and displayed as provided, "
        "but not valued, vested, or taxed by this engine",
        "Income from other sources (interest, rental income, freelance/consulting)",
        "Multiple employers / Form 12B consolidation in a single FY",
        "Surcharge on high incomes and marginal relief above surcharge thresholds",
        "Section 24(b) home loan interest, Section 80CCD(1B) additional NPS, Section 80E education "
        "loan, and other deductions beyond 80C/80D/80CCD(2)",
        "State-specific Professional Tax slabs (accepted as a manual input only)",
        "Tax exemption nuances for food/meal coupons and telephone/internet reimbursements — if "
        "included via other_allowances, they are treated as fully taxable rather than partially exempt",
        "Perquisite valuation (company car, rent-free accommodation, etc.)",
        "Senior citizen / super senior citizen tax slabs",
        "Arrears, relief under Section 89, and multi-year gratuity service calculations",
    ],
}


def _http_error(status_code: int, detail: dict) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=detail)


def _ai_call(fn, *args, **kwargs):
    """Run an app.ai.* call, translating its failure modes into HTTP errors
    that are distinct from the deterministic engine's (400/422): 503 means
    the AI layer has no credentials configured, 429 means Gemini's free-tier
    quota is exhausted (never a crash — see app/ai/gemini_client.py), 502
    means some other Gemini/network failure."""
    try:
        return fn(*args, **kwargs)
    except MissingCredentialsError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except QuotaExhaustedError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:  # Gemini/network failures — never let these look like a 500 bug
        raise HTTPException(status_code=502, detail=f"AI request failed: {e}")


@app.post("/parse-fields")
def parse_fields(req: ParseFieldsRequest):
    result = validate_ctc_breakup(req.fields)
    if not result.valid:
        return _http_error(422, result.to_dict())
    return {"valid": True, "fields": req.fields}


@app.post("/breakdown")
def breakdown(req: BreakdownRequest):
    ctc_dict = req.ctc_breakup.model_dump()
    validation = validate_ctc_breakup(ctc_dict)
    if not validation.valid:
        return _http_error(422, validation.to_dict())

    try:
        in_hand_result = engine.compute_in_hand(ctc_dict, regime=req.regime, fy=req.fy)
    except rules.RuleNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Unknown FY '{e.fy}' for rule '{e.rule_id}'")

    flags = engine.detect_red_flags(ctc_dict, fy=req.fy)

    return {"breakdown": in_hand_result, "red_flags": flags}


@app.post("/regime-comparison")
def regime_comparison(req: RegimeComparisonRequest):
    hra_exemption = 0.0
    hra_detail = None
    if req.rent_paid is not None:
        if req.basic is None or req.hra_received is None:
            return _http_error(422, {"missing_fields": ["basic", "hra_received"],
                                      "reason": "basic and hra_received are required to compute an HRA exemption "
                                                "when rent_paid is supplied"})
        try:
            hra_detail = engine.compute_hra_exemption(req.basic, req.hra_received, req.rent_paid,
                                                        req.is_metro, fy=req.fy)
        except rules.RuleNotFoundError as e:
            raise HTTPException(status_code=400, detail=f"Unknown FY '{e.fy}' for rule '{e.rule_id}'")
        hra_exemption = hra_detail["exempt_amount"]

    try:
        result = engine.compute_regime_comparison(req.gross_salary, req.deductions_claimed,
                                                    hra_exemption, fy=req.fy)
    except rules.RuleNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Unknown FY '{e.fy}' for rule '{e.rule_id}'")

    if hra_detail is not None:
        result["hra_exemption_detail"] = hra_detail
    return result


@app.get("/rule/{rule_id}")
def get_rule(rule_id: str, fy: str | None = None):
    try:
        return rules.get_rule(rule_id, fy)
    except rules.RuleNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"No rule '{e.rule_id}' found for FY {e.fy}")


@app.get("/completeness-scope")
def completeness_scope():
    return COMPLETENESS_SCOPE


@app.get("/meta")
def meta():
    return {"current_fy": rules.current_fy(), "ruleset_version": rules.ruleset_version()}


@app.post("/waterfall")
def waterfall(req: WaterfallRequest):
    ctc_dict = req.ctc_breakup.model_dump()
    validation = validate_ctc_breakup(ctc_dict)
    if not validation.valid:
        return _http_error(422, validation.to_dict())
    try:
        return engine.compute_ctc_waterfall(ctc_dict, regime=req.regime, fy=req.fy)
    except rules.RuleNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Unknown FY '{e.fy}' for rule '{e.rule_id}'")


@app.post("/classify")
def classify(req: ClassifyRequest):
    ctc_dict = req.ctc_breakup.model_dump()
    validation = validate_ctc_breakup(ctc_dict)
    if not validation.valid:
        return _http_error(422, validation.to_dict())
    try:
        return engine.classify_compensation_components(ctc_dict, regime=req.regime, fy=req.fy)
    except rules.RuleNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Unknown FY '{e.fy}' for rule '{e.rule_id}'")


@app.post("/quality-score")
def quality_score(req: QualityScoreRequest):
    ctc_dict = req.ctc_breakup.model_dump()
    validation = validate_ctc_breakup(ctc_dict)
    if not validation.valid:
        return _http_error(422, validation.to_dict())
    try:
        return engine.compute_offer_quality_score(ctc_dict, regime=req.regime, fy=req.fy)
    except rules.RuleNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Unknown FY '{e.fy}' for rule '{e.rule_id}'")


@app.post("/compare-offers")
def compare_offers(req: CompareOffersRequest):
    for offer in (req.offer_a, req.offer_b):
        validation = validate_ctc_breakup(offer.ctc_breakup.model_dump())
        if not validation.valid:
            return _http_error(422, {"offer": offer.label, **validation.to_dict()})

    offer_a = {"label": req.offer_a.label, "regime": req.offer_a.regime,
               "ctc_breakup": req.offer_a.ctc_breakup.model_dump()}
    offer_b = {"label": req.offer_b.label, "regime": req.offer_b.regime,
               "ctc_breakup": req.offer_b.ctc_breakup.model_dump()}
    try:
        return engine.compare_offers(offer_a, offer_b, fy=req.fy)
    except rules.RuleNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Unknown FY '{e.fy}' for rule '{e.rule_id}'")


@app.post("/gratuity-epf-timeline")
def gratuity_epf_timeline(req: TimelineRequest):
    try:
        return engine.compute_epf_gratuity_timeline(
            req.joining_date, as_of_date=req.as_of_date, separation_date=req.separation_date, fy=req.fy,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid date: {e}")
    except rules.RuleNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Unknown FY '{e.fy}' for rule '{e.rule_id}'")


SAMPLE_OFFERS_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_offers.json"


@app.get("/sample-offers")
def sample_offers():
    with SAMPLE_OFFERS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/ai/parse-offer")
def ai_parse_offer(req: ParseOfferTextRequest):
    result = _ai_call(ai_parser.parse_offer_letter, req.offer_text)
    return result.model_dump()


@app.post("/ai/parse-offer-document")
async def ai_parse_offer_document(file: UploadFile = File(...)):
    """Real document/vision understanding — sends the PDF/image straight to
    Gemini (multi-page PDFs and scanned images both work natively), no
    separate OCR pipeline. See app/ai/parser.py for size/type limits."""
    data = await file.read()
    mime_type = file.content_type or "application/octet-stream"
    try:
        result = ai_parser.parse_offer_document(data, mime_type)
    except ai_parser.DocumentTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except ai_parser.UnsupportedDocumentTypeError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except MissingCredentialsError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except QuotaExhaustedError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI request failed: {e}")
    return result.model_dump()


@app.post("/ai/ask")
def ai_ask(req: AskRequest):
    ctc_dict = req.ctc_breakup.model_dump()
    validation = validate_ctc_breakup(ctc_dict)
    if not validation.valid:
        return _http_error(422, validation.to_dict())
    result = _ai_call(
        ai_agent.ask, ctc_dict, req.question, fy=req.fy,
        history=[turn.model_dump() for turn in req.history],
    )
    return result.model_dump()


@app.post("/ai/explain")
def ai_explain(req: ExplainRequest):
    ctc_dict = req.ctc_breakup.model_dump()
    validation = validate_ctc_breakup(ctc_dict)
    if not validation.valid:
        return _http_error(422, validation.to_dict())
    try:
        computed = {
            "in_hand": engine.compute_in_hand(ctc_dict, regime=req.regime, fy=req.fy),
            "red_flags": engine.detect_red_flags(ctc_dict, fy=req.fy),
            "quality_score": engine.compute_offer_quality_score(ctc_dict, regime=req.regime, fy=req.fy),
        }
    except rules.RuleNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Unknown FY '{e.fy}' for rule '{e.rule_id}'")
    explanation = _ai_call(
        ai_agent.narrate,
        "Explain what this offer actually means for the candidate: how the headline CTC "
        "breaks down into guaranteed vs. at-risk pay, what their real take-home is, and "
        "any red flags worth knowing about.",
        computed,
    )
    return {"explanation": explanation, "computed": computed}


@app.post("/ai/negotiate")
def ai_negotiate(req: NegotiateRequest):
    ctc_dict = req.ctc_breakup.model_dump()
    validation = validate_ctc_breakup(ctc_dict)
    if not validation.valid:
        return _http_error(422, validation.to_dict())
    try:
        computed = {
            "in_hand": engine.compute_in_hand(ctc_dict, regime=req.regime, fy=req.fy),
            "red_flags": engine.detect_red_flags(ctc_dict, fy=req.fy),
            "quality_score": engine.compute_offer_quality_score(ctc_dict, regime=req.regime, fy=req.fy),
            "classification": engine.classify_compensation_components(ctc_dict, regime=req.regime, fy=req.fy),
        }
    except rules.RuleNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Unknown FY '{e.fy}' for rule '{e.rule_id}'")
    negotiation_points = _ai_call(
        ai_agent.narrate,
        "Based on this offer's numbers, give the candidate a prioritized list of what to "
        "negotiate (e.g. reducing variable-pay concentration, clarifying a clawback clause, "
        "raising fixed pay) — ground every point in a specific figure from the JSON below, "
        "don't give generic negotiation advice.",
        computed,
    )
    return {"negotiation_points": negotiation_points, "computed": computed}


@app.post("/ai/negotiation-message")
def ai_negotiation_message(req: NegotiationMessageRequest):
    ctc_dict = req.ctc_breakup.model_dump()
    validation = validate_ctc_breakup(ctc_dict)
    if not validation.valid:
        return _http_error(422, validation.to_dict())
    try:
        computed = {
            "in_hand": engine.compute_in_hand(ctc_dict, regime=req.regime, fy=req.fy),
            "red_flags": engine.detect_red_flags(ctc_dict, fy=req.fy),
            "quality_score": engine.compute_offer_quality_score(ctc_dict, regime=req.regime, fy=req.fy),
        }
    except rules.RuleNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Unknown FY '{e.fy}' for rule '{e.rule_id}'")

    if req.audience == "recruiter_email":
        instruction = (
            "Draft a short, professional email to a recruiter asking to negotiate this offer. "
            "Ground the ask in specific figures from the JSON below (e.g. variable-pay %, a red "
            "flag) rather than generic language. Keep it polite and concise."
        )
    else:
        instruction = (
            "Produce a short bulleted list of talking points the candidate can use on a live call "
            "with HR to negotiate this offer, each grounded in a specific figure from the JSON below."
        )
    message = _ai_call(ai_agent.narrate, instruction, computed)
    return {"message": message, "computed": computed}


@app.post("/ai/compare-offers")
def ai_compare_offers(req: CompareOffersRequest):
    for offer in (req.offer_a, req.offer_b):
        validation = validate_ctc_breakup(offer.ctc_breakup.model_dump())
        if not validation.valid:
            return _http_error(422, {"offer": offer.label, **validation.to_dict()})

    offer_a = {"label": req.offer_a.label, "regime": req.offer_a.regime,
               "ctc_breakup": req.offer_a.ctc_breakup.model_dump()}
    offer_b = {"label": req.offer_b.label, "regime": req.offer_b.regime,
               "ctc_breakup": req.offer_b.ctc_breakup.model_dump()}
    try:
        computed = engine.compare_offers(offer_a, offer_b, fy=req.fy)
    except rules.RuleNotFoundError as e:
        raise HTTPException(status_code=400, detail=f"Unknown FY '{e.fy}' for rule '{e.rule_id}'")
    verdict = _ai_call(
        ai_agent.narrate,
        f"Compare {req.offer_a.label} and {req.offer_b.label} for the candidate and give a "
        "clear verdict on which is financially safer/better and why — headline CTC can be "
        "misleading, so weigh guaranteed pay, risk, and in-hand pay from the JSON below.",
        computed,
    )
    return {"verdict": verdict, "computed": computed}
