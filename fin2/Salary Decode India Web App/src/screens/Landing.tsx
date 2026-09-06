interface Props {
  onNavToInput: (tab: "upload" | "paste" | "manual") => void;
  onTrySample: (targetScreen: string) => void;
  loadingSample: boolean;
}

const features = [
  {
    icon: "💸",
    title: "Know your estimated in-hand",
    desc: "See exactly what hits your bank every month — not just the CTC headline.",
    color: "bg-[#ECFDF5] text-[#059669]",
  },
  {
    icon: "🔍",
    title: "See where your CTC goes",
    desc: "Employer PF, gratuity, TDS, professional tax — understand every rupee.",
    color: "bg-[#EEF2FF] text-[#3730A3]",
  },
  {
    icon: "🚩",
    title: "Spot offer-letter red flags",
    desc: "High variable pay, discretionary bonuses, CTC inflated by employer PF.",
    color: "bg-[#FFFBEB] text-[#B45309]",
  },
  {
    icon: "⚖️",
    title: "Compare offers confidently",
    desc: "Two offers? See which gives more reliable monthly money in your hands.",
    color: "bg-[#EDE9FE] text-[#6D28D9]",
  },
];

export default function Landing({ onNavToInput, onTrySample, loadingSample }: Props) {
  return (
    <div className="min-h-screen bg-[#F5F6FA]">
      {/* Hero */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 pt-16 pb-20">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          {/* Left */}
          <div className="fade-slide-up">
            <div className="inline-flex items-center gap-2 bg-[#EEF2FF] text-[#3730A3] text-xs font-semibold px-3 py-1.5 rounded-full mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-[#3730A3]" />
              Free · No sign-up · Private
            </div>
            <h1
              className="text-4xl sm:text-5xl font-bold text-[#1A1D2E] leading-tight mb-5"
              style={{ fontFamily: "Manrope, sans-serif" }}
            >
              Understand your{" "}
              <span className="text-[#3730A3]">real salary</span>
              —not just your CTC.
            </h1>
            <p className="text-lg text-[#64748B] leading-relaxed mb-4 max-w-lg">
              Decode your offer, estimate monthly in-hand pay, spot fine print, and know what you can actually spend.
            </p>
            <p className="text-sm text-[#94A3B8] mb-8 max-w-lg">
              Whether you are starting a role, switching jobs, or reviewing your salary, see where your money goes.
            </p>

            <div className="flex flex-col sm:flex-row gap-3 mb-6">
              <button
                onClick={() => onNavToInput("upload")}
                className="flex items-center justify-center gap-2 bg-[#3730A3] text-white px-6 py-3 rounded-xl font-semibold text-sm hover:bg-[#312E81] transition-all shadow-md shadow-indigo-200 hover:shadow-lg hover:shadow-indigo-200 hover:-translate-y-0.5 active:translate-y-0"
              >
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                Upload Offer Letter
              </button>
              <button
                onClick={() => onNavToInput("manual")}
                className="flex items-center justify-center gap-2 bg-white text-[#3730A3] border border-[#C7D2FE] px-6 py-3 rounded-xl font-semibold text-sm hover:bg-[#EEF2FF] transition-all"
              >
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
                Enter Salary Manually
              </button>
            </div>

            <button
              onClick={() => onTrySample("breakdown")}
              disabled={loadingSample}
              className="text-sm text-[#64748B] hover:text-[#3730A3] transition-colors underline underline-offset-2 disabled:opacity-50"
            >
              {loadingSample ? "Loading sample offer…" : "Try with a sample offer →"}
            </button>

            <div className="mt-8 flex items-center gap-2 text-xs text-[#94A3B8]">
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              Your document is used only to calculate your salary estimate. Nothing is stored.
            </div>
          </div>

          {/* Right — Hero visual */}
          <div className="fade-slide-up delay-2 relative">
            <div className="bg-white rounded-2xl border border-[#E2E5F0] shadow-xl p-6 relative">
              {/* Mini salary flow card */}
              <div className="text-xs font-semibold text-[#94A3B8] uppercase tracking-wider mb-4">Your Salary, Decoded</div>

              <div className="flex items-center justify-between mb-6">
                <div>
                  <div className="text-xs text-[#94A3B8] mb-0.5">Annual CTC</div>
                  <div className="text-2xl font-bold text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>₹12,00,000</div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-8 h-px bg-[#C7D2FE]" />
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3730A3" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
                <div>
                  <div className="text-xs text-[#94A3B8] mb-0.5">Monthly In-hand</div>
                  <div className="text-2xl font-bold text-[#059669]" style={{ fontFamily: "Manrope, sans-serif" }}>₹76,800</div>
                </div>
              </div>

              {/* Waterfall bars */}
              {[
                { label: "Gross CTC / 12", val: 100, color: "bg-[#818CF8]" },
                { label: "− Employer PF & Gratuity", val: -8, color: "bg-[#FDE68A]" },
                { label: "− Employee PF", val: -5, color: "bg-[#FECACA]" },
                { label: "− TDS (estimated tax)", val: -13, color: "bg-[#FCA5A5]" },
                { label: "− Professional tax", val: -2, color: "bg-[#FDE68A]" },
                { label: "= Monthly in-hand", val: 72, color: "bg-[#6EE7B7]" },
              ].map((row, i) => (
                <div key={i} className="flex items-center gap-3 mb-2">
                  <div className="w-28 text-xs text-[#64748B] truncate shrink-0">{row.label}</div>
                  <div className="flex-1 h-5 bg-[#F5F6FA] rounded-md overflow-hidden">
                    <div
                      className={`h-full rounded-md transition-all ${row.color}`}
                      style={{ width: `${Math.abs(row.val)}%` }}
                    />
                  </div>
                </div>
              ))}

              {/* Badges */}
              <div className="absolute -top-3 -right-3 bg-[#FFFBEB] border border-[#FDE68A] rounded-xl px-3 py-1.5 text-xs font-semibold text-[#B45309] shadow-sm">
                🚩 Variable pay: 10% of CTC
              </div>
            </div>

            {/* Floating mini card */}
            <div className="absolute -bottom-4 -left-4 bg-white border border-[#E2E5F0] rounded-xl px-4 py-3 shadow-lg text-xs">
              <div className="text-[#94A3B8] mb-0.5">Gratuity eligible in</div>
              <div className="font-bold text-[#3730A3]" style={{ fontFamily: "Manrope, sans-serif" }}>4 yrs 7 months</div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature cards */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 pb-20">
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {features.map((f, i) => (
            <div
              key={i}
              className={`fade-slide-up delay-${i + 1} bg-white rounded-2xl border border-[#E2E5F0] p-6 hover:shadow-md transition-shadow cursor-pointer`}
              onClick={() => onTrySample(i === 2 ? "review" : i === 3 ? "compare" : "breakdown")}
            >
              <div className={`w-10 h-10 rounded-xl ${f.color} flex items-center justify-center text-xl mb-4`}>
                {f.icon}
              </div>
              <h3 className="font-semibold text-[#1A1D2E] text-sm mb-2" style={{ fontFamily: "Manrope, sans-serif" }}>
                {f.title}
              </h3>
              <p className="text-xs text-[#64748B] leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="bg-white border-t border-[#E2E5F0] py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <h2
            className="text-2xl font-bold text-[#1A1D2E] text-center mb-12"
            style={{ fontFamily: "Manrope, sans-serif" }}
          >
            How it works
          </h2>
          <div className="grid sm:grid-cols-3 gap-8">
            {[
              { step: "01", title: "Enter your salary details", desc: "Upload an offer letter, paste the salary breakup, or fill in the fields manually." },
              { step: "02", title: "Review the breakdown", desc: "See every component — what reaches your bank, what goes to PF, tax, and gratuity." },
              { step: "03", title: "Understand and optimise", desc: "Compare tax regimes, plan your monthly budget, and compare multiple offers side by side." },
            ].map((s, i) => (
              <div key={i} className="flex gap-4">
                <div className="text-4xl font-black text-[#EEF2FF] select-none" style={{ fontFamily: "Manrope, sans-serif" }}>{s.step}</div>
                <div>
                  <h3 className="font-semibold text-[#1A1D2E] mb-1" style={{ fontFamily: "Manrope, sans-serif" }}>{s.title}</h3>
                  <p className="text-sm text-[#64748B] leading-relaxed">{s.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-20 text-center">
        <h2
          className="text-3xl font-bold text-[#1A1D2E] mb-4"
          style={{ fontFamily: "Manrope, sans-serif" }}
        >
          Ready to understand your real salary?
        </h2>
        <p className="text-[#64748B] mb-8">
          Takes under 2 minutes. Free, private, and no account needed.
        </p>
        <button
          onClick={() => onNavToInput("upload")}
          className="bg-[#3730A3] text-white px-8 py-3.5 rounded-xl font-semibold hover:bg-[#312E81] transition-all shadow-lg shadow-indigo-200 hover:-translate-y-0.5 active:translate-y-0"
        >
          Decode My Salary →
        </button>
      </section>
    </div>
  );
}
