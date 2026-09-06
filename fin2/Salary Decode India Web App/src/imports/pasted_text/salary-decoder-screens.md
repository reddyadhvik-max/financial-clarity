Create these screens and prototype interactions:

Landing page

Friendly hero heading: “Understand your real salary—not just your CTC.”

Supporting copy: “Decode your offer, estimate monthly in-hand pay, spot fine print, and know what you can actually spend.”

Three prominent actions:

Upload Offer Letter

Paste Offer Text

Enter Salary Manually

Secondary button: “Try with a sample offer”

Use an inviting hero visual: a simplified salary journey illustration showing CTC becoming monthly in-hand.

Below, show four calm feature cards:

Know your estimated in-hand

See where your CTC goes

Spot offer-letter red flags

Compare offers confidently

Include a clear privacy note: “Your document is used only to calculate your salary estimate.”

Minimal top navigation: Home, Decode Salary, Compare Offers, Spendable Money, PF & Gratuity Timeline, How It Works.

Decode Salary — input screen

Use tabs or segmented controls for:

Upload offer letter

Paste offer text

Manual entry

Upload tab: large drag-and-drop PDF/image area, upload progress, selected filename, remove/replace actions, validation states, and friendly loading message: “Reading your offer letter…”

Paste tab: large text area with sample salary-breakup placeholder, “Analyse Offer Letter” primary button, and Clear text action.

Manual entry: organise information in simple accordion cards:

Basic details: company, job title, work city, joining date

Salary: annual CTC, basic salary, HRA, special allowance

Benefits: employer and employee PF, gratuity, health insurance

Variable components: variable pay, performance bonus, joining bonus, retention bonus

Deductions: professional tax, ESI

Tax inputs: old/new regime, 80C, 80D, monthly rent

Monthly budget: rent, EMI, insurance, groceries, travel, other expenses

Include annual/monthly toggle, ₹ formatting, “I don’t know this value” links, required markers, plain-language tooltips, and a persistent bottom CTA: “Calculate My In-Hand Salary.”

Parsed-offer review

Show a reassuring success header: “We found the main salary details. Please review before calculating.”

Present company name and detected annual CTC in summary cards.

Main editable table with columns: Component, Amount, Source/status, Edit.

Source chips:

Found in offer letter — mint

Estimated — lavender

Missing—please add — amber

Right-side “Things worth checking” panel with red-flag cards:

Variable pay is a high percentage of CTC

Joining bonus makes first-year CTC look higher

Employer PF/gratuity are included in CTC

Bonus is discretionary

Fixed pay looks low relative to CTC

Give each alert a concise “Why it matters” explanation.

Actions: Reanalyse, Continue to Salary Breakdown.

Main salary decoder dashboard

Build this as the primary, polished results screen.

Top summary band with four large cards:

Annual CTC: ₹12,00,000

Estimated monthly in-hand: ₹76,800

Estimated annual take-home: ₹9,21,600

CTC not received as monthly bank salary

Clearly show selected tax regime and a gentle “Estimate based on your entered details and assumptions” disclaimer.

Add a visual CTC-to-in-hand waterfall or flow:
CTC → employer-side components → employee deductions → income tax/TDS → monthly in-hand.

Use a visually distinct final green/mint “Expected bank credit” result.

Detailed breakdown table:
Component | Monthly amount | Reaches your bank? | Simple explanation

Use clear positive/negative visual labels:

Yes

Deposited to EPF

Deducted

Usually paid later

Include expandable “Learn more” rows that explain basic salary, HRA, employer PF, gratuity, employee PF, TDS, professional tax, and variable pay.

Add a “Why is my in-hand lower than CTC ÷ 12?” card with the user’s top three specific reasons, using simple language and ranked visual bars.

Tax and salary optimisation

Use a calm interactive scenario screen titled “Explore your take-home.”

Old vs new tax regime segmented toggle.

Inputs: 80C contribution, 80D health insurance premium, monthly rent, optional NPS and voluntary PF.

Use friendly sliders plus editable number fields.

A live sticky results card should animate updated values:

Estimated monthly in-hand

Estimated annual tax

Change from current selection

Include a highlighted recommendation: “Best estimated option for your entered details.”

Show transparent reasoning, for example: “The old regime may reduce estimated tax by ₹18,000 if your rent and deductions are valid.”

Clearly state this is an estimate, not tax advice.

Spendable Money

Title: “What is actually left after your monthly commitments?”

Left side: simple monthly expense inputs with icons: rent, EMI, insurance, groceries, utilities, transport, mobile/internet, family support, savings, and other fixed expenses.

Right side: animated spendable-money composition:
Monthly in-hand − fixed expenses − EMI and insurance − essentials = freely spendable / saveable amount.

Show:

Monthly in-hand salary

Total fixed expenses

Remaining monthly buffer

EMI percentage

Savings percentage

Suggested emergency-fund contribution

Use calm, actionable insight cards:

“Your EMI uses more than 40% of estimated in-hand.”

“Your fixed commitments leave less than 10% as a buffer.”

“You have not added an emergency-fund allocation.”

Avoid judgemental language.

Compare Offers

Design a clear two-offer comparison, expandable to three offers.

Header actions: Analyse a new offer, Use saved offer, Add manually.

Offer tabs/cards: “Company A — Bengaluru” and “Company B — Pune.”

Comparison table with the most important rows:
Annual CTC, fixed pay, variable pay, estimated monthly in-hand, annual take-home, employer PF, gratuity, joining bonus, monthly spendable amount, and major red flags.

Highlight winners with understated badges:
Highest CTC, Highest monthly in-hand, Most stable fixed pay, Lowest variable-pay risk, Best monthly spending power.

Include a prominent transparent insight card:
“Offer B has a higher CTC, but Offer A gives ₹4,500 more reliable monthly in-hand because less of its pay is variable.”

If showing “Best overall match,” include a visible “How we scored this” link or drawer.

PF and Gratuity Timeline

Create an easy, visually appealing timeline screen.

Inputs: joining date, expected exit date/number of months, basic salary/PF amount.

Timeline milestones:
Joining date → Month 18: PF remains yours and can be transferred → Year 3: gratuity generally not vested yet → Year 5: gratuity eligibility milestone → after vesting: estimated gratuity payable on exit.

Results cards: continuous service completed, gratuity vesting date, likely eligibility, estimated gratuity if eligible, and EPF explanation.

Include plain-language informational callouts: PF is normally transferable between jobs; gratuity depends on continuous service and applicable rules.

Clearly label legal and tax details as estimates based on assumptions.

Shared UX details

Include Back, Edit details, Reset/start new analysis, Save locally, Copy summary, and optional Download PDF actions.

Make every financial term understandable through hover/tap glossary tooltips.

Use accessible contrast, descriptive labels, visible focus states, keyboard-friendly forms, and large mobile touch targets.

On mobile, convert tables into stacked comparison cards and retain a sticky primary action.

Build clickable prototype flows across Landing → Input → Review → Results → Tax → Spendable Money → Compare Offers.

Use realistic Indian salary sample data throughout so screens feel complete and believable.

