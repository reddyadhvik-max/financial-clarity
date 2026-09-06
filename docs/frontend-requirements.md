# Financial Clarity — Frontend Requirements

This is the contract the frontend builds against. It does not prescribe visual
design (that's the frontend owner's call) — it lists every section the UI
needs, the exact data each section consumes, and where that data comes from.
The existing `frontend/` folder (manual-entry form + neumorphic styling) is a
reference implementation of most of this and can be reused, restyled, or
replaced — the backend contract below is what actually has to be honored.

**Backend base URL** (local dev): `http://127.0.0.1:8000`, started via
`uvicorn app.main:app --reload` from `backend/`. No auth, CORS is open
(`allow_origins=["*"]`), so the frontend can be a static page served from
anywhere during development.

**Core rule that shapes every screen**: the frontend never computes a rupee
value itself. Every number on screen comes from a backend response field, and
every number should be able to answer "why?" by looking up its `rule_id` via
`GET /rule/{rule_id}`.

---

## 1. Offer Input screen

Two entry paths into the same downstream flow:

- **Manual entry** (already built in the reference frontend) — a form for
  `basic`, `hra`, `special_allowance`, `bonus`, `employer_pf`, city
  (`is_metro`), tax regime, and old-regime-only fields (`rent_paid`,
  80C/80D). See `frontend/index.html` for the existing field set — reuse it.
- **Offer-letter upload** (PDF/text) — **not implemented yet**, blocked on
  the AI parsing agent (`POST /parse-offer-letter`, in progress — see
  `ai/architecture.md`). Build the UI slot for it now (an upload dropzone /
  tab next to manual entry) but treat the actual parse call as a stub or
  feature-flagged-off section until that endpoint exists. When it lands, the
  response will include structured `CTCBreakup` fields **plus a per-field
  confidence score**, which feeds section 5 below.

Regardless of entry path, the frontend ends up with a `CTCBreakup` object and
a `regime` ("old" | "new") to send to `POST /breakdown`.

## 2. Breakdown / Ledger screen

Calls `POST /breakdown` with `{ ctc_breakup, regime, fy? }`. Response shape:

```jsonc
{
  "breakdown": {
    "regime": "new",
    "ctc_total": 800000,
    "gross_salary_annual": 700000,
    "gross_salary_monthly": 58333.33,
    "taxable_income": 625000,
    "std_deduction_rule_id": "STD_DEDUCTION_NEW",
    "std_deduction_amount": 75000,
    "hra_exemption_amount": 0,
    "deductions": [
      { "name": "Employee PF (EPF)", "rule_id": "PF_EMPLOYEE_RATE", "amount": 48000, "frequency": "annual" },
      { "name": "Income Tax (TDS)", "rule_id": "NEW_REGIME_SLABS", "amount": 20800, "frequency": "annual" }
      // ...one entry per deduction actually applied; count and order vary
    ],
    "total_deductions_annual": 68800,
    "in_hand_annual": 631200,
    "in_hand_monthly": 52600.0,
    "employer_side": {
      "employer_pf": { "amount": 48000, "rule_id": "PF_EMPLOYER_RATE" },
      "employer_esi": { "amount": 0, "rule_id": null },
      "gratuity_provision": { "amount": 23076.92, "rule_id": "GRATUITY_FACTOR" }
    },
    "esi_eligible": false,
    "tax_breakdown": {
      "regime": "new", "taxable_income": 625000,
      "tax_before_rebate": 20800, "brackets": [ /* see §4b */ ],
      "rebate_rule_id": "NEW_REGIME_REBATE_87A", "rebate_amount": 0,
      "tax_after_rebate": 20800,
      "cess_rule_id": "CESS_RATE", "cess_amount": 832, "total_tax": 21632
    }
  },
  "red_flags": [ /* see §6 */ ]
}
```

Required UI elements:
- **Headline number**: `in_hand_monthly` (and/or annual) — the single most
  prominent figure on the screen.
- **Ledger table**: one row per `deductions[]` entry (label + signed amount),
  plus `gross_salary_annual`, `std_deduction_amount`, `hra_exemption_amount`
  (only if > 0), and `in_hand_annual` as a final emphasized row.
- **Audit-trail "why?" affordance** on every row that carries a `rule_id`:
  clicking it calls `GET /rule/{rule_id}?fy=...` and shows the rule's
  `description`, `value`, and `source` inline. This is a named differentiator
  in the pitch deck — don't treat it as optional polish.
- **Employer-side breakdown** (`employer_side`) shown separately from the
  employee ledger — it's part of `ctc_total` but never subtracted from
  in-hand pay; keep it visually distinct so users don't double-count it.
- **422 handling**: a `POST /breakdown` that fails validation returns
  `{ "valid": false, "missing_fields": [...], "malformed_fields": {...} }`
  with HTTP 422 — surface these as inline field errors, not a generic
  failure message.

## 3. Regime Comparison screen — not yet in the reference frontend

Calls `POST /regime-comparison` with
`{ gross_salary, deductions_claimed?, basic?, hra_received?, rent_paid?, is_metro?, fy? }`.
Response:

```jsonc
{
  "gross_salary": 700000,
  "old_regime_tax": { /* same shape as tax_breakdown above, regime: "old" */ },
  "new_regime_tax": { /* same shape, regime: "new" */ },
  "recommended": "new",
  "annual_savings_with_recommended": 12500,
  "per_deduction_impact": [
    { "name": "Section 80C", "rule_id": "CAP_80C", "claimed_amount": 150000,
      "tax_saved": 31200, "applies_to": "old_regime" }
    // present only for deductions actually claimed (HRA / 80C / 80D)
  ],
  "hra_exemption_detail": { /* only present if rent_paid was supplied — see §4a */ }
}
```

UI needs:
- A clear **recommended regime** callout with `annual_savings_with_recommended`.
- Side-by-side old vs new totals (`total_tax` from each `*_regime_tax` object).
- A list of `per_deduction_impact` showing what each claimed deduction is
  worth in tax saved — this is the natural place for a bar chart (§4c).

## 4. Visualizations (explicit requirement — this project needs real charts, not just tables)

All chart data below is already present in the two response bodies above —
no new backend endpoint is required for any of these.

**a. Salary Composition chart** (donut or stacked bar)
Segments: `basic`, `hra`, `special_allowance`, `bonus`, and each key in
`other_allowances` (from the request payload, not the response — echo back
what the user entered) — should sum to `gross_salary_annual`.

**b. CTC → In-Hand bridge / waterfall chart**
Steps, left to right: `ctc_total` → minus employer-side add-ons
(`employer_side.employer_pf`, `employer_esi`, `gratuity_provision`) → 
`gross_salary_annual` → minus each `deductions[]` entry → `in_hand_annual`.
This is the single most important chart in the product — it's the visual
answer to "where did my CTC actually go."

**c. Old vs New Regime comparison chart** (grouped/side-by-side bar)
Bars per regime: `tax_before_rebate`, `rebate_amount` (as a reduction),
`cess_amount`, `total_tax`. Pair with the `per_deduction_impact` list as a
secondary bar chart ("tax saved per deduction") when regime is old or being
compared.

**d. Tax slab / bracket ladder chart**
From `tax_breakdown.brackets` (or `old_regime_tax.brackets` /
`new_regime_tax.brackets`): each bracket has `min`, `max`, `rate`,
`taxable_amount_in_bracket`, `tax_in_bracket`. Render as a stacked/segmented
bar showing how much income falls in each slab and how much tax each slab
contributes — this is what makes "why is my tax X" self-evident without
reading a paragraph.

**e. Completeness indicator**
Not a chart — a simple two-column disclosure (already built: `GET
/completeness-scope` returns `{ covered: string[], not_covered: string[] }`).
Keep it visible, not buried, per the "judge-proof" pitch angle: this tool is
explicit about its own limits.

**f. Red-flags panel**
List, not a chart — see §6. A severity-colored badge list is sufficient; a
chart would overstate 3-5 boolean-ish findings.

## 5. Confidence / clarification states (depends on AI parsing — build the UI shell now)

Once `parse_offer_letter` exists, parsed fields will carry a confidence score
per field. Any field below the (planned) 0.7 threshold — or missing
entirely — must be presented to the user as **"please confirm or correct
this"**, pre-filled with the parsed guess but editable, rather than silently
accepted. Design this now as a visual state on the manual-entry fields
(e.g., an amber outline + inline confidence note) so it can be wired to real
data without a redesign later.

## 6. Red flags

`red_flags[]` inside the `/breakdown` response, e.g.:

```jsonc
{ "flag_id": "MISSING_PF", "severity": "critical", "rule_id": "PF_EMPLOYER_RATE",
  "field": "employer_pf",
  "message": "No employer PF contribution found in the offer. EPF is mandatory..." }
```

`severity` is one of `critical` | `warning` | `info` — map each to a distinct
color/icon. `rule_id` may be `null` for flags that aren't rule-derived
(service bond, joining-bonus clawback) — don't assume it's always present.

## 7. Global UI states

- **Loading** — while any POST/GET is in flight (disable the trigger control,
  show a lightweight in-progress indicator).
- **Backend unreachable** — network failure on any call; show a clear message
  with the configured API base URL and the exact command to start it
  (`uvicorn app.main:app --reload`), not a generic error.
- **Empty state** — before the first breakdown is requested.
- **Live recompute** — the reference frontend recomputes on every field edit
  once a result already exists (debounced ~450ms) and marks changed ledger
  rows with a delta badge; keep this pattern, it's a good UX.

## 8. Non-goals (mirror `GET /completeness-scope`, do not silently imply more)

Capital gains, other income sources, multiple employers/Form 12B, surcharge
and marginal relief, Sections 24(b)/80CCD(1B)/80E, employer NPS 80CCD(2),
state Professional Tax slabs, perquisite valuation, senior-citizen slabs,
Section 89 relief. If the UI ever implies a number covers these, that's a bug.

## 9. Roadmap features to leave room for (not built yet, don't block on them)

See `financial-clarity-implementation-plan (1).md`'s "Post-MVP roadmap" for
full detail — Multi-Offer Comparison, Tax-Saving What-If Sliders, and a
Localized Purchasing-Power Index are planned but not scoped for this build.
Worth keeping the layout flexible enough that a second offer, a slider panel,
or a city-adjustment factor could slot in later without a rewrite — but do
not build UI for these now.
