import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const metrics = (tp: number, fp: number, fn: number, tn: number) => ({
  true_positives: tp,
  false_positives: fp,
  false_negatives: fn,
  true_negatives: tn,
  precision: tp + fp ? tp / (tp + fp) : 0,
  recall: tp + fn ? tp / (tp + fn) : 0,
  false_positive_rate: fp + tn ? fp / (fp + tn) : 0,
  total_flagged: tp + fp,
  total_evaluated: tp + fp + fn + tn,
})

const baselineRule = {
  rule_id: 'RP-BASELINE-001',
  name: 'High transaction amount baseline',
  description: 'Flags a high amount.',
  rationale: 'Documented synthetic baseline.',
  conditions: [{ field: 'amount', operator: 'greater_than_or_equal', value: 1500 }],
  logical_operator: 'and',
  status: 'approved',
  version: 1,
}

const candidate = {
  rule_id: 'AGT-abc12345-1',
  name: 'Small card-not-present burst',
  description: 'Agent-proposed candidate.',
  rationale: 'Advisory describes small-dollar repeated attempts.',
  conditions: [
    { field: 'amount', operator: 'less_than', value: 25 },
    { field: 'transactions_1h', operator: 'greater_than_or_equal', value: 3 },
  ],
  logical_operator: 'and',
  status: 'draft',
  version: 1,
}

const advisory = {
  advisory_id: 'jpm-card-testing',
  title: 'Preventing Card Testing: Spot It Early, Stop It Fast',
  publisher: 'J.P. Morgan Payments',
  source_url: 'https://www.jpmorgan.com/insights/payments/merchant-services/preventing-card-testing-attacks',
  published_date: null,
  retrieved_at: '2026-10-14',
  source_type: 'industry_guidance',
  rights_note: 'Short attributed excerpts.',
  content_sha256: 'a'.repeat(64),
  excerpt: 'Card testing is when fraudsters attempt to validate stolen card details by making $0 or low-dollar transactions.',
}

const simAdvisory = { ...advisory, advisory_id: 'fbi-ic3-sim-swap-2022', title: 'Criminals Increasing SIM Swap Schemes', source_type: 'government_psa' }

const comparison = {
  evaluated_split: 'test',
  seed: 41,
  baseline_metrics: metrics(15, 8, 24, 1155),
  candidate_metrics: metrics(20, 6, 19, 1157),
  combined_metrics: metrics(35, 14, 4, 1149),
  fraud_missed_by_baseline: [],
  fraud_missed_by_candidate: [],
  fraud_missed_by_combined: [],
}

function report(overrides: Record<string, unknown> = {}) {
  return {
    investigation_id: 'inv-1',
    created_at: '2026-10-14T10:00:00Z',
    origin: 'live',
    status: 'pending_human_review',
    headline: 'Adding AGT-abc12345-1 changed held-out rule-set recall by +51.3 pp.',
    advisory,
    dataset: { dataset_id: 'card-scenario-v2', version: '2.0.0', generator_seed: 2027, size: 6000, synthetic: true, description: 'd', limitations: 'Fully synthetic.' },
    seed: 41,
    split_sizes: { train: 3599, validation: 1199, test: 1202 },
    model_run: { provider: 'google-gemini', framework: 'google-adk', model: 'gemini-3.8-flash', model_version: null, max_llm_calls: 12, timeout_seconds: 120, llm_calls: 6, input_tokens: 9000, output_tokens: 800, errors: [] },
    findings: {
      technique_name: 'Card testing',
      summary: 'Fraudsters validate stolen cards with low-dollar attempts.',
      behaviors: ['Small-dollar attempts'],
      indicators: ['High decline rate'],
      required_fields: ['amount', 'transactions_1h', 'ip_address'],
      testable_hypotheses: ['Small high-velocity CNP attempts'],
      uncertainties: ['Merchant-side IP signals are unavailable'],
      evidence_quotes: [advisory.excerpt],
    },
    evidence_quotes: [
      { quote: advisory.excerpt, verified: true },
      { quote: 'An invented sentence', verified: false },
    ],
    coverage: { status: 'partially_testable', available_fields: ['amount', 'transactions_1h'], missing_fields: ['ip_address'], existing_rule_fields: ['amount'], existing_rules_use_required_fields: ['amount'] },
    agent_conclusion: { coverage_assessment: 'gap_identified', selected_candidate_rule_id: candidate.rule_id, recommendation: 'recommend_for_review', rationale: 'Baseline only checks large amounts.', limitations: [] },
    candidates: [{ rule: candidate, validation: { ...comparison, evaluated_split: 'validation' } }],
    selected_rule: candidate,
    baseline_rule: baselineRule,
    holdout: comparison,
    holdout_delta: { recall_change: 0.513, precision_change: 0.062, false_positive_rate_change: 0.0052, alert_change: 26, fraud_newly_detected: 20 },
    guardrails: [
      { check: 'Untrusted input isolated', passed: true, detail: 'Delimited.' },
      { check: 'Evidence quotes verified', passed: false, detail: '1 of 2 quotes found verbatim in the source text.' },
    ],
    trace: [
      { step: 1, tool: 'get_rule_catalog', arguments: {}, ok: true, summary: '1 existing rule(s); 7 available fields' },
      { step: 2, tool: 'evaluate_candidate_rule', arguments: {}, ok: false, summary: 'Rejected: fields not available in this dataset: ip_address' },
    ],
    limitations: ['Fully synthetic.', 'Public intelligence is not transaction ground truth.'],
    ...overrides,
  }
}

function jsonResponse(payload: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => payload } as Response
}

describe('Intelligence investigations workspace', () => {
  let fetchMock: ReturnType<typeof vi.fn>
  let stored: { report: ReturnType<typeof report>; reviews: unknown[] }

  beforeEach(() => {
    window.location.hash = ''
    stored = { report: report(), reviews: [] }
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/health')) return jsonResponse({ status: 'ok' })
      if (url.endsWith('/api/v1/agent/status')) return jsonResponse({ configured: true, model: 'gemini-3.8-flash', framework: 'google-adk', max_llm_calls: 12, timeout_seconds: 120, max_candidates: 3 })
      if (url.endsWith('/api/v1/advisories')) return jsonResponse({ count: 2, items: [advisory, simAdvisory] })
      if (url.endsWith('/api/v1/investigations') && init?.method === 'POST') {
        const body = JSON.parse(String(init.body))
        if (body.advisory_id === simAdvisory.advisory_id) {
          return jsonResponse({
            report: report({ investigation_id: 'inv-2', status: 'not_testable', headline: 'Required data fields are missing; no rule was tested.', advisory: simAdvisory, candidates: [], selected_rule: null, holdout: null, holdout_delta: null, coverage: { status: 'not_testable', available_fields: [], missing_fields: ['sim_swap_event'], existing_rule_fields: ['amount'], existing_rules_use_required_fields: [] } }),
            reviews: [],
          })
        }
        return jsonResponse(stored)
      }
      if (url.endsWith('/api/v1/investigations')) return jsonResponse([])
      if (url.endsWith('/api/v1/rule-catalog')) {
        const approved = (stored.reviews as { decision: string; reviewer: string; comment: string; decided_at: string }[])
          .filter((review) => review.decision === 'approve')
          .map((review) => ({ rule: { ...candidate, status: 'approved' }, approved_by: review.reviewer, approved_at: review.decided_at, review_comment: review.comment, investigation_id: 'inv-1', advisory_title: advisory.title, technique: 'Card testing', activation: 'not_activated' }))
        return jsonResponse({ active: [baselineRule], approved_not_active: approved })
      }
      if (url.endsWith('/api/v1/investigations/inv-1/review')) {
        const body = JSON.parse(String(init?.body))
        stored = { ...stored, reviews: [{ review_id: 'inv-1-R1', investigation_id: 'inv-1', rule_id: candidate.rule_id, rule_version: 1, decided_at: '2026-10-14T10:05:00Z', activation: 'not_activated', ...body }] }
        return jsonResponse(stored.reviews[0])
      }
      if (url.endsWith('/api/v1/investigations/inv-1')) return jsonResponse(stored)
      return jsonResponse({}, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('runs an investigation and renders source-linked, verified, measured results', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: `Investigate ${advisory.title}` }))

    expect(await screen.findByText(/changed held-out rule-set recall/)).toBeInTheDocument()
    expect(screen.getByText('Verified in source')).toBeInTheDocument()
    expect(screen.getByText('Not found in source')).toBeInTheDocument()
    expect(screen.getByText('ip_address')).toBeInTheDocument()
    expect(screen.getByText('+51.3 pp')).toBeInTheDocument()
    expect(screen.getByText('Rejected: fields not available in this dataset: ip_address')).toBeInTheDocument()
    expect(screen.getByText(/1 of 2 quotes found verbatim/)).toBeInTheDocument()
    expect(screen.getByRole('table', { name: /candidate rules and validation metrics/i })).toHaveTextContent('Selected')

    const post = fetchMock.mock.calls.find(([input, init]) => String(input).endsWith('/api/v1/investigations') && init?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ advisory_id: advisory.advisory_id })
  })

  it('records a human review decision without activating the rule', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: `Investigate ${advisory.title}` }))
    await screen.findByText(/changed held-out rule-set recall/)

    fireEvent.click(screen.getByRole('button', { name: /approve for further testing/i }))
    expect(await screen.findByText(/enter a reviewer name and a comment/i)).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Reviewer'), { target: { value: 'analyst-1' } })
    fireEvent.change(screen.getByLabelText('Comment'), { target: { value: 'Run on real data next.' } })
    fireEvent.click(screen.getByRole('button', { name: /approve for further testing/i }))

    const history = await screen.findByRole('list', { name: 'Review history' })
    expect(within(history).getByText('Approved for further testing')).toBeInTheDocument()
    expect(within(history).getByText(/activation: not activated/)).toBeInTheDocument()

    const catalog = screen.getByRole('region', { name: 'Reviewed rule catalog' })
    expect(await within(catalog).findByText('Approved · not active')).toBeInTheDocument()
    expect(within(catalog).getByText(/Approved by analyst-1/)).toBeInTheDocument()
  })

  it('shows the reviewed rule catalog and a covered-by-existing-rules result', async () => {
    const normalFetch = fetchMock.getMockImplementation() as (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith('/api/v1/investigations') && init?.method === 'POST') {
        return jsonResponse({
          report: report({ status: 'covered_by_existing_rules', headline: 'The agent assessed this technique as already covered by the reviewed rule set (RP-BASELINE-001, AGT-abc12345-1); no new rule is proposed.', selected_rule: null, holdout: null, holdout_delta: null, reference_rules: [baselineRule, { ...candidate, status: 'approved' }], review_history_used: 1 }),
          reviews: [],
        })
      }
      return normalFetch(input, init)
    })
    render(<App />)
    expect(await screen.findByRole('region', { name: 'Reviewed rule catalog' })).toHaveTextContent('Active baseline')
    fireEvent.click(await screen.findByRole('button', { name: `Investigate ${advisory.title}` }))
    expect(await screen.findByText(/already covered by the reviewed rule set/)).toBeInTheDocument()
    expect(screen.getByText(/compared against 2 reviewed rule\(s\) · 1 prior review\(s\)/)).toBeInTheDocument()
    expect(screen.getByText('No candidate awaits review')).toBeInTheDocument()
  })

  it('shows an untestable advisory without inventing a candidate or held-out result', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: `Investigate ${simAdvisory.title}` }))

    expect(await screen.findByText('Required data fields are missing; no rule was tested.')).toBeInTheDocument()
    expect(screen.getByText('sim_swap_event')).toBeInTheDocument()
    expect(screen.queryByText(/HELD-OUT TEST/)).not.toBeInTheDocument()
    expect(screen.getByText('No candidate awaits review')).toBeInTheDocument()
  })

  it('disables live runs when the agent is not configured', async () => {
    const normalFetch = fetchMock.getMockImplementation() as (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith('/api/v1/agent/status')) return jsonResponse({ configured: false, model: 'gemini-3.8-flash', framework: 'google-adk', max_llm_calls: 12, timeout_seconds: 120, max_candidates: 3 })
      return normalFetch(input, init)
    })
    render(<App />)
    expect(await screen.findByText(/no Gemini credentials are configured/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: `Investigate ${advisory.title}` })).toBeDisabled()
  })
})
