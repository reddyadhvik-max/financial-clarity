"""Pydantic models for the AI layer's own outputs.

These describe what Gemini is allowed to say, not what the engine
calculates — no field here holds a number Gemini invented itself. Extracted
compensation values always carry a confidence and the exact source text they
were read from, so a low-confidence or unsupported read is visible rather
than silently trusted.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.schemas import CTCBreakup


class ExtractedField(BaseModel):
    value: float | str | bool | None = Field(
        None, description="The extracted value, or null if not mentioned in the letter at all"
    )
    confidence: float = Field(ge=0, le=1, description="0-1 confidence that `value` is correct")
    source_text: str | None = Field(
        None, description="The exact phrase in the offer letter this value was read from"
    )
    page: int | None = Field(
        None, description="1-indexed page number this was read from, if the source is a multi-page "
                           "document and the page is determinable; null for plain-text input"
    )


class Ambiguity(BaseModel):
    field: str = Field(description="Which compensation field this ambiguity concerns")
    question: str = Field(description="A short, concrete question to ask the user to resolve it")
    reason: str = Field(description="Why the offer letter text was insufficient to decide this confidently")


class Clause(BaseModel):
    """One employment/legal clause the parser found beyond plain compensation fields."""

    clause_type: str = Field(
        description="e.g. service_bond, non_compete, confidentiality, ip_assignment, termination, "
                    "probation, relocation, other"
    )
    quote: str = Field(description="The exact clause text, or the closest verbatim excerpt")
    interpretation: str = Field(description="Plain-language explanation of what this clause means")
    risk_level: Literal["low", "medium", "high"] = Field(
        description="How much this clause could disadvantage the candidate"
    )
    page: int | None = None


class Contradiction(BaseModel):
    """A deterministic, Python-computed consistency check — never an LLM-invented finding."""

    description: str
    fields_involved: list[str] = Field(default_factory=list)


class ParsedOfferAI(BaseModel):
    """Structured extraction of one offer letter. Maps 1:1 onto CTCBreakup fields."""

    company_name: ExtractedField | None = None
    job_title: ExtractedField | None = None
    city: ExtractedField | None = None
    ctc_total: ExtractedField | None = None
    basic: ExtractedField | None = None
    hra: ExtractedField | None = None
    special_allowance: ExtractedField | None = None
    dearness_allowance: ExtractedField | None = None
    bonus: ExtractedField | None = None
    retention_bonus: ExtractedField | None = None
    sales_commission: ExtractedField | None = None
    employer_pf: ExtractedField | None = None
    employer_nps: ExtractedField | None = None
    gratuity: ExtractedField | None = None
    gratuity_clause_present: ExtractedField | None = None
    health_insurance_premium: ExtractedField | None = None
    notice_period_days: ExtractedField | None = None
    has_service_bond: ExtractedField | None = None
    joining_bonus_has_clawback: ExtractedField | None = None
    joining_bonus_clawback_period_months: ExtractedField | None = None
    equity_type: ExtractedField | None = None
    equity_grant_value: ExtractedField | None = None
    equity_vesting_schedule: ExtractedField | None = None

    clauses: list[Clause] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(
        default_factory=list, description="Populated by a deterministic Python consistency check after "
                                            "extraction, never by the model itself"
    )
    needs_user_input: bool = Field(
        description="True if any extracted field has confidence below 0.6, or ambiguities is non-empty"
    )


class ToolCallLog(BaseModel):
    """One engine function the agent invoked while answering — for provenance in the UI."""

    tool: str
    args: dict
    result_summary: str = Field(description="One line describing what the tool returned, not the full payload")


class AgentAnswer(BaseModel):
    answer: str
    tool_calls: list[ToolCallLog] = Field(default_factory=list)


class ParseOfferTextRequest(BaseModel):
    offer_text: str = Field(description="Raw extracted text of the offer letter")


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    ctc_breakup: CTCBreakup
    question: str
    fy: str | None = None
    history: list[ChatTurn] = Field(default_factory=list)


class ExplainRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    ctc_breakup: CTCBreakup
    regime: Literal["old", "new"] = "new"
    fy: str | None = None


class NegotiateRequest(ExplainRequest):
    pass


class NegotiationMessageRequest(ExplainRequest):
    audience: Literal["recruiter_email", "hr_call_talking_points"] = "recruiter_email"
