# Phase 1 — AI/Agentic

## What we built
`ai/architecture.md`: orchestrator flow diagram, the five agent tools (`parse_offer_letter`, `lookup_rule`, `compute_breakdown`, `generate_explanation`, `flag_completeness`), and the single real branch point — low parser confidence (<0.7) or a missing field routes to asking the user instead of guessing.

## Why
This is the design-only scope the team split assigns to Phase 1 for roles 3/4 — deliberately not building yet, since the tools depend on the backend contract (`backend/api_contract.md`) that was only locked in this same phase. Documenting the clarification branch now, before code, is what lets us claim at Round 1 that the "agentic" part of the system is a real decision point and not just a marketing label on an LLM call.

## What we explicitly did not do, and why
- No tool has real logic — `compute_breakdown` and `generate_explanation` are contract-only until Phase 2 wires them to the actual `/breakdown` and `/explain` endpoints.
- `parse_offer_letter`'s confidence-scoring model isn't chosen yet — real PDF parsing is Phase 3 scope, sequenced after the manual-entry path proves the backend contract works end-to-end in Phase 2.
- `flag_completeness` logic (the threshold check itself) isn't implemented — flagged as the simplest tool and a fallback candidate for role 5 if the team is short an agent-logic person, per the plan's team notes.
