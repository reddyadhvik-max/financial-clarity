"""Generates 10 randomized, realistic offer-letter .txt fixtures for manual
testing of the multi-offer comparison feature.

Each letter always states Total CTC (the anchor figure), then randomly
includes ~90% of a pool of 23 other fields real Indian offer letters
typically state — dropping ~10% at random per letter — so comparing any
two of the ten produces a genuine mix of found/estimated/missing and "NA"
values to look at, rather than every field lining up perfectly.

`total_gross_pay` and `target_net_pay` are deliberately never stated
directly (real offer letters essentially never spell these out verbatim —
they're derived figures) — that's realistic, not a gap in the generator.

Run from the person4-data-parsing/ directory:
    python sample_offers/generate_samples.py
"""
import random
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent
SEED = 42  # reproducible — rerunning regenerates the exact same 10 letters

COMPANIES = [
    "Northwind Analytics Pvt Ltd", "Cobalt Systems India", "Vertex Cloud Technologies",
    "Bluepeak Software Solutions", "Ironleaf Consulting", "Sundial Fintech Pvt Ltd",
    "Marigold Digital Pvt Ltd", "Copperline Robotics", "Silverbrook Data Labs",
    "Amberstone Retail Tech",
]
CITIES = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Gurugram", "Mumbai", "Noida", "Kolkata"]
DESIGNATIONS = [
    "Software Engineer", "Senior Data Analyst", "Product Manager", "DevOps Engineer",
    "QA Engineer", "Backend Developer", "UX Designer", "Business Analyst",
    "Machine Learning Engineer", "Site Reliability Engineer",
]
FIRST_NAMES = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Ishita", "Vikram", "Sneha",
               "Arjun", "Ananya", "Karan", "Priya"]
LAST_NAMES = ["Mehta", "Iyer", "Rao", "Sharma", "Nair", "Kapoor", "Reddy", "Verma",
              "Bhatt", "Chatterjee"]
EQUITY_TYPES = ["ESOPs", "RSUs", "ESPP"]

# --- field templates -------------------------------------------------------
# Each entry: key -> function(ctx) -> a sentence/line using ONLY phrasing
# that schema.py's alias list actually recognizes (verified against real
# parser output before being trusted here — see generate_samples.py's
# companion check at the bottom of this file).

def _rs(amount: float) -> str:
    return f"Rs. {amount:,.0f}"


def build_field_lines(ctx: dict) -> dict[str, str]:
    ctc = ctx["ctc"]
    basic = ctc * ctx["basic_pct"]
    hra = basic * 0.5
    special_allowance = ctc * 0.10
    lta = ctc * 0.02
    da = ctc * 0.03
    employer_pf = basic * 0.12
    gratuity = (basic / 12) * 0.576923077
    superannuation = ctc * 0.03
    target_bonus = ctc * ctx["bonus_pct"]
    sales_commission = ctc * 0.04
    joining_bonus = ctc * 0.05
    relocation = 40000 + ctx["rand"].randint(0, 30000)
    retention_bonus = ctc * 0.03
    equity_value = ctc * ctx["equity_pct"]
    health_insurance = 12000 + ctx["rand"].randint(0, 8000)
    food_allowance = 18000 + ctx["rand"].randint(0, 6000)
    internet_reimb = 6000 + ctx["rand"].randint(0, 4000)
    cab_deduction = 9000 + ctx["rand"].randint(0, 5000)

    return {
        "basic_pay": f"Basic Pay: {_rs(basic)} per annum.",
        "hra": f"House Rent Allowance (HRA): {_rs(hra)} per annum.",
        "special_allowance": f"Special Allowance: {_rs(special_allowance)} per annum.",
        "lta": f"Leave Travel Allowance (LTA): {_rs(lta)} per annum.",
        "da": f"Dearness Allowance: {_rs(da)} per annum.",
        "employer_pf": f"Employer PF: {_rs(employer_pf)} per annum.",
        "gratuity": f"Gratuity: {_rs(gratuity)} per annum.",
        "superannuation_nps": f"Superannuation: {_rs(superannuation)} per annum.",
        "target_bonus": f"Variable Component of {_rs(target_bonus)} per annum (Performance-Based), paid out {ctx['bonus_freq']}.",
        "sales_commission": f"Sales Commission of {_rs(sales_commission)} per annum, based on quota attainment.",
        "joining_bonus": f"You will also be eligible for a Joining Bonus of {_rs(joining_bonus)}, subject to a Clawback Period of {ctx['clawback_months']} months if you leave voluntarily within that period.",
        "relocation_allowance": f"A one-time Relocation Allowance of {_rs(relocation)} will be provided to assist with your move.",
        "retention_bonus": f"A Retention Bonus of {_rs(retention_bonus)} will be paid on completion of 18 months of service.",
        "equity": (
            f"As part of our long-term plan, you will be granted {ctx['equity_type']} with a Total Equity Grant Value "
            f"of {_rs(equity_value)}, vesting over 4 years with a Cliff Period of 12 months."
        ),
        "health_insurance_premium": f"Health Insurance Premium of {_rs(health_insurance)} per annum is covered by the company.",
        "food_meal_allowance": f"Food Allowance (Sodexo) of {_rs(food_allowance)} per annum.",
        "internet_phone_reimbursement": f"Internet Reimbursement of {_rs(internet_reimb)} per annum.",
        "cab_transport_deduction": f"Cab Deduction of {_rs(cab_deduction)} per annum will apply for company transport.",
    }


# Field pool eligible for random ~10% omission. "equity" bundles equity_type +
# equity_grant_value + equity_vesting_schedule + equity_cliff_months into one
# sentence (dropping it drops all four together, which is realistic — a
# letter either has an equity clause or it doesn't).
OPTIONAL_FIELD_KEYS = [
    "basic_pay", "hra", "special_allowance", "lta", "da",
    "employer_pf", "gratuity", "superannuation_nps",
    "target_bonus", "sales_commission",
    "joining_bonus", "relocation_allowance", "retention_bonus", "equity",
    "health_insurance_premium", "food_meal_allowance",
    "internet_phone_reimbursement", "cab_transport_deduction",
]


def build_letter(index: int, rand: random.Random) -> str:
    company = COMPANIES[index]
    city = CITIES[index % len(CITIES)]
    designation = DESIGNATIONS[index % len(DESIGNATIONS)]
    first = FIRST_NAMES[rand.randrange(len(FIRST_NAMES))]
    last = LAST_NAMES[rand.randrange(len(LAST_NAMES))]
    employee = f"{first} {last}"

    ctc = rand.randint(8, 32) * 100000  # Rs. 8L - 32L, rounded to nearest lakh
    ctx = {
        "ctc": ctc,
        "basic_pct": rand.uniform(0.38, 0.48),
        "bonus_pct": rand.uniform(0.08, 0.18),
        "bonus_freq": rand.choice(["Monthly", "Quarterly", "Annually"]),
        "equity_pct": rand.uniform(0.03, 0.12),
        "equity_type": rand.choice(EQUITY_TYPES),
        "clawback_months": rand.choice([6, 9, 12, 18]),
        "rand": rand,
    }

    field_lines = build_field_lines(ctx)

    # Drop ~10% of the optional fields, at random, per letter.
    n_to_drop = max(1, round(len(OPTIONAL_FIELD_KEYS) * 0.10))
    dropped = set(rand.sample(OPTIONAL_FIELD_KEYS, n_to_drop))
    included_keys = [k for k in OPTIONAL_FIELD_KEYS if k not in dropped]

    join_day = rand.randint(1, 28)
    join_month = rand.randint(1, 12)
    joining_date = f"{join_day:02d}/{join_month:02d}/2026"

    lines = [
        f"Company Name: {company}",
        f"Address: {rand.randint(1, 99)}th Floor, Tech Park, {city}",
        f"Email: hr@{company.split()[0].lower()}.com",
        "",
        f"Dear {employee},",
        "",
        f"We are thrilled to extend an offer of employment to you at {company} for the "
        f"position of {designation}. Your performance during the interview process has "
        "impressed us, and we believe you will be a valuable addition to our team.",
        "",
        "Your Compensation Package",
        f"Your Total Compensation (CTC) for the year will be {_rs(ctc)}.",
        "",
        "Compensation Breakup:",
    ]
    for key in included_keys:
        lines.append(field_lines[key])

    lines += [
        "",
        "Joining Date",
        f"Your expected joining date is on or before {joining_date}. Please ensure you "
        "arrive promptly to begin your exciting journey with us.",
        "",
        "Pre-Employment Requirements",
        "Before joining our team, we require you to sign a Non-Disclosure Agreement (NDA) "
        "as a part of our employment prerequisites.",
        "",
        "Yours truly,",
        "Human Resources",
        f"{company}",
    ]
    return "\n".join(lines)


def main() -> None:
    rand = random.Random(SEED)
    for i in range(10):
        letter = build_letter(i, rand)
        path = OUTPUT_DIR / f"sample_offer_{i + 1:02d}.txt"
        path.write_text(letter, encoding="utf-8")
        print(f"wrote {path.name}")


if __name__ == "__main__":
    main()
