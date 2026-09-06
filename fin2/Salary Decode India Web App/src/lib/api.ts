// Thin client for the FastAPI backend (backend/app/main.py). Every number
// shown in the UI must come from one of these calls — no client-side salary
// or tax math. See src/lib/types.ts for the response shapes.
import type {
  AgentAnswer,
  BreakdownResponse,
  ChatTurn,
  ClassificationResult,
  CompareOffersComputed,
  CtcBreakup,
  GratuityEpfTimeline,
  InHandBreakdown,
  ParsedOfferAI,
  QualityScoreResult,
  RedFlag,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/** FastAPI's HTTPException body is `{"detail": "..."}` — unwrap that string
 * so ApiError.message is the actual human-readable text, not raw JSON. */
function messageFromDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && typeof (detail as { detail?: unknown }).detail === "string") {
    return (detail as { detail: string }).detail;
  }
  return JSON.stringify(detail);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(messageFromDetail(detail));
    this.status = status;
    this.detail = detail;
  }

  /** True when the AI layer has no Gemini credentials configured (backend 503). */
  get isAiUnavailable(): boolean {
    return this.status === 503;
  }

  /** True when Gemini's free-tier quota is exhausted (backend 429) — message
   * is already a friendly "try again later" string, safe to show directly. */
  get isRateLimited(): boolean {
    return this.status === 429;
  }

  /** True when the Gemini request itself failed (backend 502) — safe to retry. */
  get isAiRequestFailure(): boolean {
    return this.status === 502;
  }
}

/** One place to turn an AI-call failure into a message worth showing the
 * user — credentials/quota errors already have a clear, friendly reason;
 * anything else falls back to the caller's generic retry copy. */
export function describeAiError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.isAiUnavailable) return "AI isn't configured on the server (missing Gemini credentials).";
    if (err.isRateLimited) return err.message;
  }
  return fallback;
}

// --- Gemini call budget discipline -----------------------------------------
// The backend runs on Gemini's free tier (20 requests/day). Every function
// below that reaches an /ai/* endpoint is wrapped in `cachedAiCall` so that
// re-clicking "Explain my offer" (etc.) after navigating away and back — or
// simply re-rendering — reuses the previous answer instead of spending a
// fresh quota unit on an identical request. Keyed on the actual request
// payload, so a real edit (a corrected field, a different question) always
// gets a fresh call; only a true repeat is served from cache. Chat
// (`askAgent`) is deliberately NOT cached — each question is genuinely new.
// A failed call (including a 429) is evicted immediately so the next
// attempt, once quota allows, is a real retry rather than a cached rejection.
const aiCallCache = new Map<string, Promise<unknown>>();

function cachedAiCall<T>(cacheKey: string, run: () => Promise<T>): Promise<T> {
  const existing = aiCallCache.get(cacheKey);
  if (existing) return existing as Promise<T>;
  const promise = run().catch((err) => {
    aiCallCache.delete(cacheKey);
    throw err;
  });
  aiCallCache.set(cacheKey, promise);
  return promise as Promise<T>;
}

async function request<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

async function requestGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export interface SampleOffer {
  id: string;
  label: string;
  description: string;
  joining_date: string;
  ctc_breakup: Record<string, unknown>;
}

export async function fetchSampleOffers(): Promise<SampleOffer[]> {
  const data = await requestGet<{ samples: SampleOffer[] }>("/sample-offers");
  return data.samples;
}

export function fetchBreakdown(
  ctcBreakup: CtcBreakup,
  regime: "old" | "new" = "new",
  fy?: string,
): Promise<BreakdownResponse> {
  return request("/breakdown", { ctcBreakup, regime, fy });
}

export function parseOfferText(offerText: string): Promise<ParsedOfferAI> {
  return cachedAiCall(`parse-text:${offerText}`, () =>
    request("/ai/parse-offer", { offer_text: offerText }));
}

/** Real document/vision understanding — sends the PDF/image straight to Gemini. */
export async function parseOfferDocument(file: File): Promise<ParsedOfferAI> {
  // name+size+lastModified is a cheap, stable fingerprint — good enough to
  // recognize "the same file, re-selected" without re-reading its bytes.
  const cacheKey = `parse-doc:${file.name}:${file.size}:${file.lastModified}`;
  return cachedAiCall(cacheKey, async () => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${BASE_URL}/ai/parse-offer-document`, { method: "POST", body: formData });
    if (!res.ok) {
      let detail: unknown;
      try {
        detail = await res.json();
      } catch {
        detail = await res.text();
      }
      throw new ApiError(res.status, detail);
    }
    return res.json() as Promise<ParsedOfferAI>;
  });
}

export function fetchNegotiationMessage(
  ctcBreakup: CtcBreakup,
  audience: "recruiter_email" | "hr_call_talking_points",
  regime: "old" | "new" = "new",
): Promise<{ message: string; computed: ExplainComputed }> {
  return cachedAiCall(`negotiation-message:${JSON.stringify({ ctcBreakup, audience, regime })}`, () =>
    request("/ai/negotiation-message", { ctcBreakup, audience, regime }));
}

export interface ExplainComputed {
  in_hand: InHandBreakdown;
  red_flags: RedFlag[];
  quality_score: QualityScoreResult;
}

export function fetchExplanation(
  ctcBreakup: CtcBreakup,
  regime: "old" | "new" = "new",
): Promise<{ explanation: string; computed: ExplainComputed }> {
  return cachedAiCall(`explain:${JSON.stringify({ ctcBreakup, regime })}`, () =>
    request("/ai/explain", { ctcBreakup, regime }));
}

export function fetchNegotiationPoints(
  ctcBreakup: CtcBreakup,
  regime: "old" | "new" = "new",
): Promise<{ negotiation_points: string; computed: ExplainComputed & { classification: unknown } }> {
  return cachedAiCall(`negotiate:${JSON.stringify({ ctcBreakup, regime })}`, () =>
    request("/ai/negotiate", { ctcBreakup, regime }));
}

export function fetchOfferComparisonVerdict(
  offerA: { label: string; ctcBreakup: CtcBreakup; regime?: "old" | "new" },
  offerB: { label: string; ctcBreakup: CtcBreakup; regime?: "old" | "new" },
): Promise<{ verdict: string; computed: CompareOffersComputed }> {
  const payload = {
    offerA: { label: offerA.label, ctcBreakup: offerA.ctcBreakup, regime: offerA.regime ?? "new" },
    offerB: { label: offerB.label, ctcBreakup: offerB.ctcBreakup, regime: offerB.regime ?? "new" },
  };
  return cachedAiCall(`compare:${JSON.stringify(payload)}`, () => request("/ai/compare-offers", payload));
}

export function askAgent(
  ctcBreakup: CtcBreakup,
  question: string,
  history: ChatTurn[] = [],
): Promise<AgentAnswer> {
  return request("/ai/ask", { ctcBreakup, question, history });
}

export function fetchClassification(
  ctcBreakup: CtcBreakup,
  regime: "old" | "new" = "new",
): Promise<ClassificationResult> {
  return request("/classify", { ctcBreakup, regime });
}

export function fetchQualityScore(
  ctcBreakup: CtcBreakup,
  regime: "old" | "new" = "new",
): Promise<QualityScoreResult> {
  return request("/quality-score", { ctcBreakup, regime });
}

export function fetchGratuityTimeline(
  joiningDate: string,
  options: { asOfDate?: string; separationDate?: string; fy?: string } = {},
): Promise<GratuityEpfTimeline> {
  return request("/gratuity-epf-timeline", {
    joiningDate,
    asOfDate: options.asOfDate,
    separationDate: options.separationDate,
    fy: options.fy,
  });
}
