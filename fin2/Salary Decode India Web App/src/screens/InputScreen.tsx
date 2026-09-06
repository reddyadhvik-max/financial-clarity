import { useState, useEffect } from "react";
import type { SalaryData } from "../data/sampleData";
import { defaultSalaryData } from "../data/sampleData";
import { ApiError, describeAiError, parseOfferDocument, parseOfferText } from "../lib/api";
import { mergeParsedOfferIntoSalaryData } from "../lib/mapping";
import type { ParsedOfferAI } from "../lib/types";

interface Props {
  initialTab?: "upload" | "paste" | "manual";
  initialData?: SalaryData;
  onContinue: (data: SalaryData, parsed?: ParsedOfferAI) => void;
}

const AI_STAGES = [
  "Reading document…",
  "Detecting compensation components…",
  "Classifying fixed vs. variable pay…",
  "Scanning for employment clauses…",
  "Checking for ambiguities…",
];

function AiProcessingStages() {
  const [stageIndex, setStageIndex] = useState(0);
  useEffect(() => {
    const handle = setInterval(() => setStageIndex(i => Math.min(i + 1, AI_STAGES.length - 1)), 1400);
    return () => clearInterval(handle);
  }, []);
  return (
    <div className="text-left w-full max-w-xs mx-auto space-y-1.5">
      {AI_STAGES.map((stage, i) => (
        <div key={stage} className={`flex items-center gap-2 text-xs transition-opacity ${i <= stageIndex ? "opacity-100" : "opacity-30"}`}>
          <span>{i < stageIndex ? "✓" : i === stageIndex ? "◌" : "○"}</span>
          <span className={i === stageIndex ? "text-[#3730A3] font-medium" : "text-[#64748B]"}>{stage}</span>
        </div>
      ))}
    </div>
  );
}

const cities = ["Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Pune", "Chennai", "Kolkata", "Ahmedabad", "Noida", "Gurgaon"];

function Field({
  label,
  tooltip,
  required,
  children,
}: {
  label: string;
  tooltip?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5">
        <label className="text-xs font-medium text-[#374151]">
          {label} {required && <span className="text-[#FB7185]">*</span>}
        </label>
        {tooltip && (
          <div className="relative">
            <button
              onMouseEnter={() => setShow(true)}
              onMouseLeave={() => setShow(false)}
              className="w-4 h-4 rounded-full bg-[#E2E5F0] text-[#64748B] text-[10px] flex items-center justify-center"
            >
              ?
            </button>
            {show && (
              <div className="absolute left-5 top-0 z-10 w-52 bg-[#1A1D2E] text-white text-xs rounded-lg px-3 py-2 shadow-xl">
                {tooltip}
              </div>
            )}
          </div>
        )}
      </div>
      {children}
    </div>
  );
}

function RupeeInput({
  value,
  onChange,
  placeholder,
}: {
  value: number;
  onChange: (v: number) => void;
  placeholder?: string;
}) {
  return (
    <div className="relative">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8] text-sm">₹</span>
      <input
        type="number"
        value={value || ""}
        onChange={e => onChange(Number(e.target.value))}
        placeholder={placeholder || "0"}
        className="w-full pl-7 pr-3 py-2 bg-[#F5F6FA] border border-[#E2E5F0] rounded-xl text-sm text-[#1A1D2E] focus:outline-none focus:ring-2 focus:ring-[#818CF8] focus:border-transparent transition-all"
      />
    </div>
  );
}

function AccordionSection({
  title,
  subtitle,
  children,
  defaultOpen,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  return (
    <div className="border border-[#E2E5F0] rounded-2xl overflow-hidden bg-white">
      <button
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-[#F5F6FA] transition-colors"
        onClick={() => setOpen(v => !v)}
      >
        <div>
          <div className="font-semibold text-sm text-[#1A1D2E]" style={{ fontFamily: "Manrope, sans-serif" }}>{title}</div>
          {subtitle && <div className="text-xs text-[#94A3B8] mt-0.5">{subtitle}</div>}
        </div>
        <svg
          width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="#64748B" strokeWidth={2.5}
          className={`shrink-0 transition-transform duration-300 ${open ? "rotate-180" : ""}`}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="px-5 pb-5 grid sm:grid-cols-2 gap-4 border-t border-[#E2E5F0] pt-4">
          {children}
        </div>
      )}
    </div>
  );
}

export default function InputScreen({ initialTab, initialData, onContinue }: Props) {
  const [tab, setTab] = useState<"upload" | "paste" | "manual">(initialTab ?? "manual");
  // Reuse whatever's already been parsed/entered this session (e.g. coming
  // back via "Edit details") rather than resetting to the sample defaults —
  // avoids forcing the user to re-upload/re-paste (and Gemini to re-parse)
  // just to tweak one field manually.
  const [d, setD] = useState<SalaryData>(initialData ?? defaultSalaryData);
  const [dragOver, setDragOver] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pastedText, setPastedText] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const [uploadedParsed, setUploadedParsed] = useState<ParsedOfferAI | null>(null);

  const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
  const ALLOWED_UPLOAD_TYPES = ["application/pdf", "image/png", "image/jpeg", "image/webp"];

  const set = (k: keyof SalaryData) => (v: number | string) =>
    setD(prev => ({ ...prev, [k]: v }));

  const handleUpload = async (file: File) => {
    setParseError(null);
    setUploadedParsed(null);

    if (file.size > MAX_UPLOAD_BYTES) {
      setParseError(`File is ${(file.size / 1_048_576).toFixed(1)} MB — the limit is 10 MB.`);
      return;
    }
    if (!ALLOWED_UPLOAD_TYPES.includes(file.type)) {
      setParseError("Unsupported file type. Please upload a PDF, PNG, JPG, or WEBP.");
      return;
    }

    setUploadedFile(file.name);
    setLoading(true);
    try {
      const parsed = await parseOfferDocument(file);
      setUploadedParsed(parsed);
    } catch (err) {
      setUploadedFile(null);
      if (err instanceof ApiError && err.status === 413) {
        setParseError("File is too large for the server to process.");
      } else if (err instanceof ApiError && err.status === 415) {
        setParseError("Unsupported file type.");
      } else {
        setParseError(describeAiError(err, "Couldn't read that document right now. Please try again."));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = () => {
    onContinue(d);
  };

  const handleAnalyseText = async () => {
    setParseError(null);
    setLoading(true);
    try {
      const parsed = await parseOfferText(pastedText);
      onContinue(mergeParsedOfferIntoSalaryData(parsed, d), parsed);
    } catch (err) {
      setParseError(describeAiError(err, "Couldn't parse that text right now. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
      <div className="mb-8 fade-slide-up">
        <h1 className="text-2xl font-bold text-[#1A1D2E] mb-2" style={{ fontFamily: "Manrope, sans-serif" }}>
          Decode your salary
        </h1>
        <p className="text-sm text-[#64748B]">
          Upload your offer letter, paste the salary breakup, or fill in the details manually.
        </p>
      </div>

      {/* Tab selector */}
      <div className="fade-slide-up delay-1 flex gap-1 bg-[#F0F1F7] rounded-xl p-1 mb-6 w-fit">
        {(["upload", "paste", "manual"] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === t
                ? "bg-white text-[#3730A3] shadow-sm"
                : "text-[#64748B] hover:text-[#3730A3]"
            }`}
          >
            {t === "upload" ? "Upload PDF" : t === "paste" ? "Paste Text" : "Manual Entry"}
          </button>
        ))}
      </div>

      {/* Upload tab */}
      {tab === "upload" && (
        <div className="fade-slide-up space-y-4">
          <div
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => {
              e.preventDefault();
              setDragOver(false);
              const file = e.dataTransfer.files[0];
              if (file) handleUpload(file);
            }}
            className={`border-2 border-dashed rounded-2xl p-12 text-center transition-all cursor-pointer ${
              dragOver ? "border-[#818CF8] bg-[#EEF2FF]" : "border-[#C7D2FE] bg-white hover:border-[#818CF8] hover:bg-[#F8F9FF]"
            }`}
            onClick={() => document.getElementById("file-input")?.click()}
          >
            <input
              id="file-input"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); }}
            />
            {loading ? (
              <div>
                <div className="w-12 h-12 mx-auto mb-4 relative">
                  <div className="absolute inset-0 border-3 border-[#C7D2FE] rounded-full" />
                  <div className="absolute inset-0 border-3 border-t-[#3730A3] rounded-full animate-spin" style={{ borderWidth: 3 }} />
                </div>
                <div className="text-sm font-medium text-[#3730A3] mb-3">Gemini is analyzing your offer…</div>
                <AiProcessingStages />
              </div>
            ) : uploadedFile ? (
              <div>
                <div className="w-12 h-12 mx-auto mb-3 bg-[#ECFDF5] rounded-xl flex items-center justify-center text-2xl">📄</div>
                <div className="text-sm font-medium text-[#1A1D2E] mb-1">{uploadedFile}</div>
                <button
                  className="text-xs text-[#FB7185] hover:underline"
                  onClick={e => { e.stopPropagation(); setUploadedFile(null); }}
                >
                  Remove and upload another
                </button>
              </div>
            ) : (
              <div>
                <div className="w-14 h-14 mx-auto mb-4 bg-[#EEF2FF] rounded-2xl flex items-center justify-center text-3xl">📎</div>
                <div className="text-sm font-semibold text-[#1A1D2E] mb-1">Drop your offer letter here</div>
                <div className="text-xs text-[#94A3B8]">PDF, PNG, or JPG • Up to 10 MB</div>
                <div className="mt-3 inline-flex items-center gap-2 bg-[#3730A3] text-white text-xs font-semibold px-4 py-2 rounded-lg">
                  Choose file
                </div>
              </div>
            )}
          </div>

          {uploadedFile && uploadedParsed && !loading && (
            <button
              onClick={() => onContinue(mergeParsedOfferIntoSalaryData(uploadedParsed, d), uploadedParsed)}
              className="w-full bg-[#3730A3] text-white py-3 rounded-xl font-semibold text-sm hover:bg-[#312E81] transition-all shadow-md shadow-indigo-200"
            >
              Continue to review →
            </button>
          )}

          {parseError && (
            <div className="text-xs text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] rounded-xl px-4 py-3">
              {parseError}
            </div>
          )}

          <div className="flex items-center gap-2 text-xs text-[#94A3B8]">
            <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            Your document is sent to our AI for analysis only — not stored.
          </div>
        </div>
      )}

      {/* Paste tab */}
      {tab === "paste" && (
        <div className="fade-slide-up space-y-4">
          <textarea
            value={pastedText}
            onChange={e => setPastedText(e.target.value)}
            rows={12}
            placeholder={`Paste your salary breakup here. For example:\n\nBasic Salary: ₹40,000/month\nHRA: ₹16,000/month\nSpecial Allowance: ₹24,000/month\nEmployer PF: ₹4,800/month\nEmployee PF: ₹4,800/month\nVariable Pay: ₹10,000/month\nTotal CTC: ₹12,00,000 per annum`}
            className="w-full p-4 bg-white border border-[#E2E5F0] rounded-2xl text-sm text-[#1A1D2E] placeholder-[#94A3B8] focus:outline-none focus:ring-2 focus:ring-[#818CF8] resize-none"
          />
          <div className="flex gap-3">
            <button
              onClick={handleAnalyseText}
              disabled={loading || !pastedText.trim()}
              className="flex-1 bg-[#3730A3] text-white py-3 rounded-xl font-semibold text-sm hover:bg-[#312E81] transition-all shadow-md shadow-indigo-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Reading with AI…" : "Analyse Offer Text →"}
            </button>
            <button
              onClick={() => { setPastedText(""); setParseError(null); }}
              className="px-5 py-3 border border-[#E2E5F0] rounded-xl text-sm text-[#64748B] hover:bg-[#F5F6FA] transition-colors"
            >
              Clear
            </button>
          </div>
          {parseError && (
            <div className="text-xs text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] rounded-xl px-4 py-3">
              {parseError}
            </div>
          )}
        </div>
      )}

      {/* Manual tab */}
      {tab === "manual" && (
        <div className="fade-slide-up space-y-3">
          <AccordionSection title="Basic details" subtitle="Company, role, and location" defaultOpen>
            <Field label="Company name" required>
              <input
                value={d.company}
                onChange={e => set("company")(e.target.value)}
                className="w-full px-3 py-2 bg-[#F5F6FA] border border-[#E2E5F0] rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#818CF8] transition-all"
              />
            </Field>
            <Field label="Job title">
              <input
                value={d.jobTitle}
                onChange={e => set("jobTitle")(e.target.value)}
                className="w-full px-3 py-2 bg-[#F5F6FA] border border-[#E2E5F0] rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#818CF8] transition-all"
              />
            </Field>
            <Field label="Work city" tooltip="Used to estimate HRA exemption. Metro cities get 50% basic as HRA limit.">
              <select
                value={d.city}
                onChange={e => set("city")(e.target.value)}
                className="w-full px-3 py-2 bg-[#F5F6FA] border border-[#E2E5F0] rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#818CF8] transition-all"
              >
                {cities.map(c => <option key={c}>{c}</option>)}
              </select>
            </Field>
          </AccordionSection>

          <AccordionSection title="Salary components" subtitle="Annual amounts" defaultOpen>
            <Field label="Annual CTC" required tooltip="Total Cost to Company — the full package value, not your take-home.">
              <RupeeInput value={d.ctc} onChange={v => set("ctc")(v)} placeholder="12,00,000" />
            </Field>
            <Field label="Basic salary (annual)" tooltip="Usually 40–50% of CTC. Base for PF, gratuity, and HRA calculations.">
              <RupeeInput value={d.basic} onChange={v => set("basic")(v)} />
            </Field>
            <Field label="HRA (annual)" tooltip="House Rent Allowance. Usually 40–50% of basic salary.">
              <RupeeInput value={d.hra} onChange={v => set("hra")(v)} />
            </Field>
            <Field label="Special allowance (annual)" tooltip="Remaining CTC balance after other components. Fully taxable.">
              <RupeeInput value={d.specialAllowance} onChange={v => set("specialAllowance")(v)} />
            </Field>
          </AccordionSection>

          <AccordionSection title="Benefits and PF" subtitle="Employer contributions">
            <Field label="Employer PF (annual)" tooltip="12% of basic paid by employer. May or may not be included in CTC — check your offer letter.">
              <RupeeInput value={d.employerPF} onChange={v => set("employerPF")(v)} />
            </Field>
            <Field label="Employee PF (annual)" tooltip="12% of basic deducted from your salary and deposited to your EPF account.">
              <RupeeInput value={d.employeePF} onChange={v => set("employeePF")(v)} />
            </Field>
            <Field label="Gratuity (annual)" tooltip="Approximately 4.81% of basic. Paid only after 5 years of continuous service.">
              <RupeeInput value={d.gratuity} onChange={v => set("gratuity")(v)} />
            </Field>
            <Field label="Health insurance premium (annual)">
              <RupeeInput value={d.healthInsurance} onChange={v => set("healthInsurance")(v)} />
            </Field>
          </AccordionSection>

          <AccordionSection title="Variable pay" subtitle="Performance bonuses and one-time payments">
            <Field label="Variable / performance pay (annual)" tooltip="Target variable pay. Usually paid quarterly or annually based on performance rating.">
              <RupeeInput value={d.variablePay} onChange={v => set("variablePay")(v)} />
            </Field>
            <Field label="Joining bonus (one-time)" tooltip="Paid in the first month. Usually has a clawback clause if you leave within 1–2 years.">
              <RupeeInput value={d.joiningBonus} onChange={v => set("joiningBonus")(v)} />
            </Field>
          </AccordionSection>

          <AccordionSection title="Deductions" subtitle="Professional tax and ESI">
            <Field label="Professional tax (annual)" tooltip="State-mandated deduction. Ranges from ₹1,200–₹2,500 per year depending on your state.">
              <RupeeInput value={d.professionalTax} onChange={v => set("professionalTax")(v)} />
            </Field>
          </AccordionSection>

          <AccordionSection title="Tax inputs" subtitle="Optimise your take-home">
            <div className="col-span-2">
              <div className="text-xs font-medium text-[#374151] mb-2">Tax regime</div>
              <div className="flex gap-2">
                {(["new", "old"] as const).map(r => (
                  <button
                    key={r}
                    onClick={() => set("regime")(r)}
                    className={`flex-1 py-2 rounded-xl text-xs font-semibold border transition-all ${
                      d.regime === r
                        ? "bg-[#3730A3] text-white border-[#3730A3]"
                        : "bg-white text-[#64748B] border-[#E2E5F0] hover:border-[#818CF8]"
                    }`}
                  >
                    {r === "new" ? "New regime (default)" : "Old regime"}
                  </button>
                ))}
              </div>
            </div>
            {d.regime === "old" && (
              <>
                <Field label="Section 80C (annual)" tooltip="PF, ELSS, PPF, life insurance premiums, home loan principal. Up to ₹1.5L deductible.">
                  <RupeeInput value={d.section80C} onChange={v => set("section80C")(v)} />
                </Field>
                <Field label="Section 80D (annual)" tooltip="Health insurance premiums for self and family. Up to ₹25,000 deductible.">
                  <RupeeInput value={d.section80D} onChange={v => set("section80D")(v)} />
                </Field>
                <Field label="Monthly rent paid" tooltip="Used to calculate HRA exemption. You must be paying rent and not own a house in the city.">
                  <RupeeInput value={d.monthlyRent} onChange={v => set("monthlyRent")(v)} />
                </Field>
              </>
            )}
          </AccordionSection>

          {/* Sticky CTA */}
          <div className="sticky bottom-4 z-10">
            <button
              onClick={handleSubmit}
              className="w-full bg-[#3730A3] text-white py-4 rounded-xl font-semibold hover:bg-[#312E81] transition-all shadow-xl shadow-indigo-200"
            >
              Calculate My In-Hand Salary →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
