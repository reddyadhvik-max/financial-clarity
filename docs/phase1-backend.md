# Phase 1 — Backend

## What we built
- `backend/rule_schema.sql`: versioned (by `fy_id`) rule tables — tax slabs (old/new regime), flat rules (standard deduction, rebate, cess, EPF %), HRA formula inputs by city class, and old-regime deduction categories (80C, 80D, etc.).
- `backend/api_contract.md`: locked request/response shapes for `/api/v1/breakdown`, `/api/v1/explain`, and `/api/v1/parse-offer-letter` (stub).

## Why
The core constraint is that the LLM never does arithmetic — every number in a `/breakdown` response carries a `rule_id` traceable to a schema row, which is what makes the audit-trail feature (Phase 3) and the explainability judging criterion possible at all. Locking the contract now, before any code, lets roles 3/4 (AI) build their orchestrator and tool stubs against a fixed shape in Phase 2 instead of guessing at backend internals.

## What we explicitly did not do, and why
- No calculation logic implemented yet — only the schema and contract. The actual CTC-to-in-hand endpoint is a Phase 2 deliverable (manual entry only).
- Only one FY's worth of rule data is modeled in the schema, not populated — seeding real FY2024-25 slab values happens when the endpoint is built in Phase 2, since seeding now with no consumer would be dead work.
- Old-regime deduction categories are schema'd but not wired into any calc yet — old-vs-new comparison is explicitly a Phase 3 feature (full rule table).
