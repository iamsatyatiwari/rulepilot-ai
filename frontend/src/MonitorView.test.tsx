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

const score = (id: string, active: boolean, shadow: boolean) => ({
  transaction_id: id,
  decision: active ? 'flag' : 'allow',
  decided_by: active ? [baselineRule.rule_id] : [],
  active_rules: [verdict(baselineRule, active)],
  shadow_rules: [verdict(approvedRule, shadow)],
  shadow_flagged_by: shadow ? [approvedRule.rule_id] : [],
  caught_only_in_shadow: !active && shadow,
  note: 'Shadow rules are human-approved but not active: they are evaluated for comparison and never change the decision.',
})

const txn = (id: string, amount: number) => ({
  transaction_id: id, amount, account_age_days: 300, transactions_24h: 9, distance_from_home_km: 12, transactions_1h: 7, declined_attempts_24h: 5, card_present: 0,
})

const feed = {
  seed: 1,
  disclaimer: 'Mock bank feed: fresh synthetic transactions.',
  summary: {
    transactions: 3, synthetic_fraud: 2, flagged_by_active_rules: 1, fraud_caught_by_active_rules: 1,
    fraud_caught_only_in_shadow: 1, fraud_missed_by_all_rules: 0, legitimate_flagged_by_active_rules: 0,
    legitimate_flagged_only_in_shadow: 0, shadow_rules: 1,
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
          approved_not_active: [{ rule: approvedRule, approved_by: 'analyst-1', approved_at: '2026-10-14T10:05:00Z', review_comment: 'ok', investigation_id: 'inv-1', advisory_title: 'Preventing Card Testing', technique: 'Card testing', activation: 'not_activated' }],
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

  it('lists active and shadow rules separately', async () => {
    render(<App />)
    const rules = await screen.findByRole('region', { name: 'Rules applied to the feed' })
    expect(await within(rules).findByText('Shadow · approved')).toBeInTheDocument()
    expect(within(rules).getByText('Active · decides')).toBeInTheDocument()
    expect(screen.getByText('1 rule(s) in shadow')).toBeInTheDocument()
  })

  it('streams a feed and highlights fraud caught only by an approved rule', async () => {
    render(<App />)
    await screen.findByText('Shadow · approved')
    vi.useFakeTimers()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /stream 20 transactions/i }))
    })
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
    vi.useRealTimers()

    const table = screen.getByRole('table', { name: /mock bank transactions/i })
    expect(within(table).getAllByRole('row')).toHaveLength(4)
    expect(within(table).getByText('Caught only by approved rule')).toBeInTheDocument()
    expect(within(table).getByText('Caught by active rule')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Feed summary' })).getByText('+1')).toBeInTheDocument()

    const post = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/api/v1/transactions/simulate'))
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ count: 20, seed: 1 })
  })

  it('scores a single transaction and explains that shadow rules do not decide', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Card-testing burst' }))
    fireEvent.click(screen.getByRole('button', { name: /score transaction/i }))

    expect(await screen.findByText('Allowed, but an approved rule would flag it')).toBeInTheDocument()
    expect(screen.getByText(/never change the decision/)).toBeInTheDocument()
    const post = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/api/v1/transactions/score'))
    const body = JSON.parse(String(post?.[1]?.body))
    expect(body.transaction).toMatchObject({ amount: 3.5, transactions_1h: 9, card_present: 0 })
    expect(body.transaction).not.toHaveProperty('ground_truth_fraud')
  })
})
