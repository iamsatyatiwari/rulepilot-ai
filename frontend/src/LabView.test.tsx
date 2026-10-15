import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const simRule = {
  rule_id: 'AGT-550906a0-2',
  name: 'Recent SIM change and credential reset',
  description: 'd',
  rationale: 'r',
  conditions: [
    { field: 'days_since_sim_change', operator: 'less_than_or_equal', value: 2 },
    { field: 'credential_resets_24h', operator: 'greater_than_or_equal', value: 1 },
  ],
  logical_operator: 'and',
  status: 'approved',
  version: 1,
}

const match = { transaction_id: 'LAB-MATCH', amount: 42, days_since_sim_change: 2, credential_resets_24h: 1, hour_of_day: 14 }
const miss = { ...match, transaction_id: 'LAB-MISS', days_since_sim_change: 3 }
const jsonResponse = (payload: unknown, status = 200) => ({ ok: status < 300, status, json: async () => payload }) as Response

describe('Rule lab', () => {
  let fetchMock: ReturnType<typeof vi.fn>
  let cases: unknown[]

  beforeEach(() => {
    window.location.hash = '#lab'
    cases = []
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const body = init?.body ? JSON.parse(String(init.body)) : null
      if (url.endsWith('/health')) return jsonResponse({ status: 'ok' })
      if (url.endsWith('/api/v1/lab/rules')) return jsonResponse([{ rule: simRule, source: 'approved_active', label: 'AGT-550906a0-2 · SIM swap (approved, active)' }])
      if (url.endsWith('/api/v1/lab/generate')) return jsonResponse(body.match ? match : miss)
      if (url.endsWith('/api/v1/lab/explain')) {
        const days = body.transaction.days_since_sim_change
        const resets = body.transaction.credential_resets_24h
        const conditions = [
          { field: 'days_since_sim_change', operator: 'less_than_or_equal', threshold: 2, value: days ?? null, passed: days == null ? null : days <= 2 },
          { field: 'credential_resets_24h', operator: 'greater_than_or_equal', threshold: 1, value: resets ?? null, passed: resets == null ? null : resets >= 1 },
        ]
        return jsonResponse({ rule_id: simRule.rule_id, logical_operator: 'and', flagged: conditions.every((c) => c.passed), conditions })
      }
      if (url.endsWith('/api/v1/lab/cases') && init?.method === 'POST') {
        const saved = { ...body, case_id: `case-${cases.length + 1}`, source: 'analyst', created_by: 'analyst', note: '', created_at: '2026-10-16T10:00:00Z' }
        cases.push(saved)
        return jsonResponse(saved, 201)
      }
      if (url.endsWith('/api/v1/lab/cases')) return jsonResponse([...cases])
      if (url.endsWith('/api/v1/lab/run')) {
        const results = (cases as { case_id: string; expected: string }[]).map((c) => ({ case: c, flagged: true, passed: c.expected === 'fraud' }))
        return jsonResponse({ rule_id: simRule.rule_id, cases: results.length, passed: results.filter((r) => r.passed).length, fraud_cases: results.length, fraud_caught: results.length, legit_cases: 0, false_alarms: 0, results })
      }
      throw new Error(`unexpected ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('shows the rule and the transaction side by side and saves a generated case', async () => {
    render(<App />)
    const sideBySide = await screen.findByRole('region', { name: 'Rule and transaction side by side' })
    fireEvent.click(await screen.findByRole('button', { name: /example that matches/i }))
    expect(await within(sideBySide).findByText('Rule FLAGS this transaction')).toBeInTheDocument()
    expect(within(sideBySide).getAllByText(/passes/)).toHaveLength(2)

    fireEvent.click(screen.getByRole('button', { name: /near miss/i }))
    expect(await within(sideBySide).findByText('Rule ALLOWS this transaction')).toBeInTheDocument()
    expect(within(sideBySide).getByText(/fails/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /example that matches/i }))
    await within(sideBySide).findByText('Rule FLAGS this transaction')
    fireEvent.click(screen.getByRole('button', { name: /save as test case/i }))
    const table = await screen.findByRole('table', { name: /saved test cases/i })
    expect(within(table).getByText('AGT-550906a0-2 should flag')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('heading', { name: '1 of 1 pass' })).toBeInTheDocument())
    const saved = fetchMock.mock.calls.find(([input, init]) => String(input).endsWith('/api/v1/lab/cases') && init?.method === 'POST')
    expect(JSON.parse(String(saved?.[1]?.body))).toMatchObject({ expected: 'fraud', transaction: { days_since_sim_change: 2, credential_resets_24h: 1 } })
  })
})
