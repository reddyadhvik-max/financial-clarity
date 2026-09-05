# Financial Clarity — Low-Fi Wireframe (Phase 1)

Single flow: **Upload → Breakdown → Regime Toggle**. Text/box wireframe only — no real components yet.

## Screen 1 — Upload / Manual Entry

```
+--------------------------------------------------+
|  Financial Clarity                                |
+--------------------------------------------------+
|                                                    |
|   Drop your offer letter (PDF) here                |
|   [ Choose file ]                                  |
|                                                    |
|   ── or enter manually ──                          |
|                                                    |
|   CTC (annual):        [__________]               |
|   Basic %:             [__________]                |
|   HRA %:               [__________]                |
|   City (metro/non-metro): [ dropdown ]             |
|   Other allowances:    [__________]                |
|                                                    |
|                          [ Get Breakdown → ]        |
+--------------------------------------------------+
```

## Screen 2 — Breakdown

```
+--------------------------------------------------+
|  ← Back              Financial Clarity             |
+--------------------------------------------------+
|  Completeness: ●●●●○  (80% — 1 field assumed)      |
|                                                    |
|  In-hand (monthly): ₹ XX,XXX                       |
|  ---------------------------------------------     |
|  Basic          ₹ ______   [rule: FY24-basic-slab] |
|  HRA            ₹ ______   [rule: FY24-hra-metro]  |
|  PF (employee)  ₹ ______   [rule: FY24-epf-12pct]  |
|  Tax (regime)   ₹ ______   [rule: FY24-newregime]  |
|  ---------------------------------------------     |
|                                                    |
|  [ Old Regime ]   ( New Regime )   ← toggle         |
|                                                    |
|  "In the new regime, you pay less tax because you  |
|   have no HRA/80C deductions to claim, and CTC     |
|   is below the ₹7L rebate threshold."              |
+--------------------------------------------------+
```

## Screen 3 — Regime Toggle (interaction only, same screen as above)

Toggling old/new regime re-runs the deterministic backend calc and re-renders numbers + explanation live. No separate screen — a state change on Screen 2.

## Notes

- Audit-trail click-through (number → rule) and confidence indicator are **stubbed as static labels** here — real interaction comes in Phase 3.
- Upload path box exists on screen but is **non-functional** in Phase 1 — manual entry is the only working path until Phase 2.
