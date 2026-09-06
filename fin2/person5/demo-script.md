# Financial Clarity — 2-Minute Demo Script

Owner: Person 5. Run `python scripts/e2e_smoke.py` against the live backend
right before presenting — if it fails, fix or fall back before you're on
stage, not during.

**Setup (before judges arrive):** backend running (`uvicorn app.main:app
--reload` from `backend/`), frontend open in a browser tab
(`frontend/index.html`, served or via `file://`), footer shows API status
"reachable". Have this doc off-screen for reference, not read aloud.

---

## 0:00 – 0:15 — The hook

> "Offer letters are written to be skimmed, not understood. We built
> Financial Clarity to read one straight: what actually lands in your
> account, and why — with every number traceable to the tax rule that
> produced it."

Click **"Clean offer"** (sample chip, left page).

## 0:15 – 0:45 — The breakdown, and the audit trail

Breakdown appears on the right: in-hand amount, ledger rows.

> "This is a completely ordinary offer — nothing wrong with it. Every row
> here came from our backend's tax engine, not a guess."

Click **"▸ why?"** next to the Income Tax row.

> "Click any number, and it tells you exactly which rule produced it —
> the actual slab, the actual section of the Income Tax Act. Nothing here
> is a black box."

## 0:45 – 1:15 — The red flags (the differentiator)

Click **"Red-flag offer"** sample chip.

> "Now here's an offer that looks fine on the surface — but watch what we
> catch."

Point to the "Worth a second look" panel — 7 flags fire at once (high
variable pay, low basic salary, missing PF, no gratuity clause, long notice
period, a service bond, and a joining-bonus clawback).

> "Seven things wrong with this offer, all caught automatically. Half of
> these, a candidate reading the PDF themselves would never notice — the
> missing PF contribution alone is a legal red flag most people wouldn't
> catch until their first payslip."

## 1:15 – 1:40 — Old regime, and spendable money

Click **"Senior, old regime"** sample chip.

> "It also handles the old tax regime — HRA exemption, 80C, 80D — and this
> is where it goes one step further than a tax calculator."

Scroll to **"Your monthly spendable money."** Type a rent figure (e.g.
₹25,000) into the budget inputs live.

> "We don't stop at in-hand pay. Add your actual monthly costs — rent, EMI,
> insurance, food, transport — and it shows you salary, deductions,
> essentials, and what's actually left to spend. That's the number people
> actually plan their life around, not the number on the offer letter."

## 1:40 – 2:00 — Close

> "Every figure on this page is explainable, every red flag is a real
> statutory rule, and it tells you not just what you'll be paid, but what
> you'll actually have. That's Financial Clarity."

---

## Fallback plan (backend down mid-demo)

If the footer shows "unreachable": the frontend surfaces the exact fix
inline ("Make sure it's running — `uvicorn app.main:app --reload`"). If
there's no time to restart it live, narrate the three sample offers from
`backend/data/sample_offers.json` and the pitch deck's screenshots instead
of freezing on a broken screen — don't let the judges watch you debug.

## Which sample offer proves what

| Sample chip | Regime | Red flags | Proves |
|---|---|---|---|
| Clean offer | New | 0 | Baseline breakdown + audit trail |
| Red-flag offer | New | 7 | Red-flag detection, the headline differentiator |
| Senior, old regime | Old | 0 | HRA exemption, 80C/80D, and the budgeting flow |
