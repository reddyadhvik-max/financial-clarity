# Offer Letter Data Parser (Person 4 — Data Parser)

A resilient, multi-layer parsing engine that extracts, normalizes, and
validates compensation data (CTC breakdowns) from offer letters — raw text,
structured PDFs, or scanned images — and holds the result in a per-session,
in-memory store for lookup, filtering, and multi-offer comparison.
**Nothing is ever written to disk**: offer letters carry real compensation
data, and data from one upload session must not survive — or leak into —
another. See "Session-scoped storage" below.

This is a standalone module inside the `financial-clarity` monorepo (its own
`requirements.txt`, its own FastAPI service on its own port), separate from
the main Offer Decoder backend in `../backend`. Named `person4-data-parser`
on disk rather than the literal "person 4 (data parser)" — spaces and
parentheses in a folder name cause friction with `python -m`, imports, and
shell quoting on Windows, so it's spelled out here in the README instead.

## Why it isn't a fragile regex script

Real offer letters vary wildly in formatting — some spell everything out in
prose, some put the actual numbers in an Annexure table, some are scanned
images with no text layer at all, and every company has its own shorthand
for the same concept ("PF" vs "Employer's PF Contribution" vs "EPF"). A
single regex pass breaks the moment the format changes. This parser layers
four independent strategies and always tells you *how confident* it is in
each answer, rather than presenting a guess as a fact:

1. **Input tolerance** (`extractors.py`) — routes raw text, a text-layer PDF
   (via `pdfplumber`), or a scanned PDF/image (OCR fallback via
   `pytesseract`, when installed) all into the same plain-text + tables
   representation, then sanitizes it (`sanitize.py`: strips zero-width
   characters, normalizes smart quotes/dashes, fixes hyphenated line-wraps).
2. **Layer 1 — spatial/tabular** (`tabular.py`) — reads a real Annexure-style
   table (Component | Monthly | Annual) straight from `pdfplumber`'s table
   extraction. Strongest signal; always tagged `"found"`.
3. **Layer 2 — strict label regex** (`patterns.py`) — matches a field's known
   label (and its company-specific acronyms, from `schema.py`'s alias list)
   immediately adjacent to a value, on a **word boundary** (so "DA" never
   matches inside "Date").
4. **Layer 3 — loose fallback** (`patterns.py`) — the label appears
   somewhere in the same line/clause as a value, without a tight adjacency.
   Always tagged `"estimated"`, never `"found"`.
5. **Layer 4 — payroll-rule estimation** (`confidence.py`) — a small set of
   fields can be *derived* rather than guessed: e.g. Basic Pay from a stated
   Employer PF (statutory 12% rate), or Gross Pay from CTC minus retirals.
   Also tagged `"estimated"`, with the formula recorded as evidence.

Every field that isn't found by any of the above is `null` and tagged
`"missing"` — **never coerced to 0**. A missing Employer PF is a different
fact than a stated zero, and treating them the same would hide a real red
flag.

## Categorized output schema

Every parse returns one JSON object:

```jsonc
{
  "metadata": { "company_name": ..., "employee_name": ..., "designation": ..., "joining_date": ... },
  "fields": {
    "top_line":   { "total_ctc": {...}, "total_gross_pay": {...}, "target_net_pay": {...} },
    "fixed":      { "basic_pay": {...}, "hra": {...}, "special_allowance": {...}, "lta": {...}, "da": {...} },
    "retirals":   { "employer_pf": {...}, "gratuity": {...}, "superannuation_nps": {...} },
    "variable":   { "target_bonus": {...}, "variable_pay_frequency": {...}, "sales_commission": {...} },
    "one_time":   { "joining_bonus": {...}, "joining_bonus_clawback_months": {...}, "relocation_allowance": {...},
                    "retention_bonus": {...}, "equity_type": {...}, "equity_grant_value": {...},
                    "equity_unit_count": {...}, "equity_vesting_schedule": {...}, "equity_cliff_months": {...} },
    "deductions": { "health_insurance_premium": {...}, "food_meal_allowance": {...},
                    "internet_phone_reimbursement": {...}, "cab_transport_deduction": {...} }
  },
  "derived": { "fixed_total": {...}, "retirals_total": {...}, "variable_total": {...},
               "one_time_total": {...}, "deductions_total": {...}, "top_line_total": {...} },
  "checksum": { "checked": true, "total_ctc": 1800000.0, "component_sum": 1741015.0,
                "difference": -58985.0, "difference_pct": 3.28, "within_tolerance": true },
  "red_flags": [ { "flag_id": "...", "severity": "critical|warning|info", "field": "...", "message": "..." } ],
  "used_ocr": false,
  "warnings": []
}
```

Every leaf field is `{"value": ..., "confidence_tier": "found"|"estimated"|"missing", "evidence": "..."}`.
This is the real, verified output of `tests/sample_offer_letter.txt` — not a hypothetical example
(see `tests/test_parser.py`, which asserts against it directly).

**Acronyms/shortforms recognized** (see `schema.py::ALIASES` for the full list —
this is a sample, not the complete set): `CTC` (Cost to Company), `HRA`
(House Rent Allowance), `LTA` (Leave Travel Allowance), `DA` (Dearness
Allowance), `PF`/`EPF` (Provident Fund), `NPS` (National Pension Scheme),
`ESOP`/`RSU`/`ESPP` (equity types), `GMP` (Guaranteed Monthly Pay).

## Red-flag / anomaly detection (`redflags.py`)

Runs after extraction, over the final parsed JSON:

- **`HIGH_VARIABLE_PAY`** — variable pay (target bonus + sales commission) is >20% of Total CTC.
- **`ONE_TIME_PAYMENT_CLIFF`** — one-time payments (joining/retention bonus, relocation, equity) are >15% of CTC, implying a year-two compensation cliff.
- **`MISSING_GRATUITY_HIGH_VALUE`** — no gratuity found on an offer above ₹10L CTC.
- **`MISSING_EMPLOYER_PF`** — Basic Pay is stated but no Employer PF was found.
- **`CTC_CHECKSUM_MISMATCH`** — extracted components don't sum to the stated Total CTC within 5% tolerance.

## Multi-offer comparison (`compare.py`)

`compare_offers(result_a, result_b)` produces a field-by-field diff. **If one
offer states a field the other lacks, the missing side renders as the
literal string `"NA"`** — not `null`, not `0` — since this view is meant to
be read directly by a person comparing two offers. Each offer's own
`confidence_tier` is preserved alongside the `"NA"` marker, so "the field
was never found in this letter" stays distinguishable from "the field is
zero."

## Session-scoped storage (`storage.py` + `sessions.py`)

Storage is still plain SQLite — no server, no extra dependency — but it is
**native in-memory SQLite (`sqlite3.connect(":memory:")`), one connection per
upload session, never a file on disk.** `sessions.py`'s `SessionStore` is an
in-process registry mapping a `session_id` to its own private in-memory
connection. A session's data exists only as long as that connection is open;
it ends in exactly one of three ways, all of which permanently discard the
data (there is no file left over to clean up, because there was never one):

1. **Explicit close** — `DELETE /session` — call this when the user finishes
   their upload/comparison flow.
2. **Idle timeout** — 30 minutes of inactivity (`SESSION_IDLE_TIMEOUT_SECONDS`
   in `sessions.py`) and the session is evicted automatically.
3. **Process restart** — in-memory means in-memory; nothing survives the
   service stopping, by construction.

The API resolves sessions via an `X-Session-Id` header: omit it and a new
session is created and returned in the response header; pass it back on
later requests to keep working in the same session. Two different sessions
can never see each other's offers — `list_offers`/`get_offer` only ever see
rows in the connection they were given, and there's no shared table for a
different session's connection to accidentally query. Supports listing with
filters within a session: by company name, CTC range, or "show me every
offer still missing field X in category Y" — the checklist/filter capability
the product needs for the comparison UI.

**Not for durable retention.** If the team later wants offers to survive a
server restart or be shared across sessions, that's a deliberate product
decision to revisit (and would need explicit user consent to retain that
data) — it is not something to silently add back.

## Running the service

```bash
cd person4-data-parser
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt
uvicorn parser.api:app --reload --port 8100
```

Endpoints:

| Method | Path | What it does |
|---|---|---|
| GET | `/checklist` | Categorized list of every field this parser looks for, plus its known aliases — for a frontend "found vs. still need to check" UI. Not session-scoped (static schema data). |
| POST | `/session` | Explicitly starts a fresh session (optional — any other endpoint auto-creates one if you don't pass `X-Session-Id`). Returns `{"session_id": "..."}`. |
| DELETE | `/session` | Ends the session named by the `X-Session-Id` header immediately, discarding every offer parsed in it. |
| POST | `/parse/text` | `{"text": "...", "source_filename": "..."}` → parses, saves into the current session, returns the full result with an `offer_id` + `session_id`. |
| POST | `/parse/pdf` | Multipart file upload of a `.pdf` → same result shape. The uploaded PDF itself is written to a temp file only long enough to parse it, then deleted. |
| GET | `/offers` | List offers in the current session. Filters: `company_name`, `min_ctc`, `max_ctc`, `missing_field` (+ optional `category`). |
| GET | `/offers/{offer_id}` | Fetch one offer's full parsed result, if it exists in the current session. |
| POST | `/compare` | `{"offer_id_a", "offer_id_b", "label_a"?, "label_b"?}` → field-by-field comparison with `"NA"` for one-sided fields. Both offers must be in the current session. |

## Running the tests

```bash
cd person4-data-parser
pip install -r requirements.txt
python -m pytest tests/ -v
```

43 tests, all passing as of this writing — including several **regression
tests for real bugs caught while building this** (word-boundary matching so
"DA" doesn't match inside "Date"; a generic "incentive" alias that used to
misattribute an equity grant as sales commission; a table-column-header
"Monthly" that used to be misread as the bonus payout frequency). Those
tests exist specifically so nobody re-introduces the same bug later.

`tests/sample_offer_letter.txt` and `tests/sample_offer_letter.pdf` are
real fixtures — every expected value in the tests was checked against an
actual parser run first, not hand-derived and hoped to be correct. The PDF
fixture exercises the genuine `pdfplumber` text + table extraction path; it's
committed to the repo, so running the tests doesn't require regenerating it
(that only matters if you want to modify the fixture — see
`tests/generate_sample_pdf.py`, which needs `reportlab`, a test-fixture-only
dependency not listed in the main `requirements.txt`).

## OCR setup (optional — only needed for scanned/image-only PDFs)

`pytesseract` and `pdf2image` (both in `requirements.txt`) are Python
wrappers around external binaries that must be installed separately:

- **Tesseract OCR** — [installer for Windows](https://github.com/UB-Mannheim/tesseract/wiki); add it to PATH.
- **Poppler** (for `pdf2image` to rasterize PDF pages) — [Windows builds](https://github.com/oschwartz10612/poppler-windows); add `bin/` to PATH.

Without these, `extract_from_pdf()` still works fine for any PDF with a real
text layer — it only falls back to OCR when a PDF's text layer is
near-empty, and degrades gracefully (returns whatever it has plus a warning
in the `warnings` list) if OCR isn't available rather than crashing.

## Known limitations

- Regex/heuristic extraction, not a trained ML model — an offer letter with
  wildly unconventional phrasing may under-extract. That's why every field
  carries a confidence tier instead of silently trusting the result.
- OCR accuracy for scanned documents depends entirely on Tesseract and scan
  quality; this module doesn't attempt any image preprocessing (deskew,
  denoise) beyond what Tesseract does itself.
- The checksum/red-flag thresholds (5% tolerance, 20%/15% pay-mix
  thresholds, ₹10L "high value" cutoff) are reasonable defaults, not
  regulatory constants — tune them in `confidence.py`/`redflags.py` if the
  team wants different sensitivity.
- The session store is a single process's in-memory dict — it isn't shared
  across multiple `uvicorn` worker processes. Run this service with one
  worker; a session's data lives only in whichever process created it, by
  design (see `sessions.py`).
