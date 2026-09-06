# Person 5 — Budgeting, Integration & Demo Ownership

This folder is a contribution record for grading/review, not a separate
build — the actual working code lives in the main tree (`frontend/`,
`backend/`, `docs/`, `scripts/`) so the app keeps running for the rest of
the team. Everything below either points at the shared files that were
edited, or is copied here from a standalone file that already lives
elsewhere in the repo (noted per item).

## Role brief

- Build the spendable-money inputs: rent, EMI, insurance, food, transport, other recurring costs.
- Calculate monthly disposable money from the backend's in-hand output.
- Display a simple "salary → deductions → essentials → spendable amount" flow.
- Connect every frontend page and ensure navigation feels like one product.
- Maintain demo data and make sure all three sample offers work reliably.
- Write the 2-minute demo script and pitch deck.
- Run full end-to-end tests at hours 14, 24, and 32.
- Own final bug triage: fix demo-breaking issues first; reject new features after hour 30.

## What was built, and where

### 1. Budgeting: salary → deductions → essentials → spendable

Lives in the shared frontend files:

- `frontend/index.html:139-193` — the "Your monthly spendable money" panel:
  6 recurring-cost inputs (rent, EMI, insurance, food, transport, other)
  and the flow display (salary → deductions note → in-hand → essentials
  note → spendable, with an overspending warning).
- `frontend/app.js:493-522` — `essentialsTotal()` and `updateBudget()`.
  Essentials are plain user-entered numbers, not backend tax/PF output, so
  this is the one place in the frontend that computes a rupee figure
  itself — everything upstream of "in-hand" still comes verbatim from
  `POST /breakdown`.
- `frontend/styles.css` — `.budget`, `.budget-flow`, `.flow-step` etc.,
  matching the existing neumorphic/glass design tokens.

### 2. City → metro/non-metro classification

Replaced the old binary metro/non-metro dropdown with a free-text city
field, since picking "metro" or "non-metro" directly requires already
knowing the HRA rule.

- `frontend/index.html:57-72` — the `city_name` text input (with a
  `<datalist>` of common Indian cities for autocomplete) and a live
  classification hint element.
- `frontend/app.js:74-109` — `METRO_CITIES` / `classifyCity()` (handles
  common aliases: Bombay, Calcutta, Madras, New Delhi) and
  `updateCityHint()`, which shows the classification inline as the person
  types rather than deciding it silently.
- `frontend/app.js:149` — `buildPayload()` now derives `is_metro` from the
  typed city name instead of a stored dropdown value.

### 3. Sample offers (demo reliability)

- **Canonical data**: `backend/data/sample_offers.json` (not duplicated
  here — see the copy below, which is read-only reference).
- **Frontend wiring**: `frontend/app.js:421-491` (`SAMPLE_OFFERS`,
  `loadSample()`) and `frontend/index.html:29-34` (the three sample-chip
  buttons: Clean offer / Red-flag offer / Senior, old regime).
- Three offers were designed to each prove something specific:

  | Sample | Regime | Red flags | Proves |
  |---|---|---|---|
  | Clean offer | New | 0 | Baseline breakdown + audit trail |
  | Red-flag offer | New | 7 (all at once) | Red-flag detection — the headline differentiator |
  | Senior, old regime | Old | 0 | HRA exemption + 80C/80D + budgeting flow |

  All three were verified against a live `uvicorn` instance of
  `backend/app/main.py`, not just read through — see `e2e_smoke.py` below.

### 4. End-to-end test harness

- **Canonical script**: `scripts/e2e_smoke.py` (repo root) — hits
  `/completeness-scope`, `/rule/:id`, and `POST /breakdown` for all three
  sample offers, asserting exact expected `in_hand_monthly`,
  `red_flag_count`, and (for the senior offer) `hra_exemption_amount`.
  Run it before every demo checkpoint (hours 14, 24, 32):

  ```
  cd backend && uvicorn app.main:app --reload   # terminal 1
  python scripts/e2e_smoke.py                    # terminal 2, from repo root
  ```

  Last run: **17/17 checks passed** (backend: 31/31 pytest also passing).
- A copy is included in this folder (`e2e_smoke.py`) for review — it will
  not resolve its data-file path correctly if run from here; run the
  original at the repo root.

### 5. Demo script

- **Canonical**: `docs/demo-script.md` — a beat-by-beat 2-minute walkthrough
  scripted around the three sample offers, plus a fallback plan if the
  backend goes down mid-demo. Copied here as `demo-script.md` for review.

## Files in this folder

- `README.md` — this file.
- `sample_offers.json` — read-only copy of `backend/data/sample_offers.json`.
- `e2e_smoke.py` — read-only copy of `scripts/e2e_smoke.py` (run the original, not this one).
- `demo-script.md` — read-only copy of `docs/demo-script.md`.
