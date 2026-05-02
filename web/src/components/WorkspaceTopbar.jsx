import { API_BASE_URL, GRAFANA_BASE_URL } from '../app/constants'

export default function WorkspaceTopbar({
  summary,
  isRunRailOpen,
  isSidebarOpen,
  isFiltersOpen,
  isSettingsOpen,
  isZenMode,
  onToggleRunRail,
  onToggleSidebar,
  onToggleFilters,
  onToggleSettings,
  onToggleZenMode,
}) {
  return (
    <header className="workspace-topbar">
      <div className="workspace-title-group">
        <div className="workspace-title">
          <span className="eyebrow">AOI Review Workstation</span>
          <h1>PCB defect review</h1>
        </div>
      </div>
      <div className="workspace-meta">
        <div className="meta-pill">Runs {summary.runs}</div>
        <div className="meta-pill fail">Fail runs {summary.failRuns}</div>
        <div className="meta-pill">Events {summary.events}</div>
        <a className="meta-link" href={`${API_BASE_URL}/health`} target="_blank" rel="noreferrer">
          API
        </a>
        <a
          className="meta-link"
          href={`${GRAFANA_BASE_URL}/d/aoi-overview/aoi-overview`}
          target="_blank"
          rel="noreferrer"
        >
          Grafana
        </a>
        <div className="topbar-divider"></div>
        <button
          type="button"
          className={`dock-button ${isZenMode ? 'active' : ''}`}
          onClick={onToggleZenMode}
          title="Toggle Zen Mode (P/F Keys)"
          style={isZenMode ? { borderColor: 'var(--warn)', color: 'var(--warn)', background: 'rgba(219, 171, 9, 0.15)' } : {}}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"></path></svg>
        </button>
        <button
          type="button"
          className={`dock-button ${isRunRailOpen ? 'active' : ''}`}
          onClick={onToggleRunRail}
          title="Toggle Run History"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="10" x2="21" y2="10"></line><line x1="9" y1="22" x2="9" y2="10"></line></svg>
        </button>
        <button
          type="button"
          className={`dock-button ${isSidebarOpen ? 'active' : ''}`}
          onClick={onToggleSidebar}
          title="Toggle Defect List"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
        </button>
        <button
          type="button"
          className={`dock-button ${isFiltersOpen ? 'active' : ''}`}
          onClick={onToggleFilters}
          title="Toggle Defect Filters"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>
        </button>
        <button
          type="button"
          className={`dock-button ${isSettingsOpen ? 'active' : ''}`}
          onClick={onToggleSettings}
          title="System Settings"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
        </button>
      </div>
    </header>
  )
}
