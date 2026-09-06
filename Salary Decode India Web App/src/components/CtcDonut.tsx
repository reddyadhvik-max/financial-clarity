import type { ClassificationResult } from "../lib/types";
import { fmt } from "../data/sampleData";

interface Props {
  classification: ClassificationResult;
}

const BUCKET_COLOR: Record<string, string> = {
  fixed_compensation: "#3730A3",
  employer_contributions: "#818CF8",
  variable: "#FBBF24",
  one_time: "#94A3B8",
  equity: "#6D28D9",
};

const BUCKET_LABEL: Record<string, string> = {
  fixed_compensation: "Fixed",
  employer_contributions: "Employer contributions",
  variable: "Variable",
  one_time: "One-time",
  equity: "Equity",
};

/** Pure-SVG donut — no charting library needed for a handful of segments. */
export default function CtcDonut({ classification }: Props) {
  const segments = classification.buckets.filter(b => b.total > 0 && b.bucket !== "one_time");
  const total = segments.reduce((sum, b) => sum + b.total, 0);
  if (total <= 0) return null;

  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="flex items-center gap-6">
      <svg width="150" height="150" viewBox="0 0 150 150" className="shrink-0 -rotate-90">
        <circle cx="75" cy="75" r={radius} fill="none" stroke="#F0F1F7" strokeWidth="18" />
        {segments.map((b, i) => {
          const fraction = b.total / total;
          const dash = fraction * circumference;
          const circle = (
            <circle
              key={i}
              cx="75" cy="75" r={radius}
              fill="none"
              stroke={BUCKET_COLOR[b.bucket] ?? "#CBD5E1"}
              strokeWidth="18"
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-offset}
            />
          );
          offset += dash;
          return circle;
        })}
      </svg>
      <div className="space-y-2 flex-1">
        {segments.map((b, i) => (
          <div key={i} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: BUCKET_COLOR[b.bucket] ?? "#CBD5E1" }} />
              <span className="text-[#64748B]">{BUCKET_LABEL[b.bucket] ?? b.label}</span>
            </div>
            <div className="text-right">
              <span className="font-semibold text-[#1A1D2E]">{fmt(b.total)}</span>
              {b.pct_of_ctc !== null && <span className="text-[#94A3B8] ml-1">({Math.round(b.pct_of_ctc * 100)}%)</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
