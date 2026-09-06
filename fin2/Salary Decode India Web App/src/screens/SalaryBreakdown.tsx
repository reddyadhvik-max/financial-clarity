import { useState, useEffect } from "react";
import type { SalaryData } from "../data/sampleData";
import { fmt } from "../data/sampleData";
import { describeAiError, fetchClassification, fetchExplanation, fetchNegotiationMessage, fetchNegotiationPoints, fetchQualityScore } from "../lib/api";
import { salaryDataToCtcBreakup } from "../lib/mapping";
import CtcDonut from "../components/CtcDonut";
import QualityScoreCard from "../components/QualityScoreCard";
import type { BreakdownResponse, ClassificationResult, QualityScoreResult } from "../lib/types";

interface Props {
  data: SalaryData;
  breakdown: BreakdownResponse | null;
  loading: boolean;
  error: string | null;
  onNav: (s: string) => void;
}

function AiInsightButton({
  label, loadingLabel, onRun, result, error,
}: {
  label: string;
  loadingLabel: string;
  onRun: () => Promise<string>;
  result: string | null;
  error: string | null;
}) {
  const [text, setText] = useState<string | null>(result);
  const [err, setErr] = useState<string | null>(error);
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    setErr(null);
    try {
      setText(await onRun());
    } catch (e) {
      setErr(describeAiError(e, "Couldn't get a response right now."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button
        onClick={handleClick}
        disabled={loading}
        className="w-full bg-white border border-[#E2E5F0] text-[#3730A3] py-3 rounded-xl font-semibold text-sm hover:bg-[#EEF2FF] transition-colors disabled:opacity-50"
      >
        {loading ? loadingLabel : text ? `↻ ${label}` : `🤖 ${label}`}
      </button>
      {err && <p className="text-xs text-[#DC2626] mt-2">{err}</p>}
      {text && (
        <div className="mt-2 bg-[#F8F9FF] border border-[#E2E5F0] rounded-2xl p-4 text-xs text-[#374151] leading-relaxed whitespace-pre-line">
          {text}
        </div>
      )}
    </div>
  );
}

const BANK = "bg-[#ECFDF5] text-[#059669]";
const PF = "bg-[#EDE9FE] text-[#6D28D9]";
const DED = "bg-[#FEE2E2] text-[#DC2626]";
const LATER = "bg-[#FEF9C3] text-[#B45309]";

function StatusBadge({ type }: { type: string }) {
  const map: Record<string, string> = {
    "Yes": BANK,
    "Deposited to EPF": PF,
    "Deducted": DED,
    "Usually paid later": LATER,
    "Estimated": "bg-[#EDE9FE] text-[#6D28D9]",
  };
  return (
    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${map[type] || "bg-[#F0F1F7] text-[#64748B]"}`}>
      {type}
    </span>
  );
}

function LearnMore({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1 text-[10px] text-[#3730A3] font-medium mt-1 hover:underline"
      >
        {open ? "Hide" : "Learn more"}
        <svg
          width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}
          className={`transition-transform ${open ? "rotate-180" : ""}`}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="mt-2 text-xs text-[#64748B] bg-[#F8F9FF] rounded-xl p-3 leading-relaxed border border-[#E2E5F0]">
          {children}
        </div>
      )}
    </div>
  );
}

export default function SalaryBreakdown({ data, breakdown, loading, error, onNav }: Props) {
  const [classification, setClassification] = useState<ClassificationResult | null>(null);
  const [qualityScore, setQualityScore] = useState<QualityScoreResult | null>(null);

  useEffect(() => {
    const ctc = salaryDataToCtcBreakup(data);
    fetchClassification(ctc, data.regime).then(setClassification).catch(() => setClassification(null));
    fetchQualityScore(ctc, data.regime).then(setQualityScore).catch(() => setQualityScore(null));
  }, [data]);

  if (loading || !breakdown) {
    return (
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16 text-center">
        {error ? (
          <p className="text-sm text-[#DC2626]">{error}</p>
        ) : (
          <>
            <div className="w-10 h-10 mx-auto mb-4 border-3 border-[#C7D2FE] border-t-[#3730A3] rounded-full animate-spin" style={{ borderWidth: 3 }} />
            <p className="text-sm text-[#64748B]">Calculating your real in-hand pay…</p>
          </>
        )}
      </div>
    );
  }

  const b = breakdown.breakdown;
  const findDeduction = (nameSubstr: string) =>
    b.deductions.find(d => d.name.includes(nameSubstr))?.amount ?? 0;
  const ruleIdFor = (nameSubstr: string) =>
    b.deductions.find(d => d.name.includes(nameSubstr))?.rule_id ?? null;

  const employeePfAnnual = findDeduction("Employee PF");
  const professionalTaxAnnual = findDeduction("Professional Tax");
  const annualTax = b.tax_breakdown.total_tax;
  const employerPfAnnual = b.employer_side.employer_pf.amount;
  const gratuityAnnual = b.employer_side.gratuity_provision.amount;

  const monthly = {
    basic: data.basic / 12,
    hra: data.hra / 12,
    special: data.specialAllowance / 12,
    empPF: employerPfAnnual / 12,
    eeePF: employeePfAnnual / 12,
    gratuity: gratuityAnnual / 12,
    tds: annualTax / 12,
    pt: professionalTaxAnnual / 12,
  };

  const summaryCards = [
    { label: "Annual CTC", value: fmt(b.ctc_total), sub: "Total package value", color: "text-[#1A1D2E]", bg: "bg-white" },
    { label: "Est. monthly in-hand", value: fmt(b.in_hand_monthly), sub: "Bank credit each month", color: "text-[#059669]", bg: "bg-[#ECFDF5]" },
    { label: "Est. annual take-home", value: fmt(b.in_hand_annual), sub: "Fixed pay received in year", color: "text-[#3730A3]", bg: "bg-[#EEF2FF]" },
    { label: "Not in monthly salary", value: fmt(b.ctc_total - b.in_hand_annual), sub: "PF, gratuity, tax, variable", color: "text-[#B45309]", bg: "bg-[#FFFBEB]" },
  ];

  const waterfall = [
    { label: "Annual CTC", value: b.ctc_total, type: "gross", bar: 100 },
    { label: "− Employer PF", value: -employerPfAnnual, type: "neg", bar: Math.round((employerPfAnnual / b.ctc_total) * 100) },
    { label: "− Gratuity accrual", value: -gratuityAnnual, type: "neg", bar: Math.round((gratuityAnnual / b.ctc_total) * 100) },
    { label: "− Variable pay (at risk)", value: -data.variablePay, type: "warn", bar: Math.round((data.variablePay / b.ctc_total) * 100) },
    { label: "= Fixed gross salary", value: b.gross_salary_annual, type: "mid", bar: Math.round((b.gross_salary_annual / b.ctc_total) * 100) },
    { label: "− Employee PF", value: -employeePfAnnual, type: "neg", bar: Math.round((employeePfAnnual / b.ctc_total) * 100) },
    { label: "− TDS (estimated)", value: -annualTax, type: "neg", bar: Math.round((annualTax / b.ctc_total) * 100) },
    { label: "− Professional tax", value: -professionalTaxAnnual, type: "neg", bar: Math.round((professionalTaxAnnual / b.ctc_total) * 100) },
    { label: "= Monthly in-hand × 12", value: b.in_hand_annual, type: "result", bar: Math.round((b.in_hand_annual / b.ctc_total) * 100) },
  ];

  const tableRows = [
    { label: "Basic salary", monthly: monthly.basic, reaches: "Yes", explain: "Fully taxable. Base for PF and gratuity calculations.", more: "Basic salary is the core component of your pay. PF (12%) and gratuity (4.81%) are calculated on it. It is also fully included in your taxable income.", ruleId: null as string | null },
    { label: "HRA", monthly: monthly.hra, reaches: "Yes", explain: "Taxable, but HRA exemption reduces tax if you pay rent.", more: `If you pay rent and do not own a house in the city where you work, a portion of HRA is exempt from tax. This offer's computed exemption: ${fmt(b.hra_exemption_amount)}/year.`, ruleId: b.hra_exemption_amount > 0 ? "HRA_METRO_PCT / HRA_RENT_OFFSET_PCT" : null },
    { label: "Special allowance", monthly: monthly.special, reaches: "Yes", explain: "Fully taxable. The remaining CTC balance.", more: "Companies put leftover CTC here after allocating basic, HRA, PF, and other components. It is fully taxable with no exemption.", ruleId: null },
    { label: "Employer PF", monthly: monthly.empPF, reaches: "Deposited to EPF", explain: "Goes to your EPF account, not your bank.", more: "Your employer's PF contribution goes to your EPF account. This money is yours but accessible only after you leave the job or retire.", ruleId: b.employer_side.employer_pf.rule_id },
    { label: "Gratuity", monthly: monthly.gratuity, reaches: "Usually paid later", explain: "Accrues each month; paid only after 5 years of service.", more: "Gratuity is a statutory benefit under the Payment of Gratuity Act. You are eligible after completing 5 years of continuous service.", ruleId: b.employer_side.gratuity_provision.rule_id },
    { label: "Employee PF", monthly: monthly.eeePF, reaches: "Deducted", explain: "Deducted from salary and deposited to your EPF account.", more: "You contribute a share of basic to EPF. This is your savings — accessible when you resign or retire.", ruleId: ruleIdFor("Employee PF") },
    { label: "TDS (estimated income tax)", monthly: monthly.tds, reaches: "Deducted", explain: "Tax deducted at source monthly by your employer.", more: `Based on the ${b.regime} tax regime. Estimated annual tax: ${fmt(annualTax)}. This is an estimate — actual TDS may vary based on declarations and investments.`, ruleId: ruleIdFor("Income Tax") },
    { label: "Professional tax", monthly: monthly.pt, reaches: "Deducted", explain: "State-mandated deduction.", more: "Professional tax is deducted by your employer and paid to the state government.", ruleId: ruleIdFor("Professional Tax") },
  ];

  const reasons = [
    { label: "Income tax (TDS)", value: annualTax, pct: Math.round((annualTax / b.ctc_total) * 100) },
    { label: "Employee PF contribution", value: employeePfAnnual, pct: Math.round((employeePfAnnual / b.ctc_total) * 100) },
    { label: "Employer PF & gratuity in CTC", value: employerPfAnnual + gratuityAnnual, pct: Math.round(((employerPfAnnual + gratuityAnnual) / b.ctc_total) * 100) },
    { label: "Variable pay (not monthly)", value: data.variablePay, pct: Math.round((data.variablePay / b.ctc_total) * 100) },
  ];

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      {/* Header */}
      <div className="fade-slide-up mb-2">
        <div className="flex items-center justify-between flex-wrap gap-3 mb-2">
          <h1 className="text-2xl font-bold text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>
            Your salary breakdown
          </h1>
          <div className="flex items-center gap-2 text-xs bg-[#EEF2FF] text-[#3730A3] px-3 py-1.5 rounded-full font-medium">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {b.regime === "new" ? "New" : "Old"} tax regime
          </div>
        </div>
        <p className="text-xs text-[#94A3B8]">
          Every number above is computed by a versioned, rule-based tax engine — not an estimate rounded on the spot. Not tax advice.
        </p>
      </div>

      {/* Summary band */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6 fade-slide-up delay-1">
        {summaryCards.map((card, i) => (
          <div key={i} className={`${card.bg} border border-[#E2E5F0] rounded-2xl px-5 py-4`}>
            <div className="text-xs text-[#94A3B8] mb-1">{card.label}</div>
            <div className={`text-xl font-bold count-up ${card.color}`} style={{ fontFamily: "Manrope, sans-serif" }}>
              {card.value}
            </div>
            <div className="text-xs text-[#94A3B8] mt-0.5">{card.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-5 gap-6">
        {/* Left column */}
        <div className="lg:col-span-3 space-y-6">
          {/* CTC composition donut */}
          {classification && (
            <div className="fade-slide-up bg-white border border-[#E2E5F0] rounded-2xl p-5">
              <h2 className="font-semibold text-sm text-[#1A1D2E] mb-4" style={{ fontFamily: "Manrope, sans-serif" }}>
                CTC composition
              </h2>
              <CtcDonut classification={classification} />
            </div>
          )}

          {/* Waterfall */}
          <div className="fade-slide-up delay-2 bg-white border border-[#E2E5F0] rounded-2xl p-5">
            <h2 className="font-semibold text-sm text-[#1A1D2E] mb-4" style={{ fontFamily: "Manrope, sans-serif" }}>
              CTC → Monthly in-hand
            </h2>
            <div className="space-y-2">
              {waterfall.map((row, i) => {
                const isResult = row.type === "result";
                const isGross = row.type === "gross";
                const color = isResult ? "bg-[#6EE7B7]" : isGross ? "bg-[#818CF8]" : row.type === "neg" ? "bg-[#FCA5A5]" : row.type === "warn" ? "bg-[#FDE68A]" : "bg-[#C7D2FE]";
                return (
                  <div key={i} className="flex items-center gap-3">
                    <div className={`w-36 text-xs shrink-0 ${isResult ? "font-semibold text-[#059669]" : isGross ? "font-semibold text-[#1A1D2E]" : "text-[#64748B]"}`}>
                      {row.label}
                    </div>
                    <div className="flex-1 h-6 bg-[#F5F6FA] rounded-lg overflow-hidden">
                      <div className={`h-full rounded-lg ${color} transition-all`} style={{ width: `${row.bar}%` }} />
                    </div>
                    <div className={`w-24 text-right text-xs font-medium shrink-0 ${isResult ? "text-[#059669]" : row.value < 0 ? "text-[#DC2626]" : "text-[#1A1D2E]"}`}>
                      {row.value > 0 ? fmt(row.value) : `−${fmt(Math.abs(row.value))}`}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-4 flex items-center justify-between bg-[#ECFDF5] border border-[#A7F3D0] rounded-xl px-4 py-3">
              <div className="text-sm font-bold text-[#059669]" style={{ fontFamily: "Manrope, sans-serif" }}>
                Expected bank credit / month
              </div>
              <div className="text-xl font-bold text-[#059669] count-up" style={{ fontFamily: "Manrope, sans-serif" }}>
                {fmt(b.in_hand_monthly)}
              </div>
            </div>
          </div>

          {/* Breakdown table */}
          <div className="fade-slide-up delay-3 bg-white border border-[#E2E5F0] rounded-2xl overflow-hidden">
            <div className="px-5 py-4 border-b border-[#F0F1F7]">
              <h2 className="font-semibold text-sm text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>
                Detailed component breakdown
              </h2>
            </div>
            <div className="divide-y divide-[#F0F1F7]">
              <div className="grid grid-cols-12 px-5 py-2 text-[10px] font-semibold text-[#94A3B8] uppercase tracking-wider">
                <div className="col-span-4">Component</div>
                <div className="col-span-2 text-right">Monthly</div>
                <div className="col-span-3 text-center">Reaches bank?</div>
                <div className="col-span-3">What it means</div>
              </div>
              {tableRows.map((row, i) => (
                <div key={i} className="px-5 py-3 hover:bg-[#F8F9FF] transition-colors">
                  <div className="grid grid-cols-12 items-start">
                    <div className="col-span-4">
                      <div className="text-sm text-[#1A1D2E]">{row.label}</div>
                      <LearnMore>
                        {row.more}
                        {row.ruleId && (
                          <div className="mt-2 text-[10px] text-[#94A3B8] font-mono">rule_id: {row.ruleId}</div>
                        )}
                      </LearnMore>
                    </div>
                    <div className="col-span-2 text-right text-sm font-medium text-[#1A1D2E] pt-0.5">{fmt(Math.round(row.monthly))}</div>
                    <div className="col-span-3 text-center pt-0.5">
                      <StatusBadge type={row.reaches} />
                    </div>
                    <div className="col-span-3 text-xs text-[#64748B] leading-relaxed pt-0.5">{row.explain}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right column */}
        <div className="lg:col-span-2 space-y-4">
          {qualityScore && <QualityScoreCard score={qualityScore} />}

          {/* Why lower card */}
          <div className="fade-slide-up delay-2 bg-white border border-[#E2E5F0] rounded-2xl p-5">
            <h3 className="font-semibold text-sm text-[#1A1D2E] mb-1" style={{ fontFamily: "Manrope, sans-serif" }}>
              Why is my in-hand lower than CTC ÷ 12?
            </h3>
            <p className="text-xs text-[#94A3B8] mb-4">CTC ÷ 12 = {fmt(Math.round(b.ctc_total / 12))}. Your in-hand is {fmt(b.in_hand_monthly)}.</p>
            <div className="space-y-3">
              {reasons.map((r, i) => (
                <div key={i}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-[#64748B]">{r.label}</span>
                    <span className="font-semibold text-[#1A1D2E]">{fmt(r.value)}/yr</span>
                  </div>
                  <div className="h-2 bg-[#F0F1F7] rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-[#818CF8]"
                      style={{ width: `${r.pct * 2.5}%` }}
                    />
                  </div>
                  <div className="text-[10px] text-[#94A3B8] mt-0.5">{r.pct}% of CTC</div>
                </div>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="fade-slide-up delay-3 space-y-2">
            <button
              onClick={() => onNav("tax")}
              className="w-full bg-[#3730A3] text-white py-3 rounded-xl font-semibold text-sm hover:bg-[#312E81] transition-all shadow-md shadow-indigo-200"
            >
              Explore tax scenarios →
            </button>
            <button
              onClick={() => onNav("spendable")}
              className="w-full bg-white border border-[#E2E5F0] text-[#3730A3] py-3 rounded-xl font-semibold text-sm hover:bg-[#EEF2FF] transition-colors"
            >
              Plan spendable money →
            </button>
            <button
              onClick={() => onNav("compare")}
              className="w-full bg-white border border-[#E2E5F0] text-[#64748B] py-3 rounded-xl text-sm hover:bg-[#F5F6FA] transition-colors"
            >
              Compare with another offer
            </button>
          </div>

          {/* AI insights */}
          <div className="fade-slide-up delay-4 space-y-3">
            <AiInsightButton
              label="Explain my offer"
              loadingLabel="AI is reading your offer…"
              result={null}
              error={null}
              onRun={async () => (await fetchExplanation(salaryDataToCtcBreakup(data), data.regime)).explanation}
            />
            <AiInsightButton
              label="What should I negotiate?"
              loadingLabel="AI is thinking…"
              result={null}
              error={null}
              onRun={async () => (await fetchNegotiationPoints(salaryDataToCtcBreakup(data), data.regime)).negotiation_points}
            />
            <AiInsightButton
              label="Draft a negotiation email"
              loadingLabel="AI is drafting…"
              result={null}
              error={null}
              onRun={async () => (await fetchNegotiationMessage(salaryDataToCtcBreakup(data), "recruiter_email", data.regime)).message}
            />
          </div>

          {/* Regime hint */}
          <div className="fade-slide-up delay-4 bg-[#F8F9FF] border border-[#E2E5F0] rounded-2xl p-4 text-xs text-[#64748B] leading-relaxed">
            <span className="font-semibold text-[#3730A3]">Tip: </span>
            Switching tax regimes may change your take-home. Use the tax scenario tool to compare old vs new regime for your specific situation.
          </div>
        </div>
      </div>
    </div>
  );
}
