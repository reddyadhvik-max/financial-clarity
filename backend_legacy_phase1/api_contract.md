# Financial Clarity — API Contract (Phase 1)

Contract between UI ↔ backend ↔ AI orchestrator. Locked here so roles 3/4 (AI) can build against it in Phase 2 without waiting on backend internals.

## POST /api/v1/breakdown

Deterministic calculation only — no LLM call happens inside this endpoint.

### Request

```json
{
  "input_source": "manual",            // "manual" | "parsed" (Phase 3)
  "fy_id": "FY2024-25",
  "regime": "new",                     // "old" | "new"
  "ctc_annual": 1200000,
  "basic_pct": 40,
  "hra_pct": 20,
  "city_class": "metro",               // "metro" | "non_metro"
  "other_allowances_annual": 0,
  "declared_deductions": {             // only relevant for "old" regime
    "80C": 0,
    "80D": 0
  }
}
```

### Response

```json
{
  "fy_id": "FY2024-25",
  "regime": "new",
  "in_hand_monthly": 83500,
  "line_items": [
    {
      "label": "Basic",
      "amount_annual": 480000,
      "rule_id": "FY24-25-basic-from-ctc"
    },
    {
      "label": "HRA",
      "amount_annual": 240000,
      "rule_id": "FY24-25-hra-metro"
    },
    {
      "label": "PF (employee)",
      "amount_annual": 57600,
      "rule_id": "FY24-25-epf-employee-pct"
    },
    {
      "label": "Income Tax",
      "amount_annual": 62400,
      "rule_id": "FY24-25-new-slab-2"
    }
  ],
  "completeness": {
    "score_pct": 100,
    "assumed_fields": []
  }
}
```

Every `line_items[].rule_id` must resolve to a row in `rule_schema.sql`. This is what the Phase 3 audit-trail UI clicks through to.

## POST /api/v1/explain

Called by the AI orchestrator's `generate_explanation` tool, not directly by the UI. Takes the `/breakdown` response and produces natural-language text — no arithmetic happens here either, it only narrates numbers already computed.

### Request
```json
{ "breakdown": { /* same shape as /breakdown response */ } }
```

### Response
```json
{ "explanation": "In the new regime, you pay less tax because..." }
```

## POST /api/v1/parse-offer-letter (stubbed until Phase 3)

### Request
`multipart/form-data`: file upload (PDF).

### Response
```json
{
  "fields": {
    "ctc_annual": { "value": 1200000, "confidence": 0.92 },
    "basic_pct":  { "value": 40, "confidence": 0.65 },
    "hra_pct":    { "value": null, "confidence": 0.0 }
  },
  "needs_clarification": ["hra_pct"]
}
```

A `confidence` below a threshold (e.g. 0.7) or a `null` value puts that field into `needs_clarification` — this is what triggers the orchestrator's ask-the-user branch (see `ai/architecture.md`) instead of guessing.

## Versioning rule
`fy_id` is required on every request touching `/breakdown` or `/parse-offer-letter`. The backend never infers "current FY" implicitly — the UI/orchestrator must pass it explicitly, so rule lookups stay traceable to a specific rule table snapshot.
