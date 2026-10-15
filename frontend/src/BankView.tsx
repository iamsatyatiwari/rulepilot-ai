import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { CreditCard, LoaderCircle, RotateCcw, ShieldAlert, ShieldCheck, Smartphone, Zap } from 'lucide-react'
import {
  apiRequest,
  postJson,
  type BankCatalog,
  type BankHistoryItem,
  type DemoCard,
  type PaymentRequest,
  type PaymentResult,
  type Rule,
  type RuleCatalog,
  type SecurityEvent,
} from './api'
import { numberFormat, ruleText, safeMessage } from './components'

type ActivityItem = { id: number; cardId: string; merchant: string; amount: number; at: string; result: PaymentResult }
type CardState = { history: BankHistoryItem[]; events: SecurityEvent[] }

const OUTCOME_LABEL: Record<PaymentResult['outcome'], string> = {
  approved: 'Approved',
  held_for_review: 'Held for review',
  declined_by_issuer: 'Declined by issuer',
}

/** ISO timestamp with the browser's UTC offset, so the server sees the customer's local hour. */
export function localIso(date: Date) {
  const offset = -date.getTimezoneOffset()
  const sign = offset >= 0 ? '+' : '-'
  const pad = (value: number) => String(Math.floor(Math.abs(value))).padStart(2, '0')
  const local = new Date(date.getTime() + offset * 60000).toISOString().slice(0, 19)
  return `${local}${sign}${pad(offset / 60)}:${pad(offset % 60)}`
}

const SIM_FIELDS = ['days_since_sim_change', 'credential_resets_24h', 'new_device', 'new_payee']
const CARD_TESTING_FIELDS = ['transactions_1h', 'transactions_24h', 'declined_attempts_24h']

/** Which one-click scenario exercises a rule, judged from the fields it checks. */
function scenarioFor(rule: Rule) {
  const fields = rule.conditions.map((c) => c.field)
  if (fields.some((f) => SIM_FIELDS.includes(f))) return 'SIM-swap takeover'
  if (fields.some((f) => CARD_TESTING_FIELDS.includes(f))) return 'Card-testing attack'
  return 'a payment that matches it'
}

const minutesAgo = (minutes: number) => localIso(new Date(Date.now() - minutes * 60000))
const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

function featureNotes(result: PaymentResult) {
  const f = result.features
  return [
    `${f.transactions_1h ?? 0} payment(s) in the last hour`,
    `${f.declined_attempts_24h ?? 0} decline(s) in 24h`,
    f.card_present ? 'card present' : 'online',
    f.new_payee ? 'new payee' : 'known payee',
    f.new_device ? 'new device' : 'known device',
    `SIM changed ${f.days_since_sim_change ?? '—'} day(s) ago`,
    `${f.credential_resets_24h ?? 0} credential reset(s) in 24h`,
  ]
}

export default function BankView() {
  const [catalog, setCatalog] = useState<BankCatalog | null>(null)
  const [rules, setRules] = useState<RuleCatalog | null>(null)
  const [cardId, setCardId] = useState('card-ben')
  const [merchantId, setMerchantId] = useState('m-grocer')
  const [amount, setAmount] = useState('46.20')
  const [cvvWrong, setCvvWrong] = useState(false)
  const [newDevice, setNewDevice] = useState(false)
  const [state, setState] = useState<Record<string, CardState>>({})
  const [activity, setActivity] = useState<ActivityItem[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const shadowCount = useRef(0)

  const loadRules = useCallback(async () => {
    try {
      setRules(await apiRequest<RuleCatalog>('/api/v1/rule-catalog'))
    } catch {
      setRules(null)
    }
  }, [])

  useEffect(() => {
    apiRequest<BankCatalog>('/api/v1/bank/catalog').then((value) => setCatalog(Array.isArray(value?.cards) ? value : null)).catch((loadError) => setError(safeMessage(loadError)))
    void loadRules()
  }, [loadRules])

  const merchants = catalog?.merchants ?? []
  const merchantName = (id: string) => merchants.find((m) => m.merchant_id === id)?.name ?? id
  const card = catalog?.cards.find((c) => c.card_id === cardId)

  // Each payment is sent with the card's history so far; the result is appended locally.
  const pay = async (
    current: Record<string, CardState>,
    request: Omit<PaymentRequest, 'history' | 'security_events' | 'at'> & { at?: string },
    extraEvents: SecurityEvent[] = [],
  ) => {
    const cardState = current[request.card_id] ?? { history: [], events: [] }
    const events = [...cardState.events, ...extraEvents]
    const at = request.at ?? localIso(new Date())
    const result = await postJson<PaymentResult>('/api/v1/bank/payments', { ...request, at, history: cardState.history, security_events: events })
    const declined = result.outcome === 'declined_by_issuer'
    const next = {
      ...current,
      [request.card_id]: { history: [...cardState.history, { at, merchant_id: request.merchant_id, amount: request.amount, declined }].slice(-200), events },
    }
    setState(next)
    if (result.score.shadow_flagged_by.length) shadowCount.current += 1
    setActivity((items) => [{ id: Date.now() + Math.random(), cardId: request.card_id, merchant: merchantName(request.merchant_id), amount: request.amount, at, result }, ...items].slice(0, 60))
    return next
  }

  const run = async (label: string, action: () => Promise<void>) => {
    setBusy(label)
    setError('')
    setNotice('')
    try {
      const latestRules = await apiRequest<RuleCatalog>('/api/v1/rule-catalog').catch(() => null)
      if (latestRules) setRules(latestRules)
      const before = shadowCount.current
      await action()
      const approvedNow = latestRules?.approved_not_active ?? []
      if (label !== 'normal' && label !== 'pay' && shadowCount.current === before) {
        setNotice(approvedNow.length
          ? `None of your approved rules reacted to this attack. ${approvedNow.map((e) => `${e.rule.rule_id} reacts to the ${scenarioFor(e.rule)}`).join('; ')}.`
          : 'No RulePilot rule is approved yet, so nothing can flag this attack. Approve one in Investigations first.')
      }
    } catch (runError) {
      setError(safeMessage(runError))
    } finally {
      setBusy(null)
    }
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const value = Number(amount)
    if (!Number.isFinite(value) || value <= 0) {
      setError('Enter an amount greater than zero.')
      return
    }
    void run('pay', async () => {
      await pay(state, { card_id: cardId, merchant_id: merchantId, amount: value, cvv_correct: !cvvWrong, new_device: newDevice })
    })
  }

  const cardTesting = () => run('card-testing', async () => {
    setCardId('card-ben')
    let current = state
    const amounts = [0.5, 1.0, 1.2, 2.0, 0.75, 1.5, 2.5, 1.0]
    for (const [index, value] of amounts.entries()) {
      current = await pay(current, { card_id: 'card-ben', merchant_id: 'm-giftcard', amount: value, cvv_correct: index % 2 === 1, new_device: true })
      await sleep(250)
    }
  })

  const simSwap = () => run('sim-swap', async () => {
    setCardId('card-chen')
    const events: SecurityEvent[] = [
      { at: minutesAgo(45), type: 'sim_change' },
      { at: minutesAgo(30), type: 'credential_reset' },
      { at: minutesAgo(20), type: 'new_device_login' },
    ]
    await pay(state, { card_id: 'card-chen', merchant_id: 'm-transfer', amount: 1240, cvv_correct: true, new_device: true }, events)
  })

  const normalDay = () => run('normal', async () => {
    setCardId('card-asha')
    let current = state
    for (const [merchant, value] of [['m-grocer', 46.2], ['m-fuel', 58.0], ['m-books', 24.9]] as const) {
      current = await pay(current, { card_id: 'card-asha', merchant_id: merchant, amount: value, cvv_correct: true, new_device: false })
      await sleep(250)
    }
  })

  const reset = () => {
    setNotice('')
    setState({})
    setActivity([])
    setError('')
  }

  const approved = rules?.approved_not_active ?? []

  return (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow"><span className="eyebrow-dot" /> DEMO BANK · FICTIONAL CARDS · NO REAL PAYMENTS</div>
          <h1>Demo bank</h1>
          <p className="welcome-subtitle">Pay with a demo card and watch the rules react. The bank's live decision uses only the <b>active</b> rule. Rules you approved in RulePilot run in <b>shadow mode</b>: they show what they would have caught, without changing the decision.</p>
        </div>
        <div className="header-actions"><button className="secondary-button" onClick={reset} disabled={busy !== null}><RotateCcw size={15} /> Reset demo</button></div>
      </section>

      <section className="panel bank-rules" aria-label="Rules in use">
        <div><span className="catalog-state state-active">Active · decides</span> <strong>RP-BASELINE-001</strong> holds any payment of 1,500 or more.</div>
        {approved.length ? approved.map((entry) => (
          <div key={entry.rule.rule_id}><span className="catalog-state state-approved">Approved · shadow</span> <strong>{entry.rule.rule_id}</strong><span>{entry.technique ?? entry.rule.name}: would flag when <code>{ruleText(entry.rule)}</code> · try the <b>{scenarioFor(entry.rule)}</b></span></div>
        )) : <p className="muted-text">No RulePilot rule is approved yet. Approve one in <a href="#investigations">Investigations</a> (or open a recorded run and approve it) to see it catch the attacks below.</p>}
      </section>

      <section className="bank-cards" aria-label="Demo cards">
        {(catalog?.cards ?? []).map((demo: DemoCard) => (
          <button key={demo.card_id} className={`bank-card ${demo.card_id === cardId ? 'bank-card-active' : ''} card-${demo.last4}`} onClick={() => setCardId(demo.card_id)} aria-pressed={demo.card_id === cardId}>
            <span className="bank-card-top"><CreditCard size={18} /> RulePilot Demo Bank</span>
            <span className="bank-card-number">•••• •••• •••• {demo.last4}</span>
            <span className="bank-card-bottom"><strong>{demo.holder}</strong><small>{demo.label}</small></span>
          </button>
        ))}
      </section>
      {card && <p className="muted-text bank-card-note">{card.description}</p>}

      <section className="bank-grid">
        <div className="bank-column">
          <form className="panel bank-form" onSubmit={submit} aria-label="Make a payment">
            <div className="panel-heading"><div><div className="section-kicker">MAKE A PAYMENT</div><h2>Pay with {card ? `${card.holder}'s card` : 'a demo card'}</h2></div></div>
            <label>Merchant
              <select value={merchantId} onChange={(event) => { setMerchantId(event.target.value); const m = merchants.find((x) => x.merchant_id === event.target.value); if (m) setAmount(String(m.typical_amount)) }}>
                {merchants.map((m) => <option key={m.merchant_id} value={m.merchant_id}>{m.name}{m.channel === 'online' ? '' : ' · in store'}</option>)}
              </select>
            </label>
            <label>Amount<input inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} /></label>
            <label className="check-row"><input type="checkbox" checked={cvvWrong} onChange={(event) => setCvvWrong(event.target.checked)} /> Wrong security code (CVV)</label>
            <label className="check-row"><input type="checkbox" checked={newDevice} onChange={(event) => setNewDevice(event.target.checked)} /> Paying from a new device</label>
            <button className="primary-button" type="submit" disabled={busy !== null || !catalog}>{busy === 'pay' ? <LoaderCircle size={15} className="spin" /> : <CreditCard size={15} />} Pay</button>
          </form>

          <section className="panel" aria-label="Attack scenarios">
            <div className="panel-heading"><div><div className="section-kicker">ONE-CLICK SCENARIOS</div><h2>Simulate an attack</h2></div><span className="review-icon"><Zap size={17} /></span></div>
            <div className="scenario-list">
              <button className="scenario-button" onClick={() => void cardTesting()} disabled={busy !== null || !catalog}>
                {busy === 'card-testing' ? <LoaderCircle size={16} className="spin" /> : <Zap size={16} />}
                <span><strong>Card-testing attack</strong><small>8 tiny online gift-card payments on Ben's card within a minute, half with a wrong CVV.</small></span>
              </button>
              <button className="scenario-button" onClick={() => void simSwap()} disabled={busy !== null || !catalog}>
                {busy === 'sim-swap' ? <LoaderCircle size={16} className="spin" /> : <Smartphone size={16} />}
                <span><strong>SIM-swap takeover</strong><small>Chen's SIM is swapped, the password reset, and 1,240 sent to a new payee from a new phone.</small></span>
              </button>
              <button className="scenario-button" onClick={() => void normalDay()} disabled={busy !== null || !catalog}>
                {busy === 'normal' ? <LoaderCircle size={16} className="spin" /> : <ShieldCheck size={16} />}
                <span><strong>Normal day</strong><small>Asha buys groceries, fuel, and a book. Nothing should be flagged.</small></span>
              </button>
            </div>
          </section>
        </div>

        <section className="panel bank-activity" aria-label="Card activity">
          <div className="panel-heading"><div><div className="section-kicker">ACTIVITY · NEWEST FIRST</div><h2>What the bank decided</h2></div></div>
          {error && <div className="inline-error" role="alert"><ShieldAlert size={15} /><span>{error}</span></div>}
          {notice && <div className="inline-note" role="status"><ShieldAlert size={14} /> {notice}</div>}
          {activity.length === 0 ? <p className="muted-text">No payments yet. Make a payment or run a scenario.</p> : (
            <ul className="activity-list">
              {activity.map((item) => {
                const shadow = item.result.score.shadow_flagged_by
                return (
                  <li key={item.id} className={`activity-item outcome-${item.result.outcome}`}>
                    <div className="activity-main">
                      <span className={`outcome-badge badge-${item.result.outcome}`}>{OUTCOME_LABEL[item.result.outcome]}</span>
                      <strong>{numberFormat.format(item.amount)}</strong>
                      <span>{item.merchant}</span>
                      <small>•••• {catalog?.cards.find((c) => c.card_id === item.cardId)?.last4} · {new Date(item.at).toLocaleTimeString()}</small>
                    </div>
                    {shadow.length > 0 && <div className="shadow-flag"><ShieldAlert size={14} /> RulePilot rule {shadow.join(', ')} would flag this (shadow mode: approved, not yet active)</div>}
                    <details>
                      <summary>Why?</summary>
                      <p>{item.result.explanation} {item.result.shadow_summary}</p>
                      <div className="chip-row">{featureNotes(item.result).map((note) => <span key={note} className="field-chip chip-neutral">{note}</span>)}</div>
                    </details>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      </section>
      {catalog && <p className="muted-text">{catalog.disclaimer}</p>}
    </>
  )
}
