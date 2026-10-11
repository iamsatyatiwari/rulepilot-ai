import { useEffect, useState } from 'react'
import {
  Activity, ArrowRight, Bell, ChevronDown,
  CircleHelp, Command, FileCheck2, GitBranch, Layers3, LayoutDashboard,
  LifeBuoy, Menu, Search, Settings2, ShieldCheck, Sparkles, X,
} from 'lucide-react'

type ApiState = 'checking' | 'online' | 'offline'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

function App() {
  const [apiState, setApiState] = useState<ApiState>('checking')
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 5000)
    fetch(`${apiBaseUrl}/health`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('API health check failed')
        return response.json()
      })
      .then((data: { status?: string }) => setApiState(data.status === 'ok' ? 'online' : 'offline'))
      .catch(() => setApiState('offline'))
      .finally(() => window.clearTimeout(timeout))
    return () => {
      controller.abort()
      window.clearTimeout(timeout)
    }
  }, [])

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
        <a className="brand" href="#overview" aria-label="RulePilot AI home">
          <span className="brand-mark"><GitBranch size={19} strokeWidth={2.5} /></span>
          <span className="brand-name">rulepilot<span>ai</span></span>
          <button className="mobile-close" onClick={() => setMenuOpen(false)} aria-label="Close menu"><X size={19} /></button>
        </a>
        <div className="workspace-picker">
          <div className="workspace-avatar">R</div>
          <div className="workspace-copy"><strong>RulePilot Workspace</strong><span>Workspace</span></div>
          <ChevronDown size={15} className="muted-icon" />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          <a className="nav-item active" href="#overview"><LayoutDashboard size={17} /><span>Overview</span></a>
          <a className="nav-item disabled" href="#rule-coverage" aria-disabled="true"><Layers3 size={17} /><span>Rule coverage</span><span className="nav-soon">Soon</span></a>
          <a className="nav-item disabled" href="#backtests" aria-disabled="true"><Activity size={17} /><span>Backtests</span><span className="nav-soon">Soon</span></a>
          <a className="nav-item disabled" href="#review-queue" aria-disabled="true"><FileCheck2 size={17} /><span>Review queue</span><span className="nav-soon">Soon</span></a>
        </nav>
        <div className="nav-label nav-label-lower">PREFERENCES</div>
        <nav className="side-nav" aria-label="Preferences">
          <a className="nav-item disabled" href="#settings" aria-disabled="true"><Settings2 size={17} /><span>Settings</span></a>
          <a className="nav-item disabled" href="#help" aria-disabled="true"><LifeBuoy size={17} /><span>Help &amp; support</span></a>
        </nav>
        <div className="sidebar-bottom">
          <div className="secure-note"><ShieldCheck size={16} /><span>Your data stays yours</span></div>
          <button className="profile-button"><div className="profile-avatar">RP</div><span className="profile-copy"><strong>Workspace admin</strong><small>Administrator</small></span><ChevronDown size={15} /></button>
        </div>
      </aside>
      {menuOpen && <button className="mobile-scrim" aria-label="Close menu" onClick={() => setMenuOpen(false)} />}

      <main className="main-content" id="overview">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMenuOpen(true)} aria-label="Open menu"><Menu size={20} /></button>
          <div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>Overview</strong></div>
          <div className="top-actions"><button className="icon-button search-button" aria-label="Search"><Search size={17} /><span>Search</span><kbd>⌘ K</kbd></button><button className="icon-button help-button" aria-label="Help"><CircleHelp size={18} /></button><button className="icon-button notification-button" aria-label="Notifications"><Bell size={18} /><i /></button><span className="top-divider" /><div className="mini-avatar">RP</div></div>
        </header>

        <div className="page-container">
          <section className="welcome-row">
            <div><div className="eyebrow"><span className="eyebrow-dot" /> RULE INTELLIGENCE</div><h1>Welcome to RulePilot AI <span className="wave">✳</span></h1><p className="welcome-subtitle">A clear view of your financial rule intelligence workspace.</p></div>
            <div className={`api-status api-${apiState}`} role="status" aria-live="polite"><span className="status-dot" />{apiState === 'checking' ? 'Checking API…' : apiState === 'online' ? 'API connected' : 'API unavailable'}<span className="status-divider" /><span className="api-label">Backend</span></div>
          </section>

          <section className="hero-card">
            <div className="hero-copy"><div className="hero-pill"><Sparkles size={13} /> MILESTONE 1 <span>·</span> FOUNDATION</div><h2>Stay ahead of<br />what your rules miss.</h2><p>RulePilot AI is being built to help financial teams find coverage gaps, explore candidate rules, and review evidence with confidence.</p><a className="hero-link" href="#roadmap">Explore the roadmap <ArrowRight size={16} /></a></div>
            <div className="hero-visual" aria-hidden="true"><div className="visual-orbit orbit-one" /><div className="visual-orbit orbit-two" /><div className="visual-orbit orbit-three" /><div className="visual-core"><Command size={30} strokeWidth={1.5} /></div><div className="visual-node node-a"><ShieldCheck size={16} /></div><div className="visual-node node-b"><GitBranch size={15} /></div><div className="visual-node node-c"><Activity size={15} /></div><div className="visual-spark spark-a">✳</div><div className="visual-spark spark-b">·</div></div>
            <div className="hero-footnote"><span className="hero-foot-dot" /> BUILDING THE FOUNDATION <span className="hero-foot-line" /> 01 / 04</div>
          </section>

          <section className="metric-grid" aria-label="Workspace status">
            <article className="metric-card"><div className="metric-top"><span className="metric-icon icon-green"><Layers3 size={16} /></span><span className="metric-label">Rules monitored</span><span className="metric-badge badge-neutral">—</span></div><div className="metric-value">—</div><div className="metric-foot">Connect a data source to get started</div></article>
            <article className="metric-card"><div className="metric-top"><span className="metric-icon icon-amber"><Activity size={16} /></span><span className="metric-label">Coverage gaps</span><span className="metric-badge badge-neutral">—</span></div><div className="metric-value">—</div><div className="metric-foot">No analysis has been run yet</div></article>
            <article className="metric-card"><div className="metric-top"><span className="metric-icon icon-blue"><FileCheck2 size={16} /></span><span className="metric-label">Pending review</span><span className="metric-badge badge-neutral">—</span></div><div className="metric-value">—</div><div className="metric-foot">Review queue is not available yet</div></article>
            <article className="metric-card"><div className="metric-top"><span className="metric-icon icon-violet"><GitBranch size={16} /></span><span className="metric-label">Backtests run</span><span className="metric-badge badge-neutral">—</span></div><div className="metric-value">—</div><div className="metric-foot">Backtesting is coming in a later milestone</div></article>
          </section>

          <section className="lower-grid" id="roadmap">
            <article className="panel roadmap-panel"><div className="panel-heading"><div><h3>Product roadmap</h3><p>Building toward continuous rule intelligence</p></div><span className="roadmap-count">01 <span>/ 04</span></span></div><div className="roadmap-list">
              <div className="roadmap-item complete"><div className="roadmap-marker"><span>✓</span></div><div className="roadmap-text"><strong>Workspace foundation</strong><span>Project shell, API, and connectivity</span></div><span className="roadmap-state state-done">IN PROGRESS</span></div>
              <div className="roadmap-item"><div className="roadmap-marker">02</div><div className="roadmap-text"><strong>Bring in transaction data</strong><span>Secure data onboarding and schema mapping</span></div><span className="roadmap-state">UP NEXT</span></div>
              <div className="roadmap-item"><div className="roadmap-marker">03</div><div className="roadmap-text"><strong>Discover coverage gaps</strong><span>Surface areas existing rules may miss</span></div></div>
              <div className="roadmap-item"><div className="roadmap-marker">04</div><div className="roadmap-text"><strong>Test, review, improve</strong><span>Backtest candidates with human oversight</span></div></div>
            </div></article>
            <article className="panel activity-panel"><div className="panel-heading"><div><h3>Workspace activity</h3><p>Recent changes and events</p></div><button className="panel-menu" aria-label="More activity options">···</button></div><div className="empty-activity"><div className="empty-icon"><Activity size={21} /></div><strong>Nothing to report yet</strong><p>Workspace events will appear here as you connect data and start exploring.</p><span className="empty-foot"><span className="live-dot" /> LIVE FEED <span>·</span> READY WHEN YOU ARE</span></div></article>
          </section>
          <footer className="page-footer"><span>RULEPILOT AI <span className="footer-dot">·</span> CONTINUOUS FINANCIAL RULE INTELLIGENCE</span><span>Milestone 1 <span className="footer-dot">·</span> Foundation</span></footer>
        </div>
      </main>
    </div>
  )
}

export default App
