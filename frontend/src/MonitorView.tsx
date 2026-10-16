import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Activity, CircleAlert, Eye, Play, RefreshCw, ShieldAlert, ShieldCheck } from 'lucide-react'
import {
  apiRequest,
  postJson,
  type FeedItem,
  type RuleCatalog,
  type SimulateResponse,
  type Transaction,
  type TransactionScore,
} from './api'
import { CandidateConditions, formatCount, numberFormat, safeMessage } from './components'

const BATCH_SIZE = 20
const REVEAL_MS = 90

type Outcome = { label: string; tone: 'shadow' | 'caught' | 'missed' | 'false-alarm' | 'quiet' }

function outcomeOf(item: FeedItem): Outcome {
  const { score, synthetic_fraud: fraud } = item
  if (fraud && score.caught_only_by_approved) return { label: 'Caught by approved rule', tone: 'shadow' }
  if (fraud && score.decision === 'flag') return { label: 'Caught by active rule', tone: 'caught' }
  if (fraud) return { label: 'Missed by all rules', tone: 'missed' }
  if (score.decision === 'flag') return { label: 'False alarm · active', tone: 'false-alarm' }
  return { label: 'Allowed', tone: 'quiet' }
}

const FIELDS: { key: keyof Transaction; label: string; step: string }[] = [
  { key: 'amount', label: 'Amount', step: '0.01' },
  { key: 'transactions_1h', label: 'Transactions (1h)', step: '1' },
  { key: 'transactions_24h', label: 'Transactions (24h)', step: '1' },
  { key: 'declined_attempts_24h', label: 'Declines (24h)', step: '1' },
  { key: 'card_present', label: 'Card present (0/1)', step: '1' },
  { key: 'distance_from_home_km', label: 'Distance from home (km)', step: '0.1' },
  { key: 'account_age_days', label: 'Account age (days)', step: '1' },
  { key: 'hour_of_day', label: 'Hour of day (0-23)', step: '1' },
  { key: 'new_device', label: 'New device (0/1)', step: '1' },
  { key: 'days_since_sim_change', label: 'Days since SIM change', step: '1' },
  { key: 'credential_resets_24h', label: 'Credential resets (24h)', step: '1' },
  { key: 'new_payee', label: 'New payee (0/1)', step: '1' },
]

const PRESETS: Record<string, Transaction> = {
  'Card-testing burst': { amount: 3.5, transactions_1h: 9, transactions_24h: 14, declined_attempts_24h: 6, card_present: 0, distance_from_home_km: 40, account_age_days: 420, hour_of_day: 3, new_device: 1, days_since_sim_change: 640, credential_resets_24h: 0, new_payee: 1 },
  'SIM-swap takeover': { amount: 1240, transactions_1h: 1, transactions_24h: 2, declined_attempts_24h: 0, card_present: 0, distance_from_home_km: 35, account_age_days: 2100, hour_of_day: 2, new_device: 1, days_since_sim_change: 1, credential_resets_24h: 2, new_payee: 1 },
  'Large purchase abroad': { amount: 2400, transactions_1h: 1, transactions_24h: 2, declined_attempts_24h: 0, card_present: 1, distance_from_home_km: 1800, account_age_days: 900, hour_of_day: 15, new_device: 0, days_since_sim_change: 410, credential_resets_24h: 0, new_payee: 1 },
  'Everyday purchase': { amount: 42.1, transactions_1h: 0, transactions_24h: 2, declined_attempts_24h: 0, card_present: 1, distance_from_home_km: 6, account_age_days: 1500, hour_of_day: 12, new_device: 0, days_since_sim_change: 980, credential_resets_24h: 0, new_payee: 0 },
}

const INTEGER_FIELDS = new Set<keyof Transaction>(['transactions_1h', 'transactions_24h', 'declined_attempts_24h', 'card_present', 'account_age_days', 'hour_of_day', 'new_device', 'days_since_sim_change', 'credential_resets_24h', 'new_payee'])

function toPayload(form: Record<string, string>): Transaction {
  const transaction: Transaction = { transaction_id: 'MANUAL-001' }
  for (const { key } of FIELDS) {
    const raw = form[key]?.trim()
    if (!raw) continue
    const value = Number(raw)
    if (!Number.isFinite(value)) continue
    ;(transaction as Record<string, number | string | null>)[key] = INTEGER_FIELDS.has(key) ? Math.round(value) : value
  }
  return transaction
}

function presetForm(preset: Transaction): Record<string, string> {
  return Object.fromEntries(FIELDS.map(({ key }) => [key, preset[key] == null ? '' : String(preset[key])]))
}

function Verdicts({ score }: { score: TransactionScore }) {
  return (
    <ul className="verdict-list">
      {score.active_rules.map((verdict) => (
        <li key={verdict.rule_id}><span className={`catalog-state ${verdict.investigation_id ? 'state-approved' : 'state-active'}`}>{verdict.investigation_id ? 'Approved · active' : 'Active'}</span><strong>{verdict.rule_id}</strong><span className={`verdict ${verdict.flagged ? 'verdict-flag' : 'verdict-allow'}`}>{verdict.flagged ? 'Flag' : 'Allow'}</span>{verdict.missing_fields.length > 0 && <small>missing: {verdict.missing_fields.join(', ')}</small>}</li>
      ))}
      {score.shadow_rules.map((verdict) => (
        <li key={verdict.rule_id}><span className="catalog-state state-approved">Shadow</span><strong>{verdict.rule_id}</strong><span className={`verdict ${verdict.flagged ? 'verdict-flag' : 'verdict-allow'}`}>{verdict.flagged ? 'Would flag' : 'Would allow'}</span>{verdict.missing_fields.length > 0 && <small>missing: {verdict.missing_fields.join(', ')}</small>}</li>
      ))}
    </ul>
  )
}

export default function MonitorView() {
  const [catalog, setCatalog] = useState<RuleCatalog | null>(null)
  const [feed, setFeed] = useState<SimulateResponse | null>(null)
  const [visible, setVisible] = useState(0)
  const [seed, setSeed] = useState(1)
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState<Record<string, string>>(presetForm(PRESETS['Card-testing burst']))
  const [single, setSingle] = useState<TransactionScore | null>(null)
  const [scoring, setScoring] = useState(false)
  const timer = useRef<number | undefined>(undefined)

  const loadCatalog = async () => {
    try {
      setCatalog(await apiRequest<RuleCatalog>('/api/v1/rule-catalog'))
    } catch (caught) {
      setError(safeMessage(caught))
    }
  }

  useEffect(() => {
    void loadCatalog()
    return () => window.clearInterval(timer.current)
  }, [])

  const stream = async () => {
    window.clearInterval(timer.current)
    setStreaming(true)
    setError('')
    try {
      const [result] = await Promise.all([
        postJson<SimulateResponse>('/api/v1/transactions/simulate', { count: BATCH_SIZE, seed }),
        loadCatalog(),
      ])
      setFeed(result)
      setVisible(0)
      setSeed((value) => value + 1)
      timer.current = window.setInterval(() => {
        setVisible((count) => {
          if (count + 1 >= result.items.length) window.clearInterval(timer.current)
          return Math.min(count + 1, result.items.length)
        })
      }, REVEAL_MS)
    } catch (caught) {
      setError(safeMessage(caught))
    } finally {
      setStreaming(false)
    }
  }

  const scoreOne = async (event: FormEvent) => {
    event.preventDefault()
    setScoring(true)
    setError('')
    try {
      setSingle(await postJson<TransactionScore>('/api/v1/transactions/score', { transaction: toPayload(form) }))
    } catch (caught) {
      setError(safeMessage(caught))
    } finally {
      setScoring(false)
    }
  }

  const approvedCount = catalog?.approved_not_active.length ?? 0
  const summary = feed?.summary
  const done = feed !== null && visible >= feed.items.length

  return (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow"><span className="eyebrow-dot" /> MOCK BANK FEED → ORIGINAL RULE + APPROVED RULES DECIDE</div>
          <h1>Transaction monitor</h1>
          <p className="welcome-subtitle">A simulated bank feed sends fresh synthetic transactions to the rule engine. The original rule and every rule a human approved make the decision together, so you can see how much more fraud the approved rules catch and what they cost in false alarms.</p>
        </div>
        <div className="header-actions">
          <span className="agent-chip agent-ready"><Eye size={14} /> {approvedCount} approved rule(s) active</span>
          <button className="primary-button" onClick={() => void stream()} disabled={streaming}>{streaming ? <RefreshCw size={15} className="spin" /> : <Play size={15} />} Stream {BATCH_SIZE} transactions</button>
        </div>
      </section>

      {error && <section className="state-card error-card" role="alert"><div className="state-icon error"><ShieldAlert size={19} /></div><div className="state-copy"><strong>The transaction monitor is unavailable</strong><p>{error}</p></div></section>}

      <section className="panel catalog-panel" aria-label="Rules applied to the feed">
        <div className="panel-heading"><div><div className="section-kicker">RULES APPLIED TO EVERY TRANSACTION</div><h2>The original rule and approved rules decide</h2><p>Approving a rule in Investigations activates it here. Rejecting it or requesting changes deactivates it. Every change is in the audit log.</p></div><span className="review-icon"><ShieldCheck size={17} /></span></div>
        <ul className="catalog-list">
          {catalog?.active.map((rule) => <li key={rule.rule_id}><span className="catalog-state state-active">Active · decides</span><div><strong>{rule.rule_id}</strong> · {rule.name}<CandidateConditions rule={rule} /></div></li>)}
          {catalog?.approved_not_active.map((entry) => <li key={entry.rule.rule_id}><span className="catalog-state state-approved">Approved · active</span><div><strong>{entry.rule.rule_id}</strong> · {entry.rule.name}<CandidateConditions rule={entry.rule} /><p className="catalog-provenance">From “{entry.advisory_title}”, approved by {entry.approved_by}.</p></div></li>)}
        </ul>
        {catalog && approvedCount === 0 && <p className="muted-text">No approved rules yet. Approve a candidate in Investigations and it will be applied here.</p>}
      </section>

      {summary && (
        <section className="delta-strip monitor-strip" aria-label="Feed summary">
          <div><span>Transactions</span><strong>{formatCount(summary.transactions)}</strong></div>
          <div><span>Synthetic fraud</span><strong>{formatCount(summary.synthetic_fraud)}</strong></div>
          <div><span>Caught by active rules</span><strong>{formatCount(summary.fraud_caught_by_active_rules)}</strong></div>
          <div className="strip-highlight"><span>Extra fraud caught by approved rules</span><strong className="good">+{formatCount(summary.fraud_caught_by_approved_rules ?? 0)}</strong></div>
          <div><span>Missed by all rules</span><strong className={summary.fraud_missed_by_all_rules ? 'warn' : ''}>{formatCount(summary.fraud_missed_by_all_rules)}</strong></div>
          <div><span>Extra false alarms from approved rules</span><strong className={summary.legitimate_flagged_by_approved_rules ? 'warn' : ''}>{formatCount(summary.legitimate_flagged_by_approved_rules ?? 0)}</strong></div>
        </section>
      )}

      <section className="panel" aria-label="Transaction feed">
        <div className="panel-heading"><div><div className="section-kicker">LIVE FEED · SYNTHETIC</div><h2>Incoming transactions</h2><p>{feed ? `${feed.disclaimer} Batch seed ${feed.seed}.` : 'Press “Stream transactions” to send a batch from the mock bank feed.'}</p></div><span className="review-icon"><Activity size={17} /></span></div>
        {feed ? (
          <div className="table-wrap">
            <table className="feed-table">
              <caption className="sr-only">Mock bank transactions with rule decisions</caption>
              <thead><tr><th scope="col">Transaction</th><th scope="col">Amount</th><th scope="col">Txns 1h</th><th scope="col">Declines 24h</th><th scope="col">Card present</th><th scope="col">SIM change (days)</th><th scope="col">New device</th><th scope="col">Decision</th><th scope="col">Approved rule</th><th scope="col">Synthetic label</th><th scope="col">Outcome</th></tr></thead>
              <tbody>
                {feed.items.slice(0, visible).map((item) => {
                  const outcome = outcomeOf(item)
                  const t = item.transaction
                  return (
                    <tr key={t.transaction_id ?? ''} className={`feed-row row-${outcome.tone}`}>
                      <th scope="row" className="transaction-id">{t.transaction_id}</th>
                      <td>{numberFormat.format(t.amount ?? 0)}</td>
                      <td>{t.transactions_1h}</td>
                      <td>{t.declined_attempts_24h}</td>
                      <td>{t.card_present ? 'Yes' : 'No'}</td>
                      <td>{t.days_since_sim_change ?? '—'}</td>
                      <td>{t.new_device == null ? '—' : t.new_device ? 'Yes' : 'No'}</td>
                      <td><span className={`verdict ${item.score.decision === 'flag' ? 'verdict-flag' : 'verdict-allow'}`}>{item.score.decision === 'flag' ? 'Flag' : 'Allow'}</span></td>
                      <td>{item.score.approved_flagged_by?.length ? <span className="verdict verdict-shadow">{item.score.approved_flagged_by.join(', ')}</span> : <span className="not-missed">—</span>}</td>
                      <td>{item.synthetic_fraud ? 'Fraud' : 'Legitimate'}</td>
                      <td><span className={`outcome-tag tone-${outcome.tone}`}>{outcome.label}</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {!done && <div className="empty-table"><RefreshCw size={14} className="spin" /> Receiving transactions…</div>}
          </div>
        ) : <div className="empty-table"><Activity size={15} /> No transactions streamed yet.</div>}
      </section>

      <section className="report-grid two">
        <form className="panel" onSubmit={scoreOne} aria-label="Score a single transaction">
          <div className="panel-heading"><div><div className="section-kicker">TRY ONE TRANSACTION</div><h2>Score a transaction</h2><p>Send one transaction to the engine. Missing fields fail closed: a rule that needs them does not flag.</p></div></div>
          <div className="preset-row">{Object.keys(PRESETS).map((name) => <button key={name} type="button" className="secondary-button" onClick={() => { setForm(presetForm(PRESETS[name])); setSingle(null) }}>{name}</button>)}</div>
          <div className="field-grid">
            {FIELDS.map(({ key, label, step }) => (
              <label key={key}><span>{label}</span><input type="number" step={step} min={0} value={form[key] ?? ''} onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))} /></label>
            ))}
          </div>
          <div className="review-actions"><button className="primary-button" type="submit" disabled={scoring}>{scoring ? <RefreshCw size={15} className="spin" /> : <ShieldCheck size={15} />} Score transaction</button></div>
        </form>
        <section className="panel" aria-label="Score result" aria-live="polite">
          <div className="panel-heading"><div><div className="section-kicker">RESULT</div><h2>{single ? (single.caught_only_by_approved ? 'Flagged by an approved rule' : single.decision === 'flag' ? 'Flagged by the original rule' : 'Allowed') : 'No transaction scored yet'}</h2><p>{single ? single.note : 'Pick a preset or enter values, then score it.'}</p></div>{single?.caught_only_by_approved && <span className="review-icon"><CircleAlert size={17} /></span>}</div>
          {single && <Verdicts score={single} />}
        </section>
      </section>
    </>
  )
}
