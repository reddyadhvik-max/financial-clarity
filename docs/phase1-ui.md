# Phase 1 — UI/UX

## What we built
A low-fi text/box wireframe (`frontend/wireframe.md`) covering the single flow: upload/manual-entry screen → breakdown screen (numbers + rule tags + completeness indicator + regime toggle). No real components, no styling, no working code.

## Why
Round 1 checks concept clarity, not code volume. The wireframe proves the flow is scoped to one coherent path (not a scattered feature list) and shows two judging-relevant elements already placed in the layout: the completeness indicator and the per-number rule tag (audit trail) — both differentiators called out for Phase 3.

## What we explicitly did not do, and why
- No real UI framework/components built yet — Phase 2 builds the actual breakdown screen for manual entry only.
- Upload box is decorative, not wired — PDF parsing doesn't exist until Phase 3 (`parse_offer_letter`).
- Audit-trail click interaction and live confidence scoring are static placeholders — real interactivity is a Phase 3 deliverable, not attempted early since it depends on backend rule-id metadata (Phase 3) and parser confidence scores (Phase 3) that don't exist yet.
