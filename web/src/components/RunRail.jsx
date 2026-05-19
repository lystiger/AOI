import { DETAIL_FILTER_DEFAULTS, RUN_FILTER_DEFAULTS } from '../app/constants'
import { EmptyStateMessage, FilterField, RunCard } from './shared'

export default function RunRail({ workspace }) {
  const {
    runsLoading,
    runs,
    pendingRuns,
    reviewRuns,
    runFilters,
    setRunFilters,
    selectedRunId,
    setSelectedRunId,
    handleCreateRun,
    isCreatingRun,
  } = workspace

  return (
    <aside className="panel run-rail">
      <div className="rail-section rail-header">
        <div className="rail-heading">
          <div className="rail-heading-top">
            <p className="eyebrow">Run browser</p>
            <button
              type="button"
              className="rail-help-button"
              title="Browse runs, select active history, and filter the queue."
              aria-label="About run browser"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3" />
                <path d="M12 17h.01" />
                <path d="M10 21.2a9 9 0 1 1 4 0l-4 1.3z" />
              </svg>
            </button>
          </div>
          <h2>History</h2>
        </div>
      </div>
      <div className="rail-section rail-filters">
        <div className="rail-filter-header">
          <div className="rail-filter-heading">
            <p className="eyebrow">Filters</p>
            <span className="section-note">Live query controls</span>
          </div>
          <button
            type="button"
            className="ghost-button rail-filter-reset"
            onClick={() => setRunFilters(RUN_FILTER_DEFAULTS)}
          >
            Reset
          </button>
        </div>
        <button
          type="button"
          className="ghost-button rail-action-button rail-action-button-primary rail-create-button"
          onClick={handleCreateRun}
          disabled={isCreatingRun}
        >
          {isCreatingRun ? 'Creating...' : 'New Run'}
        </button>
        <FilterField
          compact
          label="Limit"
          type="number"
          value={runFilters.limit}
          onChange={(value) => setRunFilters((current) => ({ ...current, limit: value }))}
        />
        <FilterField
          compact
          label="PCB"
          value={runFilters.pcb_id}
          onChange={(value) => setRunFilters((current) => ({ ...current, pcb_id: value }))}
        />
        <FilterField
          compact
          label="Status"
          value={runFilters.status}
          onChange={(value) => setRunFilters((current) => ({ ...current, status: value }))}
          options={[
            { label: 'All', value: '' },
            { label: 'PASS', value: 'PASS' },
            { label: 'FAIL', value: 'FAIL' },
          ]}
        />
        <FilterField
          compact
          label="Model"
          value={runFilters.model_version}
          onChange={(value) => setRunFilters((current) => ({ ...current, model_version: value }))}
        />
        <FilterField
          compact
          label="Defect"
          value={runFilters.defect_type}
          onChange={(value) => setRunFilters((current) => ({ ...current, defect_type: value }))}
        />
      </div>
      <div className="rail-section rail-list">
        {runsLoading ? (
          <div className="empty-state rail-loading-state">Loading runs…</div>
        ) : runs.length ? (
          <>
            {pendingRuns.length ? (
              <div className="rail-group">
                <div className="rail-group-header">
                  <p className="eyebrow">Pending Setup</p>
                  <span className="section-note">{pendingRuns.length}</span>
                </div>
                {pendingRuns.map((run) => (
                  <RunCard key={run.id} run={run} active={run.id === selectedRunId} onSelect={setSelectedRunId} />
                ))}
              </div>
            ) : null}
            {reviewRuns.length ? (
              <div className="rail-group">
                <div className="rail-group-header">
                  <p className="eyebrow">Review History</p>
                  <span className="section-note">{reviewRuns.length}</span>
                </div>
                {reviewRuns.map((run) => (
                  <RunCard key={run.id} run={run} active={run.id === selectedRunId} onSelect={setSelectedRunId} />
                ))}
              </div>
            ) : null}
          </>
        ) : (
          <EmptyStateMessage
            title="No runs available"
            body="Runs appear here after inspection events are ingested. Until a run exists, there is nothing to select for PCB scan upload."
          />
        )}
      </div>
    </aside>
  )
}
