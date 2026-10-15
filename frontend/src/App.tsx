import { useEffect, useState } from 'react'
import { Activity, BookOpen, Check, CreditCard, FileSearch, FlaskConical, GitBranch, LayoutDashboard, Menu, ShieldCheck, X } from 'lucide-react'
import { apiRequest, type ApiHealth } from './api'
import BankView from './BankView'
import GuideView from './GuideView'
import InvestigationView from './InvestigationView'
import LabView from './LabView'
import MonitorView from './MonitorView'
import RuleEngineView from './RuleEngineView'

type View = 'guide' | 'investigations' | 'bank' | 'lab' | 'monitor' | 'engine'

const VIEWS: View[] = ['guide', 'investigations', 'bank', 'lab', 'monitor', 'engine']
const VIEW_TITLE: Record<View, string> = { guide: 'Start here', investigations: 'Investigations', bank: 'Demo bank', lab: 'Rule lab', monitor: 'Transaction monitor', engine: 'Rule engine' }
type HealthState = 'checking' | 'online' | 'offline'

function viewFromHash(): View {
  const hash = window.location.hash.slice(1) as View
  return VIEWS.includes(hash) ? hash : 'guide'
}

function App() {
  const [view, setView] = useState<View>(viewFromHash)
  const [healthState, setHealthState] = useState<HealthState>('checking')
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    let active = true
    apiRequest<ApiHealth>('/health')
      .then((health) => active && setHealthState(health.status === 'ok' ? 'online' : 'offline'))
      .catch(() => active && setHealthState('offline'))
    const onHash = () => setView(viewFromHash())
    window.addEventListener('hashchange', onHash)
    return () => {
      active = false
      window.removeEventListener('hashchange', onHash)
    }
  }, [])

  const navigate = (next: View) => {
    setView(next)
    setMenuOpen(false)
    window.history.replaceState(null, '', `#${next}`)
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
        <a className="brand" href="#guide" onClick={() => navigate('guide')} aria-label="RulePilot AI start page">
          <span className="brand-mark"><GitBranch size={19} strokeWidth={2.5} /></span>
          <span className="brand-name">rulepilot<span>ai</span></span>
        </a>
        <button className="mobile-close" onClick={() => setMenuOpen(false)} aria-label="Close navigation"><X size={18} /></button>
        <div className="nav-label nav-label-first">DEMO</div>
        <nav className="side-nav" aria-label="Main navigation">
          {([
            ['guide', BookOpen, 'Start here', 'GUIDE'],
            ['investigations', FileSearch, 'Investigations', 'GEMINI'],
            ['bank', CreditCard, 'Demo bank', 'TRY IT'],
            ['lab', FlaskConical, 'Rule lab', 'TEST'],
          ] as const).map(([target, Icon, label, tag]) => (
            <button key={target} className={`nav-item ${view === target ? 'active' : ''}`} onClick={() => navigate(target)} aria-current={view === target ? 'page' : undefined}><Icon size={17} /><span>{label}</span><span className="nav-soon">{tag}</span></button>
          ))}
        </nav>
        <div className="nav-label nav-label-lower">ADVANCED</div>
        <nav className="side-nav" aria-label="Advanced navigation">
          <button className={`nav-item ${view === 'monitor' ? 'active' : ''}`} onClick={() => navigate('monitor')} aria-current={view === 'monitor' ? 'page' : undefined}><Activity size={17} /><span>Transaction monitor</span><span className="nav-soon">SHADOW</span></button>
          <button className={`nav-item ${view === 'engine' ? 'active' : ''}`} onClick={() => navigate('engine')} aria-current={view === 'engine' ? 'page' : undefined}><LayoutDashboard size={17} /><span>Rule engine</span><span className="nav-soon">BASELINE</span></button>
        </nav>
        <div className="platform-note"><ShieldCheck size={15} /><span>Gemini proposes · engine measures<br />Humans decide · nothing auto-activates</span></div>
        <div className="sidebar-bottom"><div className="profile-button"><div className="profile-avatar">RP</div><span className="profile-copy"><strong>RulePilot AI</strong><small>Continuous rule intelligence</small></span><Check size={15} /></div></div>
      </aside>
      {menuOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}

      <main className="main-content" id="overview">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMenuOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
          <div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>{VIEW_TITLE[view]}</strong></div>
          <div className="top-actions">
            <span className={`api-status api-${healthState}`} role="status" aria-live="polite"><span className="status-dot" />{healthState === 'checking' ? 'Checking API' : healthState === 'online' ? 'API connected' : 'API unavailable'}</span>
            <span className="top-divider" /><div className="mini-avatar" aria-label="RulePilot workspace">RP</div>
          </div>
        </header>

        <div className="page-container">
          {view === 'guide' && <GuideView onNavigate={navigate} />}
          {view === 'investigations' && <InvestigationView />}
          {view === 'bank' && <BankView />}
          {view === 'lab' && <LabView />}
          {view === 'monitor' && <MonitorView />}
          {view === 'engine' && <RuleEngineView />}
          <footer className="page-footer"><span>RULEPILOT AI <i>·</i> CONTINUOUS FINANCIAL RULE INTELLIGENCE</span><span>Synthetic data only <i>·</i> Not a production fraud system</span></footer>
        </div>
      </main>
    </div>
  )
}

export default App
