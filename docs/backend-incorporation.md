# Backend Incorporation Note (2026-09-05)

## What happened
`WEHACK.zip` appeared on Desktop containing a complete, working FastAPI backend ("Offer Decoder") for this exact project — CTC breakdown, PF/ESI, HRA exemption, old-vs-new regime comparison, and offer red-flag detection, with a full `pytest` suite. This is teammate work (built via the Antigravity CLI connection through omniroute), well ahead of the Phase 1 backend scaffolding drafted here.

## What changed
- Original Phase 1 stub (`backend/rule_schema.sql`, `backend/api_contract.md`) moved to `backend_legacy_phase1/` — kept for reference, no longer the active contract.
- `backend/` now contains the real code: `app/engine.py` (pure calc functions), `app/rules.py` (rule loader over `data/rules.json`), `app/validation.py`, `app/schemas.py` (Pydantic models), `app/main.py` (FastAPI routes), and `tests/`.
- `ai/architecture.md` updated to call the real endpoints (`POST /parse-fields`, `POST /breakdown`, `POST /regime-comparison`, `GET /rule/{rule_id}`, `GET /completeness-scope`) instead of the placeholder `/api/v1/*` contract.

## Real backend scope, vs. the plan's phase gates
The `WEHACK` backend already covers most of what Phases 2-3 called for: a working manual-entry calc endpoint (Phase 2 goal), full old-vs-new regime comparison and validation (Phase 3 goal), plus red-flag detection that wasn't in the original plan at all. It is missing:
- `parse_offer_letter` (PDF → structured fields) — still the AI team's job; the backend only validates already-structured fields via `/parse-fields`.
- `generate_explanation` — still the AI team's job; the backend deliberately stays silent on prose, only exposing `GET /rule/:id` for the agent to cite.

## Not yet verified
No Python interpreter is available on this machine, so `pytest -q` has not actually been run here — the test files exist and look sound on read-through, but pass/fail status is unconfirmed. Recommend running `pip install -r backend/requirements.txt && pytest -q` on a machine with Python before relying on this as "tested" for a judging round.

## Practical effect on the plan
Since the backend is largely done, the team can pull forward AI-side work (wiring `compute_breakdown`/`compute_regime_comparison`/`generate_explanation` against the real endpoints) into whatever the next working session is, rather than waiting for a Phase 2 backend build step that's now mostly redundant. Frontend can also start building the real breakdown screen against real responses instead of mocked data.
