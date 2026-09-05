"""Pydantic request/response models for the API layer."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CTCBreakup(BaseModel):
    basic: float | None = Field(None, description="Annual Basic salary (INR)")
    hra: float | None = Field(None, description="Annual HRA (INR)")
    special_allowance: float = 0
    other_allowances: dict[str, float] = Field(default_factory=dict)
    bonus: float = 0
    employer_pf: float | None = None
    pf_on_full_basic: bool = True
    gratuity: float | None = None
    professional_tax: float = 0
    deductions_claimed: dict[str, float] = Field(default_factory=dict)
    rent_paid: float | None = None
    is_metro: bool = False
    ctc_total: float | None = None

    # red-flag-only fields, ignored by compute_in_hand
    gratuity_clause_present: bool = True
    notice_period_days: float | None = None
    has_service_bond: bool = False
    joining_bonus_has_clawback: bool = False


class ParseFieldsRequest(BaseModel):
    fields: dict[str, Any]


class BreakdownRequest(BaseModel):
    ctc_breakup: CTCBreakup
    regime: Literal["old", "new"] = "new"
    fy: str | None = None


class RegimeComparisonRequest(BaseModel):
    gross_salary: float
    deductions_claimed: dict[str, float] = Field(default_factory=dict)
    basic: float | None = Field(None, description="Needed only if rent_paid is given, to derive HRA exemption")
    hra_received: float | None = None
    rent_paid: float | None = None
    is_metro: bool = False
    fy: str | None = None
