import { useEffect, useState } from 'react'
import { Activity, Check, FileSearch, GitBranch, LayoutDashboard, Menu, ShieldCheck, X } from 'lucide-react'
import { apiRequest, type ApiHealth } from './api'
import InvestigationView from './InvestigationView'
import MonitorView from './MonitorView'
import RuleEngineView from './RuleEngineView'

type View = 'investigations' | 'monitor' | 'engine'

const VIEW_TITLE: Record<View, string> = { investigations: 'Intelligence investigations', monitor: 'Transaction monitor', engine: 'Rule engine' }
type HealthState = 'checking' | 'online' | 'offline'

function viewFromHash(): View {
  if (window.location.hash === '#engine') return 'engine'
  if (window.location.hash === '#monitor') return 'monitor'
  return 'investigations'
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
        <a className="brand" href="#investigations" onClick={() => navigate('investigations')} aria-label="RulePilot AI investigations">
          <span className="brand-mark"><GitBranch size={19} strokeWidth={2.5} /></span>
          <span className="brand-name">rulepilot<span>ai</span></span>
        </a>
        <button className="mobile-close" onClick={() => setMenuOpen(false)} aria-label="Close navigation"><X size={18} /></button>
        <div className="workspace-picker"><div className="workspace-avatar">R</div><div className="workspace-copy"><strong>RulePilot Workspace</strong><span>Payment-card fraud · synthetic data</span></div><span className="workspace-chip">DEMO</span></div>
        <div className="nav-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          <button className={`nav-item ${view === 'investigations' ? 'active' : ''}`} onClick={() => navigate('investigations')} aria-current={view === 'investigations' ? 'page' : undefined}><FileSearch size={17} /><span>Investigations</span><span className="nav-soon">AGENT</span></button>
          <button className={`nav-item ${view === 'monitor' ? 'active' : ''}`} onClick={() => navigate('monitor')} aria-current={view === 'monitor' ? 'page' : undefined}><Activity size={17} /><span>Transaction monitor</span><span className="nav-soon">SHADOW</span></button>
          <button className={`nav-item ${view === 'engine' ? 'active' : ''}`} onClick={() => navigate('engine')} aria-current={view === 'engine' ? 'page' : undefined}><LayoutDashboard size={17} /><span>Rule engine</span><span className="nav-soon">BASELINE</span></button>
        </nav>
        <div className="nav-label nav-label-lower">PLATFORM</div>
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
          {view === 'engine' ? <RuleEngineView /> : view === 'monitor' ? <MonitorView /> : <InvestigationView />}
          <footer className="page-footer"><span>RULEPILOT AI <i>·</i> CONTINUOUS FINANCIAL RULE INTELLIGENCE</span><span>Synthetic data only <i>·</i> Not a production fraud system</span></footer>
        </div>
      </main>
    </div>
  )
}

export default App
