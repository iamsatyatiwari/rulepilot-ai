import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

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

const candidateRule = {
  rule_id: 'DISC-41-amount-greater-than-557p365',
  name: 'Candidate: amount greater_than 557.365',
  description: 'A single numeric threshold proposed from the training split.',
  rationale: 'Generated from training-only thresholds and selected with validation evidence.',
  conditions: [{ field: 'amount', operator: 'greater_than', value: 557.365 }],
  logical_operator: 'and',
  status: 'draft',
  version: 1,
}

const metrics = {
  true_positives: 2,
  false_positives: 4,
  false_negatives: 3,
  true_negatives: 15,
  precision: 1 / 3,
  recall: 0.4,
  false_positive_rate: 4 / 19,
  total_flagged: 6,
  total_evaluated: 24,
}

const discovery = {
  status: 'candidate_found',
  reason: null,
  seed: 41,
  training_count: 72,
  validation_count: 24,
  test_count: 24,
  candidates_evaluated: 34,
  candidate_rule: candidateRule,
  validation_metrics: metrics,
  baseline_test_metrics: metrics,
  candidate_test_metrics: metrics,
  fraud_missed_by_baseline: [],
}

const backtest = {
  evaluated_split: 'test',
  baseline_rule: baselineRule,
  candidate_rule: candidateRule,
  baseline_metrics: metrics,
  candidate_metrics: {
    true_positives: 3,
    false_positives: 6,
    false_negatives: 2,
    true_negatives: 13,
    precision: 1 / 3,
    recall: 0.6,
    false_positive_rate: 6 / 19,
    total_flagged: 9,
    total_evaluated: 24,
  },
  fraud_missed_by_baseline: ['SYN-0003', 'SYN-0008', 'SYN-0015'],
  fraud_missed_by_candidate: ['SYN-0008', 'SYN-0015'],
}

function jsonResponse(payload: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response
}

describe('RulePilot dashboard API integration', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/health')) return jsonResponse({ status: 'ok' })
      if (url.endsWith('/api/v1/rules')) return jsonResponse({ count: 1, items: [baselineRule] })
      if (url.endsWith('/api/v1/rules/discover')) return jsonResponse(discovery)
      if (url.endsWith('/api/v1/backtests/run')) return jsonResponse(backtest)
      if (url.endsWith('/api/v1/info')) return jsonResponse({ name: 'RulePilot AI API', status: 'ready', health: '/health' })
      return jsonResponse({}, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    window.location.hash = '#engine'
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('loads API-backed dataset and candidate data, then renders returned comparison and misses', async () => {
    render(<App />)

    expect(await screen.findByText('120 records')).toBeInTheDocument()
    expect(screen.getByText(candidateRule.rule_id)).toBeInTheDocument()
    expect(screen.getByText('greater_than')).toBeInTheDocument()
    expect(screen.getByText('Pending human review')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /approve|reject/i })).not.toBeInTheDocument()
    expect(screen.getByText(/no rule is ever activated from this dashboard/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /run backtest on held-out test split/i }))

    expect(await screen.findByText('Measured precision / recall trade-off')).toBeInTheDocument()
    expect(screen.getAllByText('33.3%').length).toBeGreaterThan(0)
    expect(screen.getByText('60.0%')).toBeInTheDocument()
    expect(screen.getByText('+20.0 pp')).toBeInTheDocument()
    expect(screen.getByText('3 more')).toBeInTheDocument()

    const table = screen.getByRole('table', { name: /test-split fraud transaction ids/i })
    const baselineOnlyRow = within(table).getByRole('row', { name: /SYN-0003/ })
    const sharedMissRow = within(table).getByRole('row', { name: /SYN-0008/ })
    expect(within(baselineOnlyRow).getByText('Missed')).toBeInTheDocument()
    expect(within(sharedMissRow).getAllByText('Missed')).toHaveLength(2)

    const backtestCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/api/v1/backtests/run'))
    expect(backtestCall).toBeDefined()
    expect(JSON.parse(String(backtestCall?.[1]?.body)).candidate_rule.rule_id).toBe(candidateRule.rule_id)
  })

  it('shows a retry state when the backend cannot be reached', async () => {
    const normalFetch = fetchMock.getMockImplementation() as (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    let failDiscovery = true
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (failDiscovery && String(input).endsWith('/api/v1/rules/discover')) {
        failDiscovery = false
        return jsonResponse({}, 503)
      }
      return normalFetch(input, init)
    })
    render(<App />)

    expect(await screen.findByText('Workspace data is unavailable')).toBeInTheDocument()
    expect(screen.getByRole('alert')).not.toHaveTextContent('Traceback')
    fireEvent.click(screen.getByRole('button', { name: /retry connection/i }))
    expect(await screen.findByText('120 records')).toBeInTheDocument()
  })

  it('keeps API health independent when discovery fails but health remains reachable', async () => {
    const normalFetch = fetchMock.getMockImplementation() as (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith('/api/v1/rules/discover')) return jsonResponse({}, 503)
      return normalFetch(input, init)
    })
    render(<App />)

    expect(await screen.findByText('Workspace data is unavailable')).toBeInTheDocument()
    expect(screen.getByText('API connected')).toBeInTheDocument()
  })

  it('formats zero-denominator metrics as measured zeroes', async () => {
    const zeroMetrics = {
      ...metrics,
      true_positives: 0,
      false_positives: 0,
      false_negatives: 0,
      true_negatives: 24,
      precision: 0,
      recall: 0,
      false_positive_rate: 0,
      total_flagged: 0,
    }
    const zeroBacktest = {
      ...backtest,
      baseline_metrics: zeroMetrics,
      candidate_metrics: zeroMetrics,
      fraud_missed_by_baseline: [],
      fraud_missed_by_candidate: [],
    }
    const normalFetch = fetchMock.getMockImplementation() as (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith('/api/v1/backtests/run')) return jsonResponse(zeroBacktest)
      return normalFetch(input, init)
    })
    render(<App />)
    await screen.findByText('120 records')
    fireEvent.click(screen.getByRole('button', { name: /run backtest on held-out test split/i }))

    expect(await screen.findByText('Measured precision / recall trade-off')).toBeInTheDocument()
    expect(screen.getAllByText('0.0%').length).toBeGreaterThanOrEqual(6)
    expect(screen.getByText(/neither rule missed fraud ids/i)).toBeInTheDocument()
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument()
  })

  it('renders missing metric values as unavailable instead of NaN', async () => {
    const incompleteBacktest = {
      ...backtest,
      candidate_metrics: {
        ...backtest.candidate_metrics,
        precision: undefined,
        total_flagged: undefined,
      },
    }
    const normalFetch = fetchMock.getMockImplementation() as (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith('/api/v1/backtests/run')) return jsonResponse(incompleteBacktest)
      return normalFetch(input, init)
    })
    render(<App />)
    await screen.findByText('120 records')
    fireEvent.click(screen.getByRole('button', { name: /run backtest on held-out test split/i }))

    expect(await screen.findByText('Measured precision / recall trade-off')).toBeInTheDocument()
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
    expect(document.body).toHaveTextContent(/unavailable count of alerts/i)
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument()
  })
})
