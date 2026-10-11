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

export type ApiRoot = { name: string; status: string; health: string }
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

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')

export class ApiRequestError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), 10000)
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: init?.signal ?? controller.signal,
      headers: {
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    })
    if (!response.ok) {
      if (response.status === 422) {
        throw new ApiRequestError('The API rejected the request. Refresh the dashboard and try again.')
      }
      if (response.status === 409) {
        throw new ApiRequestError('This rule conflicts with the existing baseline rule.')
      }
      throw new ApiRequestError('The API could not complete the request. Please retry.')
    }
    return (await response.json()) as T
  } catch (error) {
    if (error instanceof ApiRequestError) throw error
    throw new ApiRequestError('Could not reach the RulePilot API. Check the backend URL and retry.')
  } finally {
    window.clearTimeout(timeoutId)
  }
}

export const getApiBaseUrl = () => API_BASE_URL
