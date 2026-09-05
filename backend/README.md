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

## What every number carries

Every deduction, tax bracket, HRA limb, and red flag in a response
carries a `rule_id` pointing at `GET /rule/:rule_id`, so the frontend and
`generate_explanation` (AI-side) never have to invent a rule description
— they look it up.
