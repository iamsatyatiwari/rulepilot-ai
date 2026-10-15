import { useCallback, useEffect, useMemo, useState } from 'react'
import { Check, FlaskConical, LoaderCircle, Save, ShieldAlert, Trash2, Wand2, X } from 'lucide-react'
import {
  apiRequest,
  postJson,
  type Explanation,
  type LabRule,
  type RunSummary,
  type TestCase,
  type Transaction,
} from './api'
import { numberFormat, ruleText, safeMessage } from './components'

const FIELDS: { key: keyof Transaction; label: string; step: string }[] = [
  { key: 'amount', label: 'Amount', step: '0.01' },
  { key: 'transactions_1h', label: 'Payments in last hour', step: '1' },
  { key: 'transactions_24h', label: 'Payments in last 24h', step: '1' },
  { key: 'declined_attempts_24h', label: 'Declines in last 24h', step: '1' },
  { key: 'card_present', label: 'Card present (0/1)', step: '1' },
  { key: 'distance_from_home_km', label: 'Distance from home (km)', step: '0.1' },
  { key: 'account_age_days', label: 'Account age (days)', step: '1' },
  { key: 'hour_of_day', label: 'Hour of day (0-23)', step: '1' },
  { key: 'new_device', label: 'New device (0/1)', step: '1' },
  { key: 'days_since_sim_change', label: 'Days since SIM change', step: '1' },
  { key: 'credential_resets_24h', label: 'Credential resets (24h)', step: '1' },
  { key: 'new_payee', label: 'New payee (0/1)', step: '1' },
]
const INTEGER = new Set(FIELDS.filter((f) => f.step === '1').map((f) => f.key))
const OPERATOR: Record<string, string> = { greater_than: '>', greater_than_or_equal: '≥', less_than: '<', less_than_or_equal: '≤', equals: '=', not_equals: '≠' }
const SOURCE_LABEL: Record<LabRule['source'], string> = { baseline: 'Original rule · active', approved_active: 'Approved · active', candidate: 'Candidate · not approved' }

type Form = Record<string, string>

function toTransaction(form: Form): Transaction {
  const transaction: Transaction = { transaction_id: 'LAB-MANUAL' }
  for (const { key } of FIELDS) {
    const raw = form[key]?.trim()
    if (!raw) continue
    const value = Number(raw)
    if (Number.isFinite(value)) (transaction as Record<string, number | string | null>)[key] = INTEGER.has(key) ? Math.round(value) : value
  }
  return transaction
}

const toForm = (transaction: Transaction): Form =>
  Object.fromEntries(FIELDS.map(({ key }) => [key, transaction[key] == null ? '' : String(transaction[key])]))

export default function LabView() {
  const [rules, setRules] = useState<LabRule[]>([])
  const [ruleId, setRuleId] = useState('')
  const [form, setForm] = useState<Form>({})
  const [explanation, setExplanation] = useState<Explanation | null>(null)
  const [cases, setCases] = useState<TestCase[]>([])
  const [run, setRun] = useState<RunSummary | null>(null)
  const [name, setName] = useState('')
  const [expected, setExpected] = useState<'fraud' | 'legit'>('fraud')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState('')

  const selected = useMemo(() => rules.find((item) => item.rule.rule_id === ruleId) ?? null, [rules, ruleId])
  const transaction = useMemo(() => toTransaction(form), [form])

  const loadCases = useCallback(async () => {
    setCases(await apiRequest<TestCase[]>('/api/v1/lab/cases'))
  }, [])

  useEffect(() => {
    apiRequest<LabRule[]>('/api/v1/lab/rules')
      .then((items) => {
        setRules(items)
        const preferred = items.find((item) => item.source === 'approved_active') ?? items[0]
        if (preferred) setRuleId(preferred.rule.rule_id)
      })
      .catch((loadError) => setError(safeMessage(loadError)))
    loadCases().catch((loadError) => setError(safeMessage(loadError)))
  }, [loadCases])

  // Re-check the rule against the transaction whenever either changes.
  useEffect(() => {
    if (!selected) return
    const timer = window.setTimeout(() => {
      postJson<Explanation>('/api/v1/lab/explain', { rule: selected.rule, transaction })
        .then(setExplanation)
        .catch((explainError) => setError(safeMessage(explainError)))
    }, 200)
    return () => window.clearTimeout(timer)
  }, [selected, transaction])

  // Re-run all saved cases when the rule or the case list changes.
  useEffect(() => {
    if (!selected) return
    postJson<RunSummary>('/api/v1/lab/run', { rule: selected.rule }).then(setRun).catch(() => setRun(null))
  }, [selected, cases])

  const act = async (label: string, action: () => Promise<void>) => {
    setBusy(label)
    setError('')
    try {
      await action()
    } catch (actError) {
      setError(safeMessage(actError))
    } finally {
      setBusy(null)
    }
  }

  const generate = (match: boolean) => act(match ? 'match' : 'miss', async () => {
    if (!selected) return
    const example = await postJson<Transaction>('/api/v1/lab/generate', { rule: selected.rule, match })
    setForm(toForm(example))
    setExpected(match ? 'fraud' : 'legit')
    setName(match ? `${selected.rule.rule_id} should flag` : `${selected.rule.rule_id} near miss`)
  })

  const save = () => act('save', async () => {
    if (!name.trim()) throw new Error('Give the test case a name.')
    await postJson('/api/v1/lab/cases', { name: name.trim(), transaction, expected })
    setName('')
    await loadCases()
  })

  const remove = (caseId: string) => act(`delete-${caseId}`, async () => {
    await apiRequest(`/api/v1/lab/cases/${caseId}`, { method: 'DELETE' })
    await loadCases()
  })

  const resultFor = (caseId: string) => run?.results.find((r) => r.case.case_id === caseId)

  return (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow"><span className="eyebrow-dot" /> RULE LAB · HAND-MADE TEST DATA</div>
          <h1>Rule lab</h1>
          <p className="welcome-subtitle">Pick a rule, build a transaction next to it, and see which conditions pass. Generate an example that matches or just misses, label it fraud or legitimate, and save it as a test case. Customer fraud reports from the Demo bank appear here too.</p>
        </div>
      </section>
      {error && <div className="inline-error" role="alert"><ShieldAlert size={15} /><span>{error}</span></div>}

      <label className="dataset-picker">Rule
        <select value={ruleId} onChange={(event) => setRuleId(event.target.value)}>
          {rules.map((item) => <option key={item.rule.rule_id} value={item.rule.rule_id}>{item.label}</option>)}
        </select>
      </label>

      <section className="lab-grid">
        <section className="panel" aria-label="Rule and transaction side by side">
          <div className="panel-heading"><div><div className="section-kicker">{selected ? SOURCE_LABEL[selected.source] : 'RULE'}</div><h2>{selected ? selected.rule.name : 'No rule selected'}</h2>{selected && <p><code>{ruleText(selected.rule)}</code></p>}</div></div>
          {selected && explanation && (
            <>
              <div className="table-wrap">
                <table className="lab-table">
                  <caption className="sr-only">Each rule condition next to the transaction value</caption>
                  <thead><tr><th scope="col">Field</th><th scope="col">Rule needs</th><th scope="col">This transaction</th><th scope="col">Result</th></tr></thead>
                  <tbody>
                    {explanation.conditions.map((c) => (
                      <tr key={c.field + c.operator}>
                        <th scope="row">{c.field.replace(/_/g, ' ')}</th>
                        <td>{OPERATOR[c.operator] ?? c.operator} {numberFormat.format(c.threshold)}</td>
                        <td>{c.value == null ? <em>missing</em> : numberFormat.format(c.value)}</td>
                        <td>{c.passed === null ? <span className="lab-miss">missing → fails</span> : c.passed ? <span className="lab-pass"><Check size={14} /> passes</span> : <span className="lab-fail"><X size={14} /> fails</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className={`lab-verdict ${explanation.flagged ? 'lab-verdict-flag' : 'lab-verdict-allow'}`} role="status">
                {explanation.flagged ? 'Rule FLAGS this transaction' : 'Rule ALLOWS this transaction'} <small>({explanation.logical_operator.toUpperCase()}: {explanation.logical_operator === 'and' ? 'every condition must pass' : 'any condition passing is enough'})</small>
              </div>
            </>
          )}
        </section>

        <section className="panel lab-builder" aria-label="Test transaction">
          <div className="panel-heading"><div><div className="section-kicker">TEST TRANSACTION</div><h2>Build or generate one</h2></div></div>
          <div className="review-actions">
            <button className="primary-button" onClick={() => void generate(true)} disabled={!selected || busy !== null}>{busy === 'match' ? <LoaderCircle size={15} className="spin" /> : <Wand2 size={15} />} Example that matches</button>
            <button className="secondary-button" onClick={() => void generate(false)} disabled={!selected || busy !== null}>{busy === 'miss' ? <LoaderCircle size={15} className="spin" /> : <Wand2 size={15} />} Near miss</button>
            <button className="secondary-button" onClick={() => setForm({})} disabled={busy !== null}>Clear</button>
          </div>
          <div className="field-grid">
            {FIELDS.map(({ key, label, step }) => (
              <label key={key}><span>{label}</span><input type="number" step={step} min={0} value={form[key] ?? ''} onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))} /></label>
            ))}
          </div>
          <div className="lab-save">
            <label>Test case name<input value={name} maxLength={120} onChange={(event) => setName(event.target.value)} placeholder="e.g. Gift-card burst at 3 a.m." /></label>
            <fieldset><legend>This transaction is</legend>
              <label className="check-row"><input type="radio" name="expected" checked={expected === 'fraud'} onChange={() => setExpected('fraud')} /> Fraud (rule should flag)</label>
              <label className="check-row"><input type="radio" name="expected" checked={expected === 'legit'} onChange={() => setExpected('legit')} /> Legitimate (rule should allow)</label>
            </fieldset>
            <button className="primary-button" onClick={() => void save()} disabled={busy !== null}>{busy === 'save' ? <LoaderCircle size={15} className="spin" /> : <Save size={15} />} Save as test case</button>
          </div>
        </section>
      </section>

      <section className="panel" aria-label="Test cases">
        <div className="panel-heading"><div><div className="section-kicker">TEST CASES · RUN AGAINST THE SELECTED RULE</div><h2>{run ? `${run.passed} of ${run.cases} pass` : 'Saved test cases'}</h2>{run && <p>Catches {run.fraud_caught} of {run.fraud_cases} fraud cases · {run.false_alarms} false alarm(s) on {run.legit_cases} legitimate cases.</p>}</div><span className="review-icon"><FlaskConical size={17} /></span></div>
        {cases.length === 0 ? <p className="muted-text">No test cases yet. Generate or build a transaction above and save it, or press “Report fraud” on a payment in the Demo bank.</p> : (
          <div className="table-wrap">
            <table className="lab-table">
              <caption className="sr-only">Saved test cases and their result under the selected rule</caption>
              <thead><tr><th scope="col">Test case</th><th scope="col">Source</th><th scope="col">Expected</th><th scope="col">Rule says</th><th scope="col">Result</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {cases.map((item) => {
                  const result = resultFor(item.case_id)
                  return (
                    <tr key={item.case_id}>
                      <th scope="row"><span className="candidate-name">{item.name}</span><small>{item.created_by}</small></th>
                      <td><span className={`catalog-state ${item.source === 'customer_report' ? 'state-approved' : 'state-active'}`}>{item.source === 'customer_report' ? 'Customer report' : 'Analyst'}</span></td>
                      <td>{item.expected === 'fraud' ? 'Fraud' : 'Legitimate'}</td>
                      <td>{result ? (result.flagged ? 'Flag' : 'Allow') : '—'}</td>
                      <td>{result ? (result.passed ? <span className="lab-pass"><Check size={14} /> pass</span> : <span className="lab-fail"><X size={14} /> fail</span>) : '—'}</td>
                      <td className="lab-actions">
                        <button className="text-button" onClick={() => setForm(toForm(item.transaction))}>Load</button>
                        <button className="text-button" onClick={() => void remove(item.case_id)} aria-label={`Delete ${item.name}`} disabled={busy !== null}><Trash2 size={14} /></button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
