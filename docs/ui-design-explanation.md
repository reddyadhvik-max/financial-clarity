# UI Design — What We Used and Why (for judges)

## The concept: a ledger, rendered as glass

Financial Clarity's job is to take a confusing offer letter and show, plainly, what lands in your account and why. We built the interface around a literal metaphor: **an open ledger book** — input on the left page, output on the right, numbers right-aligned in accounting convention, every entry separated by a ruled line. This isn't decoration; a ledger is what the product actually is, so the UI's structure mirrors its function.

On top of that structure we applied a **glassmorphism** treatment: frosted, translucent panels floating over a soft, blurred gradient background, rather than flat opaque cards. Two reasons:

1. **Trust through transparency, made literal.** The product's core promise is explainability — every number traces back to a rule, nothing is a black box. A glass surface, where content and structure remain legible through translucency rather than hidden behind an opaque card, is a visual echo of that same idea: nothing here is opaque.
2. **It reads as current and considered, not a spreadsheet.** Offer-letter breakdowns are usually shown as dense, intimidating tables. Glass panels with soft depth make the same rigorous ledger data feel approachable, without diluting the numbers themselves.

## What we actually built

**Frosted-glass surfaces** — `backdrop-filter: blur(22px) saturate(160%)` on the header, the ledger spread, and the footer, each with a translucent white fill, a soft highlight border, and a layered shadow for depth. Behind everything sit three large, blurred color blooms (emerald, ochre, mint — drawn from the same palette as the rest of the UI, not arbitrary decoration) that give the glass something to refract.

**Hover and interaction feedback** — every clickable element responds visibly to being pointed at or pressed, so the interface never feels static:
- The primary "See my breakdown" button lifts and its glow intensifies on hover, and compresses slightly on click, giving tactile confirmation of the action.
- The old/new tax-regime toggle is a pair of glass pills; hovering lifts them, and the active regime gets a bright emerald gradient fill so the current selection is unambiguous at a glance.
- Ledger rows highlight softly on hover, and the "why?" rule-lookup buttons tint and lift, signaling they're interactive before you click.
- When a number changes (e.g. after toggling regime), that row briefly flashes — a "correction mark," like a bookkeeper striking through and re-entering a figure — with a small ▲/▼ badge showing exactly how much it changed. This is functional feedback, not decoration: it answers "what just changed and by how much" without the user re-reading every row.

**Audio feedback** — a light, high, glassy tone plays on hovering a button, and a softer, lower tone on click. Both are synthesized live with the Web Audio API (a few lines of oscillator code), not pre-recorded audio files, so there's zero asset weight and no licensing question. Sound is rate-limited so fast mouse movement across the interface doesn't turn into noise, and the sounds are deliberately quiet and short so they read as texture, not gimmick.

## Why this design serves the judging criteria, not just aesthetics

- **Explainability**: the audit-trail "why?" chips and the glass metaphor both point at the same idea — every figure is inspectable, nothing is hidden.
- **Technical depth**: glassmorphism (`backdrop-filter`), live count-up/correction animations, and procedurally generated audio are all implemented with plain CSS/JS — no UI framework, no external audio library, no image assets — which keeps the frontend dependency-free and fast to demo on any machine.
- **Accessibility**: every animation and the count-up effect respect `prefers-reduced-motion`; all interactive elements have visible keyboard focus states; color choices maintain contrast against the glass backgrounds.

## What we deliberately did not do

- No motion for motion's sake: hover/click feedback only fires in response to an actual user action (pointer entering a button, a click, a value changing) — nothing animates on page load or scroll.
- No sound on non-interactive elements (form fields, plain text) — only on buttons, toggles, and disclosure triggers, so it never becomes noise while filling in numbers.
- No glass effect on the numbers themselves — the ledger table stays crisp and fully opaque where precision matters; blur is reserved for structural chrome (panels, backgrounds), never for the figures a person is trying to read accurately.
