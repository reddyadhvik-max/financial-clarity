"""API layer. Thin wrappers around the pure engine functions in app/engine.py.

Not backend work (handled elsewhere, upstream of this service):
  - Reading/parsing the offer-letter PDF (the AI parsing agent's job — it
    calls POST /parse-fields with clean structured JSON).
  - Generating plain-language explanations (the AI agent's job — it should
    call GET /rule/:rule_id rather than inventing rule descriptions).
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import engine, rules
from app.schemas import BreakdownRequest, ParseFieldsRequest, RegimeComparisonRequest
from app.validation import validate_ctc_breakup

app = FastAPI(title="Offer Decoder API", version="0.1.0")

# The frontend is a static page (opened via file:// or a plain static server),
# so it has no fixed origin the backend can allowlist. Open CORS here since
# this API carries no auth/session state to protect against cross-origin misuse.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

COMPLETENESS_SCOPE = {
    "covered": [
        "Salaried income: Basic, HRA, special allowance, other fixed allowances, bonus/variable pay",
        "Employee & employer PF (EPF)",
        "Employee & employer ESI",
        "Gratuity provisioning and Section 10(10) exemption cap",
        "HRA exemption (old regime)",
        "Standard deduction (old & new regime)",
        "Section 80C and 80D deductions (old regime)",
        "Old vs new regime tax slab comparison, incl. Section 87A rebate",
        "Health & Education Cess",
        "Basic offer red flags: variable pay concentration, low basic, missing PF, missing gratuity "
        "clause, long notice period, service bonds, joining bonus clawbacks",
    ],
    "not_covered": [
        "Capital gains (equity, mutual funds, property, ESOPs already vested/sold)",
        "Income from other sources (interest, rental income, freelance/consulting)",
        "Multiple employers / Form 12B consolidation in a single FY",
        "Surcharge on high incomes and marginal relief above surcharge thresholds",
        "Section 24(b) home loan interest, Section 80CCD(1B) NPS, Section 80E education loan, and "
        "other deductions beyond 80C/80D",
        "Employer NPS contribution under Section 80CCD(2) (allowed under both regimes)",
        "State-specific Professional Tax slabs (accepted as a manual input only)",
        "Perquisite valuation (company car, ESOPs, rent-free accommodation, etc.)",
        "Senior citizen / super senior citizen tax slabs",
        "Arrears, relief under Section 89, and multi-year gratuity service calculations",
    ],
}


def _http_error(status_code: int, detail: dict) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=detail)


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
