import { Database, ShieldAlert } from 'lucide-react'
import { ApiRequestError, type Metrics, type Rule } from './api'

export const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 })

export function formatCount(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? numberFormat.format(value) : '—'
}

export function formatPercent(value: number | null | undefined, digits = 1) {
  return typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : '—'
}

export function formatDelta(value: number, digits = 1) {
  if (!Number.isFinite(value)) return '—'
  const points = value * 100
  const direction = points > 0 ? '+' : ''
  return `${direction}${points.toFixed(digits)} pp`
}

export function metricDirection(value: number) {
  if (value > 0.000001) return 'up'
  if (value < -0.000001) return 'down'
  return 'same'
}

export function metricDelta(candidate: number, baseline: number) {
  return Number.isFinite(candidate) && Number.isFinite(baseline) ? candidate - baseline : Number.NaN
}

export function safeMessage(error: unknown) {
  if (error instanceof ApiRequestError) return error.message
  return 'RulePilot could not load this result. Please retry.'
}

export function MetricColumn({ label, metrics, accent }: { label: string; metrics: Metrics; accent: 'neutral' | 'green' }) {
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

export function CandidateConditions({ rule }: { rule: Rule }) {
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
