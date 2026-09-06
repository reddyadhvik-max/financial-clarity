import { useState } from "react";
import { fmt, defaultSalaryData } from "../data/sampleData";
import type { SalaryData } from "../data/sampleData";
import { describeAiError, fetchOfferComparisonVerdict } from "../lib/api";
import { salaryDataToCtcBreakup } from "../lib/mapping";
import type { CompareOffersComputed } from "../lib/types";

interface Props {
  primaryData: SalaryData;
  onNav: (s: string) => void;
}

const offerBDefault: SalaryData = {
  ...defaultSalaryData,
  company: "Wipro Technologies",
  jobTitle: "Lead Software Engineer",
  city: "Pune",
  ctc: 1380000,
  basic: 496800,
  hra: 198720,
  specialAllowance: 414480,
  employerPF: 59616,
  gratuity: 23885,
  variablePay: 207000,
  professionalTax: 2500,
};

function RupeeField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="text-[10px] font-medium text-[#374151] block mb-1">{label}</label>
      <div className="relative">
        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8] text-xs">₹</span>
        <input
          type="number"
          value={value || ""}
          onChange={e => onChange(Number(e.target.value) || 0)}
          className="w-full pl-6 pr-2 py-1.5 bg-[#F5F6FA] border border-[#E2E5F0] rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#818CF8]"
        />
      </div>
    </div>
  );
}

export default function CompareOffers({ primaryData, onNav }: Props) {
  const [offerB, setOfferB] = useState<SalaryData>(offerBDefault);
  const set = (k: keyof SalaryData) => (v: number | string) => setOfferB(prev => ({ ...prev, [k]: v }));

  const [result, setResult] = useState<{ verdict: string; computed: CompareOffersComputed } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runComparison = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetchOfferComparisonVerdict(
        { label: "Offer A", ctcBreakup: salaryDataToCtcBreakup(primaryData), regime: primaryData.regime },
        { label: "Offer B", ctcBreakup: salaryDataToCtcBreakup(offerB), regime: offerB.regime },
      );
      setResult(r);
    } catch (err) {
      setError(describeAiError(err, "Couldn't compare these offers right now. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  const a = result?.computed.offer_a;
  const b = result?.computed.offer_b;

  const rows: { label: string; a: string; b: string; winnerA?: boolean; winnerB?: boolean }[] = a && b ? [
    { label: "Annual CTC", a: fmt(a.in_hand.ctc_total), b: fmt(b.in_hand.ctc_total),
      winnerA: result!.computed.best_for_total_comp === "offer_a", winnerB: result!.computed.best_for_total_comp === "offer_b" },
    { label: "Est. monthly in-hand", a: fmt(a.in_hand.in_hand_monthly), b: fmt(b.in_hand.in_hand_monthly),
      winnerA: result!.computed.best_for_cashflow === "offer_a", winnerB: result!.computed.best_for_cashflow === "offer_b" },
    { label: "Est. annual take-home", a: fmt(a.in_hand.in_hand_annual), b: fmt(b.in_hand.in_hand_annual) },
    { label: "Offer quality score (0-100)", a: String(a.quality_score.overall_score), b: String(b.quality_score.overall_score),
      winnerA: a.quality_score.overall_score > b.quality_score.overall_score,
      winnerB: b.quality_score.overall_score > a.quality_score.overall_score },
    { label: "Variable pay % of CTC",
      a: `${Math.round((a.classification.buckets.find(x => x.bucket === "variable")?.pct_of_ctc ?? 0) * 100)}%`,
      b: `${Math.round((b.classification.buckets.find(x => x.bucket === "variable")?.pct_of_ctc ?? 0) * 100)}%` },
  ] : [];

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      <div className="fade-slide-up mb-6">
        <h1 className="text-2xl font-bold text-[#1A1D2E] mb-1" style={{ fontFamily: "Manrope, sans-serif" }}>
          Compare offers
        </h1>
        <p className="text-sm text-[#94A3B8]">
          Enter a second offer's details and let AI weigh in on which is actually better for you.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4 mb-6 fade-slide-up delay-1">
        <div className="bg-white border-2 border-[#E2E5F0] rounded-2xl px-5 py-4">
          <div className="text-xs font-semibold text-[#94A3B8] mb-0.5">Offer A — your analyzed offer</div>
          <div className="font-bold text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>{primaryData.company}</div>
          <div className="text-xs text-[#64748B] mb-3">{primaryData.jobTitle} · {primaryData.city}</div>
          <div className="text-[10px] text-[#94A3B8]">Annual CTC</div>
          <div className="text-lg font-bold text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>{fmt(primaryData.ctc)}</div>
        </div>

        <div className="bg-white border-2 border-[#C7D2FE] rounded-2xl px-5 py-4">
          <div className="text-xs font-semibold text-[#94A3B8] mb-2">Offer B — edit to compare</div>
          <div className="grid grid-cols-2 gap-2 mb-3">
            <input value={offerB.company} onChange={e => set("company")(e.target.value)}
              placeholder="Company" className="col-span-2 px-2 py-1.5 bg-[#F5F6FA] border border-[#E2E5F0] rounded-lg text-xs font-semibold" />
            <input value={offerB.jobTitle} onChange={e => set("jobTitle")(e.target.value)}
              placeholder="Job title" className="px-2 py-1.5 bg-[#F5F6FA] border border-[#E2E5F0] rounded-lg text-xs" />
            <input value={offerB.city} onChange={e => set("city")(e.target.value)}
              placeholder="City" className="px-2 py-1.5 bg-[#F5F6FA] border border-[#E2E5F0] rounded-lg text-xs" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <RupeeField label="Basic (annual)" value={offerB.basic} onChange={set("basic") as (v: number) => void} />
            <RupeeField label="HRA (annual)" value={offerB.hra} onChange={set("hra") as (v: number) => void} />
            <RupeeField label="Special allowance" value={offerB.specialAllowance} onChange={set("specialAllowance") as (v: number) => void} />
            <RupeeField label="Variable pay" value={offerB.variablePay} onChange={set("variablePay") as (v: number) => void} />
            <RupeeField label="Employer PF" value={offerB.employerPF} onChange={set("employerPF") as (v: number) => void} />
            <RupeeField label="Gratuity" value={offerB.gratuity} onChange={set("gratuity") as (v: number) => void} />
          </div>
        </div>
      </div>

      <div className="fade-slide-up delay-2 mb-6">
        <button
          onClick={runComparison}
          disabled={loading}
          className="w-full bg-[#3730A3] text-white py-3 rounded-xl font-semibold text-sm hover:bg-[#312E81] transition-all shadow-md shadow-indigo-200 disabled:opacity-50"
        >
          {loading ? "AI is comparing these offers…" : result ? "Re-compare with AI →" : "Compare with AI →"}
        </button>
        {error && <p className="text-xs text-[#DC2626] mt-2">{error}</p>}
      </div>

      {result && (
        <>
          {/* AI Verdict */}
          <div className="fade-slide-up delay-2 bg-[#EEF2FF] border border-[#C7D2FE] rounded-2xl px-5 py-4 mb-6">
            <div className="flex items-start gap-3">
              <span className="text-xl shrink-0">🤖</span>
              <div>
                <div className="text-sm font-semibold text-[#3730A3] mb-1" style={{ fontFamily: "Manrope, sans-serif" }}>
                  AI verdict
                </div>
                <p className="text-xs text-[#64748B] leading-relaxed whitespace-pre-line">{result.verdict}</p>
              </div>
            </div>
          </div>

          {/* Comparison table */}
          <div className="fade-slide-up delay-3 bg-white border border-[#E2E5F0] rounded-2xl overflow-hidden mb-6">
            <div className="grid grid-cols-3 px-5 py-3 border-b border-[#F0F1F7] bg-[#F8F9FF]">
              <div className="text-xs font-semibold text-[#94A3B8]">Component</div>
              <div className="text-xs font-semibold text-[#94A3B8] text-center">Offer A</div>
              <div className="text-xs font-semibold text-[#94A3B8] text-center">Offer B</div>
            </div>
            <div className="divide-y divide-[#F0F1F7]">
              {rows.map((row, i) => (
                <div key={i} className="grid grid-cols-3 px-5 py-3 items-center">
                  <div className="text-sm text-[#64748B]">{row.label}</div>
                  <div className={`text-center text-sm font-medium ${row.winnerA ? "text-[#059669]" : "text-[#1A1D2E]"}`}>{row.a}</div>
                  <div className={`text-center text-sm font-medium ${row.winnerB ? "text-[#059669]" : "text-[#1A1D2E]"}`}>{row.b}</div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      <div className="fade-slide-up delay-4 flex gap-3">
        <button
          onClick={() => onNav("pf")}
          className="flex-1 bg-[#3730A3] text-white py-3 rounded-xl font-semibold text-sm hover:bg-[#312E81] transition-all shadow-md shadow-indigo-200"
        >
          View PF & Gratuity timeline →
        </button>
        <button
          onClick={() => onNav("breakdown")}
          className="px-5 py-3 border border-[#E2E5F0] rounded-xl text-sm text-[#64748B] hover:bg-[#F5F6FA] transition-colors"
        >
          ← Back
        </button>
      </div>
    </div>
  );
}
