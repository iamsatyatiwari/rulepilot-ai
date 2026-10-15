import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { localIso } from './BankView'

const approvedRule = {
  rule_id: 'AGT-a48565d1-1',
  name: 'Card testing burst',
  description: 'd',
  rationale: 'r',
  conditions: [{ field: 'transactions_1h', operator: 'greater_than_or_equal', value: 5 }],
  logical_operator: 'and',
  status: 'draft',
  version: 1,
}

const catalog = {
  cards: [
    { card_id: 'card-asha', holder: 'Asha Rao', label: 'Everyday debit', last4: '1001', account_age_days: 2140, days_since_sim_change: 812, description: 'Long-standing customer.' },
    { card_id: 'card-ben', holder: 'Ben Ortiz', label: 'Online shopper credit', last4: '2002', account_age_days: 960, days_since_sim_change: 430, description: 'Shops online.' },
    { card_id: 'card-chen', holder: 'Chen Wei', label: 'Premium current account', last4: '3003', account_age_days: 3120, days_since_sim_change: 1290, description: 'High balance.' },
  ],
  merchants: [
    { merchant_id: 'm-grocer', name: 'Corner Grocer', channel: 'in_store', distance_from_home_km: 2.5, typical_amount: 46.2 },
    { merchant_id: 'm-giftcard', name: 'QuickGift Cards (online)', channel: 'online', distance_from_home_km: 0, typical_amount: 2 },
    { merchant_id: 'm-transfer', name: 'Transfer to new payee: J. Doe', channel: 'online', distance_from_home_km: 0, typical_amount: 1240 },
  ],
  disclaimer: 'Demo bank with fictional cardholders and cards. No real payments are made.',
}

function result(body: { history: unknown[]; cvv_correct: boolean }) {
  const shadow = body.history.length >= 5
  return {
    outcome: body.cvv_correct ? 'approved' : 'declined_by_issuer',
    explanation: body.cvv_correct ? 'Approved: no active rule flagged this payment.' : 'Declined by the card issuer.',
    shadow_summary: shadow ? 'Approved RulePilot rule AGT-a48565d1-1 would flag this payment.' : 'No approved RulePilot rule would flag this payment.',
    features: { transactions_1h: body.history.length, declined_attempts_24h: 0, card_present: 0, new_payee: 0, new_device: 1, days_since_sim_change: 430, credential_resets_24h: 0 },
    score: { transaction_id: 'BANK', decision: 'allow', decided_by: [], active_rules: [], shadow_rules: [], shadow_flagged_by: shadow ? [approvedRule.rule_id] : [], caught_only_in_shadow: shadow, note: '' },
  }
}

const jsonResponse = (payload: unknown) => ({ ok: true, status: 200, json: async () => payload }) as Response

describe('Demo bank', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    window.location.hash = '#bank'
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/health')) return jsonResponse({ status: 'ok' })
      if (url.endsWith('/api/v1/bank/catalog')) return jsonResponse(catalog)
      if (url.endsWith('/api/v1/rule-catalog')) return jsonResponse({ active: [], approved_not_active: [{ rule: approvedRule, approved_by: 'analyst', approved_at: '2026-10-15T10:00:00Z', review_comment: 'ok', investigation_id: 'inv-1', advisory_title: 'Preventing Card Testing', technique: 'Card testing', activation: 'not_activated' }] })
      if (url.endsWith('/api/v1/bank/payments')) return jsonResponse(result(JSON.parse(String(init?.body))))
      throw new Error(`unexpected ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('runs the card-testing attack with growing card history and shows shadow catches', async () => {
    render(<App />)
    expect(await screen.findByText('AGT-a48565d1-1')).toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: /card-testing attack/i }))

    const activity = screen.getByRole('region', { name: 'Card activity' })
    const paymentCalls = () => fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/api/v1/bank/payments'))
    await waitFor(() => expect(paymentCalls()).toHaveLength(8), { timeout: 4000 })
    await waitFor(() => expect(within(activity).getAllByText(/would flag this \(shadow mode/)).toHaveLength(3))
    const payments = paymentCalls()
    const bodies = payments.map(([, init]) => JSON.parse(String(init?.body)))
    expect(bodies.map((body) => body.history.length)).toEqual([0, 1, 2, 3, 4, 5, 6, 7])
    expect(bodies.every((body) => body.card_id === 'card-ben' && /[+-]\d\d:\d\d$/.test(body.at))).toBe(true)
    expect(within(activity).getAllByText('Approved').length).toBeGreaterThan(0)
    expect(within(activity).getAllByText('Declined by issuer').length).toBeGreaterThan(0)
  })

  it('sends SIM-swap security events with the takeover transfer', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /sim-swap takeover/i }))
    await screen.findByText(/Transfer to new payee/, { selector: '.activity-main span' })
    const body = JSON.parse(String(fetchMock.mock.calls.find(([input]) => String(input).endsWith('/api/v1/bank/payments'))?.[1]?.body))
    expect(body).toMatchObject({ card_id: 'card-chen', merchant_id: 'm-transfer', amount: 1240, new_device: true })
    expect(body.security_events.map((event: { type: string }) => event.type)).toEqual(['sim_change', 'credential_reset', 'new_device_login'])
  })

  it('explains when no approved rule covers the attack that was run', async () => {
    render(<App />)
    expect(await screen.findByText(/try the/)).toHaveTextContent('Card-testing attack')
    fireEvent.click(await screen.findByRole('button', { name: /sim-swap takeover/i }))
    expect(await screen.findByText(/None of your approved rules reacted to this attack/)).toHaveTextContent('AGT-a48565d1-1 reacts to the Card-testing attack')
  })

  it('formats local timestamps with the UTC offset', () => {
    expect(localIso(new Date('2026-10-15T08:00:00Z'))).toMatch(/^2026-10-1\dT\d\d:\d\d:00[+-]\d\d:\d\d$/)
  })
})

describe('Start here', () => {
  beforeEach(() => {
    window.location.hash = ''
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/v1/bank/catalog')) return jsonResponse(catalog)
      if (url.endsWith('/api/v1/rule-catalog')) return jsonResponse({ active: [], approved_not_active: [] })
      return jsonResponse({ status: 'ok' })
    }))
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('is the default page and links to the demo bank', async () => {
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'From fraud advisory to a tested rule' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /open the demo bank/i }))
    expect(window.location.hash).toBe('#bank')
  })
})
