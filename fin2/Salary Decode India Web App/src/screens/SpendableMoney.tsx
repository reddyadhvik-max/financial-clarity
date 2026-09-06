import { useState, useMemo } from "react";
import { fmt } from "../data/sampleData";

interface Props {
  inHandMonthly: number;
  onNav: (s: string) => void;
}

const expenseCategories = [
  { key: "rent", label: "Rent / housing", icon: "🏠", default: 22000 },
  { key: "emi", label: "Loan EMIs", icon: "🏦", default: 0 },
  { key: "insurance", label: "Insurance premiums", icon: "🛡️", default: 1500 },
  { key: "groceries", label: "Groceries & essentials", icon: "🛒", default: 8000 },
  { key: "utilities", label: "Utilities & bills", icon: "💡", default: 2500 },
  { key: "transport", label: "Transport & fuel", icon: "🚗", default: 4000 },
  { key: "mobile", label: "Mobile & internet", icon: "📱", default: 800 },
  { key: "family", label: "Family support", icon: "👨‍👩‍👧", default: 0 },
  { key: "savings", label: "Investments / savings", icon: "💰", default: 5000 },
  { key: "other", label: "Other fixed expenses", icon: "📦", default: 3000 },
];

function ExpenseRow({
  icon,
  label,
  value,
  onChange,
}: {
  icon: string;
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xl w-7 shrink-0">{icon}</span>
      <div className="flex-1 text-sm text-[#1A1D2E] truncate">{label}</div>
      <div className="relative w-32 shrink-0">
        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8] text-xs">₹</span>
        <input
          type="number"
          value={value || ""}
          onChange={e => onChange(Number(e.target.value) || 0)}
          placeholder="0"
          className="w-full pl-6 pr-2 py-1.5 bg-[#F5F6FA] border border-[#E2E5F0] rounded-lg text-xs text-right focus:outline-none focus:ring-2 focus:ring-[#818CF8] transition-all"
        />
      </div>
    </div>
  );
}

export default function SpendableMoney({ inHandMonthly, onNav }: Props) {
  const inHand = inHandMonthly;

  const [expenses, setExpenses] = useState<Record<string, number>>(
    Object.fromEntries(expenseCategories.map(c => [c.key, c.default]))
  );

  const set = (key: string) => (v: number) => setExpenses(prev => ({ ...prev, [key]: v }));

  const totalFixed = useMemo(() => Object.values(expenses).reduce((a, b) => a + b, 0), [expenses]);
  const buffer = inHand - totalFixed;
  const emiAmt = expenses.emi;
  const emiPct = Math.round((emiAmt / inHand) * 100);
  const savePct = Math.round((expenses.savings / inHand) * 100);
  const bufferPct = Math.round((buffer / inHand) * 100);
  const emergencyFund = inHand * 6;

  const insights: { text: string; color: string; icon: string }[] = [];
  if (emiPct > 40) insights.push({ text: `Your loan EMIs use ${emiPct}% of estimated in-hand. Lenders typically cap this at 40%.`, color: "border-[#FEE2E2] bg-[#FFF5F5]", icon: "⚠️" });
  if (bufferPct < 10 && buffer > 0) insights.push({ text: "Your fixed commitments leave less than 10% as a free buffer. Consider reviewing subscriptions or variable expenses.", color: "border-[#FFFBEB] bg-[#FFFBEB]", icon: "🔔" });
  if (expenses.savings === 0) insights.push({ text: "You have not added an emergency-fund or savings allocation. A good starting point is 10–20% of in-hand.", color: "border-[#FDE68A] bg-[#FFFBEB]", icon: "💡" });
  if (buffer < 0) insights.push({ text: "Your expenses exceed your estimated in-hand. Review your budget — something may need adjusting.", color: "border-[#FEE2E2] bg-[#FFF5F5]", icon: "🚨" });

  // Donut-style composition bars
  const segments = [
    { label: "Fixed expenses", value: totalFixed - expenses.emi, color: "bg-[#818CF8]" },
    { label: "Loan EMIs", value: expenses.emi, color: "bg-[#FCA5A5]" },
    { label: "Savings", value: expenses.savings, color: "bg-[#6EE7B7]" },
    { label: "Free buffer", value: Math.max(0, buffer - expenses.savings), color: "bg-[#BAE6FD]" },
  ].filter(s => s.value > 0);
  const total = segments.reduce((a, s) => a + s.value, 0);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      <div className="fade-slide-up mb-6">
        <h1 className="text-2xl font-bold text-[#1A1D2E] mb-1" style={{ fontFamily: "Manrope, sans-serif" }}>
          What is actually left after your monthly commitments?
        </h1>
        <p className="text-sm text-[#94A3B8]">
          Based on an estimated in-hand of <span className="font-semibold text-[#3730A3]">{fmt(inHand)}/month</span>
        </p>
      </div>

      <div className="grid lg:grid-cols-5 gap-6">
        {/* Expense inputs */}
        <div className="lg:col-span-3 fade-slide-up delay-1 bg-white border border-[#E2E5F0] rounded-2xl p-5">
          <h2 className="font-semibold text-sm text-[#1A1D2E] mb-5" style={{ fontFamily: "Manrope, sans-serif" }}>
            Monthly expenses
          </h2>
          <div className="space-y-4">
            {expenseCategories.map(cat => (
              <ExpenseRow
                key={cat.key}
                icon={cat.icon}
                label={cat.label}
                value={expenses[cat.key]}
                onChange={set(cat.key)}
              />
            ))}
          </div>
          <div className="flex items-center justify-between pt-4 mt-4 border-t border-[#F0F1F7]">
            <span className="text-sm font-semibold text-[#1A1D2E]">Total monthly expenses</span>
            <span className="text-sm font-bold text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>{fmt(totalFixed)}</span>
          </div>
        </div>

        {/* Right panel */}
        <div className="lg:col-span-2 space-y-4">
          {/* Composition bar */}
          <div className="fade-slide-up delay-2 bg-white border border-[#E2E5F0] rounded-2xl p-5">
            <h3 className="font-semibold text-sm text-[#1A1D2E] mb-4" style={{ fontFamily: "Manrope, sans-serif" }}>
              Monthly in-hand split
            </h3>

            {/* Stacked bar */}
            <div className="h-5 rounded-full overflow-hidden flex mb-3">
              {segments.map((s, i) => (
                <div
                  key={i}
                  className={`${s.color} transition-all`}
                  style={{ width: `${(s.value / inHand) * 100}%` }}
                  title={`${s.label}: ${fmt(s.value)}`}
                />
              ))}
              {buffer < 0 && (
                <div className="bg-[#FCA5A5] flex-1" />
              )}
            </div>
            <div className="flex flex-wrap gap-2 mb-5">
              {segments.map((s, i) => (
                <div key={i} className="flex items-center gap-1 text-[10px] text-[#64748B]">
                  <span className={`w-2 h-2 rounded-full ${s.color}`} />
                  {s.label}
                </div>
              ))}
            </div>

            {/* Summary rows */}
            <div className="space-y-3">
              {[
                { label: "Monthly in-hand salary", value: inHand, bold: false, color: "text-[#1A1D2E]" },
                { label: "Total fixed expenses", value: -totalFixed, bold: false, color: "text-[#DC2626]" },
                { label: "Remaining monthly buffer", value: buffer, bold: true, color: buffer >= 0 ? "text-[#059669]" : "text-[#DC2626]" },
              ].map((row, i) => (
                <div key={i} className={`flex items-center justify-between ${row.bold ? "pt-3 border-t border-[#F0F1F7]" : ""}`}>
                  <span className="text-xs text-[#64748B]">{row.label}</span>
                  <span className={`text-sm font-${row.bold ? "bold" : "medium"} ${row.color} count-up`} style={{ fontFamily: "Manrope, sans-serif" }}>
                    {row.value >= 0 ? fmt(row.value) : `−${fmt(Math.abs(row.value))}`}
                  </span>
                </div>
              ))}
            </div>

            {/* Key metrics */}
            <div className="grid grid-cols-3 gap-2 mt-4 pt-4 border-t border-[#F0F1F7]">
              {[
                { label: "EMI ratio", value: `${emiPct}%`, warning: emiPct > 40 },
                { label: "Savings rate", value: `${savePct}%`, warning: savePct < 10 },
                { label: "Free buffer", value: `${Math.max(0, bufferPct)}%`, warning: bufferPct < 10 },
              ].map((m, i) => (
                <div key={i} className={`rounded-xl px-3 py-2 text-center ${m.warning ? "bg-[#FFFBEB]" : "bg-[#F5F6FA]"}`}>
                  <div className={`text-base font-bold ${m.warning ? "text-[#B45309]" : "text-[#3730A3]"}`} style={{ fontFamily: "Manrope, sans-serif" }}>
                    {m.value}
                  </div>
                  <div className="text-[10px] text-[#94A3B8]">{m.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Emergency fund */}
          <div className="fade-slide-up delay-3 bg-[#EEF2FF] border border-[#C7D2FE] rounded-2xl p-4">
            <div className="flex items-start gap-2">
              <span className="text-lg">🏛️</span>
              <div>
                <div className="text-xs font-semibold text-[#3730A3] mb-1">Suggested emergency fund</div>
                <div className="text-xl font-bold text-[#3730A3]" style={{ fontFamily: "Manrope, sans-serif" }}>{fmt(emergencyFund)}</div>
                <div className="text-[10px] text-[#64748B] mt-1">6 months of in-hand salary. Start with whatever you can and build gradually.</div>
              </div>
            </div>
          </div>

          {/* Insight cards */}
          {insights.length > 0 && (
            <div className="fade-slide-up delay-4 space-y-2">
              {insights.map((ins, i) => (
                <div key={i} className={`border rounded-2xl px-4 py-3 flex items-start gap-2 ${ins.color}`}>
                  <span className="shrink-0">{ins.icon}</span>
                  <p className="text-xs text-[#64748B] leading-relaxed">{ins.text}</p>
                </div>
              ))}
            </div>
          )}

          <div className="fade-slide-up delay-5 flex gap-2">
            <button
              onClick={() => onNav("compare")}
              className="flex-1 bg-[#3730A3] text-white py-2.5 rounded-xl text-xs font-semibold hover:bg-[#312E81] transition-all"
            >
              Compare offers →
            </button>
            <button
              onClick={() => onNav("tax")}
              className="px-4 py-2.5 border border-[#E2E5F0] rounded-xl text-xs text-[#64748B] hover:bg-[#F5F6FA] transition-colors"
            >
              ← Tax
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
