import { useEffect, useMemo, useState } from 'react'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || window.location.origin
const GRAFANA_BASE_URL = import.meta.env.VITE_GRAFANA_BASE_URL || 'http://localhost:3000'

const RUN_FILTER_DEFAULTS = {
  limit: '15',
  pcb_id: '',
  status: '',
  model_version: '',
  defect_type: '',
}

const DETAIL_FILTER_DEFAULTS = {
  component_id: '',
  defect_type: '',
  severity: '',
  inspection_result: '',
}

function buildQuery(filters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined) {
      params.set(key, value)
    }
  })
  const query = params.toString()
  return query ? `?${query}` : ''
}

async function fetchJson(url, signal) {
  const response = await fetch(url, { signal })
  const payload = await response.json()
  if (!response.ok || payload.status === 'error') {
    throw new Error(payload.message || 'Request failed')
  }
  return payload
}

function formatTimestamp(timestamp) {
  if (!timestamp) {
    return '-'
  }
  return new Date(timestamp).toLocaleString()
}

function StatCard({ label, value, tone = 'neutral' }) {
  return (
    <article className={`stat-card tone-${tone}`}>
      <span className="eyebrow">{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

function FilterField({ label, value, onChange, type = 'text', options }) {
  return (
    <label className="field">
      <span>{label}</span>
      {options ? (
        <select value={value} onChange={(event) => onChange(event.target.value)}>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          type={type}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </label>
  )
}

function StatusChip({ value, kind = 'status' }) {
  return <span className={`chip ${kind} ${String(value).toLowerCase()}`}>{value}</span>
}

function RunCard({ run, active, onSelect }) {
  return (
    <button
      type="button"
      className={`run-card${active ? ' active' : ''}`}
      onClick={() => onSelect(run.id)}
    >
      <div className="run-card-top">
        <div>
          <strong>{run.pcb_id}</strong>
          <div className="muted">{formatTimestamp(run.timestamp)}</div>
        </div>
        <StatusChip value={run.status} />
      </div>
      <div className="run-card-bottom">
        <span>{run.event_count} events</span>
        <span>{run.model_version || 'no model version'}</span>
        <span>{run.id.slice(0, 8)}</span>
      </div>
    </button>
  )
}

function DetailTable({ rows }) {
  if (!rows.length) {
    return <div className="empty-state">No defect records matched the current filters.</div>
  }

  return (
    <div className="table-shell">
      <table>
        <thead>
          <tr>
            <th>Component</th>
            <th>Defect</th>
            <th>Severity</th>
            <th>Result</th>
            <th>Confidence</th>
            <th>Latency</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.component_id}</td>
              <td>{row.defect_type}</td>
              <td>
                <StatusChip value={row.severity} kind="severity" />
              </td>
              <td>
                <StatusChip value={row.inspection_result} />
              </td>
              <td>{row.confidence_score}</td>
              <td>{row.inference_latency_ms} ms</td>
              <td>{formatTimestamp(row.timestamp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function App() {
  const [runFilters, setRunFilters] = useState(RUN_FILTER_DEFAULTS)
  const [detailFilters, setDetailFilters] = useState(DETAIL_FILTER_DEFAULTS)
  const [runs, setRuns] = useState([])
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [selectedRun, setSelectedRun] = useState(null)
  const [runsLoading, setRunsLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()

    async function loadRuns() {
      setRunsLoading(true)
      setError('')
      try {
        const payload = await fetchJson(`/runs${buildQuery(runFilters)}`, controller.signal)
        setRuns(payload.runs)
        if (!payload.runs.length) {
          setSelectedRun(null)
        }
        setSelectedRunId((currentId) => {
          if (currentId && payload.runs.some((run) => run.id === currentId)) {
            return currentId
          }
          return payload.runs[0]?.id ?? null
        })
      } catch (loadError) {
        if (loadError.name === 'AbortError') {
          return
        }
        setError(loadError.message)
        setRuns([])
        setSelectedRunId(null)
      } finally {
        setRunsLoading(false)
      }
    }

    loadRuns()
    const timer = window.setInterval(loadRuns, 10000)
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [runFilters])

  useEffect(() => {
    if (!selectedRunId) {
      return
    }

    const controller = new AbortController()

    async function loadRunDetail() {
      setDetailLoading(true)
      setError('')
      try {
        const payload = await fetchJson(
          `/runs/${selectedRunId}${buildQuery(detailFilters)}`,
          controller.signal,
        )
        setSelectedRun(payload.run)
      } catch (loadError) {
        if (loadError.name === 'AbortError') {
          return
        }
        setError(loadError.message)
        setSelectedRun(null)
      } finally {
        setDetailLoading(false)
      }
    }

    loadRunDetail()
    return () => controller.abort()
  }, [selectedRunId, detailFilters])

  const summary = useMemo(() => {
    const failRuns = runs.filter((run) => run.status === 'FAIL').length
    const passRuns = runs.filter((run) => run.status === 'PASS').length
    const totalEvents = runs.reduce((sum, run) => sum + Number(run.event_count || 0), 0)
    return {
      recentRuns: runs.length,
      failRuns,
      passRuns,
      totalEvents,
    }
  }, [runs])

  return (
    <div className="app-shell">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">AOI Monitoring Console</p>
          <h1>Production inspection, minus the curl commands.</h1>
          <p className="hero-text">
            This frontend sits on top of the AOI ingestion API and SQLite store. It is
            focused on operator flow: find runs quickly, inspect failures, and jump to
            Grafana only when you need the raw stream.
          </p>
        </div>
        <aside className="hero-card">
          <span className="eyebrow">Live Tools</span>
          <a href={`${API_BASE_URL}/health`} target="_blank" rel="noreferrer">
            API health
          </a>
          <a
            href={`${GRAFANA_BASE_URL}/d/aoi-overview/aoi-overview`}
            target="_blank"
            rel="noreferrer"
          >
            Grafana overview
          </a>
        </aside>
      </header>

      <section className="stats-grid">
        <StatCard label="Recent runs" value={summary.recentRuns} />
        <StatCard label="Fail runs" value={summary.failRuns} tone="fail" />
        <StatCard label="Pass runs" value={summary.passRuns} tone="pass" />
        <StatCard label="Events loaded" value={summary.totalEvents} />
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <main className="workspace">
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Runs</p>
              <h2>Inspection history</h2>
            </div>
            <button
              type="button"
              className="ghost-button"
              onClick={() => setRunFilters(RUN_FILTER_DEFAULTS)}
            >
              Reset filters
            </button>
          </div>
          <div className="panel-body">
            <div className="filter-grid">
              <FilterField
                label="Limit"
                type="number"
                value={runFilters.limit}
                onChange={(value) => setRunFilters((current) => ({ ...current, limit: value }))}
              />
              <FilterField
                label="PCB ID"
                value={runFilters.pcb_id}
                onChange={(value) => setRunFilters((current) => ({ ...current, pcb_id: value }))}
              />
              <FilterField
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
                label="Model version"
                value={runFilters.model_version}
                onChange={(value) =>
                  setRunFilters((current) => ({ ...current, model_version: value }))
                }
              />
              <FilterField
                label="Defect type"
                value={runFilters.defect_type}
                onChange={(value) =>
                  setRunFilters((current) => ({ ...current, defect_type: value }))
                }
              />
            </div>

            <div className="section-note">Auto-refreshes every 10 seconds.</div>

            <div className="run-list">
              {runsLoading ? (
                <div className="empty-state">Loading runs…</div>
              ) : runs.length ? (
                runs.map((run) => (
                  <RunCard
                    key={run.id}
                    run={run}
                    active={run.id === selectedRunId}
                    onSelect={setSelectedRunId}
                  />
                ))
              ) : (
                <div className="empty-state">No runs matched the current filters.</div>
              )}
            </div>
          </div>
        </section>

        <section className="panel detail-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Detail</p>
              <h2>Run inspection detail</h2>
            </div>
            {selectedRun ? <StatusChip value={selectedRun.status} /> : null}
          </div>
          <div className="panel-body">
            {!selectedRunId ? (
              <div className="empty-state">Select a run to inspect its defect records.</div>
            ) : detailLoading ? (
              <div className="empty-state">Loading run detail…</div>
            ) : selectedRun ? (
              <>
                <div className="detail-grid">
                  <div className="detail-card">
                    <span className="eyebrow">Run ID</span>
                    <strong>{selectedRun.id}</strong>
                  </div>
                  <div className="detail-card">
                    <span className="eyebrow">Board</span>
                    <strong>{selectedRun.pcb_id}</strong>
                  </div>
                  <div className="detail-card">
                    <span className="eyebrow">Timestamp</span>
                    <strong>{formatTimestamp(selectedRun.timestamp)}</strong>
                  </div>
                  <div className="detail-card">
                    <span className="eyebrow">Model</span>
                    <strong>{selectedRun.model_version || 'None'}</strong>
                  </div>
                </div>

                <div className="subfilter-grid">
                  <FilterField
                    label="Component"
                    value={detailFilters.component_id}
                    onChange={(value) =>
                      setDetailFilters((current) => ({ ...current, component_id: value }))
                    }
                  />
                  <FilterField
                    label="Defect"
                    value={detailFilters.defect_type}
                    onChange={(value) =>
                      setDetailFilters((current) => ({ ...current, defect_type: value }))
                    }
                  />
                  <FilterField
                    label="Severity"
                    value={detailFilters.severity}
                    onChange={(value) =>
                      setDetailFilters((current) => ({ ...current, severity: value }))
                    }
                    options={[
                      { label: 'All', value: '' },
                      { label: 'none', value: 'none' },
                      { label: 'minor', value: 'minor' },
                      { label: 'major', value: 'major' },
                      { label: 'critical', value: 'critical' },
                    ]}
                  />
                  <FilterField
                    label="Result"
                    value={detailFilters.inspection_result}
                    onChange={(value) =>
                      setDetailFilters((current) => ({ ...current, inspection_result: value }))
                    }
                    options={[
                      { label: 'All', value: '' },
                      { label: 'PASS', value: 'PASS' },
                      { label: 'FAIL', value: 'FAIL' },
                    ]}
                  />
                </div>

                <div className="detail-toolbar">
                  <span className="section-note">
                    {selectedRun.event_count} visible defect records
                  </span>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => setDetailFilters(DETAIL_FILTER_DEFAULTS)}
                  >
                    Reset detail filters
                  </button>
                </div>

                <DetailTable rows={selectedRun.defect_logs || []} />
              </>
            ) : (
              <div className="empty-state">The selected run could not be loaded.</div>
            )}
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
