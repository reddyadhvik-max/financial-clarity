"""Pydantic request/response models for the API layer.

Field names are snake_case internally (matches the engine and 48 existing
tests), but every request model also accepts camelCase — the team's shared
schema notes use `specialAllowance`/`employerPF`/`variablePay` — via
`alias_generator=to_camel` plus `populate_by_name=True`. `bonus` and
`employer_pf` additionally accept the exact team spelling
(`variablePay`, `employerPF`) since to_camel would otherwise produce
`employerPf` (lowercase second letter) and wouldn't rename `bonus` at all.
Send either style; both land on the same snake_case field.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CTCBreakup(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    basic: float | None = Field(None, description="Annual Basic salary (INR)")
    hra: float | None = Field(None, description="Annual HRA (INR)")
    special_allowance: float = 0
    other_allowances: dict[str, float] = Field(default_factory=dict)
    bonus: float = Field(0, validation_alias=AliasChoices("bonus", "variablePay", "variable_pay"))
    employer_pf: float | None = Field(None, validation_alias=AliasChoices("employer_pf", "employerPF", "employerPf"))
    pf_on_full_basic: bool = True
    gratuity: float | None = None
    professional_tax: float = 0
    deductions_claimed: dict[str, float] = Field(default_factory=dict)
    rent_paid: float | None = None
    is_metro: bool = False
    ctc_total: float | None = None
    one_time_components: dict[str, float] = Field(default_factory=dict)

    dearness_allowance: float = 0

    lta_received: float = 0
    lta_exemption_claimed: float = 0

    employer_nps: float | None = Field(None, validation_alias=AliasChoices("employer_nps", "superannuation",
                                                                            "employerNPS", "employerNps"))

    health_insurance_premium: float = 0

    transport_deduction: float = 0

    retention_bonus: float = 0
    sales_commission: float = Field(0, validation_alias=AliasChoices("sales_commission", "salesCommission",
                                                                      "incentives"))
    variable_pay_frequency: Literal["monthly", "quarterly", "annually"] | None = None

    equity_type: Literal["ESOP", "RSU", "ESPP"] | None = None
    equity_grant_value: float | None = None
    equity_unit_count: float | None = None
    equity_vesting_schedule: str | None = None
    equity_cliff_period_months: float | None = None

    gratuity_clause_present: bool = True
    notice_period_days: float | None = None
    has_service_bond: bool = False
    joining_bonus_has_clawback: bool = False
    joining_bonus_clawback_period_months: float | None = None


class ParseFieldsRequest(BaseModel):
    fields: dict[str, Any]


class BreakdownRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    ctc_breakup: CTCBreakup
    regime: Literal["old", "new"] = "new"
    fy: str | None = None


class RegimeComparisonRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    gross_salary: float
    deductions_claimed: dict[str, float] = Field(default_factory=dict)
    basic: float | None = Field(None, description="Needed only if rent_paid is given, to derive HRA exemption")
    hra_received: float | None = None
    rent_paid: float | None = None
    is_metro: bool = False
    fy: str | None = None


class WaterfallRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    ctc_breakup: CTCBreakup
    regime: Literal["old", "new"] = "new"
    fy: str | None = None


class ClassifyRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    ctc_breakup: CTCBreakup
    regime: Literal["old", "new"] = "new"
    fy: str | None = None


class QualityScoreRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    ctc_breakup: CTCBreakup
    regime: Literal["old", "new"] = "new"
    fy: str | None = None


class OfferInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    label: str = "Offer"
    ctc_breakup: CTCBreakup
    regime: Literal["old", "new"] = "new"


class CompareOffersRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    offer_a: OfferInput
    offer_b: OfferInput
    fy: str | None = None


class TimelineRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    joining_date: str = Field(description="ISO date (YYYY-MM-DD) the employee joined/will join")
    as_of_date: str | None = Field(None, description="ISO date to evaluate tenure at; defaults to today")
    separation_date: str | None = Field(
        None, description="ISO date of resignation/termination, if evaluating an exit rather than the present"
    )
    fy: str | None = None
