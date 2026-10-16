import { ArrowRight, BookOpen, CreditCard, FileSearch, ShieldCheck, UserCheck } from 'lucide-react'

export type GuideTarget = 'investigations' | 'bank' | 'monitor'

const STEPS: { title: string; body: string; action: string; target: GuideTarget; icon: typeof FileSearch }[] = [
  {
    title: 'Investigate a fraud advisory',
    body: 'Pick “Preventing Card Testing” and press Investigate. Gemini reads the advisory, checks which data and rules exist, proposes up to three rules, and the engine measures them. Takes 20–90 seconds. No key? Open a recorded run from History.',
    action: 'Go to Investigations',
    target: 'investigations',
    icon: FileSearch,
  },
  {
    title: 'Read the result and approve',
    body: 'The summary says what was found and how much the proposed rule improves detection on held-out data. Enter your name and a comment, then Approve. The rule becomes active in the Demo bank straight away; Reject switches it off.',
    action: 'Review in Investigations',
    target: 'investigations',
    icon: UserCheck,
  },
  {
    title: 'Try it in the demo bank',
    body: 'Run the “Card-testing attack” on a demo card. Before approval the bank lets the tiny payments through (the original rule only checks amounts of 1,500 or more). After you approve the rule, the same attack is held for review from about the sixth attempt.',
    action: 'Open the Demo bank',
    target: 'bank',
    icon: CreditCard,
  },
  {
    title: 'See the learning loop',
    body: 'Investigate the same advisory again: the agent now compares against your approved rule and answers “Covered by existing rules”. Investigate the SIM-swap advisory to see a second technique, then run the SIM-swap scenario in the bank.',
    action: 'Back to Investigations',
    target: 'investigations',
    icon: ShieldCheck,
  },
]

export default function GuideView({ onNavigate }: { onNavigate: (target: GuideTarget) => void }) {
  return (
    <>
      <section className="welcome-row">
        <div>
          <div className="eyebrow"><span className="eyebrow-dot" /> START HERE · 4 STEPS · ABOUT 5 MINUTES</div>
          <h1>From fraud advisory to a tested rule</h1>
          <p className="welcome-subtitle">Fraud techniques change faster than detection rules. RulePilot reads new intelligence with Gemini, proposes rules, measures them with deterministic code, and lets a person decide.</p>
        </div>
      </section>

      <ol className="guide-steps">
        {STEPS.map((step, index) => {
          const Icon = step.icon
          return (
            <li key={step.title} className="guide-step">
              <span className="guide-number">{index + 1}</span>
              <div>
                <h2><Icon size={18} /> {step.title}</h2>
                <p>{step.body}</p>
                <button className="secondary-button" onClick={() => onNavigate(step.target)}>{step.action} <ArrowRight size={14} /></button>
              </div>
            </li>
          )
        })}
      </ol>

      <section className="panel guide-principles">
        <div className="panel-heading"><div><div className="section-kicker">HOW TO READ WHAT YOU SEE</div><h2>Three rules the system never breaks</h2></div><span className="review-icon"><BookOpen size={17} /></span></div>
        <ul className="bullet-list">
          <li><b>Gemini proposes, code measures.</b> Every number on screen is computed by the rule engine, never written by the model.</li>
          <li><b>The test data is used once.</b> The agent only sees training and validation data; the held-out result is computed after it finishes.</li>
          <li><b>Humans decide.</b> Gemini can only propose. A rule starts blocking payments only when a person approves it, and rejecting it switches it off again. Every decision is in the audit log.</li>
        </ul>
        <p className="muted-text">All transactions are synthetic or simulated. Results show how the workflow behaves, not real-world detection rates.</p>
      </section>
    </>
  )
}
