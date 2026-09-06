import type { QualityScoreResult } from "../lib/types";

interface Props {
  score: QualityScoreResult;
}

const DIMENSION_LABEL: Record<string, string> = {
  fixed_ratio: "Guaranteed pay ratio",
  variable_dependence: "Variable-pay dependence",
  take_home_ratio: "Take-home efficiency",
  benefits: "Benefits completeness",
};

function scoreColor(score: number): string {
  if (score >= 75) return "#059669";
  if (score >= 50) return "#B45309";
  return "#DC2626";
}

export default function QualityScoreCard({ score }: Props) {
  const color = scoreColor(score.overall_score);
  return (
    <div className="bg-white border border-[#E2E5F0] rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-sm text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>Offer Quality Score</h3>
        <div className="text-2xl font-bold" style={{ color, fontFamily: "Manrope, sans-serif" }}>
          {score.overall_score}<span className="text-xs text-[#94A3B8] font-normal">/100</span>
        </div>
      </div>
      <div className="space-y-3">
        {Object.entries(score.sub_scores).map(([key, sub]) => (
          <div key={key}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-[#64748B]">{DIMENSION_LABEL[key] ?? key}</span>
              <span className="font-medium text-[#1A1D2E]">{Math.round(sub.score)}/100</span>
            </div>
            <div className="h-1.5 bg-[#F0F1F7] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${sub.score}%`, background: scoreColor(sub.score) }}
              />
            </div>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-[#94A3B8] mt-4">
        Every dimension is a transparent formula against a versioned benchmark (rule_id: {score.weights_rule_id}) — not an opaque AI opinion.
      </p>
    </div>
  );
}
