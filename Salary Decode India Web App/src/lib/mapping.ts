// Converts between this app's form shape (SalaryData) and the backend's
// CtcBreakup, and merges an AI-parsed offer (ParsedOfferAI) into a SalaryData
// draft. This is the only place those two shapes should ever meet — screens
// should never hand-translate field names themselves.
import { defaultSalaryData } from "../data/sampleData";
import type { SalaryData } from "../data/sampleData";
import type { CtcBreakup, ExtractedField, ParsedOfferAI } from "./types";
import type { SampleOffer } from "./api";

const METRO_CITIES = ["mumbai", "delhi", "bengaluru", "bangalore", "kolkata", "chennai"];

export function salaryDataToCtcBreakup(d: SalaryData): CtcBreakup {
  return {
    basic: d.basic,
    hra: d.hra,
    specialAllowance: d.specialAllowance,
    bonus: d.variablePay,
    employerPF: d.employerPF,
    gratuity: d.gratuity,
    professionalTax: d.professionalTax,
    healthInsurancePremium: d.healthInsurance,
    rentPaid: d.regime === "old" ? d.monthlyRent * 12 : undefined,
    isMetro: METRO_CITIES.includes(d.city.toLowerCase()),
    deductionsClaimed:
      d.regime === "old" ? { "80C": d.section80C, "80D": d.section80D } : {},
  };
}

/** Reads one extracted field's numeric value, or falls back if absent/null. */
function num(field: ExtractedField | null | undefined, fallback: number): number {
  if (!field) return fallback;
  return typeof field.value === "number" ? field.value : fallback;
}

/** Reads one extracted field's string value, or falls back if absent/null. */
function str(field: ExtractedField | null | undefined, fallback: string): string {
  if (!field) return fallback;
  return typeof field.value === "string" && field.value.trim() ? field.value : fallback;
}

/**
 * Merges an AI-parsed offer into a SalaryData draft. Fields the parser
 * couldn't find (value === null, or flagged as an ambiguity) keep the
 * existing draft's value rather than being overwritten with a guess — the
 * caller is expected to surface those via `parsed.ambiguities` instead.
 */
export function mergeParsedOfferIntoSalaryData(parsed: ParsedOfferAI, base: SalaryData): SalaryData {
  const basic = num(parsed.basic, base.basic);
  const hra = num(parsed.hra, base.hra);
  const specialAllowance = num(parsed.special_allowance, base.specialAllowance);
  const bonus = num(parsed.bonus, base.variablePay);
  const employerPF = num(parsed.employer_pf, base.employerPF);
  const gratuity = num(parsed.gratuity, base.gratuity);

  // Only trust an explicitly-stated total CTC; otherwise the sum of the
  // components we just read is a far better estimate than leaving a stale
  // default CTC from before this document was parsed.
  const ctc = parsed.ctc_total?.value != null
    ? num(parsed.ctc_total, base.ctc)
    : basic + hra + specialAllowance + bonus + employerPF + gratuity;

  return {
    ...base,
    company: str(parsed.company_name, base.company),
    jobTitle: str(parsed.job_title, base.jobTitle),
    city: str(parsed.city, base.city),
    ctc,
    basic,
    hra,
    specialAllowance,
    variablePay: bonus,
    employerPF,
    gratuity,
    healthInsurance: num(parsed.health_insurance_premium, base.healthInsurance),
  };
}

/** Converts one backend /sample-offers entry (snake_case, engine-shaped) into
 * this app's SalaryData form shape, so "try a sample offer" runs through the
 * exact same real /breakdown call as a user-entered offer. */
export function sampleOfferToSalaryData(sample: SampleOffer): SalaryData {
  const c = sample.ctc_breakup as Record<string, number | boolean | undefined>;
  const num = (v: unknown, fallback = 0): number => (typeof v === "number" ? v : fallback);
  const basic = num(c.basic);
  const hra = num(c.hra);
  const specialAllowance = num(c.special_allowance);
  const bonus = num(c.bonus);
  const deductionsClaimed = (c.deductions_claimed as Record<string, number> | undefined) ?? {};
  return {
    ...defaultSalaryData,
    company: sample.label,
    jobTitle: "",
    city: c.is_metro ? "Mumbai" : "Pune",
    ctc: basic + hra + specialAllowance + bonus + num(c.employer_pf) + num(c.gratuity),
    basic,
    hra,
    specialAllowance,
    employerPF: num(c.employer_pf),
    employeePF: Math.round(basic * 0.12),
    gratuity: num(c.gratuity),
    variablePay: bonus,
    joiningBonus: 0,
    professionalTax: num(c.professional_tax),
    healthInsurance: 0,
    regime: Object.keys(deductionsClaimed).length > 0 ? "old" : "new",
    section80C: deductionsClaimed["80C"] ?? 0,
    section80D: deductionsClaimed["80D"] ?? 0,
    monthlyRent: num(c.rent_paid) / 12,
  };
}
