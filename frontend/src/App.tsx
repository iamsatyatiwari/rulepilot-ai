import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Check,
  CircleHelp,
  Database,
  FileCheck2,
  GitBranch,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  Minus,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'
import {
  ApiRequestError,
  apiRequest,
  type ApiHealth,
  type ApiRoot,
  type BacktestReport,
  type DiscoveryReport,
  type Metrics,
  type Rule,
  type RuleList,
} from './api'

type LoadState = 'loading' | 'ready' | 'error'
type HealthState = 'checking' | 'online' | 'offline'

type WorkspaceData = {
  apiRoot: ApiRoot
  ruleList: RuleList
  discovery: DiscoveryReport
}

const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 })

function formatCount(value: number) {
  return Number.isFinite(value) ? numberFormat.format(value) : '—'
}

function formatPercent(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : '—'
}

function formatDelta(value: number) {
  if (!Number.isFinite(value)) return '—'
  const points = value * 100
  const direction = points > 0 ? '+' : ''
  return `${direction}${points.toFixed(1)} pp`
}

function metricDirection(value: number) {
  if (value > 0.000001) return 'up'
  if (value < -0.000001) return 'down'
  return 'same'
}

function metricDelta(candidate: number, baseline: number) {
  return Number.isFinite(candidate) && Number.isFinite(baseline) ? candidate - baseline : Number.NaN
}

function safeMessage(error: unknown) {
  if (error instanceof ApiRequestError) return error.message
  return 'RulePilot could not load this result. Please retry.'
}

function MetricColumn({ label, metrics, accent }: { label: string; metrics: Metrics; accent: 'neutral' | 'green' }) {
  return (
    <article className={`comparison-column comparison-${accent}`}>
      <div className="comparison-title-row">
        <div>
          <p className="comparison-eyebrow">{label}</p>
          <h3>{formatCount(metrics.total_flagged)} <span>alerts</span></h3>
        </div>
        <span className={`alert-mark ${accent}`}><ShieldAlert size={17} /></span>
      </div>
      <div className="primary-metrics">
        <div className="primary-metric"><span>Precision</span><strong>{formatPercent(metrics.precision)}</strong></div>
        <div className="primary-metric"><span>Recall</span><strong>{formatPercent(metrics.recall)}</strong></div>
        <div className="primary-metric"><span>False-positive rate</span><strong>{formatPercent(metrics.false_positive_rate)}</strong></div>
      </div>
      <div className="confusion-grid" aria-label={`${label} confusion matrix`}>
        <div><span>True positives</span><strong>{formatCount(metrics.true_positives)}</strong></div>
        <div><span>False positives</span><strong>{formatCount(metrics.false_positives)}</strong></div>
        <div><span>False negatives</span><strong>{formatCount(metrics.false_negatives)}</strong></div>
        <div><span>True negatives</span><strong>{formatCount(metrics.true_negatives)}</strong></div>
      </div>
      <div className="comparison-footer"><span><Database size={13} /> Transactions evaluated</span><strong>{formatCount(metrics.total_evaluated)}</strong></div>
    </article>
  )
}

function Tradeoff({ baseline, candidate }: { baseline: Metrics; candidate: Metrics }) {
  const recallDelta = metricDelta(candidate.recall, baseline.recall)
  const precisionDelta = metricDelta(candidate.precision, baseline.precision)
  const fprDelta = metricDelta(candidate.false_positive_rate, baseline.false_positive_rate)
  const alertsDelta = candidate.total_flagged - baseline.total_flagged
  const recallIcon = metricDirection(recallDelta)
  const precisionIcon = metricDirection(precisionDelta)
  const alertChange = Number.isFinite(alertsDelta)
    ? `${formatCount(Math.abs(alertsDelta))} ${alertsDelta >= 0 ? 'more' : 'fewer'}`
    : 'an unavailable count of'

  return (
    <div className="tradeoff-card" role="status">
      <div className="tradeoff-icon"><Activity size={17} /></div>
      <div className="tradeoff-content">
        <strong>Measured precision / recall trade-off</strong>
        <p>
          On this held-out synthetic split, candidate recall changed by <b>{formatDelta(recallDelta)}</b> and
          precision by <b>{formatDelta(precisionDelta)}</b> versus baseline. False-positive rate changed by{' '}
          <b>{formatDelta(fprDelta)}</b>; the candidate generated <b>{alertChange}</b> alerts.
          These are measured differences, not a claim that the candidate is better.
        </p>
      </div>
      <div className="delta-pills" aria-label="Candidate changes">
        <span className={`delta-${recallIcon}`}>{recallIcon === 'down' ? <ArrowDownRight size={13} /> : recallIcon === 'up' ? <ArrowUpRight size={13} /> : <Minus size={13} />} Recall {formatDelta(recallDelta)}</span>
        <span className={`delta-${precisionIcon}`}>{precisionIcon === 'down' ? <ArrowDownRight size={13} /> : precisionIcon === 'up' ? <ArrowUpRight size={13} /> : <Minus size={13} />} Precision {formatDelta(precisionDelta)}</span>
      </div>
    </div>
  )
}

function CandidateConditions({ rule }: { rule: Rule }) {
  return (
    <div className="condition-list">
      <div className="condition-operator">{rule.logical_operator.toUpperCase()}</div>
      {rule.conditions.map((condition, index) => (
        <div className="condition-row" key={`${condition.field}-${condition.operator}-${index}`}>
          <span className="condition-index">{String(index + 1).padStart(2, '0')}</span>
          <code>{condition.field}</code>
          <span className="condition-comparison">{condition.operator}</span>
          <strong>{numberFormat.format(condition.value)}</strong>
        </div>
      ))}
    </div>
  )
}

function App() {
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [loadError, setLoadError] = useState('')
  const [healthState, setHealthState] = useState<HealthState>('checking')
  const [workspace, setWorkspace] = useState<WorkspaceData | null>(null)
  const [backtest, setBacktest] = useState<BacktestReport | null>(null)
  const [backtestLoading, setBacktestLoading] = useState(false)
  const [backtestError, setBacktestError] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)

  const loadWorkspace = useCallback(async () => {
    setLoadState('loading')
    setLoadError('')
    setHealthState('checking')
    setBacktest(null)
    setBacktestError('')
    try {
      const [healthResult, rootResult, ruleResult, discoveryResult] = await Promise.allSettled([
        apiRequest<ApiHealth>('/health'),
        apiRequest<ApiRoot>('/'),
        apiRequest<RuleList>('/api/v1/rules'),
        apiRequest<DiscoveryReport>('/api/v1/rules/discover', {
          method: 'POST',
          body: JSON.stringify({ seed: 41 }),
        }),
      ])
      setHealthState(healthResult.status === 'fulfilled' && healthResult.value.status === 'ok' ? 'online' : 'offline')
      if (rootResult.status === 'rejected') throw rootResult.reason
      if (ruleResult.status === 'rejected') throw ruleResult.reason
      if (discoveryResult.status === 'rejected') throw discoveryResult.reason
      setWorkspace({ apiRoot: rootResult.value, ruleList: ruleResult.value, discovery: discoveryResult.value })
      setLoadState('ready')
    } catch (error) {
      setLoadError(safeMessage(error))
      setLoadState('error')
    }
  }, [])

  useEffect(() => {
    void loadWorkspace()
  }, [loadWorkspace])

  const candidate = workspace?.discovery.candidate_rule ?? null
  const dataCount = workspace
    ? workspace.discovery.training_count + workspace.discovery.validation_count + workspace.discovery.test_count
    : 0
  const backtestCanRun = Boolean(candidate && loadState === 'ready' && !backtestLoading)
  const catalogBaseline = workspace?.ruleList.items[0]
  const missedTransactions = useMemo(() => {
    if (!backtest) return []
    const baseline = new Set(backtest.fraud_missed_by_baseline)
    const candidateMissed = new Set(backtest.fraud_missed_by_candidate ?? [])
    return [...new Set([...baseline, ...candidateMissed])]
      .sort((first, second) => first.localeCompare(second, undefined, { numeric: true }))
      .map((transactionId) => ({
        transactionId,
        baselineMiss: baseline.has(transactionId),
        candidateMiss: candidateMissed.has(transactionId),
      }))
  }, [backtest])

  const runBacktest = async () => {
    if (!candidate || !workspace) return
    setBacktestLoading(true)
    setBacktestError('')
    try {
      const result = await apiRequest<BacktestReport>('/api/v1/backtests/run', {
        method: 'POST',
        body: JSON.stringify({ candidate_rule: candidate, seed: workspace.discovery.seed }),
      })
      setBacktest(result)
    } catch (error) {
      setBacktestError(safeMessage(error))
    } finally {
      setBacktestLoading(false)
    }
  }

  const reviewPending = candidate && ['draft', 'pending_review'].includes(candidate.status)

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
        <a className="brand" href="#overview" aria-label="RulePilot AI overview">
          <span className="brand-mark"><GitBranch size={19} strokeWidth={2.5} /></span>
          <span className="brand-name">rulepilot<span>ai</span></span>
        </a>
        <button className="mobile-close" onClick={() => setMenuOpen(false)} aria-label="Close navigation"><X size={18} /></button>
        <div className="workspace-picker"><div className="workspace-avatar">R</div><div className="workspace-copy"><strong>RulePilot Workspace</strong><span>Local synthetic workspace</span></div><span className="workspace-chip">DEV</span></div>
        <div className="nav-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          <a className="nav-item active" href="#overview"><LayoutDashboard size={17} /><span>Overview</span></a>
          <a className="nav-item" href="#candidate"><GitBranch size={17} /><span>Rule proposals</span><span className="nav-soon">VIEW</span></a>
          <a className="nav-item" href="#comparison"><Activity size={17} /><span>Backtests</span><span className="nav-soon">VIEW</span></a>
          <a className="nav-item" href="#review"><FileCheck2 size={17} /><span>Review queue</span><span className="nav-soon">LIMITED</span></a>
        </nav>
        <div className="nav-label nav-label-lower">PLATFORM</div>
        <div className="platform-note"><ShieldCheck size={15} /><span>Deterministic engine<br />Synthetic data only</span></div>
        <div className="sidebar-bottom"><div className="profile-button"><div className="profile-avatar">RP</div><span className="profile-copy"><strong>RulePilot AI</strong><small>Milestone 2B workspace</small></span><Check size={15} /></div></div>
      </aside>
      {menuOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}

      <main className="main-content" id="overview">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMenuOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
          <div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>Rule intelligence</strong></div>
          <div className="top-actions">
            <span className="app-health"><span className="health-dot online" /> Application ready</span>
            <span className={`api-status api-${healthState}`} role="status" aria-live="polite"><span className="status-dot" />{healthState === 'checking' ? 'Checking API' : healthState === 'online' ? 'API connected' : 'API unavailable'}</span>
            <span className="top-divider" /><div className="mini-avatar" aria-label="RulePilot workspace">RP</div>
          </div>
        </header>

        <div className="page-container">
          <section className="welcome-row">
            <div><div className="eyebrow"><span className="eyebrow-dot" /> CONTINUOUS FINANCIAL RULE INTELLIGENCE</div><h1>Rule intelligence overview</h1><p className="welcome-subtitle">Inspect a proposed rule, compare measured backtest results, and review where each rule missed fraud.</p></div>
            <div className="header-actions"><span className="dataset-chip"><Database size={14} /> Synthetic dataset</span><button className="secondary-button" onClick={() => void loadWorkspace()} disabled={loadState === 'loading'}><RefreshCw size={15} className={loadState === 'loading' ? 'spin' : ''} /> Refresh data</button></div>
          </section>

          {loadState === 'loading' && (
            <section className="state-card loading-card" aria-live="polite"><LoaderCircle size={22} className="spin" /><div><strong>Connecting to the rule engine</strong><p>Loading API health, rule catalog, and discovery evidence…</p></div></section>
          )}

          {loadState === 'error' && (
            <section className="state-card error-card" role="alert"><div className="state-icon error"><ShieldAlert size={19} /></div><div className="state-copy"><strong>Workspace data is unavailable</strong><p>{loadError}</p></div><button className="primary-button" onClick={() => void loadWorkspace()}><RefreshCw size={15} /> Retry connection</button></section>
          )}

          {loadState === 'ready' && workspace && (
            <>
              <section className="overview-grid" aria-label="Application and dataset status">
                <article className="overview-card api-overview"><div className="overview-icon green"><Activity size={17} /></div><div className="overview-copy"><span>API service</span><strong>{workspace.apiRoot.name}</strong><small><span className="inline-dot" /> {workspace.apiRoot.status === 'ready' ? 'Serving requests' : workspace.apiRoot.status}</small></div><div className="overview-state">{healthState === 'online' ? 'ONLINE' : 'UNAVAILABLE'}</div></article>
                <article className="overview-card"><div className="overview-icon blue"><Database size={17} /></div><div className="overview-copy"><span>Dataset</span><strong>{formatCount(dataCount)} records</strong><small>Small synthetic development fixture</small></div><div className="overview-state neutral">SYNTHETIC</div></article>
                <article className="overview-card"><div className="overview-icon amber"><GitBranch size={17} /></div><div className="overview-copy"><span>Candidate proposal</span><strong>{candidate ? candidate.rule_id : 'No candidate available'}</strong><small>{candidate ? `Selected from ${formatCount(workspace.discovery.candidates_evaluated)} validation candidates` : workspace.discovery.reason || 'Insufficient evidence'}</small></div><div className="overview-state amber-text">{candidate ? 'DRAFT' : 'EMPTY'}</div></article>
              </section>

              <section className="hero-card">
                <div className="hero-copy"><div className="hero-pill"><Sparkles size={13} /> RULE ENGINE <span>·</span> MILESTONE 2B</div><h2>See what your rules<br />catch — and what they miss.</h2><p>Compare the documented baseline with a data-derived candidate using the backend's held-out synthetic test split.</p><div className="dataset-splits"><span><b>{formatCount(workspace.discovery.training_count)}</b> train</span><i /><span><b>{formatCount(workspace.discovery.validation_count)}</b> validation</span><i /><span><b>{formatCount(workspace.discovery.test_count)}</b> test</span></div></div>
                <div className="hero-visual" aria-hidden="true"><div className="visual-orbit orbit-one" /><div className="visual-orbit orbit-two" /><div className="visual-orbit orbit-three" /><div className="visual-core"><GitBranch size={27} /></div><div className="visual-node node-a"><ShieldCheck size={15} /></div><div className="visual-node node-b"><Activity size={15} /></div><div className="visual-node node-c"><Database size={14} /></div><span className="visual-spark">✳</span></div>
                <div className="hero-footnote"><span className="hero-foot-dot" /> API-REPORTED SPLIT SIZES <span className="hero-foot-line" /> SEED {workspace.discovery.seed}</div>
              </section>

              <section className="section-heading comparison-heading" id="comparison"><div><div className="section-kicker">HELD-OUT EVALUATION</div><h2>Baseline vs candidate</h2><p>{catalogBaseline ? `Catalog baseline ${catalogBaseline.rule_id} and the discovered candidate are compared on the same test split.` : 'The current backtest response supplies the baseline and candidate metrics.'}</p></div><button className="primary-button run-button" onClick={() => void runBacktest()} disabled={!backtestCanRun} aria-busy={backtestLoading} aria-label={backtest ? 'Run backtest again on held-out test split' : 'Run backtest on held-out test split'}>
                {backtestLoading ? <LoaderCircle size={16} className="spin" /> : <Activity size={16} />}
                {backtestLoading ? 'Running backtest…' : backtest ? 'Run backtest again' : 'Run backtest'}
                {!backtestLoading && <ArrowRight size={15} />}
              </button></section>

              {backtestError && <div className="inline-error" role="alert"><ShieldAlert size={16} /><span>{backtestError}</span><button onClick={() => void runBacktest()} disabled={backtestLoading}>Retry</button></div>}

              {backtestLoading && <div className="state-card inline-loading" aria-live="polite"><LoaderCircle size={20} className="spin" /><div><strong>Running held-out backtest</strong><p>Evaluating baseline and candidate against the same test records…</p></div></div>}

              {!candidate && <div className="state-card empty-card"><div className="state-icon"><Sparkles size={18} /></div><div><strong>No candidate could be proposed</strong><p>{workspace.discovery.reason || 'The discovery API returned insufficient evidence for this dataset.'}</p></div></div>}

              {candidate && !backtest && !backtestLoading && !backtestError && <div className="state-card empty-card"><div className="state-icon"><Activity size={18} /></div><div><strong>Ready to evaluate</strong><p>The candidate and dataset evidence are loaded. Run a backtest to retrieve measured baseline and candidate results.</p></div><button className="text-button" onClick={() => void runBacktest()}>Run backtest <ArrowRight size={14} /></button></div>}

              {backtest && (
                <>
                  <div className="result-banner"><span><Check size={15} /> Backtest complete</span><span>Test split · {formatCount(backtest.candidate_metrics.total_evaluated)} transactions</span></div>
                  <section className="comparison-grid" aria-label="Baseline and candidate backtest metrics">
                    <MetricColumn label={backtest.baseline_rule.name} metrics={backtest.baseline_metrics} accent="neutral" />
                    <MetricColumn label={backtest.candidate_rule.name} metrics={backtest.candidate_metrics} accent="green" />
                  </section>
                  <Tradeoff baseline={backtest.baseline_metrics} candidate={backtest.candidate_metrics} />
                </>
              )}

              <section className="detail-grid">
                <article className="panel candidate-panel" id="candidate">
                  <div className="panel-heading"><div><div className="section-kicker">RULE INSPECTION</div><h2>Candidate proposal</h2><p>Exact rule returned by the discovery API</p></div><span className="status-badge draft-badge">{candidate?.status ?? 'No candidate'}</span></div>
                  {candidate ? <>
                    <div className="candidate-identity"><div className="rule-symbol"><GitBranch size={18} /></div><div><strong>{candidate.name}</strong><span>{candidate.rule_id} <span className="identity-dot">·</span> v{candidate.version}</span></div></div>
                    <p className="candidate-description">{candidate.description}</p>
                    <h3 className="subheading">Exact condition{candidate.conditions.length > 1 ? 's' : ''}</h3>
                    <CandidateConditions rule={candidate} />
                    <h3 className="subheading rationale-heading">Rationale</h3><p className="rationale-copy">{candidate.rationale}</p>
                    <div className="evidence-card"><div className="evidence-title"><Sparkles size={15} /><strong>Validation evidence</strong><span>TRAIN → VALIDATION</span></div><p>Thresholds were derived from {formatCount(workspace.discovery.training_count)} training records. The selected proposal was chosen from {formatCount(workspace.discovery.candidates_evaluated)} non-degenerate candidates using validation metrics.</p>{workspace.discovery.validation_metrics && <div className="evidence-stats"><span>Precision <b>{formatPercent(workspace.discovery.validation_metrics.precision)}</b></span><span>Recall <b>{formatPercent(workspace.discovery.validation_metrics.recall)}</b></span><span>False positives <b>{formatCount(workspace.discovery.validation_metrics.false_positives)}</b></span></div>}</div>
                  </> : <div className="empty-inline"><Sparkles size={18} /><span>No candidate rule is available for inspection.</span></div>}
                </article>

                <article className="panel review-panel" id="review">
                  <div className="panel-heading"><div><div className="section-kicker">HUMAN OVERSIGHT</div><h2>Review status</h2><p>Approval and activation are separate decisions</p></div><span className="review-icon"><FileCheck2 size={18} /></span></div>
                  <div className="review-status"><span className="review-status-dot" /><div><strong>{reviewPending ? 'Pending human review' : candidate ? `Backend status: ${candidate.status}` : 'No proposal to review'}</strong><p>{candidate ? `The backend currently labels this rule “${candidate.status}”.` : 'Discovery has no candidate proposal to review.'}</p></div></div>
                  <div className="review-limitation"><ShieldAlert size={17} /><div><strong>Decision recording is not available</strong><p>The current API has no persistent approve/reject endpoint. No review decision was sent or simulated, and this dashboard will not activate rules.</p></div></div>
                  <div className="review-foot"><ShieldCheck size={14} /> Proposal remains non-active</div>
                </article>
              </section>

              <section className="panel missed-panel" id="missed-fraud">
                <div className="panel-heading missed-heading"><div><div className="section-kicker">FALSE-NEGATIVE EVIDENCE</div><h2>Fraud missed on the test split</h2><p>Only transaction IDs returned by the backtest API are shown; no feature values are exposed here.</p></div><span className="missed-total"><ShieldAlert size={15} />{missedTransactions.length} IDs</span></div>
                {backtest ? (
                  backtest.fraud_missed_by_candidate ? missedTransactions.length ? <div className="table-wrap"><table><caption className="sr-only">Test-split fraud transaction IDs missed by each rule</caption><thead><tr><th scope="col">Transaction ID</th><th scope="col">Baseline</th><th scope="col">Candidate</th></tr></thead><tbody>{missedTransactions.map((item) => <tr key={item.transactionId}><th scope="row" className="transaction-id">{item.transactionId}</th><td>{item.baselineMiss ? <span className="miss-tag baseline-tag"><X size={12} /> Missed</span> : <span className="not-missed">—</span>}</td><td>{item.candidateMiss ? <span className="miss-tag candidate-tag"><X size={12} /> Missed</span> : <span className="not-missed">—</span>}</td></tr>)}</tbody></table></div> : <div className="no-misses"><Check size={16} /> Neither rule missed fraud IDs on this test split.</div> : <div className="api-version-note"><CircleHelp size={16} /><span>This backend response version exposes baseline missed IDs only; candidate missed-ID evidence is unavailable.</span></div>
                ) : <div className="empty-table"><Activity size={18} /><span>Run a backtest to load missed-fraud evidence from the API.</span></div>}
              </section>

              <footer className="page-footer"><span>RULEPILOT AI <i>·</i> DETERMINISTIC RULE ENGINE</span><span>{workspace.apiRoot.name} <i>·</i> Synthetic data only</span></footer>
            </>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
