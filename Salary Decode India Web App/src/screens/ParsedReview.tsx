import { useState } from "react";
import type { SalaryData } from "../data/sampleData";
import { fmt } from "../data/sampleData";
import type { BreakdownResponse, ExtractedField, ParsedOfferAI } from "../lib/types";

interface Props {
  data: SalaryData;
  parsed: ParsedOfferAI | null;
  breakdown: BreakdownResponse | null;
  loading: boolean;
  error: string | null;
  onCorrectField: (key: keyof SalaryData, value: number) => void;
  onContinue: () => void;
  onBack: () => void;
}

type SourceStatus = "found" | "estimated" | "missing";

interface Component {
  key: keyof SalaryData;
  label: string;
  annual: number;
  monthly: number;
  source: SourceStatus;
  sourceText?: string | null;
  page?: number | null;
}

const sourceChip = (s: SourceStatus) => {
  if (s === "found") return <span className="text-[10px] font-semibold bg-[#ECFDF5] text-[#059669] px-2 py-0.5 rounded-full">Found in offer</span>;
  if (s === "estimated") return <span className="text-[10px] font-semibold bg-[#EDE9FE] text-[#6D28D9] px-2 py-0.5 rounded-full">Low confidence</span>;
  return <span className="text-[10px] font-semibold bg-[#FFFBEB] text-[#B45309] px-2 py-0.5 rounded-full">Missing — add</span>;
};

/** confidence >= 0.85 -> found, >= 0.5 -> estimated (worth a second look), else missing */
function statusFromField(field: ExtractedField | null | undefined, hasValue: boolean): SourceStatus {
  if (!field) return hasValue ? "found" : "missing";
  if (field.value === null || field.value === undefined) return "missing";
  if (field.confidence >= 0.85) return "found";
  if (field.confidence >= 0.5) return "estimated";
  return "missing";
}

const RISK_STYLE: Record<string, string> = {
  high: "bg-[#FEE2E2] text-[#DC2626]",
  medium: "bg-[#FFFBEB] text-[#B45309]",
  low: "bg-[#ECFDF5] text-[#059669]",
};

function EditableAmount({ value, onSave }: { value: number; onSave: (v: number) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(value));

  if (editing) {
    return (
      <input
        autoFocus
        type="number"
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={() => { setEditing(false); onSave(Number(draft) || 0); }}
        onKeyDown={e => { if (e.key === "Enter") { setEditing(false); onSave(Number(draft) || 0); } }}
        className="w-24 text-right text-sm font-medium text-[#1A1D2E] bg-[#F5F6FA] border border-[#818CF8] rounded px-1"
      />
    );
  }
  return (
    <button
      onClick={() => { setDraft(String(value)); setEditing(true); }}
      className="text-right text-sm font-medium text-[#1A1D2E] hover:underline hover:text-[#3730A3] w-full"
      title="Click to correct"
    >
      {fmt(value)}
    </button>
  );
}

export default function ParsedReview({ data, parsed, breakdown, loading, error, onCorrectField, onContinue, onBack }: Props) {
  const components: Component[] = [
    { key: "basic", label: "Basic salary", annual: data.basic, monthly: Math.round(data.basic / 12),
      source: statusFromField(parsed?.basic, true), sourceText: parsed?.basic?.source_text, page: parsed?.basic?.page },
    { key: "hra", label: "HRA", annual: data.hra, monthly: Math.round(data.hra / 12),
      source: statusFromField(parsed?.hra, true), sourceText: parsed?.hra?.source_text, page: parsed?.hra?.page },
    { key: "specialAllowance", label: "Special allowance", annual: data.specialAllowance, monthly: Math.round(data.specialAllowance / 12),
      source: statusFromField(parsed?.special_allowance, true), sourceText: parsed?.special_allowance?.source_text, page: parsed?.special_allowance?.page },
    { key: "variablePay", label: "Variable / performance pay", annual: data.variablePay, monthly: Math.round(data.variablePay / 12),
      source: statusFromField(parsed?.bonus, true), sourceText: parsed?.bonus?.source_text, page: parsed?.bonus?.page },
    { key: "employerPF", label: "Employer PF contribution", annual: data.employerPF, monthly: Math.round(data.employerPF / 12),
      source: statusFromField(parsed?.employer_pf, true), sourceText: parsed?.employer_pf?.source_text, page: parsed?.employer_pf?.page },
    { key: "gratuity", label: "Gratuity (accrual per year)", annual: data.gratuity, monthly: Math.round(data.gratuity / 12),
      source: statusFromField(parsed?.gratuity, true), sourceText: parsed?.gratuity?.source_text, page: parsed?.gratuity?.page },
    { key: "healthInsurance", label: "Health insurance", annual: data.healthInsurance, monthly: Math.round(data.healthInsurance / 12),
      source: statusFromField(parsed?.health_insurance_premium, true), sourceText: parsed?.health_insurance_premium?.source_text, page: parsed?.health_insurance_premium?.page },
    { key: "employeePF", label: "Employee PF deduction", annual: data.employeePF, monthly: Math.round(data.employeePF / 12), source: "found" },
    { key: "professionalTax", label: "Professional tax", annual: data.professionalTax, monthly: Math.round(data.professionalTax / 12), source: "found" },
  ];

  const redFlags = breakdown?.red_flags ?? [];
  const ambiguities = parsed?.ambiguities ?? [];
  const contradictions = parsed?.contradictions ?? [];
  const clauses = parsed?.clauses ?? [];
  const severityStyle: Record<string, { icon: string; color: string }> = {
    critical: { icon: "🚩", color: "border-[#FECACA] bg-[#FEF2F2]" },
    warning: { icon: "⚠️", color: "border-[#FDE68A] bg-[#FFFBEB]" },
    info: { icon: "ℹ️", color: "border-[#E0E7FF] bg-[#EEF2FF]" },
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      {/* Header */}
      <div className="mb-8 fade-slide-up">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-[#ECFDF5] flex items-center justify-center text-xl">
            {parsed ? "🤖" : "✅"}
          </div>
          <div>
            <h1 className="text-xl font-bold text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>
              {parsed
                ? "AI read your offer letter. Please review before calculating."
                : "We found the main salary details. Please review before calculating."}
            </h1>
            <p className="text-sm text-[#64748B]">Click any amount to correct it — the analysis updates automatically.</p>
          </div>
        </div>

        {/* Summary cards */}
        <div className="grid sm:grid-cols-3 gap-4">
          <div className="bg-white border border-[#E2E5F0] rounded-2xl px-5 py-4">
            <div className="text-xs text-[#94A3B8] mb-1">Company</div>
            <div className="font-bold text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>{data.company}</div>
          </div>
          <div className="bg-white border border-[#E2E5F0] rounded-2xl px-5 py-4">
            <div className="text-xs text-[#94A3B8] mb-1">Annual CTC</div>
            <div className="font-bold text-2xl text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>{fmt(data.ctc)}</div>
          </div>
          <div className="bg-white border border-[#E2E5F0] rounded-2xl px-5 py-4">
            <div className="text-xs text-[#94A3B8] mb-1">Est. monthly in-hand</div>
            {loading ? (
              <div className="h-8 w-24 bg-[#F0F1F7] rounded-lg animate-pulse mt-1" />
            ) : error ? (
              <div className="text-xs text-[#DC2626]">{error}</div>
            ) : (
              <div className="font-bold text-2xl text-[#059669]" style={{ fontFamily: "Manrope, sans-serif" }}>
                {breakdown ? fmt(breakdown.breakdown.in_hand_monthly) : "—"}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Contradictions — deterministic consistency check, shown first since they need action */}
      {contradictions.length > 0 && (
        <div className="fade-slide-up mb-6 space-y-2">
          {contradictions.map((c, i) => (
            <div key={i} className="border border-[#FECACA] bg-[#FEF2F2] rounded-2xl p-4 flex items-start gap-2">
              <span className="text-base">⚠️</span>
              <p className="text-xs text-[#7F1D1D] leading-relaxed">{c.description}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Breakdown table */}
        <div className="lg:col-span-2 fade-slide-up delay-1 bg-white border border-[#E2E5F0] rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E2E5F0] flex items-center justify-between">
            <h2 className="font-semibold text-sm text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>Salary components</h2>
            <div className="flex items-center gap-3 text-[10px] text-[#64748B]">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#ECFDF5] border border-[#059669]" />Found</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#EDE9FE] border border-[#6D28D9]" />Low confidence</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#FFFBEB] border border-[#F59E0B]" />Missing</span>
            </div>
          </div>
          <div className="divide-y divide-[#F0F1F7]">
            <div className="grid grid-cols-4 px-5 py-2 text-[10px] font-semibold text-[#94A3B8] uppercase tracking-wider">
              <div className="col-span-2">Component</div>
              <div className="text-right">Monthly</div>
              <div className="text-right">Annual (click to fix)</div>
            </div>
            {components.map((row, i) => (
              <div key={i} className="grid grid-cols-4 px-5 py-3 items-start hover:bg-[#F8F9FF] transition-colors">
                <div className="col-span-2">
                  <div className="text-sm text-[#1A1D2E]">{row.label}</div>
                  <div className="mt-0.5">{sourceChip(row.source)}</div>
                  {row.sourceText && (
                    <div className="text-[10px] text-[#94A3B8] mt-1 italic">
                      "{row.sourceText}"{row.page ? ` — page ${row.page}` : ""}
                    </div>
                  )}
                </div>
                <div className="text-right text-sm font-medium text-[#1A1D2E]">{fmt(row.monthly)}</div>
                <EditableAmount value={row.annual} onSave={v => onCorrectField(row.key, v)} />
              </div>
            ))}
          </div>
        </div>

        {/* Red flags + ambiguities panel */}
        <div className="fade-slide-up delay-2 space-y-3">
          <h2 className="font-semibold text-sm text-[#1A1D2E] px-1" style={{ fontFamily: "Manrope, sans-serif" }}>Things worth checking</h2>

          {ambiguities.map((a, i) => (
            <div key={`amb-${i}`} className="border border-[#C7D2FE] bg-[#EEF2FF] rounded-2xl p-4">
              <div className="flex items-start gap-2 mb-2">
                <span className="text-base">❓</span>
                <div className="flex-1">
                  <div className="text-xs font-semibold text-[#1A1D2E]">{a.question}</div>
                </div>
              </div>
              <p className="text-xs text-[#64748B] leading-relaxed">{a.reason}</p>
            </div>
          ))}

          {redFlags.map((flag, i) => {
            const style = severityStyle[flag.severity] ?? severityStyle.info;
            return (
              <div key={`flag-${i}`} className={`border rounded-2xl p-4 ${style.color}`}>
                <div className="flex items-start gap-2 mb-2">
                  <span className="text-base">{style.icon}</span>
                  <div className="flex-1">
                    <div className="text-xs font-semibold text-[#1A1D2E] capitalize">
                      {flag.field.replace(/_/g, " ")}
                    </div>
                  </div>
                </div>
                <p className="text-xs text-[#64748B] leading-relaxed">{flag.message}</p>
              </div>
            );
          })}

          {ambiguities.length === 0 && redFlags.length === 0 && !loading && (
            <div className="bg-[#F5F6FA] border border-[#E2E5F0] rounded-2xl p-4 text-xs text-[#94A3B8] leading-relaxed">
              No red flags or ambiguities detected in this offer.
            </div>
          )}
        </div>
      </div>

      {/* Clause intelligence */}
      {clauses.length > 0 && (
        <div className="fade-slide-up delay-2 mt-6 bg-white border border-[#E2E5F0] rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E2E5F0]">
            <h2 className="font-semibold text-sm text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>
              Employment clauses found in the letter
            </h2>
            <p className="text-[10px] text-[#94A3B8] mt-0.5">AI-identified — not legal advice.</p>
          </div>
          <div className="divide-y divide-[#F0F1F7]">
            {clauses.map((c, i) => (
              <div key={i} className="px-5 py-4">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${RISK_STYLE[c.risk_level]}`}>
                    {c.risk_level} risk
                  </span>
                  <span className="text-xs font-semibold text-[#1A1D2E] capitalize">{c.clause_type.replace(/_/g, " ")}</span>
                  {c.page && <span className="text-[10px] text-[#94A3B8]">page {c.page}</span>}
                </div>
                <p className="text-xs text-[#64748B] italic mb-1">"{c.quote}"</p>
                <p className="text-xs text-[#374151] leading-relaxed">{c.interpretation}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="fade-slide-up delay-3 flex gap-3 mt-6">
        <button
          onClick={onBack}
          className="px-5 py-3 border border-[#E2E5F0] rounded-xl text-sm text-[#64748B] hover:bg-[#F5F6FA] transition-colors"
        >
          ← Edit details
        </button>
        <button
          onClick={onContinue}
          className="flex-1 bg-[#3730A3] text-white py-3 rounded-xl font-semibold text-sm hover:bg-[#312E81] transition-all shadow-md shadow-indigo-200"
        >
          Continue to salary breakdown →
        </button>
      </div>
    </div>
  );
}
