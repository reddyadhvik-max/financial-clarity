// Mirrors backend/app/schemas.py::CTCBreakup and backend/app/ai/schemas.py.
// Every field here maps 1:1 onto a backend field — nothing here is computed
// client-side. The backend accepts either snake_case or these camelCase
// names (see CTCBreakup's alias_generator); we send camelCase for
// readability in the frontend code.

export interface CtcBreakup {
  basic: number;
  hra: number;
  specialAllowance?: number;
  bonus?: number;
  employerPF?: number | null;
  gratuity?: number | null;
  professionalTax?: number;
  healthInsurancePremium?: number;
  rentPaid?: number | null;
  isMetro?: boolean;
  deductionsClaimed?: Record<string, number>;
  noticePeriodDays?: number | null;
  hasServiceBond?: boolean;
  joiningBonusHasClawback?: boolean;
  joiningBonusClawbackPeriodMonths?: number | null;
}

export interface TaxBracket {
  rule_id: string;
  min: number;
  max: number | null;
  rate: number;
  taxable_amount_in_bracket: number;
  tax_in_bracket: number;
}

export interface TaxBreakdown {
  regime: "old" | "new";
  taxable_income: number;
  tax_before_rebate: number;
  brackets: TaxBracket[];
  rebate_rule_id: string;
  rebate_amount: number;
  tax_after_rebate: number;
  cess_rule_id: string;
  cess_amount: number;
  total_tax: number;
}

export interface Deduction {
  name: string;
  rule_id: string;
  amount: number;
  frequency: string;
}

export interface EmployerSideItem {
  amount: number;
  rule_id: string | null;
}

export interface InHandBreakdown {
  regime: "old" | "new";
  ctc_total: number;
  gross_salary_annual: number;
  gross_salary_monthly: number;
  taxable_income: number;
  std_deduction_rule_id: string;
  std_deduction_amount: number;
  hra_exemption_amount: number;
  lta_exemption_amount: number;
  nps_deduction_amount: number;
  deductions: Deduction[];
  total_deductions_annual: number;
  in_hand_annual: number;
  in_hand_monthly: number;
  employer_side: {
    employer_pf: EmployerSideItem;
    employer_esi: EmployerSideItem;
    gratuity_provision: EmployerSideItem;
    employer_nps: EmployerSideItem;
    health_insurance: EmployerSideItem;
  };
  esi_eligible: boolean;
  tax_breakdown: TaxBreakdown;
  variable_pay_frequency: string | null;
  variable_pay_note: string | null;
  equity: unknown;
}

export interface RedFlag {
  flag_id: string;
  severity: "critical" | "warning" | "info";
  rule_id: string | null;
  field: string;
  message: string;
}

export interface BreakdownResponse {
  breakdown: InHandBreakdown;
  red_flags: RedFlag[];
}

export interface ExtractedField {
  value: number | string | boolean | null;
  confidence: number;
  source_text: string | null;
  page: number | null;
}

export interface Ambiguity {
  field: string;
  question: string;
  reason: string;
}

export interface Clause {
  clause_type: string;
  quote: string;
  interpretation: string;
  risk_level: "low" | "medium" | "high";
  page: number | null;
}

export interface Contradiction {
  description: string;
  fields_involved: string[];
}

// Every key is an optional ExtractedField — see backend/app/ai/schemas.py::ParsedOfferAI.
export type ParsedOfferAI = {
  [K in
    | "company_name"
    | "job_title"
    | "city"
    | "ctc_total"
    | "basic"
    | "hra"
    | "special_allowance"
    | "dearness_allowance"
    | "bonus"
    | "retention_bonus"
    | "sales_commission"
    | "employer_pf"
    | "employer_nps"
    | "gratuity"
    | "gratuity_clause_present"
    | "health_insurance_premium"
    | "notice_period_days"
    | "has_service_bond"
    | "joining_bonus_has_clawback"
    | "joining_bonus_clawback_period_months"
    | "equity_type"
    | "equity_grant_value"
    | "equity_vesting_schedule"]?: ExtractedField | null;
} & {
  clauses: Clause[];
  ambiguities: Ambiguity[];
  contradictions: Contradiction[];
  needs_user_input: boolean;
};

export interface ToolCallLog {
  tool: string;
  args: Record<string, unknown>;
  result_summary: string;
}

export interface AgentAnswer {
  answer: string;
  tool_calls: ToolCallLog[];
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ClassificationItem {
  label: string;
  amount: number;
}

export interface ClassificationBucket {
  bucket: string;
  label: string;
  items: ClassificationItem[];
  total: number;
  pct_of_ctc: number | null;
}

export interface ClassificationResult {
  recurring_ctc_total: number;
  one_time_total: number;
  buckets: ClassificationBucket[];
}

export interface QualitySubScore {
  score: number;
  value: number | null;
  benchmark: number | null;
  rule_id: string;
  weight: number;
}

export interface QualityScoreResult {
  overall_score: number;
  weights_rule_id: string;
  sub_scores: Record<string, QualitySubScore>;
}

export interface OfferEvaluation {
  label: string;
  regime: "old" | "new";
  in_hand: InHandBreakdown;
  classification: ClassificationResult;
  quality_score: QualityScoreResult;
}

export interface CompareOffersComputed {
  offer_a: OfferEvaluation;
  offer_b: OfferEvaluation;
  diff: {
    ctc_total: number;
    in_hand_monthly: number;
    in_hand_annual: number;
    quality_score: number;
  };
  best_for_cashflow: "offer_a" | "offer_b" | "tie";
  best_for_total_comp: "offer_a" | "offer_b" | "tie";
}

export interface GratuityMilestone {
  label: string;
  date: string;
  rule_id: string | null;
  status: "past" | "upcoming";
}

export interface GratuityEpfTimeline {
  joining_date: string;
  evaluation_date: string;
  tenure_years: number;
  gratuity: {
    vested: boolean;
    outcome?: "payable" | "forfeited";
    vesting_date?: string;
    days_to_vesting?: number | null;
    rule_id: string;
    note: string;
  };
  epf: {
    continuous_service_years: number;
    tax_free_withdrawal_eligible: boolean;
    rule_id: string;
    withdrawal_note: string;
    transfer_note: string;
  };
  milestones: GratuityMilestone[];
}
