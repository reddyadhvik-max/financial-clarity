import { useState, useMemo, useEffect } from "react";
import type { SalaryData } from "../data/sampleData";
import { fmt } from "../data/sampleData";
import { ApiError, fetchGratuityTimeline } from "../lib/api";
import type { GratuityEpfTimeline } from "../lib/types";

interface Props {
  data: SalaryData;
  onNav: (s: string) => void;
}

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${MONTH_NAMES[d.getMonth()]} ${d.getFullYear()}`;
}

export default function PFGratuity({ data, onNav }: Props) {
  const today = new Date();
  const todayStr = today.toISOString().split("T")[0];
  const exitDefault = new Date(today);
  exitDefault.setFullYear(exitDefault.getFullYear() + 5);

  const [joiningDate, setJoiningDate] = useState(todayStr);
  const [exitDate, setExitDate] = useState(exitDefault.toISOString().split("T")[0]);
  const [basic, setBasic] = useState(Math.round(data.basic / 12));
  const [empPFMonthly, setEmpPFMonthly] = useState(Math.round(data.employeePF / 12));

  const [timeline, setTimeline] = useState<GratuityEpfTimeline | null>(null);
  const [timelineError, setTimelineError] = useState<string | null>(null);

  // Debounced — this is the real, rule-versioned engine call (vesting
  // thresholds come from data/rules.json, not hardcoded here).
  useEffect(() => {
    if (!joiningDate || !exitDate) return;
    const handle = setTimeout(() => {
      setTimelineError(null);
      fetchGratuityTimeline(joiningDate, { separationDate: exitDate })
        .then(setTimeline)
        .catch(err => {
          setTimeline(null);
          setTimelineError(err instanceof ApiError ? "Couldn't compute the timeline for these dates." : "Couldn't reach the backend.");
        });
    }, 350);
    return () => clearTimeout(handle);
  }, [joiningDate, exitDate]);

  // Rupee projections (gratuity payout, PF corpus with assumed interest) are
  // inherently a future estimate — the engine only tells us eligibility
  // dates via rule_ids, not a compounded-interest projection. We use the
  // real `tenure_years`/`vested` outcome from the backend once it's loaded,
  // and fall back to local date math only while that request is in flight.
  const { months, gratuityAmount, pfWithInterest, eligible } = useMemo(() => {
    const joining = new Date(joiningDate);
    const exit = new Date(exitDate);
    const localMonths = Math.max(0, (exit.getFullYear() - joining.getFullYear()) * 12 + (exit.getMonth() - joining.getMonth()));
    const months = timeline ? Math.round(timeline.tenure_years * 12) : localMonths;
    const years = months / 12;
    const eligible = timeline ? timeline.gratuity.vested : localMonths >= 60;

    const gratuityAmount = eligible ? Math.round((basic * 15 * Math.floor(years)) / 26) : 0;
    const monthlyPF = empPFMonthly + Math.round(data.employerPF / 12);
    const pfTotal = monthlyPF * months;
    const pfWithInterest = Math.round(pfTotal * Math.pow(1 + 0.0825 / 12, months));

    return { months, gratuityAmount, pfWithInterest, eligible };
  }, [joiningDate, exitDate, basic, empPFMonthly, data, timeline]);

  const yearsServed = Math.floor(months / 12);
  const monthsServed = months % 12;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
      <div className="fade-slide-up mb-6">
        <h1 className="text-2xl font-bold text-[#1A1D2E] mb-1" style={{ fontFamily: "Manrope, sans-serif" }}>
          PF & Gratuity timeline
        </h1>
        <p className="text-sm text-[#94A3B8]">
          See when you will be eligible for gratuity and estimate your EPF corpus at exit.
        </p>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Inputs */}
        <div className="fade-slide-up delay-1 bg-white border border-[#E2E5F0] rounded-2xl p-5 space-y-4">
          <h2 className="font-semibold text-sm text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>Your details</h2>

          {[
            { label: "Date of joining", type: "date", value: joiningDate, onChange: setJoiningDate },
            { label: "Expected exit date", type: "date", value: exitDate, onChange: setExitDate },
          ].map((f, i) => (
            <div key={i}>
              <label className="text-xs font-medium text-[#374151] block mb-1">{f.label}</label>
              <input
                type="date"
                value={f.value}
                onChange={e => f.onChange(e.target.value)}
                className="w-full px-3 py-2 bg-[#F5F6FA] border border-[#E2E5F0] rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#818CF8] transition-all"
              />
            </div>
          ))}

          <div>
            <label className="text-xs font-medium text-[#374151] block mb-1">Monthly basic salary</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8] text-sm">₹</span>
              <input
                type="number"
                value={basic || ""}
                onChange={e => setBasic(Number(e.target.value))}
                className="w-full pl-7 pr-3 py-2 bg-[#F5F6FA] border border-[#E2E5F0] rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#818CF8]"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-[#374151] block mb-1">Employee PF (monthly contribution)</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8] text-sm">₹</span>
              <input
                type="number"
                value={empPFMonthly || ""}
                onChange={e => setEmpPFMonthly(Number(e.target.value))}
                className="w-full pl-7 pr-3 py-2 bg-[#F5F6FA] border border-[#E2E5F0] rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#818CF8]"
              />
            </div>
          </div>
        </div>

        {/* Results + Timeline */}
        <div className="lg:col-span-2 space-y-4">
          {/* Summary cards */}
          <div className="fade-slide-up delay-2 grid sm:grid-cols-3 gap-3">
            <div className="bg-white border border-[#E2E5F0] rounded-2xl px-4 py-4">
              <div className="text-xs text-[#94A3B8] mb-1">Service duration</div>
              <div className="font-bold text-[#1A1D2E] text-lg" style={{ fontFamily: "Manrope, sans-serif" }}>
                {yearsServed}y {monthsServed}m
              </div>
            </div>
            <div className={`border rounded-2xl px-4 py-4 ${eligible ? "bg-[#ECFDF5] border-[#A7F3D0]" : "bg-white border-[#E2E5F0]"}`}>
              <div className="text-xs text-[#94A3B8] mb-1">Gratuity eligibility</div>
              <div className={`font-bold text-lg ${eligible ? "text-[#059669]" : "text-[#B45309]"}`} style={{ fontFamily: "Manrope, sans-serif" }}>
                {eligible
                  ? "Eligible ✓"
                  : (() => {
                      const vestingDate = timeline?.milestones.find(m => m.label.startsWith("Gratuity Vesting"))?.date;
                      return vestingDate ? formatDate(vestingDate) : "—";
                    })()}
              </div>
              {!eligible && <div className="text-[10px] text-[#94A3B8]">Not yet eligible</div>}
            </div>
            <div className="bg-[#EEF2FF] border border-[#C7D2FE] rounded-2xl px-4 py-4">
              <div className="text-xs text-[#94A3B8] mb-1">EPF corpus at exit</div>
              <div className="font-bold text-[#3730A3] text-lg count-up" style={{ fontFamily: "Manrope, sans-serif" }}>
                ~{fmt(pfWithInterest)}
              </div>
            </div>
          </div>

          {eligible && (
            <div className="fade-slide-up delay-2 bg-[#ECFDF5] border border-[#A7F3D0] rounded-2xl px-5 py-4">
              <div className="flex items-start gap-3">
                <span className="text-xl">🎉</span>
                <div>
                  <div className="font-semibold text-sm text-[#059669] mb-1" style={{ fontFamily: "Manrope, sans-serif" }}>
                    Estimated gratuity: {fmt(gratuityAmount)}
                  </div>
                  <p className="text-xs text-[#64748B] leading-relaxed">
                    Based on {yearsServed} completed years of service. Formula: (Monthly basic × 15 × Years) ÷ 26.
                    Actual gratuity depends on your employer's policy, applicable law, and any amendments.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Timeline — from the backend's rule-versioned engine, not hardcoded thresholds */}
          <div className="fade-slide-up delay-3 bg-white border border-[#E2E5F0] rounded-2xl p-5">
            <h2 className="font-semibold text-sm text-[#1A1D2E] mb-5" style={{ fontFamily: "Manrope, sans-serif" }}>Timeline</h2>
            {timelineError ? (
              <p className="text-xs text-[#DC2626]">{timelineError}</p>
            ) : !timeline ? (
              <div className="h-24 flex items-center justify-center">
                <div className="w-6 h-6 border-2 border-[#C7D2FE] border-t-[#3730A3] rounded-full animate-spin" />
              </div>
            ) : (
              <div className="relative">
                <div className="absolute left-3.5 top-4 bottom-4 w-px bg-[#E2E5F0]" />
                <div className="space-y-6">
                  {timeline.milestones.map((m, i) => (
                    <div key={i} className="flex gap-4 relative">
                      <div className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center ${m.status === "past" ? "bg-[#818CF8]" : "bg-[#E2E5F0]"} relative z-10`}>
                        <div className="w-2.5 h-2.5 rounded-full bg-white" />
                      </div>
                      <div className="pt-0.5 pb-2">
                        <div className="text-xs font-semibold text-[#94A3B8] mb-0.5">{formatDate(m.date)}</div>
                        <div className="text-sm font-semibold text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>{m.label}</div>
                      </div>
                    </div>
                  ))}
                  <div className="flex gap-4 relative">
                    <div className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center ${eligible ? "bg-[#059669]" : "bg-[#94A3B8]"} relative z-10`}>
                      <div className="w-2.5 h-2.5 rounded-full bg-white" />
                    </div>
                    <div className="pt-0.5 pb-2">
                      <div className="text-xs font-semibold text-[#94A3B8] mb-0.5">{formatDate(timeline.evaluation_date)}</div>
                      <div className="text-sm font-semibold text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>Exit date</div>
                      <p className="text-xs text-[#64748B] leading-relaxed mt-0.5">
                        {timeline.gratuity.note} PF balance with ~8.25% assumed interest: ~{fmt(pfWithInterest)}.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Callouts */}
          <div className="fade-slide-up delay-4 grid sm:grid-cols-2 gap-3">
            <div className="bg-[#EEF2FF] border border-[#C7D2FE] rounded-2xl p-4 text-xs text-[#64748B] leading-relaxed">
              <div className="font-semibold text-[#3730A3] mb-1">About EPF transfers</div>
              Your EPF balance stays with you when you change jobs. Transfer it to your new employer's PF account using your UAN — do not withdraw it early (withdrawals before 5 years attract tax).
            </div>
            <div className="bg-[#FFFBEB] border border-[#FDE68A] rounded-2xl p-4 text-xs text-[#64748B] leading-relaxed">
              <div className="font-semibold text-[#B45309] mb-1">About gratuity</div>
              Gratuity is payable under the Payment of Gratuity Act, 1972. Private sector employees need 5 years of continuous service. Calculations here are indicative — your employer's policy may differ.
            </div>
          </div>

          <div className="fade-slide-up delay-5 text-[10px] text-[#94A3B8] px-1 leading-relaxed">
            All figures are estimates based on your inputs and standard assumptions. PF interest rate (8.25%) and gratuity rules may change. This is not legal or financial advice.
          </div>
        </div>
      </div>

      <div className="mt-6 fade-slide-up delay-5 flex gap-3">
        <button
          onClick={() => onNav("landing")}
          className="px-5 py-3 bg-[#3730A3] text-white rounded-xl font-semibold text-sm hover:bg-[#312E81] transition-all shadow-md shadow-indigo-200"
        >
          Start a new analysis
        </button>
        <button
          onClick={() => onNav("compare")}
          className="px-5 py-3 border border-[#E2E5F0] rounded-xl text-sm text-[#64748B] hover:bg-[#F5F6FA] transition-colors"
        >
          ← Compare offers
        </button>
      </div>
    </div>
  );
}
