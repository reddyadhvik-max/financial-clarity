# Offer Decoder — Backend

FY 2025-26 India CTC/in-hand/tax-regime calculation backend. No LLM in the
calculation path — the AI layer only parses PDFs into structured fields
(`POST /parse-fields`) and turns rule text (`GET /rule/:rule_id`) into
plain-language explanations.

## Layout

- `data/rules.json` — versioned rule data (rate, cap, slab, threshold),
  keyed by `(rule_id, fy)`. Never hardcode a number in `app/engine.py`;
  add or look up a rule here instead.
- `app/rules.py` — rule loader/accessor.
- `app/engine.py` — pure calculation functions: `compute_in_hand`,
  `compute_regime_comparison`, `detect_red_flags`, plus shared helpers
  (`slab_tax`, `compute_tax_for_regime`, `compute_hra_exemption`).
- `app/validation.py` — rejects/flags incomplete or malformed CTC input
  before it reaches the engine.
- `app/schemas.py` — Pydantic request models.
- `app/main.py` — FastAPI endpoints.
- `tests/` — hand-verified numeric assertions for the engine, plus API
  and validation tests.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Test

```bash
pytest -q
```

## Endpoints

- `POST /parse-fields` — validate agent-parsed structured fields.
  `422` with `{"missing_fields": [...], "malformed_fields": {...}}` on
  failure (this is what should trigger the agent's clarification branch).
- `POST /breakdown` — validated CTC breakup → `compute_in_hand()` +
  `detect_red_flags()`.
- `POST /regime-comparison` — income + claimed deductions →
  `compute_regime_comparison()`.
- `GET /rule/:rule_id?fy=2025-26` — human-readable rule text (powers the
  audit-trail click-through; `fy` defaults to the current FY).
- `GET /completeness-scope` — static list of what is/isn't modelled
  (feeds the completeness indicator).
- `GET /meta` — current FY + ruleset version (rule-version awareness).
- `POST /waterfall` — CTC breakup → ordered CTC-to-in-hand waterfall steps,
  each still carrying a `rule_id`.
- `POST /classify` — CTC breakup → Fixed / Employer Contributions /
  Variable / One-time buckets.
- `POST /quality-score` — CTC breakup → a transparent 0-100 Compensation
  Quality Score with four weighted, rule-versioned sub-scores.
- `POST /compare-offers` — two labelled offers → per-offer breakdown plus
  cashflow/total-comp deltas.
- `POST /gratuity-epf-timeline` — joining/as-of/separation dates → gratuity
  vesting status (or payable/forfeited outcome, if `separationDate` is
  given), EPF tax-free-withdrawal eligibility, and a 4-point milestone
  timeline (join → gratuity vesting → EPF tax-free → EPS pension
  eligibility), each tied to a versioned rule.
- `GET /sample-offers` — 3 fixed, hand-built sample offers (fresher/clean,
  mid-level/bonus-heavy with red flags, senior/old-regime) for the rest of
  the team to build and demo against before offer-letter parsing exists.
  Each `ctc_breakup` is a valid `/breakdown` (etc.) request body as-is.

## Shared schema — locked

`CTCBreakup` (`app/schemas.py`) is the one shared salary schema every
endpoint above nests under `ctc_breakup`. Field names are snake_case
internally, but **every request model also accepts camelCase** (e.g.
`specialAllowance`, `variablePay`, `employerPF`) via a Pydantic alias
generator — send whichever style your part of the app already uses; both
land on the same field. `basic` and `hra` are the only required fields;
everything else defaults to 0/empty/computed.

Core fields: `basic`, `hra`, `special_allowance`, `other_allowances`
(dict), `bonus` (= "variable pay"), `employer_pf` (omit to let the engine
compute it), `gratuity` (omit to let the engine compute it),
`deductions_claimed` (`{"80C": ..., "80D": ...}`, old regime only),
`rent_paid` + `is_metro` (HRA exemption, old regime only),
`one_time_components` (dict — joining bonus, relocation; excluded from
the recurring CTC total, since they're one-off payments outside it).

Extended fields (all optional, default 0/None):
- `dearness_allowance` — folded into the statutory "Basic + DA" base used
  for PF, gratuity, and the HRA exemption (not just Basic).
- `lta_received` (cash, taxable) + `lta_exemption_claimed` (capped at
  `lta_received`, exempt under the old regime only).
- `employer_nps` (alias `superannuation`) — deductible under Section
  80CCD(2) in **both** regimes, capped at 10% of Basic+DA
  (`NPS_80CCD2_CAP_PCT`); the contribution itself is a CTC cost, not cash
  paid to the employee.
- `health_insurance_premium` — employer-paid group cover; a CTC cost only,
  never part of gross salary or taxable income.
- `transport_deduction` — cash deducted from pay for a company transport
  facility; reduces take-home like professional tax, but isn't a tax rule.
- `retention_bonus`, `sales_commission` (alias `incentives`) — additional
  variable-pay components, taxed and classified the same as `bonus`.
- `variable_pay_frequency` (`monthly`/`quarterly`/`annually`) — informational;
  if not `monthly`, the breakdown response includes a `variable_pay_note`
  warning that the monthly in-hand figure is an annual average, not what
  lands in any single month.
- `joining_bonus_clawback_period_months` — surfaced in the
  `JOINING_BONUS_CLAWBACK` red flag's message when given.
- `equity_type` (`ESOP`/`RSU`/`ESPP`), `equity_grant_value`,
  `equity_unit_count`, `equity_vesting_schedule`, `equity_cliff_period_months`
  — accepted and echoed back verbatim under an `equity` key in the
  breakdown response and as their own bucket in `/classify`. **Not valued,
  vested, or taxed** — this is a deliberate stub, not a bug; see
  `/completeness-scope`.

## What every number carries

Every deduction, tax bracket, HRA limb, and red flag in a response
carries a `rule_id` pointing at `GET /rule/:rule_id`, so the frontend and
`generate_explanation` (AI-side) never have to invent a rule description
— they look it up.
