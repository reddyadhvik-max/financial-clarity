import { useState, useEffect } from "react";
import type { SalaryData } from "../data/sampleData";
import { fmt } from "../data/sampleData";
import { fetchBreakdown } from "../lib/api";
import { salaryDataToCtcBreakup } from "../lib/mapping";
import type { InHandBreakdown, TaxBracket } from "../lib/types";

interface Props {
  data: SalaryData;
  onNav: (s: string) => void;
}

const BRACKET_COLORS = ["#E2E5F0", "#C7D2FE", "#A5B4FC", "#818CF8", "#6366F1", "#4338CA"];

/** Horizontal tax-bracket ladder — one segment per slab, sized by taxable amount. */
function TaxBracketLadder({ brackets }: { brackets: TaxBracket[] }) {
  const active = brackets.filter(b => b.taxable_amount_in_bracket > 0);
  if (active.length === 0) return null;
  return (
    <div>
      <div className="flex h-8 rounded-lg overflow-hidden mb-2">
        {active.map((b, i) => (
          <div
            key={i}
            style={{ width: `${(b.taxable_amount_in_bracket / active.reduce((s, x) => s + x.taxable_amount_in_bracket, 0)) * 100}%`, background: BRACKET_COLORS[i % BRACKET_COLORS.length] }}
            className="flex items-center justify-center text-[10px] font-semibold text-[#1A1D2E]"
            title={`${(b.rate * 100).toFixed(0)}% on ${fmt(b.taxable_amount_in_bracket)}`}
          >
            {(b.rate * 100).toFixed(0)}%
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-[#94A3B8]">
        {active.map((b, i) => (
          <span key={i}>{(b.rate * 100).toFixed(0)}%: {fmt(b.tax_in_bracket)}</span>
        ))}
      </div>
    </div>
  );
}

/** Debounces a value — used so slider drags don't fire a request per pixel. */
function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const handle = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(handle);
  }, [value, delayMs]);
  return debounced;
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
  prefix,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  prefix?: string;
}) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="text-xs font-medium text-[#374151]">{label}</label>
        <div className="relative">
          <span className="absolute left-2 top-1/2 -translate-y-1/2 text-[#94A3B8] text-xs">{prefix}</span>
          <input
            type="number"
            value={value}
            min={min}
            max={max}
            onChange={e => onChange(Math.min(max, Math.max(min, Number(e.target.value))))}
            className="w-28 pl-5 pr-2 py-1.5 bg-[#F5F6FA] border border-[#E2E5F0] rounded-lg text-xs text-right focus:outline-none focus:ring-2 focus:ring-[#818CF8]"
          />
        </div>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        style={{
          background: `linear-gradient(to right, #3730A3 ${pct}%, #E2E5F0 ${pct}%)`,
        }}
        className="w-full"
      />
      <div className="flex justify-between text-[10px] text-[#94A3B8] mt-1">
        <span>{prefix}{min.toLocaleString("en-IN")}</span>
        <span>{prefix}{max.toLocaleString("en-IN")}</span>
      </div>
    </div>
  );
}

export default function TaxScenarios({ data, onNav }: Props) {
  const [regime, setRegime] = useState<"old" | "new">("new");
  const [c80, setC80] = useState(data.section80C);
  const [c80d, setC80d] = useState(data.section80D);
  const [rent, setRent] = useState(data.monthlyRent);

  const [newBreakdown, setNewBreakdown] = useState<InHandBreakdown | null>(null);
  const [oldBreakdown, setOldBreakdown] = useState<InHandBreakdown | null>(null);
  const [error, setError] = useState<string | null>(null);

  // New regime doesn't depend on the deduction sliders — fetch once per offer.
  useEffect(() => {
    fetchBreakdown(salaryDataToCtcBreakup({ ...data, regime: "new" }), "new")
      .then(r => setNewBreakdown(r.breakdown))
      .catch(() => setError("Couldn't reach the calculation engine."));
  }, [data]);

  // Old regime depends on the sliders — debounce so dragging doesn't spam requests.
  const debouncedC80 = useDebounced(c80, 350);
  const debouncedC80d = useDebounced(c80d, 350);
  const debouncedRent = useDebounced(rent, 350);
  useEffect(() => {
    fetchBreakdown(
      salaryDataToCtcBreakup({ ...data, regime: "old", section80C: debouncedC80, section80D: debouncedC80d, monthlyRent: debouncedRent }),
      "old",
    )
      .then(r => setOldBreakdown(r.breakdown))
      .catch(() => setError("Couldn't reach the calculation engine."));
  }, [data, debouncedC80, debouncedC80d, debouncedRent]);

  const scenario = regime === "new" ? newBreakdown : oldBreakdown;
  const bestRegime = oldBreakdown && newBreakdown
    ? (oldBreakdown.in_hand_monthly >= newBreakdown.in_hand_monthly ? "old" : "new")
    : null;
  const bestDiff = oldBreakdown && newBreakdown ? Math.abs(oldBreakdown.in_hand_monthly - newBreakdown.in_hand_monthly) : 0;
  const diff = scenario && newBreakdown ? scenario.in_hand_monthly - newBreakdown.in_hand_monthly : 0;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      <div className="fade-slide-up mb-6">
        <h1 className="text-2xl font-bold text-[#1A1D2E] mb-1" style={{ fontFamily: "Manrope, sans-serif" }}>
          Explore your take-home
        </h1>
        <p className="text-sm text-[#94A3B8]">
          Adjust your tax inputs and see how your estimated in-hand changes in real time.
          This is an estimate — not tax advice.
        </p>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Left: controls */}
        <div className="lg:col-span-2 space-y-6">
          {/* Regime toggle */}
          <div className="fade-slide-up delay-1 bg-white border border-[#E2E5F0] rounded-2xl p-5">
            <h2 className="font-semibold text-sm text-[#1A1D2E] mb-4" style={{ fontFamily: "Manrope, sans-serif" }}>Tax regime</h2>
            <div className="grid sm:grid-cols-2 gap-3">
              {(["new", "old"] as const).map(r => (
                <button
                  key={r}
                  onClick={() => setRegime(r)}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    regime === r
                      ? "border-[#3730A3] bg-[#EEF2FF]"
                      : "border-[#E2E5F0] bg-white hover:border-[#C7D2FE]"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className={`text-xs font-bold ${regime === r ? "text-[#3730A3]" : "text-[#64748B]"}`}>
                      {r === "new" ? "New regime" : "Old regime"}
                    </div>
                    {bestRegime === r && (
                      <span className="text-[10px] font-semibold bg-[#ECFDF5] text-[#059669] px-2 py-0.5 rounded-full">
                        Best for you
                      </span>
                    )}
                  </div>
                  <div className="text-lg font-bold text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>
                    {(() => {
                      const b = r === "new" ? newBreakdown : oldBreakdown;
                      return b ? fmt(b.in_hand_monthly) : "…";
                    })()}
                    <span className="text-xs font-normal text-[#94A3B8] ml-1">/mo</span>
                  </div>
                  <div className="text-[10px] text-[#94A3B8] mt-1">
                    {r === "new"
                      ? "Higher standard deduction (₹75K), simpler. No exemptions."
                      : "Allows HRA, 80C, 80D exemptions. Better with high deductions."}
                  </div>
                </button>
              ))}
            </div>

            {bestDiff > 0 && (
              <div className="mt-3 bg-[#ECFDF5] border border-[#A7F3D0] rounded-xl px-4 py-3 text-xs text-[#059669]">
                <span className="font-semibold">Best estimated option: </span>
                The {bestRegime} regime gives you {fmt(bestDiff)} more per month based on your entered deductions.
                {bestRegime === "old" && " This assumes your rent, 80C, and 80D claims are valid."}
              </div>
            )}
          </div>

          {/* Deduction sliders */}
          {regime === "old" && (
            <div className="fade-slide-up delay-2 bg-white border border-[#E2E5F0] rounded-2xl p-5 space-y-6">
              <h2 className="font-semibold text-sm text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>
                Deductions and exemptions
              </h2>
              <Slider
                label="Section 80C contributions (PF, ELSS, PPF, life insurance)"
                value={c80}
                min={0}
                max={150000}
                step={5000}
                onChange={setC80}
                prefix="₹"
              />
              <Slider
                label="Section 80D health insurance premium"
                value={c80d}
                min={0}
                max={50000}
                step={1000}
                onChange={setC80d}
                prefix="₹"
              />
              <Slider
                label="Monthly rent paid"
                value={rent}
                min={0}
                max={80000}
                step={1000}
                onChange={setRent}
                prefix="₹"
              />
              <p className="text-[10px] text-[#94A3B8]">
                Employee NPS contributions (Section 80CCD(1B)) aren't modelled by the calculation
                engine yet, so that input isn't shown here rather than guessing at its effect.
              </p>
            </div>
          )}

          {/* Reasoning card */}
          <div className="fade-slide-up delay-3 bg-[#F8F9FF] border border-[#E2E5F0] rounded-2xl p-5">
            <h3 className="font-semibold text-xs text-[#3730A3] mb-3" style={{ fontFamily: "Manrope, sans-serif" }}>
              How the engine computed this
            </h3>
            {!scenario ? (
              <p className="text-xs text-[#94A3B8]">Calculating…</p>
            ) : (
              <div className="space-y-3 text-xs text-[#64748B] leading-relaxed">
                <TaxBracketLadder brackets={scenario.tax_breakdown.brackets} />
                {regime === "old" ? (
                  <>
                    <p>• Taxable income starts from your total gross salary (basic + HRA + special allowance).</p>
                    {scenario.hra_exemption_amount > 0 && <p>• HRA exemption of {fmt(scenario.hra_exemption_amount)} applied based on your rent and basic salary.</p>}
                    {c80 > 0 && <p>• 80C deduction: {fmt(Math.min(c80, 150000))} (capped at ₹1,50,000).</p>}
                    {c80d > 0 && <p>• 80D deduction: {fmt(Math.min(c80d, 25000))} (capped at ₹25,000 for self + family).</p>}
                    <p>• Standard deduction of {fmt(scenario.std_deduction_amount)} applied.</p>
                    <p>• Taxable income after deductions: {fmt(scenario.taxable_income)}.</p>
                  </>
                ) : (
                  <>
                    <p>• New regime: standard deduction of {fmt(scenario.std_deduction_amount)}. No HRA, 80C, or 80D exemptions.</p>
                    <p>• Taxable income: {fmt(scenario.taxable_income)}.</p>
                  </>
                )}
                {scenario.tax_breakdown.brackets.map((b, i) => (
                  <p key={i}>• {fmt(b.taxable_amount_in_bracket)} taxed at {(b.rate * 100).toFixed(0)}% = {fmt(b.tax_in_bracket)}.</p>
                ))}
                {scenario.tax_breakdown.rebate_amount > 0 && (
                  <p>• Section 87A rebate of {fmt(scenario.tax_breakdown.rebate_amount)} applied.</p>
                )}
                <p>• 4% health and education cess: {fmt(scenario.tax_breakdown.cess_amount)}.</p>
                <p>• Estimated annual tax: {fmt(scenario.tax_breakdown.total_tax)} | Monthly TDS: {fmt(Math.round(scenario.tax_breakdown.total_tax / 12))}.</p>
              </div>
            )}
          </div>
        </div>

        {/* Right: sticky result */}
        <div className="fade-slide-up delay-2">
          <div className="sticky top-20">
            <div className="bg-white border border-[#E2E5F0] rounded-2xl p-5 shadow-sm">
              <div className="text-xs text-[#94A3B8] mb-1 uppercase tracking-wider">Estimated monthly in-hand</div>
              {!scenario ? (
                <div className="h-10 w-32 bg-[#F0F1F7] rounded-lg animate-pulse mb-1" />
              ) : (
                <div className="text-4xl font-bold text-[#059669] count-up mb-1" style={{ fontFamily: "Manrope, sans-serif" }}>
                  {fmt(scenario.in_hand_monthly)}
                </div>
              )}
              {scenario && diff !== 0 && (
                <div className={`text-xs font-semibold mb-4 ${diff > 0 ? "text-[#059669]" : "text-[#DC2626]"}`}>
                  {diff > 0 ? "+" : ""}{fmt(diff)}/month vs new regime default
                </div>
              )}
              {error && <div className="text-xs text-[#DC2626] mb-4">{error}</div>}

              {scenario && (
                <div className="space-y-3 mt-4 pt-4 border-t border-[#F0F1F7]">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#64748B]">Estimated annual tax</span>
                    <span className="text-sm font-semibold text-[#1A1D2E] count-up">{fmt(scenario.tax_breakdown.total_tax)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#64748B]">Monthly TDS</span>
                    <span className="text-sm font-semibold text-[#1A1D2E] count-up">{fmt(Math.round(scenario.tax_breakdown.total_tax / 12))}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#64748B]">Taxable income</span>
                    <span className="text-sm font-semibold text-[#1A1D2E] count-up">{fmt(scenario.taxable_income)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-[#64748B]">Annual take-home</span>
                    <span className="text-sm font-semibold text-[#059669] count-up">{fmt(scenario.in_hand_annual)}</span>
                  </div>
                </div>
              )}

              <div className="mt-4 pt-4 border-t border-[#F0F1F7] text-[10px] text-[#94A3B8] leading-relaxed">
                Computed by the same rule-versioned tax engine as the rest of this app. Not tax advice.
              </div>
            </div>

            <div className="flex gap-2 mt-3">
              <button
                onClick={() => onNav("spendable")}
                className="flex-1 bg-[#3730A3] text-white py-2.5 rounded-xl text-xs font-semibold hover:bg-[#312E81] transition-all"
              >
                Plan budget →
              </button>
              <button
                onClick={() => onNav("breakdown")}
                className="px-4 py-2.5 border border-[#E2E5F0] rounded-xl text-xs text-[#64748B] hover:bg-[#F5F6FA] transition-colors"
              >
                ← Back
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
