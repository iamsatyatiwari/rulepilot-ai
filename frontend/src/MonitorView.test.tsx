import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
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

const approvedRule = {
  ...baselineRule,
  rule_id: 'AGT-abc12345-3',
  name: 'Card testing frequency and declines',
  conditions: [{ field: 'declined_attempts_24h', operator: 'greater_than_or_equal', value: 3 }],
}

const verdict = (rule: typeof baselineRule, flagged: boolean) => ({
  rule_id: rule.rule_id, name: rule.name, version: 1, flagged, missing_fields: [], investigation_id: null, technique: null,
})

const score = (id: string, base: boolean, approved: boolean) => ({
  transaction_id: id,
  decision: base || approved ? 'flag' : 'allow',
  decided_by: [...(base ? [baselineRule.rule_id] : []), ...(approved ? [approvedRule.rule_id] : [])],
  active_rules: [verdict(baselineRule, base), { ...verdict(approvedRule, approved), investigation_id: 'inv-1' }],
  shadow_rules: [],
  shadow_flagged_by: [],
  caught_only_in_shadow: false,
  approved_flagged_by: approved ? [approvedRule.rule_id] : [],
  caught_only_by_approved: approved && !base,
  note: 'Approved rules are active and can decide. Shadow rules, if any, are evaluated for comparison and never change the decision.',
})

const txn = (id: string, amount: number) => ({
  transaction_id: id, amount, account_age_days: 300, transactions_24h: 9, distance_from_home_km: 12, transactions_1h: 7, declined_attempts_24h: 5, card_present: 0,
})

const feed = {
  seed: 1,
  disclaimer: 'Mock bank feed: fresh synthetic transactions.',
  summary: {
    transactions: 3, synthetic_fraud: 2, flagged_by_active_rules: 2, fraud_caught_by_active_rules: 2,
    fraud_caught_only_in_shadow: 0, fraud_missed_by_all_rules: 0, legitimate_flagged_by_active_rules: 0,
    legitimate_flagged_only_in_shadow: 0, shadow_rules: 0,
    fraud_caught_by_approved_rules: 1, legitimate_flagged_by_approved_rules: 0, approved_rules: 1,
  },
  items: [
    { transaction: txn('FEED-1-001', 4.5), synthetic_fraud: true, score: score('FEED-1-001', false, true) },
    { transaction: txn('FEED-1-002', 2400), synthetic_fraud: true, score: score('FEED-1-002', true, false) },
    { transaction: txn('FEED-1-003', 30), synthetic_fraud: false, score: score('FEED-1-003', false, false) },
  ],
}

function jsonResponse(payload: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => payload } as Response
}

describe('Transaction monitor', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    window.location.hash = '#monitor'
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/health')) return jsonResponse({ status: 'ok' })
      if (url.endsWith('/api/v1/rule-catalog')) {
        return jsonResponse({
          active: [baselineRule],
          approved_not_active: [{ rule: approvedRule, approved_by: 'analyst-1', approved_at: '2026-10-14T10:05:00Z', review_comment: 'ok', investigation_id: 'inv-1', advisory_title: 'Preventing Card Testing', technique: 'Card testing', activation: 'active' }],
        })
      }
      if (url.endsWith('/api/v1/transactions/simulate') && init?.method === 'POST') return jsonResponse(feed)
      if (url.endsWith('/api/v1/transactions/score') && init?.method === 'POST') {
        const body = JSON.parse(String(init.body))
        return jsonResponse(score(body.transaction.transaction_id, false, true))
      }
      return jsonResponse({}, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('lists the original and approved rules as active', async () => {
    render(<App />)
    const rules = await screen.findByRole('region', { name: 'Rules applied to the feed' })
    expect(await within(rules).findByText('Approved · active')).toBeInTheDocument()
    expect(within(rules).getByText('Active · decides')).toBeInTheDocument()
    expect(screen.getByText('1 approved rule(s) active')).toBeInTheDocument()
  })

  it('streams a feed and highlights fraud caught by an approved rule', async () => {
    render(<App />)
    await screen.findByText('Approved · active')
    vi.useFakeTimers()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /stream 20 transactions/i }))
    })
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    vi.useRealTimers()

    const table = screen.getByRole('table', { name: /mock bank transactions/i })
    expect(within(table).getAllByRole('row')).toHaveLength(4)
    expect(within(table).getByText('Caught by approved rule')).toBeInTheDocument()
    expect(within(table).getByText('Caught by active rule')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Feed summary' })).getByText('+1')).toBeInTheDocument()

    const post = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/api/v1/transactions/simulate'))
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ count: 20, seed: 1 })
  })

  it('scores a single transaction and shows the approved rule deciding', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Card-testing burst' }))
    fireEvent.click(screen.getByRole('button', { name: /score transaction/i }))

    expect(await screen.findByText('Flagged by an approved rule')).toBeInTheDocument()
    expect(screen.getByText(/Approved rules are active/)).toBeInTheDocument()
    const post = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/api/v1/transactions/score'))
    const body = JSON.parse(String(post?.[1]?.body))
    expect(body.transaction).toMatchObject({ amount: 3.5, transactions_1h: 9, card_present: 0 })
    expect(body.transaction).not.toHaveProperty('ground_truth_fraud')
  })

  it('sends the SIM-swap preset with device, SIM-change, and payee signals as integers', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'SIM-swap takeover' }))
    fireEvent.click(screen.getByRole('button', { name: /score transaction/i }))

    await screen.findByText(/Approved rules are active/)
    const post = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/api/v1/transactions/score'))
    const body = JSON.parse(String(post?.[1]?.body))
    expect(body.transaction).toMatchObject({ days_since_sim_change: 1, new_device: 1, credential_resets_24h: 2, new_payee: 1, hour_of_day: 2 })
  })
})
