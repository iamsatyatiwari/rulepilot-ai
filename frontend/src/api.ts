export type RuleCondition = {
  field: string
  operator: string
  value: number
}

export type Rule = {
  rule_id: string
  name: string
  description: string
  rationale: string
  conditions: RuleCondition[]
  logical_operator: 'and' | 'or'
  status: 'draft' | 'pending_review' | 'approved' | 'rejected' | string
  version: number
  created_at?: string
  created_by?: string
}

export type Metrics = {
  true_positives: number
  false_positives: number
  false_negatives: number
  true_negatives: number
  precision: number
  recall: number
  false_positive_rate: number
  total_flagged: number
  total_evaluated: number
}

export type ApiInfo = { name: string; status: string; version?: string; health: string }
export type ApiHealth = { status: string }
export type RuleList = { count: number; items: Rule[] }

export type DiscoveryReport = {
  status: string
  reason: string | null
  seed: number
  training_count: number
  validation_count: number
  test_count: number
  candidates_evaluated: number
  candidate_rule: Rule | null
  validation_metrics: Metrics | null
  baseline_test_metrics: Metrics | null
  candidate_test_metrics: Metrics | null
  fraud_missed_by_baseline: string[]
}

export type BacktestReport = {
  evaluated_split: string
  baseline_rule: Rule
  candidate_rule: Rule
  baseline_metrics: Metrics
  candidate_metrics: Metrics
  fraud_missed_by_baseline: string[]
  fraud_missed_by_candidate?: string[]
}

export type AgentStatus = {
  configured: boolean
  model: string
  framework: string
  max_llm_calls: number
  timeout_seconds: number
  max_candidates: number
}

export type AdvisorySummary = {
  advisory_id: string
  title: string
  publisher: string
  source_url: string
  published_date: string | null
  retrieved_at: string
  source_type: string
  rights_note: string
  content_sha256: string
  excerpt: string
}

export type AdvisoryList = { count: number; items: AdvisorySummary[] }

export type DatasetInfo = {
  dataset_id: string
  version: string
  generator_seed: number
  size: number
  synthetic: boolean
  description: string
  limitations: string
}

export type SplitComparison = {
  evaluated_split: string
  seed: number
  baseline_metrics: Metrics
  candidate_metrics: Metrics
  combined_metrics: Metrics
  fraud_missed_by_baseline: string[]
  fraud_missed_by_candidate: string[]
  fraud_missed_by_combined: string[]
}

export type Findings = {
  technique_name: string
  summary: string
  behaviors: string[]
  indicators: string[]
  required_fields: string[]
  testable_hypotheses: string[]
  uncertainties: string[]
  evidence_quotes: string[]
}

export type AgentConclusion = {
  coverage_assessment: string
  selected_candidate_rule_id: string | null
  recommendation: string
  rationale: string
  limitations: string[]
}

export type Coverage = {
  status: 'testable' | 'partially_testable' | 'not_testable'
  available_fields: string[]
  missing_fields: string[]
  existing_rule_fields: string[]
  existing_rules_use_required_fields: string[]
}

export type InvestigationStatus =
  | 'pending_human_review'
  | 'covered_by_existing_rules'
  | 'insufficient_evidence'
  | 'not_testable'
  | 'agent_incomplete'

export type InvestigationReport = {
  customer_report_check?: { reported_cases: number; caught_by_proposed_rule: number } | null
  investigation_id: string
  created_at: string
  origin: 'live' | 'recorded' | 'scheduled'
  status: InvestigationStatus
  headline: string
  advisory: AdvisorySummary
  dataset: DatasetInfo
  seed: number
  split_sizes: Record<string, number>
  model_run: {
    provider: string
    framework: string
    model: string
    model_version: string | null
    max_llm_calls: number
    timeout_seconds: number
    llm_calls: number
    input_tokens: number
    output_tokens: number
    errors: string[]
  }
  findings: Findings | null
  evidence_quotes: { quote: string; verified: boolean }[]
  coverage: Coverage | null
  agent_conclusion: AgentConclusion | null
  candidates: { rule: Rule; validation: SplitComparison }[]
  selected_rule: Rule | null
  baseline_rule: Rule
  reference_rules?: Rule[]
  review_history_used?: number
  holdout: SplitComparison | null
  holdout_delta: {
    recall_change: number
    precision_change: number
    false_positive_rate_change: number
    alert_change: number
    fraud_newly_detected: number
  } | null
  guardrails: { check: string; passed: boolean; detail: string }[]
  trace: { step: number; tool: string; arguments: Record<string, unknown>; ok: boolean; summary: string }[]
  limitations: string[]
}

export type ReviewDecision = 'approve' | 'reject' | 'request_changes'

export type ReviewRecord = {
  review_id: string
  investigation_id: string
  rule_id: string
  rule_version: number
  decision: ReviewDecision
  reviewer: string
  comment: string
  decided_at: string
  activation: 'not_activated' | 'active'
}

export type StoredInvestigation = { report: InvestigationReport; reviews: ReviewRecord[] }

export type InvestigationSummary = {
  investigation_id: string
  created_at: string
  origin: 'live' | 'recorded' | 'scheduled'
  status: InvestigationStatus
  advisory_title: string
  advisory_id: string
  selected_rule_id: string | null
  review_decision: ReviewDecision | null
}

export type CatalogEntry = {
  rule: Rule
  approved_by: string
  approved_at: string
  review_comment: string
  investigation_id: string
  advisory_title: string
  technique: string | null
  activation: 'not_activated' | 'active'
}

export type RuleCatalog = { active: Rule[]; approved_not_active: CatalogEntry[]; approved_active?: CatalogEntry[] }

export type Transaction = {
  transaction_id?: string | null
  amount?: number | null
  account_age_days?: number | null
  transactions_24h?: number | null
  distance_from_home_km?: number | null
  transactions_1h?: number | null
  declined_attempts_24h?: number | null
  card_present?: number | null
  hour_of_day?: number | null
  new_device?: number | null
  days_since_sim_change?: number | null
  credential_resets_24h?: number | null
  new_payee?: number | null
}

export type RuleVerdict = {
  rule_id: string
  name: string
  version: number
  flagged: boolean
  missing_fields: string[]
  investigation_id: string | null
  technique: string | null
}

export type TransactionScore = {
  transaction_id: string | null
  decision: 'flag' | 'allow'
  decided_by: string[]
  active_rules: RuleVerdict[]
  shadow_rules: RuleVerdict[]
  shadow_flagged_by: string[]
  caught_only_in_shadow: boolean
  approved_flagged_by?: string[]
  caught_only_by_approved?: boolean
  note: string
}

export type FeedItem = { transaction: Transaction; synthetic_fraud: boolean; score: TransactionScore }

export type FeedSummary = {
  transactions: number
  synthetic_fraud: number
  flagged_by_active_rules: number
  fraud_caught_by_active_rules: number
  fraud_caught_only_in_shadow: number
  fraud_missed_by_all_rules: number
  legitimate_flagged_by_active_rules: number
  legitimate_flagged_only_in_shadow: number
  shadow_rules: number
  fraud_caught_by_approved_rules?: number
  legitimate_flagged_by_approved_rules?: number
  approved_rules?: number
}

export type SimulateResponse = { seed: number; disclaimer: string; summary: FeedSummary; items: FeedItem[] }

export type CustomAdvisory = { title: string; publisher: string; source_url: string; text: string }

const configuredBase = import.meta.env.VITE_API_BASE_URL as string | undefined
// Deployed builds are served by the API itself, so the same origin is used.
const API_BASE_URL = (configuredBase || (import.meta.env.PROD ? '' : 'http://localhost:8000')).replace(/\/+$/, '')

export const DEFAULT_TIMEOUT_MS = 10000
export const INVESTIGATION_TIMEOUT_MS = 180000

export class ApiRequestError extends Error {
  status?: number
  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
  }
}

function messageForStatus(status: number) {
  if (status === 422) return 'The API rejected the request. Check the inputs and try again.'
  if (status === 409) return 'This request conflicts with the current state of the rule or investigation.'
  if (status === 404) return 'The requested item was not found.'
  if (status === 429) return 'An investigation is already running. Please wait a moment and retry.'
  if (status === 503) return 'The Gemini agent is not configured on the server.'
  return 'The API could not complete the request. Please retry.'
}

export async function apiRequest<T>(path: string, init?: RequestInit, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: init?.signal ?? controller.signal,
      headers: {
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    })
    if (!response.ok) throw new ApiRequestError(messageForStatus(response.status), response.status)
    if (response.status === 204) return undefined as T
    return (await response.json()) as T
  } catch (error) {
    if (error instanceof ApiRequestError) throw error
    throw new ApiRequestError('Could not reach the RulePilot API. Check the backend URL and retry.')
  } finally {
    window.clearTimeout(timeoutId)
  }
}

export const postJson = <T,>(path: string, body: unknown, timeoutMs?: number) =>
  apiRequest<T>(path, { method: 'POST', body: JSON.stringify(body) }, timeoutMs)

export const getApiBaseUrl = () => API_BASE_URL

export type DemoCard = {
  card_id: string
  holder: string
  label: string
  last4: string
  account_age_days: number
  days_since_sim_change: number
  description: string
}

export type BankMerchant = {
  merchant_id: string
  name: string
  channel: 'online' | 'in_store'
  distance_from_home_km: number
  typical_amount: number
}

export type BankCatalog = { cards: DemoCard[]; merchants: BankMerchant[]; disclaimer: string }

export type BankHistoryItem = { at: string; merchant_id: string; amount: number; declined: boolean }
export type SecurityEvent = { at: string; type: 'sim_change' | 'credential_reset' | 'new_device_login' }

export type PaymentRequest = {
  card_id: string
  merchant_id: string
  amount: number
  at: string
  cvv_correct: boolean
  new_device: boolean
  history: BankHistoryItem[]
  security_events: SecurityEvent[]
}

export type PaymentResult = {
  outcome: 'approved' | 'held_for_review' | 'declined_by_issuer'
  explanation: string
  shadow_summary: string
  features: Transaction
  score: TransactionScore
}

export type LabRule = { rule: Rule; source: 'baseline' | 'approved_active' | 'candidate'; label: string }
export type ConditionCheck = { field: string; operator: string; threshold: number; value: number | null; passed: boolean | null }
export type Explanation = { rule_id: string; logical_operator: string; flagged: boolean; conditions: ConditionCheck[] }
export type TestCase = {
  case_id: string
  name: string
  transaction: Transaction
  expected: 'fraud' | 'legit'
  note: string
  created_by: string
  source: 'analyst' | 'customer_report'
  created_at: string
}
export type CaseResult = { case: TestCase; flagged: boolean; passed: boolean }
export type RunSummary = {
  rule_id: string
  cases: number
  passed: number
  fraud_cases: number
  fraud_caught: number
  legit_cases: number
  false_alarms: number
  results: CaseResult[]
}
export type ReportsSummary = {
  reports: number
  missed_by_active_rules: number
  ready_to_investigate: boolean
  min_missed_reports: number
  digest_advisory_id: string | null
  digest_preview: string | null
}
