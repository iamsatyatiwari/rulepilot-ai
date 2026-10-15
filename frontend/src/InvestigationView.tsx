import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import {
  ArrowRight,
  BadgeCheck,
  Bot,
  Check,
  CircleAlert,
  CircleSlash,
  ClipboardPaste,
  Database,
  ExternalLink,
  FileSearch,
  FileText,
  FlaskConical,
  GitBranch,
  History,
  LoaderCircle,
  Lock,
  Quote,
  RefreshCw,
  Scale,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  Wrench,
  X,
} from 'lucide-react'
import {
  INVESTIGATION_TIMEOUT_MS,
  apiRequest,
  postJson,
  type AdvisoryList,
  type AdvisorySummary,
  type AgentStatus,
  type CustomAdvisory,
  type InvestigationReport,
  type InvestigationStatus,
  type InvestigationSummary,
  type ReviewDecision,
  type RuleCatalog,
  type StoredInvestigation,
} from './api'
import { CandidateConditions, MetricColumn, formatCount, formatDelta, formatPercent, ruleText, safeMessage } from './components'

const STATUS_LABEL: Record<InvestigationStatus, string> = {
  pending_human_review: 'Pending human review',
  covered_by_existing_rules: 'Covered by existing rules',
  insufficient_evidence: 'Insufficient evidence',
  not_testable: 'Not testable with available data',
  agent_incomplete: 'Agent incomplete',
}

const SOURCE_LABEL: Record<string, string> = {
  government_psa: 'Government PSA',
  regulatory_advisory: 'Regulatory advisory',
  industry_guidance: 'Industry guidance',
  analyst_supplied: 'Analyst supplied',
  customer_reports: 'Customer fraud reports',
}

const DECISION_LABEL: Record<ReviewDecision, string> = {
  approve: 'Approved for further testing',
  reject: 'Rejected',
  request_changes: 'Changes requested',
}

const ORIGIN_LABEL: Record<InvestigationReport['origin'], string> = {
  live: 'Live run',
  recorded: 'Recorded run',
  scheduled: 'Scheduled run',
}

type StepState = 'done' | 'skipped' | 'failed' | 'pending'

function Pipeline({ item }: { item: StoredInvestigation }) {
  const { report, reviews } = item
  const verified = report.evidence_quotes.filter((quote) => quote.verified).length
  const steps: { label: string; detail: string; state: StepState; icon: ReactNode }[] = [
    { label: 'Source', detail: `${verified}/${report.evidence_quotes.length} quotes verified`, state: report.findings ? (verified === report.evidence_quotes.length && verified > 0 ? 'done' : 'failed') : 'failed', icon: <FileText size={15} /> },
    { label: 'Findings', detail: report.findings ? report.findings.technique_name : 'Not submitted', state: report.findings ? 'done' : 'failed', icon: <FileSearch size={15} /> },
    { label: 'Coverage', detail: report.coverage ? report.coverage.status.replace(/_/g, ' ') : '—', state: report.coverage ? (report.coverage.status === 'not_testable' ? 'skipped' : 'done') : 'failed', icon: <Scale size={15} /> },
    { label: 'Candidates', detail: `${report.candidates.length} validated`, state: report.candidates.length ? 'done' : 'skipped', icon: <GitBranch size={15} /> },
    { label: 'Held-out test', detail: report.holdout ? `${formatCount(report.holdout.combined_metrics.total_evaluated)} records, once` : 'Not run', state: report.holdout ? 'done' : 'skipped', icon: <FlaskConical size={15} /> },
    { label: 'Human review', detail: reviews.length ? DECISION_LABEL[reviews[reviews.length - 1].decision] : report.status === 'pending_human_review' ? 'Awaiting decision' : 'Nothing to review', state: reviews.length ? 'done' : report.status === 'pending_human_review' ? 'pending' : 'skipped', icon: <UserCheck size={15} /> },
  ]
  return (
    <ol className="pipeline" aria-label="Investigation pipeline">
      {steps.map((step) => (
        <li key={step.label} className={`pipeline-step step-${step.state}`}>
          <span className="pipeline-icon">{step.icon}</span>
          <span className="pipeline-copy"><strong>{step.label}</strong><small>{step.detail}</small></span>
        </li>
      ))}
    </ol>
  )
}

function FieldChips({ fields, tone }: { fields: string[]; tone: 'ok' | 'missing' | 'neutral' }) {
  if (!fields.length) return <span className="muted-text">None</span>
  return <div className="chip-row">{fields.map((field) => <code key={field} className={`field-chip chip-${tone}`}>{field}</code>)}</div>
}

function BulletList({ items }: { items: string[] }) {
  if (!items.length) return <p className="muted-text">None reported.</p>
  return <ul className="bullet-list">{items.map((item) => <li key={item}>{item}</li>)}</ul>
}

function ReviewPanel({ item, onReviewed }: { item: StoredInvestigation; onReviewed: () => Promise<void> }) {
  const [reviewer, setReviewer] = useState('')
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState<ReviewDecision | null>(null)
  const [error, setError] = useState('')
  const [changing, setChanging] = useState(false)
  const { report, reviews } = item
  const reviewable = report.status === 'pending_human_review' && report.selected_rule
  const latest = reviews.length ? reviews[reviews.length - 1] : null

  const submit = async (decision: ReviewDecision) => {
    if (!reviewer.trim() || !comment.trim()) {
      setError('Enter a reviewer name and a comment before recording a decision.')
      return
    }
    setSubmitting(decision)
    setError('')
    try {
      await postJson(`/api/v1/investigations/${report.investigation_id}/review`, { decision, reviewer: reviewer.trim(), comment: comment.trim() })
      setComment('')
      setChanging(false)
      await onReviewed()
    } catch (reviewError) {
      setError(safeMessage(reviewError))
    } finally {
      setSubmitting(null)
    }
  }

  return (
    <article className="panel" id="review">
      <div className="panel-heading"><div><div className="section-kicker">GOVERNANCE</div><h2>Human review</h2><p>Decisions are recorded with reviewer, rule version, and time. Approving a rule activates it in the Demo bank and Transaction monitor; rejecting it switches it off again.</p></div><span className="review-icon"><UserCheck size={18} /></span></div>
      {reviews.length > 0 && (
        <ul className="review-history" aria-label="Review history">
          {reviews.map((review) => (
            <li key={review.review_id}>
              <span className={`decision-badge decision-${review.decision}`}>{DECISION_LABEL[review.decision]}</span>
              <div><strong>{review.reviewer}</strong> · <span>{new Date(review.decided_at).toLocaleString()}</span><p>{review.comment}</p><small><Lock size={11} /> {review.rule_id} v{review.rule_version} · activation: {review.activation === 'active' ? 'active' : 'not activated'}</small></div>
            </li>
          ))}
        </ul>
      )}
      {reviewable && latest && !changing && (
        <div className={`review-confirmation confirmation-${latest.decision}`} role="status">
          {latest.decision === 'approve' ? <BadgeCheck size={20} /> : <CircleAlert size={20} />}
          <div>
            <strong>{latest.decision === 'approve' ? `Approved by ${latest.reviewer}` : `${DECISION_LABEL[latest.decision]} by ${latest.reviewer}`} · {new Date(latest.decided_at).toLocaleString()}</strong>
            {latest.decision === 'approve'
              ? <p>Rule <b>{latest.rule_id}</b> is now <b>active</b>: the Demo bank and Transaction monitor use it, together with the original rule, to hold suspicious payments. Record <i>Reject</i> or <i>Request changes</i> to switch it off.</p>
              : <p>Rule <b>{latest.rule_id}</b> is not in the reviewed catalog and is not used in the bank.</p>}
            <div className="review-actions">
              {latest.decision === 'approve' && <a className="primary-button" href="#bank">Test it in the Demo bank <ArrowRight size={14} /></a>}
              <button className="secondary-button" onClick={() => setChanging(true)}>Record a different decision</button>
            </div>
          </div>
        </div>
      )}
      {reviewable && (!latest || changing) ? (
        <div className="review-form">
          <label>Reviewer<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} maxLength={100} placeholder="e.g. fraud-strategy analyst" /></label>
          <label>Comment<textarea value={comment} onChange={(event) => setComment(event.target.value)} maxLength={1000} rows={3} placeholder="Reason for the decision and any follow-up testing required" /></label>
          {error && <div className="inline-error" role="alert"><ShieldAlert size={15} /><span>{error}</span></div>}
          <div className="review-actions">
            <button className="primary-button" onClick={() => void submit('approve')} disabled={submitting !== null}>{submitting === 'approve' ? <LoaderCircle size={15} className="spin" /> : <Check size={15} />} Approve for further testing</button>
            <button className="secondary-button" onClick={() => void submit('request_changes')} disabled={submitting !== null}>Request changes</button>
            <button className="secondary-button danger" onClick={() => void submit('reject')} disabled={submitting !== null}><X size={14} /> Reject</button>
          </div>
        </div>
      ) : !reviewable ? (
        <div className="review-limitation"><CircleSlash size={17} /><div><strong>No candidate awaits review</strong><p>This investigation did not produce a held-out-tested candidate, so there is nothing to approve.</p></div></div>
      ) : null}
    </article>
  )
}

function referenceRules(report: InvestigationReport) {
  return report.reference_rules?.length ? report.reference_rules : [report.baseline_rule]
}

function RuleCatalogPanel({ catalog }: { catalog: RuleCatalog | null }) {
  if (!catalog) return null
  return (
    <section aria-label="Reviewed rule catalog">
    <details className="panel catalog-panel">
      <summary className="catalog-summary">Reviewed rule catalog <small>{catalog.active.length} active · {catalog.approved_not_active.length} approved and active</small></summary>
      <div className="panel-heading"><div><div className="section-kicker">LEARNING LOOP · REVIEWED RULE CATALOG</div><h2>Rules every new investigation is compared against</h2><p>Approved candidates join the rule set: they are active in the Demo bank and every new investigation is compared against them. Reject or request changes to remove one.</p></div><span className="review-icon"><GitBranch size={17} /></span></div>
      <ul className="catalog-list">
        {catalog.active.map((rule) => (
          <li key={rule.rule_id}><span className="catalog-state state-active">Active baseline</span><div><strong>{rule.rule_id}</strong> · {rule.name} <small>v{rule.version}</small><CandidateConditions rule={rule} /></div></li>
        ))}
        {catalog.approved_not_active.map((entry) => (
          <li key={entry.rule.rule_id}><span className="catalog-state state-approved">Approved · active</span><div><strong>{entry.rule.rule_id}</strong> · {entry.rule.name} <small>v{entry.rule.version}</small><CandidateConditions rule={entry.rule} /><p className="catalog-provenance">Approved by {entry.approved_by} on {new Date(entry.approved_at).toLocaleString()} from “{entry.advisory_title}”. “{entry.review_comment}”</p></div></li>
        ))}
      </ul>
      {catalog.approved_not_active.length === 0 && <p className="muted-text">No candidates have been approved yet. Approve one in Human review and re-run an investigation to see it used.</p>}
    </details>
    </section>
  )
}

function Summary({ report, reviews }: { report: InvestigationReport; reviews: StoredInvestigation['reviews'] }) {
  const latest = reviews.length ? reviews[reviews.length - 1] : null
  const { findings, coverage, holdout_delta: delta, selected_rule: rule } = report
  const verified = report.evidence_quotes.filter((quote) => quote.verified).length
  return (
    <section className="panel summary-panel" aria-label="Summary">
      <div className="panel-heading"><div><div className="section-kicker">IN PLAIN WORDS</div><h2>What RulePilot found</h2></div></div>
      <ol className="summary-list">
        <li><strong>The advisory</strong><span>{findings ? `${findings.technique_name}: ${findings.summary}` : 'The agent did not finish reading the advisory.'} {report.evidence_quotes.length > 0 && <em>({verified} of {report.evidence_quotes.length} quotes checked word-for-word in the source)</em>}</span></li>
        <li><strong>Can our data test it?</strong><span>{coverage ? (coverage.status === 'not_testable' ? `No. The data has none of the fields it needs (${coverage.missing_fields.join(', ')}), so no rule was invented.` : coverage.status === 'partially_testable' ? `Partly. Available: ${coverage.available_fields.join(', ')}. Missing: ${coverage.missing_fields.join(', ')}.` : `Yes. All needed fields exist: ${coverage.available_fields.join(', ')}.`) : 'Unknown.'}</span></li>
        <li><strong>Proposed rule</strong><span>{rule ? <><code>{ruleText(rule)}</code> — chosen from {report.candidates.length} candidate(s) tested on validation data.</> : report.status === 'covered_by_existing_rules' ? 'None needed: the existing rules already cover this technique.' : 'None.'}</span></li>
        {report.customer_report_check && <li><strong>Customer reports</strong><span>The proposed rule catches <b>{report.customer_report_check.caught_by_proposed_rule} of {report.customer_report_check.reported_cases}</b> payments customers reported as fraud that the active rules missed.</span></li>}
        {delta && <li><strong>Result on unseen test data</strong><span>Adding it to the current rules catches <b>{formatDelta(delta.recall_change)}</b> more fraud ({delta.fraud_newly_detected >= 0 ? '+' : ''}{formatCount(delta.fraud_newly_detected)} cases) with a false-alarm change of <b>{formatDelta(delta.false_positive_rate_change, 2)}</b> ({delta.alert_change >= 0 ? '+' : ''}{formatCount(delta.alert_change)} alerts).</span></li>}
        <li><strong>Your decision</strong><span>{latest ? `${DECISION_LABEL[latest.decision]} by ${latest.reviewer}.${latest.decision === 'approve' ? ' The rule is now active in the Demo bank.' : ''}` : report.status === 'pending_human_review' ? 'Approve, request changes, or reject below. Approving switches the rule on in the Demo bank.' : 'Nothing to approve for this run.'}</span></li>
      </ol>
    </section>
  )
}

function Report({ item, onReviewed }: { item: StoredInvestigation; onReviewed: () => Promise<void> }) {
  const report: InvestigationReport = item.report
  const { findings, coverage, holdout, holdout_delta: delta } = report
  // Once a human has decided, the banner shows the decision instead of "awaiting review".
  const decision = report.status === 'pending_human_review' && item.reviews.length ? item.reviews[item.reviews.length - 1].decision : null
  const headline = decision ? report.headline.replace(/\s*Awaiting human review\.?$/, '') : report.headline
  return (
    <div className="report">
      <section className={`report-banner banner-${report.status}`} role="status">
        <div className="report-banner-main">
          <span className={`status-pill pill-${decision ? `review-${decision}` : report.status}`}>{decision ? DECISION_LABEL[decision] : STATUS_LABEL[report.status]}</span>
          <h2>{headline}</h2>
          <p>{report.advisory.title} · {report.dataset.dataset_id} v{report.dataset.version} · seed {report.seed} · compared against {referenceRules(report).length} reviewed rule(s) · {report.review_history_used ?? 0} prior review(s) available to the agent</p>
        </div>
        <div className="report-banner-meta">
          <span className={`origin-badge origin-${report.origin}`}>{ORIGIN_LABEL[report.origin]}</span>
          <small>{new Date(report.created_at).toLocaleString()}</small>
          <small><Bot size={12} /> {report.model_run.model} · {report.model_run.llm_calls} model calls</small>
        </div>
      </section>

      <Summary report={report} reviews={item.reviews} />
      <ReviewPanel item={item} onReviewed={onReviewed} />
      <details className="audit-details">
        <summary>Evidence and audit trail <small>pipeline · source quotes · findings · coverage · candidates · held-out test · agent trace · guardrails · limitations</small></summary>
      <Pipeline item={item} />

      <section className="report-grid two">
        <article className="panel">
          <div className="panel-heading"><div><div className="section-kicker">INTELLIGENCE SOURCE</div><h2>{report.advisory.title}</h2><p>{report.advisory.publisher}</p></div><span className="source-type">{SOURCE_LABEL[report.advisory.source_type] ?? report.advisory.source_type}</span></div>
          <dl className="meta-list">
            <div><dt>Source</dt><dd><a href={report.advisory.source_url} target="_blank" rel="noreferrer noopener">{report.advisory.source_url} <ExternalLink size={11} /></a></dd></div>
            <div><dt>Published</dt><dd>{report.advisory.published_date ?? 'Not stated'}</dd></div>
            <div><dt>Retrieved</dt><dd>{report.advisory.retrieved_at}</dd></div>
            <div><dt>Content SHA-256</dt><dd><code title={report.advisory.content_sha256}>{report.advisory.content_sha256.slice(0, 16)}…</code></dd></div>
          </dl>
          <h3 className="subheading">Evidence quotes</h3>
          {report.evidence_quotes.length ? (
            <ul className="quote-list">
              {report.evidence_quotes.map((quote) => (
                <li key={quote.quote} className={quote.verified ? 'quote-verified' : 'quote-unverified'}>
                  <Quote size={13} /><span>{quote.quote}</span>
                  <em>{quote.verified ? <><BadgeCheck size={12} /> Verified in source</> : <><CircleAlert size={12} /> Not found in source</>}</em>
                </li>
              ))}
            </ul>
          ) : <p className="muted-text">No quotes were submitted.</p>}
        </article>

        <article className="panel">
          <div className="panel-heading"><div><div className="section-kicker">STRUCTURED FINDINGS</div><h2>{findings?.technique_name ?? 'No findings submitted'}</h2><p>Extracted by Gemini; every claim below is checked by deterministic code.</p></div></div>
          {findings ? (
            <>
              <p className="body-copy">{findings.summary}</p>
              <div className="findings-grid">
                <div><h3 className="subheading">Behaviors</h3><BulletList items={findings.behaviors} /></div>
                <div><h3 className="subheading">Indicators</h3><BulletList items={findings.indicators} /></div>
                <div><h3 className="subheading">Testable hypotheses</h3><BulletList items={findings.testable_hypotheses} /></div>
                <div><h3 className="subheading">Uncertainties</h3><BulletList items={findings.uncertainties} /></div>
              </div>
            </>
          ) : <p className="muted-text">{report.model_run.errors.join(' ') || 'The agent stopped before submitting findings.'}</p>}
        </article>
      </section>

      {coverage && (
        <section className="panel coverage-panel">
          <div className="panel-heading"><div><div className="section-kicker">COVERAGE-GAP ANALYSIS</div><h2>Can existing data and rules test this technique?</h2><p>Computed deterministically from the fields the agent said it needs and the fields present in {report.dataset.dataset_id}.</p></div><span className={`coverage-status coverage-${coverage.status}`}>{coverage.status.replace(/_/g, ' ')}</span></div>
          <div className="coverage-grid">
            <div><h3 className="subheading">Required &amp; available</h3><FieldChips fields={coverage.available_fields} tone="ok" /></div>
            <div><h3 className="subheading">Required but missing</h3><FieldChips fields={coverage.missing_fields} tone="missing" /></div>
            <div><h3 className="subheading">Existing rules ({referenceRules(report).map((rule) => rule.rule_id).join(', ')}) check</h3><FieldChips fields={coverage.existing_rule_fields} tone="neutral" /></div>
          </div>
          {report.agent_conclusion && <div className="agent-rationale"><Bot size={15} /><div><strong>Agent assessment: {report.agent_conclusion.coverage_assessment.replace(/_/g, ' ')}</strong><p>{report.agent_conclusion.rationale}</p></div></div>}
        </section>
      )}

      {report.candidates.length > 0 && (
        <section className="panel">
          <div className="panel-heading"><div><div className="section-kicker">CANDIDATE RULES · VALIDATION SPLIT</div><h2>Proposed by the agent, measured by the engine</h2><p>Each candidate was schema-validated and evaluated on {formatCount(report.split_sizes.validation)} validation records. The test split was never visible to the agent.</p></div></div>
          <div className="table-wrap">
            <table className="candidate-table">
              <caption className="sr-only">Candidate rules and validation metrics</caption>
              <thead><tr><th scope="col">Candidate</th><th scope="col">Conditions</th><th scope="col">Candidate recall</th><th scope="col">Rule-set recall</th><th scope="col">Rule-set FPR</th><th scope="col">Alerts</th></tr></thead>
              <tbody>
                {report.candidates.map(({ rule, validation }) => {
                  const selected = report.selected_rule?.rule_id === rule.rule_id
                  return (
                    <tr key={rule.rule_id} className={selected ? 'selected-row' : ''}>
                      <th scope="row"><span className="candidate-name">{rule.name}</span><small>{rule.rule_id}{selected && <b className="selected-tag">Selected</b>}</small></th>
                      <td><CandidateConditions rule={rule} /></td>
                      <td>{formatPercent(validation.candidate_metrics.recall)}</td>
                      <td>{formatPercent(validation.baseline_metrics.recall)} → <b>{formatPercent(validation.combined_metrics.recall)}</b></td>
                      <td>{formatPercent(validation.baseline_metrics.false_positive_rate, 2)} → <b>{formatPercent(validation.combined_metrics.false_positive_rate, 2)}</b></td>
                      <td>{formatCount(validation.baseline_metrics.total_flagged)} → <b>{formatCount(validation.combined_metrics.total_flagged)}</b></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {holdout && delta && report.selected_rule && (
        <section className="holdout-section">
          <div className="section-heading comparison-heading"><div><div className="section-kicker">HELD-OUT TEST · EVALUATED ONCE BY THE ORCHESTRATOR</div><h2>Existing rule set vs rule set + {report.selected_rule.rule_id}</h2><p>{formatCount(holdout.combined_metrics.total_evaluated)} synthetic test records. Measured differences, not a claim of real-world performance.</p></div></div>
          <div className="delta-strip" aria-label="Held-out changes">
            <div><span>Recall</span><strong className={delta.recall_change > 0 ? 'good' : ''}>{formatDelta(delta.recall_change)}</strong></div>
            <div><span>Precision</span><strong className={delta.precision_change < 0 ? 'warn' : ''}>{formatDelta(delta.precision_change)}</strong></div>
            <div><span>False-positive rate</span><strong className={delta.false_positive_rate_change > 0 ? 'warn' : ''}>{formatDelta(delta.false_positive_rate_change, 2)}</strong></div>
            <div><span>Additional fraud detected</span><strong>{delta.fraud_newly_detected >= 0 ? '+' : ''}{formatCount(delta.fraud_newly_detected)}</strong></div>
            <div><span>Alert volume</span><strong>{delta.alert_change >= 0 ? '+' : ''}{formatCount(delta.alert_change)}</strong></div>
          </div>
          <section className="comparison-grid" aria-label="Held-out rule-set comparison">
            <MetricColumn label={`Existing rule set (${referenceRules(report).length})`} metrics={holdout.baseline_metrics} accent="neutral" />
            <MetricColumn label={`Existing set + ${report.selected_rule.name}`} metrics={holdout.combined_metrics} accent="green" />
          </section>
        </section>
      )}

      <section className="report-grid two">
        <article className="panel">
          <div className="panel-heading"><div><div className="section-kicker">AGENT TRACE · GOOGLE ADK</div><h2>Tool calls</h2><p>{report.model_run.llm_calls} of {report.model_run.max_llm_calls} model calls · {formatCount(report.model_run.input_tokens + report.model_run.output_tokens)} tokens · {report.model_run.timeout_seconds}s limit</p></div><span className="review-icon"><Wrench size={17} /></span></div>
          <ol className="trace-list">
            {report.trace.map((step) => (
              <li key={step.step} className={step.ok ? 'trace-ok' : 'trace-error'}>
                <span className="trace-index">{step.step}</span>
                <div><code>{step.tool}</code><p>{step.summary}</p></div>
              </li>
            ))}
          </ol>
          {report.model_run.errors.length > 0 && (report.findings
            ? <div className="inline-note"><Bot size={14} /> Capacity fallback: {report.model_run.errors.length} transient model error(s) before {report.model_run.model} completed the run.</div>
            : <div className="inline-error" role="alert"><ShieldAlert size={15} /><span>{report.model_run.errors.join(' · ')}</span></div>)}
        </article>
        <article className="panel">
          <div className="panel-heading"><div><div className="section-kicker">DETERMINISTIC GUARDRAILS</div><h2>Verification checks</h2><p>Computed by Python after the agent finished; the model cannot alter them.</p></div><span className="review-icon"><ShieldCheck size={17} /></span></div>
          <ul className="guardrail-list">
            {report.guardrails.map((check) => (
              <li key={check.check} className={check.passed ? 'guard-pass' : 'guard-fail'}>
                {check.passed ? <Check size={14} /> : <X size={14} />}
                <div><strong>{check.check}</strong><p>{check.detail}</p></div>
              </li>
            ))}
          </ul>
        </article>
      </section>

        <article className="panel">
          <div className="panel-heading"><div><div className="section-kicker">LIMITATIONS</div><h2>What this result does not show</h2></div><span className="review-icon"><CircleAlert size={17} /></span></div>
          <BulletList items={report.limitations} />
        </article>
      </details>
    </div>
  )
}

const EMPTY_CUSTOM: CustomAdvisory = { title: '', publisher: '', source_url: '', text: '' }

const DATASET_OPTIONS = [
  { id: 'payments-scenario-v3', label: 'Payments scenario v3 · 30k synthetic, card + account signals (default)' },
  { id: 'sparkov-cards-v1', label: 'Sparkov cards v1 · 75k from an independent simulator' },
  { id: 'card-scenario-v2', label: 'Card scenario v2 · 6k synthetic, card signals only' },
]

export default function InvestigationView() {
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null)
  const [advisories, setAdvisories] = useState<AdvisorySummary[]>([])
  const [history, setHistory] = useState<InvestigationSummary[]>([])
  const [current, setCurrent] = useState<StoredInvestigation | null>(null)
  const [loadError, setLoadError] = useState('')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState<string | null>(null)
  const [runError, setRunError] = useState('')
  const [elapsed, setElapsed] = useState(0)
  const [showCustom, setShowCustom] = useState(false)
  const [custom, setCustom] = useState<CustomAdvisory>(EMPTY_CUSTOM)
  const [catalog, setCatalog] = useState<RuleCatalog | null>(null)
  const [datasetId, setDatasetId] = useState(DATASET_OPTIONS[0].id)

  const refreshCatalog = useCallback(async () => {
    try {
      setCatalog(await apiRequest<RuleCatalog>('/api/v1/rule-catalog'))
    } catch {
      setCatalog(null)
    }
  }, [])

  const openInvestigation = useCallback(async (investigationId: string) => {
    try {
      setCurrent(await apiRequest<StoredInvestigation>(`/api/v1/investigations/${investigationId}`))
    } catch (error) {
      setRunError(safeMessage(error))
    }
  }, [])

  const refreshHistory = useCallback(async () => {
    const items = await apiRequest<InvestigationSummary[]>('/api/v1/investigations')
    setHistory(items)
    return items
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    const [status, advisoryList, items] = await Promise.allSettled([
      apiRequest<AgentStatus>('/api/v1/agent/status'),
      apiRequest<AdvisoryList>('/api/v1/advisories'),
      refreshHistory(),
      refreshCatalog(),
    ])
    if (status.status === 'fulfilled') setAgentStatus(status.value)
    if (advisoryList.status === 'fulfilled') setAdvisories(advisoryList.value.items)
    else setLoadError(safeMessage(advisoryList.reason))
    if (items.status === 'fulfilled' && items.value.length) await openInvestigation(items.value[0].investigation_id)
    setLoading(false)
  }, [openInvestigation, refreshHistory, refreshCatalog])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!running) return
    setElapsed(0)
    const started = Date.now()
    const timer = window.setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [running])

  const investigate = async (label: string, body: Record<string, unknown>) => {
    setRunning(label)
    setRunError('')
    try {
      const result = await postJson<StoredInvestigation>('/api/v1/investigations', { ...body, dataset_id: datasetId }, INVESTIGATION_TIMEOUT_MS)
      setCurrent(result)
      setShowCustom(false)
      await refreshHistory()
    } catch (error) {
      setRunError(safeMessage(error))
    } finally {
      setRunning(null)
    }
  }

  const submitCustom = (event: FormEvent) => {
    event.preventDefault()
    void investigate(custom.title || 'Custom advisory', { custom_advisory: custom })
  }

  const agentReady = Boolean(agentStatus?.configured)

  return (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow"><span className="eyebrow-dot" /> INTELLIGENCE → COVERAGE GAP → CANDIDATE RULE → BACKTEST → REVIEW</div>
          <h1>Intelligence investigations</h1>
          <p className="welcome-subtitle">A bounded Gemini agent reads a financial-crime advisory, checks it against existing rules and available data, and proposes candidate rules. The deterministic engine measures them; a human decides.</p>
        </div>
        <div className="header-actions">
          <span className={`agent-chip ${agentReady ? 'agent-ready' : 'agent-off'}`}><Bot size={14} /> {agentStatus ? `${agentStatus.model} · ${agentReady ? 'ready' : 'not configured'}` : 'Agent status unknown'}</span>
          <button className="secondary-button" onClick={() => void load()} disabled={loading}><RefreshCw size={15} className={loading ? 'spin' : ''} /> Refresh</button>
        </div>
      </section>

      {loadError && <section className="state-card error-card" role="alert"><div className="state-icon error"><ShieldAlert size={19} /></div><div className="state-copy"><strong>Intelligence sources are unavailable</strong><p>{loadError}</p></div><button className="primary-button" onClick={() => void load()}><RefreshCw size={15} /> Retry</button></section>}

      <section className="source-section" aria-label="Intelligence sources">
        <div className="section-heading"><div><div className="section-kicker">STEP 1 · CHOOSE AN ADVISORY</div><h2>Fraud advisories</h2><p>Press Investigate on one. Gemini treats the text as untrusted data and has no web, file, or code tools.</p></div><button className="secondary-button" onClick={() => setShowCustom((value) => !value)} aria-expanded={showCustom}><ClipboardPaste size={15} /> {showCustom ? 'Close' : 'Paste an advisory'}</button></div>
        <label className="dataset-picker">Test against data
          <select value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>
            {DATASET_OPTIONS.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
          </select>
        </label>
        <div className="advisory-grid">
          {advisories.map((advisory) => (
            <article key={advisory.advisory_id} className="advisory-card">
              <div className="advisory-top"><span className="source-type">{SOURCE_LABEL[advisory.source_type] ?? advisory.source_type}</span><small>{advisory.published_date ?? `Retrieved ${advisory.retrieved_at}`}</small></div>
              <h3>{advisory.title}</h3>
              <p className="advisory-publisher">{advisory.publisher}</p>
              <p className="advisory-excerpt">{advisory.excerpt.slice(0, 210)}…</p>
              <div className="advisory-actions">
                <a href={advisory.source_url} target="_blank" rel="noreferrer noopener" className="text-button">Source <ExternalLink size={12} /></a>
                <button className="primary-button" disabled={!agentReady || running !== null} onClick={() => void investigate(advisory.title, { advisory_id: advisory.advisory_id })} aria-label={`Investigate ${advisory.title}`}>
                  {running === advisory.title ? <LoaderCircle size={15} className="spin" /> : <FileSearch size={15} />} Investigate <ArrowRight size={14} />
                </button>
              </div>
            </article>
          ))}
        </div>
        {showCustom && (
          <form className="panel custom-form" onSubmit={submitCustom}>
            <div className="custom-grid">
              <label>Title<input required maxLength={200} value={custom.title} onChange={(event) => setCustom({ ...custom, title: event.target.value })} /></label>
              <label>Publisher<input required maxLength={200} value={custom.publisher} onChange={(event) => setCustom({ ...custom, publisher: event.target.value })} /></label>
              <label>Source URL<input required type="url" value={custom.source_url} onChange={(event) => setCustom({ ...custom, source_url: event.target.value })} placeholder="https://" /></label>
            </div>
            <label>Advisory text (50–8,000 characters)<textarea required minLength={50} maxLength={8000} rows={6} value={custom.text} onChange={(event) => setCustom({ ...custom, text: event.target.value })} /></label>
            <div className="review-actions"><button className="primary-button" type="submit" disabled={!agentReady || running !== null}><FileSearch size={15} /> Investigate pasted advisory</button><small className="muted-text">{custom.text.length.toLocaleString()} / 8,000</small></div>
          </form>
        )}
        {agentStatus && !agentReady && <div className="inline-note"><Lock size={14} /> Live investigations are disabled because no Gemini credentials are configured on the server. Recorded runs remain viewable below.</div>}
      </section>

      {running && (
        <section className="state-card running-card" aria-live="polite">
          <LoaderCircle size={22} className="spin" />
          <div><strong>Gemini agent is investigating “{running}”</strong><p>Reading the source, inspecting rules and data coverage, proposing candidates, and measuring them on validation. Typically 20–60 seconds · {elapsed}s elapsed.</p></div>
        </section>
      )}
      {runError && <div className="inline-error" role="alert"><ShieldAlert size={16} /><span>{runError}</span></div>}

      <RuleCatalogPanel catalog={catalog} />

      {history.length > 0 && (
        <section className="history-strip" aria-label="Investigation history">
          <span className="history-label"><History size={14} /> History</span>
          {history.slice(0, 8).map((summary) => (
            <button key={summary.investigation_id} className={`history-item ${current?.report.investigation_id === summary.investigation_id ? 'active' : ''}`} onClick={() => void openInvestigation(summary.investigation_id)}>
              <span className={`dot dot-${summary.status}`} />
              <span>{summary.advisory_title.length > 34 ? `${summary.advisory_title.slice(0, 34)}…` : summary.advisory_title}</span>
              <small>{summary.origin === 'recorded' ? 'recorded' : `${summary.origin === 'scheduled' ? 'scheduled · ' : ''}${new Date(summary.created_at).toLocaleTimeString()}`}</small>
            </button>
          ))}
        </section>
      )}

      {current ? (
        <Report item={current} onReviewed={async () => { await openInvestigation(current.report.investigation_id); await refreshHistory(); await refreshCatalog() }} />
      ) : !loading && !running && (
        <section className="state-card empty-card"><div className="state-icon"><Database size={18} /></div><div><strong>No investigation yet</strong><p>Choose an advisory above to run the agent. Results include source-linked findings, coverage analysis, validated candidates, a single held-out test, and a review decision.</p></div></section>
      )}
    </>
  )
}
