import { useRef, useState } from "react";
import { fmt, defaultSalaryData } from "../data/sampleData";
import type { SalaryData } from "../data/sampleData";
import {
  describeAiError,
  fetchBreakdown,
  fetchClassification,
  fetchOfferComparisonVerdict,
  fetchQualityScore,
  parseOfferDocument,
} from "../lib/api";
import { mergeParsedOfferIntoSalaryData, salaryDataToCtcBreakup } from "../lib/mapping";
import type { OfferEvaluation, RedFlag } from "../lib/types";

interface Props {
  primaryData: SalaryData;
  onNav: (s: string) => void;
}

/** OfferEvaluation plus the red flags from /breakdown, which the base type
 * doesn't carry — needed here for the detailed red-flag comparison. */
interface DetailedOffer extends OfferEvaluation {
  red_flags: RedFlag[];
}

interface UploadedOffer {
  id: string;
  fileName: string;
  status: "parsing" | "done" | "error";
  error?: string;
  label?: string;
  data?: SalaryData;
  evaluation?: DetailedOffer;
}

/** Runs the same engine calls the backend's own pairwise compare-offers
 * uses internally (in-hand, classification, quality score, red flags), so
 * every offer — the analyzed one and any number of uploaded PDFs — is
 * evaluated identically and can sit side by side in one detailed table. */
async function evaluateOffer(label: string, data: SalaryData): Promise<DetailedOffer> {
  const ctcBreakup = salaryDataToCtcBreakup(data);
  const [breakdown, classification, quality_score] = await Promise.all([
    fetchBreakdown(ctcBreakup, data.regime),
    fetchClassification(ctcBreakup, data.regime),
    fetchQualityScore(ctcBreakup, data.regime),
  ]);
  return {
    label,
    regime: data.regime,
    in_hand: breakdown.breakdown,
    classification,
    quality_score,
    red_flags: breakdown.red_flags,
  };
}

function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

type Row = { label: string; get: (o: DetailedOffer) => number; fmt?: (v: number) => string; higherIsBetter?: boolean };

/** Renders one metric-rows-by-offer-columns table. Reused for every section
 * below so the headline metrics, tax detail, compensation mix, and quality
 * sub-scores all look and behave the same way. */
function MetricTable({ offers, rows }: { offers: DetailedOffer[]; rows: Row[] }) {
  return (
    <div className="bg-white border border-[#E2E5F0] rounded-2xl overflow-x-auto">
      <div
        className="grid px-5 py-3 border-b border-[#F0F1F7] bg-[#F8F9FF] min-w-fit"
        style={{ gridTemplateColumns: `1.6fr repeat(${offers.length}, 1fr)` }}
      >
        <div className="text-xs font-semibold text-[#94A3B8]">Component</div>
        {offers.map((o, i) => (
          <div key={i} className="text-xs font-semibold text-[#94A3B8] text-center truncate px-1">{o.label}</div>
        ))}
      </div>
      <div className="divide-y divide-[#F0F1F7] min-w-fit">
        {rows.map((row, ri) => {
          const values = offers.map(row.get);
          const showWinner = row.higherIsBetter !== undefined && offers.length > 1;
          const bestValue = showWinner
            ? (row.higherIsBetter ? Math.max(...values) : Math.min(...values))
            : null;
          return (
            <div
              key={ri}
              className="grid px-5 py-3 items-center"
              style={{ gridTemplateColumns: `1.6fr repeat(${offers.length}, 1fr)` }}
            >
              <div className="text-sm text-[#64748B]">{row.label}</div>
              {offers.map((o, i) => (
                <div
                  key={i}
                  className={`text-center text-sm font-medium px-1 ${bestValue !== null && values[i] === bestValue ? "text-[#059669]" : "text-[#1A1D2E]"}`}
                >
                  {row.fmt ? row.fmt(values[i]) : fmt(values[i])}
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SectionHeading({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3 mt-8 first:mt-0">
      <div className="text-sm font-bold text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>{title}</div>
      {subtitle && <div className="text-[11px] text-[#94A3B8]">{subtitle}</div>}
    </div>
  );
}

const SEVERITY_STYLE: Record<RedFlag["severity"], string> = {
  critical: "bg-[#FEE2E2] text-[#991B1B] border-[#FCA5A5]",
  warning: "bg-[#FEF3C7] text-[#92400E] border-[#FCD34D]",
  info: "bg-[#EEF2FF] text-[#3730A3] border-[#C7D2FE]",
};

export default function CompareOffers({ primaryData, onNav }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploads, setUploads] = useState<UploadedOffer[]>([]);
  const [offerA, setOfferA] = useState<DetailedOffer | null>(null);
  const [verdict, setVerdict] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addFiles = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    const entries: UploadedOffer[] = files.map(f => ({ id: uid(), fileName: f.name, status: "parsing" }));
    setUploads(prev => [...prev, ...entries]);
    setError(null);

    await Promise.all(files.map(async (file, i) => {
      const entryId = entries[i].id;
      try {
        const parsed = await parseOfferDocument(file);
        const data = mergeParsedOfferIntoSalaryData(parsed, defaultSalaryData);
        const label = data.company || file.name.replace(/\.pdf$/i, "");
        const evaluation = await evaluateOffer(label, data);
        setUploads(prev => prev.map(u => u.id === entryId ? { ...u, status: "done", label, data, evaluation } : u));
      } catch (err) {
        const message = describeAiError(err, "Couldn't read this offer letter. Please try again.");
        setUploads(prev => prev.map(u => u.id === entryId ? { ...u, status: "error", error: message } : u));
      }
    }));
  };

  const removeUpload = (id: string) => setUploads(prev => prev.filter(u => u.id !== id));

  const readyOffers = uploads.filter((u): u is UploadedOffer & { evaluation: DetailedOffer; data: SalaryData } =>
    u.status === "done" && !!u.evaluation && !!u.data);

  const runComparison = async () => {
    if (readyOffers.length === 0) return;
    setLoading(true);
    setError(null);
    setVerdict(null);
    try {
      const a = offerA ?? await evaluateOffer("Offer A", primaryData);
      setOfferA(a);

      // The AI narrative verdict only makes sense as a head-to-head — keep it
      // for the classic "your offer vs. one other" case; three or more offers
      // get the computed detail tables below instead of an LLM summary.
      if (readyOffers.length === 1 && readyOffers[0].data) {
        const other = readyOffers[0];
        const r = await fetchOfferComparisonVerdict(
          { label: "Offer A", ctcBreakup: salaryDataToCtcBreakup(primaryData), regime: primaryData.regime },
          { label: other.label ?? other.fileName, ctcBreakup: salaryDataToCtcBreakup(other.data), regime: other.data.regime },
        );
        setVerdict(r.verdict);
      }
    } catch (err) {
      setError(describeAiError(err, "Couldn't compare these offers right now. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  const allOffers: DetailedOffer[] = offerA ? [offerA, ...readyOffers.map(o => o.evaluation)] : [];

  const pct = (v: number) => `${Math.round(v * 100)}%`;
  const variablePct = (o: DetailedOffer) => o.classification.buckets.find(b => b.bucket === "variable")?.pct_of_ctc ?? 0;

  const headlineRows: Row[] = [
    { label: "Annual CTC", get: o => o.in_hand.ctc_total, higherIsBetter: true },
    { label: "Gross salary (annual)", get: o => o.in_hand.gross_salary_annual, higherIsBetter: true },
    { label: "Est. monthly in-hand", get: o => o.in_hand.in_hand_monthly, higherIsBetter: true },
    { label: "Est. annual take-home", get: o => o.in_hand.in_hand_annual, higherIsBetter: true },
    { label: "Total tax + cess (annual)", get: o => o.in_hand.tax_breakdown.total_tax, higherIsBetter: false },
    { label: "Total deductions (annual)", get: o => o.in_hand.total_deductions_annual },
    { label: "Offer quality score (0-100)", get: o => o.quality_score.overall_score, fmt: String, higherIsBetter: true },
    { label: "Variable pay % of CTC", get: variablePct, fmt: pct },
  ];

  const bucketKeys = allOffers[0]?.classification.buckets.map(b => b.bucket) ?? [];
  const compositionRows: Row[] = bucketKeys.flatMap(key => {
    const label = allOffers[0]?.classification.buckets.find(b => b.bucket === key)?.label ?? key;
    return [
      { label: `${label} (annual)`, get: (o: DetailedOffer) => o.classification.buckets.find(b => b.bucket === key)?.total ?? 0 },
      { label: `${label} — % of CTC`, get: (o: DetailedOffer) => o.classification.buckets.find(b => b.bucket === key)?.pct_of_ctc ?? 0, fmt: pct },
    ];
  });

  const employerRows: Row[] = [
    { label: "Employer PF", get: o => o.in_hand.employer_side.employer_pf.amount, higherIsBetter: true },
    { label: "Employer ESI", get: o => o.in_hand.employer_side.employer_esi.amount, higherIsBetter: true },
    { label: "Gratuity provision", get: o => o.in_hand.employer_side.gratuity_provision.amount, higherIsBetter: true },
    { label: "Employer NPS", get: o => o.in_hand.employer_side.employer_nps.amount, higherIsBetter: true },
    { label: "Health insurance (employer-paid)", get: o => o.in_hand.employer_side.health_insurance.amount, higherIsBetter: true },
  ];

  const qualityRows: Row[] = allOffers[0]
    ? Object.keys(allOffers[0].quality_score.sub_scores).map(key => ({
        label: key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
        get: (o: DetailedOffer) => o.quality_score.sub_scores[key]?.score ?? 0,
        fmt: (v: number) => v.toFixed(0),
        higherIsBetter: true,
      }))
    : [];

  const bestCashflowIdx = allOffers.length
    ? allOffers.reduce((best, o, i) => o.in_hand.in_hand_monthly > allOffers[best].in_hand.in_hand_monthly ? i : best, 0)
    : -1;
  const bestTotalCompIdx = allOffers.length
    ? allOffers.reduce((best, o, i) => o.in_hand.ctc_total > allOffers[best].in_hand.ctc_total ? i : best, 0)
    : -1;
  const bestQualityIdx = allOffers.length
    ? allOffers.reduce((best, o, i) => o.quality_score.overall_score > allOffers[best].quality_score.overall_score ? i : best, 0)
    : -1;
  const fewestRedFlagsIdx = allOffers.length
    ? allOffers.reduce((best, o, i) => o.red_flags.length < allOffers[best].red_flags.length ? i : best, 0)
    : -1;

  const computedSummary = allOffers.length > 2
    ? `${allOffers[bestTotalCompIdx].label} has the highest annual CTC, ${allOffers[bestCashflowIdx].label} pays the most monthly in-hand, ${allOffers[bestQualityIdx].label} scores best on offer quality, and ${allOffers[fewestRedFlagsIdx].label} carries the fewest red flags.`
    : null;

  const totalRedFlags = allOffers.reduce((sum, o) => sum + o.red_flags.length, 0);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      <div className="fade-slide-up mb-6">
        <h1 className="text-2xl font-bold text-[#1A1D2E] mb-1" style={{ fontFamily: "Manrope, sans-serif" }}>
          Compare offers
        </h1>
        <p className="text-sm text-[#94A3B8]">
          Upload as many offer letter PDFs as you want — we'll read each one and line them all up against your analyzed offer, field by field.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-4 mb-4 fade-slide-up delay-1">
        <div className="bg-white border-2 border-[#E2E5F0] rounded-2xl px-5 py-4">
          <div className="text-xs font-semibold text-[#94A3B8] mb-0.5">Offer A — your analyzed offer</div>
          <div className="font-bold text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>{primaryData.company}</div>
          <div className="text-xs text-[#64748B] mb-3">{primaryData.jobTitle} · {primaryData.city}</div>
          <div className="text-[10px] text-[#94A3B8]">Annual CTC</div>
          <div className="text-lg font-bold text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>{fmt(primaryData.ctc)}</div>
        </div>

        <div className="bg-white border-2 border-[#C7D2FE] rounded-2xl px-5 py-4">
          <div className="text-xs font-semibold text-[#94A3B8] mb-2">Other offers — upload PDFs</div>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="w-full border-2 border-dashed border-[#C7D2FE] rounded-xl py-4 text-xs text-[#3730A3] font-medium hover:bg-[#EEF2FF] transition-colors"
          >
            + Add offer letter PDF(s)
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            multiple
            className="hidden"
            onChange={e => { void addFiles(e.target.files); e.target.value = ""; }}
          />

          {uploads.length > 0 && (
            <div className="mt-3 space-y-2">
              {uploads.map(u => (
                <div key={u.id} className="flex items-center justify-between gap-2 bg-[#F5F6FA] rounded-lg px-3 py-2">
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-[#1A1D2E] truncate">{u.label ?? u.fileName}</div>
                    <div className="text-[10px] text-[#94A3B8] truncate">
                      {u.status === "parsing" && "Reading offer letter…"}
                      {u.status === "done" && "Ready"}
                      {u.status === "error" && u.error}
                    </div>
                  </div>
                  <button
                    onClick={() => removeUpload(u.id)}
                    className="text-[#94A3B8] hover:text-[#DC2626] text-xs shrink-0"
                    aria-label={`Remove ${u.fileName}`}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="fade-slide-up delay-2 mb-6">
        <button
          onClick={runComparison}
          disabled={loading || readyOffers.length === 0}
          className="w-full bg-[#3730A3] text-white py-3 rounded-xl font-semibold text-sm hover:bg-[#312E81] transition-all shadow-md shadow-indigo-200 disabled:opacity-50"
        >
          {loading
            ? "Comparing offers…"
            : allOffers.length > 0
              ? "Re-compare with AI →"
              : readyOffers.length === 0
                ? "Upload at least one offer letter to compare"
                : "Compare with AI →"}
        </button>
        {error && <p className="text-xs text-[#DC2626] mt-2">{error}</p>}
      </div>

      {allOffers.length > 0 && (
        <>
          {verdict && (
            <div className="fade-slide-up delay-2 bg-[#EEF2FF] border border-[#C7D2FE] rounded-2xl px-5 py-4 mb-6">
              <div className="flex items-start gap-3">
                <span className="text-xl shrink-0">🤖</span>
                <div>
                  <div className="text-sm font-semibold text-[#3730A3] mb-1" style={{ fontFamily: "Manrope, sans-serif" }}>
                    AI verdict
                  </div>
                  <p className="text-xs text-[#64748B] leading-relaxed whitespace-pre-line">{verdict}</p>
                </div>
              </div>
            </div>
          )}

          {computedSummary && (
            <div className="fade-slide-up delay-2 bg-[#EEF2FF] border border-[#C7D2FE] rounded-2xl px-5 py-4 mb-6">
              <div className="flex items-start gap-3">
                <span className="text-xl shrink-0">📊</span>
                <p className="text-xs text-[#64748B] leading-relaxed">{computedSummary}</p>
              </div>
            </div>
          )}

          <div className="fade-slide-up delay-3">
            <SectionHeading title="Headline numbers" subtitle="Take-home pay, tax, and overall offer quality" />
            <MetricTable offers={allOffers} rows={headlineRows} />

            <SectionHeading title="Compensation mix" subtitle="How each offer's CTC breaks down into fixed, employer contributions, variable, and one-time pay" />
            <MetricTable offers={allOffers} rows={compositionRows} />

            <SectionHeading title="Employer-paid benefits" subtitle="Annual employer cost that never shows up in your take-home pay, but is still part of the offer" />
            <MetricTable offers={allOffers} rows={employerRows} />

            <SectionHeading title="Quality score breakdown" subtitle="The four weighted sub-scores behind each offer's overall quality score" />
            <MetricTable offers={allOffers} rows={qualityRows} />

            <SectionHeading
              title={`Red flags${totalRedFlags > 0 ? ` (${totalRedFlags})` : ""}`}
              subtitle="Anything the rule engine flagged as worth double-checking before you sign"
            />
            {totalRedFlags === 0 ? (
              <div className="bg-[#F0FDF4] border border-[#BBF7D0] rounded-2xl px-5 py-4 text-xs text-[#166534]">
                No red flags detected on any of these offers.
              </div>
            ) : (
              <div className="grid sm:grid-cols-2 gap-4">
                {allOffers.map((o, i) => (
                  <div key={i} className="bg-white border border-[#E2E5F0] rounded-2xl px-4 py-3">
                    <div className="text-xs font-semibold text-[#1A1D2E] mb-2">{o.label}</div>
                    {o.red_flags.length === 0 ? (
                      <div className="text-xs text-[#94A3B8]">No red flags.</div>
                    ) : (
                      <div className="space-y-2">
                        {o.red_flags.map((flag, fi) => (
                          <div key={fi} className={`text-[11px] leading-snug border rounded-lg px-2.5 py-2 ${SEVERITY_STYLE[flag.severity]}`}>
                            <span className="font-semibold uppercase tracking-wide">{flag.severity}</span> — {flag.message}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      <div className="fade-slide-up delay-4 flex gap-3 mt-8">
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
