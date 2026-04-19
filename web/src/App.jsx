import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || window.location.origin
const GRAFANA_BASE_URL = import.meta.env.VITE_GRAFANA_BASE_URL || 'http://localhost:3000'
const DEFAULT_IMAGE_ID = 'demo-full-board'

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

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

function FilterField({ label, value, onChange, type = 'text', options, compact = false }) {
  return (
    <label className={`field${compact ? ' compact' : ''}`}>
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
        <strong>{run.pcb_id}</strong>
        <StatusChip value={run.status} />
      </div>
      <div className="run-card-bottom">
        <span>{formatTimestamp(run.timestamp)}</span>
        <span>{run.event_count} events</span>
      </div>
    </button>
  )
}

function DefectListItem({ defect, active, hovered, onSelect, onHover }) {
  return (
    <button
      type="button"
      className={`defect-list-item${active ? ' active' : ''}${hovered ? ' hovered' : ''}`}
      onClick={() => onSelect(defect.id)}
      onMouseEnter={() => onHover(defect.id)}
      onMouseLeave={() => onHover(null)}
    >
      <div className="defect-list-top">
        <strong>{defect.component_id}</strong>
        <StatusChip value={defect.severity} kind="severity" />
      </div>
      <div className="defect-list-meta">
        <span>{defect.defect_type}</span>
        <StatusChip value={defect.inspection_result} />
        <span>{Number(defect.confidence_score ?? 0).toFixed(2)}</span>
      </div>
    </button>
  )
}

function PcbViewer({ image, run, defects, selectedDefect, hoveredDefectId, onHover, onSelectDefect }) {
  const [viewerScale, setViewerScale] = useState(1)
  const [viewerOffset, setViewerOffset] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const dragRef = useRef({ startX: 0, startY: 0, offsetX: 0, offsetY: 0 })
  const viewerRef = useRef(null)

  function setScale(nextScale) {
    setViewerScale(clamp(nextScale, 1, 5))
  }

  function resetViewer() {
    setViewerScale(1)
    setViewerOffset({ x: 0, y: 0 })
  }

  function focusDefect(defectId) {
    const defect = defects.find((entry) => entry.id === defectId)
    if (!defect || !viewerRef.current) {
      return
    }

    onSelectDefect(defect.id)
    const nextScale = 2
    const bounds = viewerRef.current.getBoundingClientRect()
    const centerX = (defect.overlay_x + defect.overlay_width / 2) * bounds.width
    const centerY = (defect.overlay_y + defect.overlay_height / 2) * bounds.height

    setViewerScale(nextScale)
    setViewerOffset({
      x: bounds.width / 2 - centerX * nextScale,
      y: bounds.height / 2 - centerY * nextScale,
    })
  }

  function startDrag(event) {
    if (viewerScale <= 1) {
      return
    }
    setIsDragging(true)
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      offsetX: viewerOffset.x,
      offsetY: viewerOffset.y,
    }
  }

  function moveDrag(event) {
    if (!isDragging) {
      return
    }
    setViewerOffset({
      x: dragRef.current.offsetX + (event.clientX - dragRef.current.startX),
      y: dragRef.current.offsetY + (event.clientY - dragRef.current.startY),
    })
  }

  function stopDrag() {
    setIsDragging(false)
  }

  function handleWheel(event) {
    event.preventDefault()
    setScale(viewerScale + (event.deltaY < 0 ? 0.16 : -0.16))
  }

  return (
    <section className="viewer-panel">
      <div className="viewer-toolbar">
        <div className="viewer-toolbar-group">
          <button type="button" className="ghost-button" onClick={resetViewer}>
            Fit board
          </button>
          <button
            type="button"
            className="ghost-button"
            onClick={() => selectedDefect && focusDefect(selectedDefect.id)}
            disabled={!selectedDefect}
          >
            Fit defect
          </button>
        </div>
        <div className="viewer-toolbar-group">
          <button type="button" className="ghost-button" onClick={() => setScale(viewerScale - 0.2)}>
            Zoom -
          </button>
          <div className="zoom-readout">{Math.round(viewerScale * 100)}%</div>
          <button type="button" className="ghost-button" onClick={() => setScale(viewerScale + 0.2)}>
            Zoom +
          </button>
        </div>
      </div>

      <div
        ref={viewerRef}
        className={`viewer-surface${isDragging ? ' dragging' : ''}`}
        onMouseDown={startDrag}
        onMouseMove={moveDrag}
        onMouseUp={stopDrag}
        onMouseLeave={stopDrag}
        onWheel={handleWheel}
      >
        {image ? (
          <div
            className="viewer-stage"
            style={{ transform: `translate(${viewerOffset.x}px, ${viewerOffset.y}px) scale(${viewerScale})` }}
          >
            <img className="viewer-image" src={image.image_path} alt={`${run.pcb_id} inspection board`} />
            {defects.map((defect) => {
              const overlayState =
                defect.id === selectedDefect?.id
                  ? 'selected'
                  : defect.id === hoveredDefectId
                    ? 'hovered'
                    : defect.inspection_result === 'FAIL'
                      ? 'fail'
                      : 'pass'

              return (
                <button
                  key={defect.id}
                  type="button"
                  className={`overlay-box overlay-${overlayState}`}
                  style={{
                    left: `${defect.overlay_x * 100}%`,
                    top: `${defect.overlay_y * 100}%`,
                    width: `${defect.overlay_width * 100}%`,
                    height: `${defect.overlay_height * 100}%`,
                  }}
                  onClick={(event) => {
                    event.stopPropagation()
                    onSelectDefect(defect.id)
                  }}
                  onDoubleClick={(event) => {
                    event.stopPropagation()
                    focusDefect(defect.id)
                  }}
                  onMouseEnter={() => onHover(defect.id)}
                  onMouseLeave={() => onHover(null)}
                >
                  <span>{defect.component_id}</span>
                </button>
              )
            })}
          </div>
        ) : (
          <div className="empty-state">No scan image available for this run.</div>
        )}
      </div>
    </section>
  )
}

function App() {
  const [runFilters, setRunFilters] = useState(RUN_FILTER_DEFAULTS)
  const [detailFilters, setDetailFilters] = useState(DETAIL_FILTER_DEFAULTS)
  const [runs, setRuns] = useState([])
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [selectedRun, setSelectedRun] = useState(null)
  const [selectedImageId, setSelectedImageId] = useState(DEFAULT_IMAGE_ID)
  const [selectedDefectId, setSelectedDefectId] = useState(null)
  const [hoveredDefectId, setHoveredDefectId] = useState(null)
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
    return {
      runs: runs.length,
      failRuns,
      events: runs.reduce((sum, run) => sum + Number(run.event_count || 0), 0),
    }
  }, [runs])

  const runImages = useMemo(() => {
    if (!selectedRun || !Array.isArray(selectedRun.images)) {
      return []
    }
    return selectedRun.images
  }, [selectedRun])

  const defects = useMemo(() => {
    if (!selectedRun?.defect_logs) {
      return []
    }
    return selectedRun.defect_logs.filter(
      (defect) =>
        defect.run_image_id &&
        defect.overlay_x !== null &&
        defect.overlay_y !== null &&
        defect.overlay_width !== null &&
        defect.overlay_height !== null,
    )
  }, [selectedRun])

  const effectiveSelectedImageId =
    runImages.find((image) => image.id === selectedImageId)?.id || runImages[0]?.id || DEFAULT_IMAGE_ID

  const visibleDefects = useMemo(
    () => defects.filter((defect) => defect.run_image_id === effectiveSelectedImageId),
    [defects, effectiveSelectedImageId],
  )

  const effectiveSelectedDefectId =
    visibleDefects.find((defect) => defect.id === selectedDefectId)?.id || visibleDefects[0]?.id || null

  const selectedImage =
    runImages.find((image) => image.id === effectiveSelectedImageId) || runImages[0] || null
  const selectedDefect =
    visibleDefects.find((defect) => defect.id === effectiveSelectedDefectId) || visibleDefects[0] || null

  function stepDefect(direction) {
    if (!visibleDefects.length) {
      return
    }
    const currentIndex = visibleDefects.findIndex((defect) => defect.id === effectiveSelectedDefectId)
    const safeIndex = currentIndex === -1 ? 0 : currentIndex
    const nextIndex = (safeIndex + direction + visibleDefects.length) % visibleDefects.length
    setSelectedDefectId(visibleDefects[nextIndex].id)
  }

  const failCount = defects.filter((defect) => defect.inspection_result === 'FAIL').length

  return (
    <div className="app-shell">
      <header className="workspace-topbar">
        <div className="workspace-title">
          <span className="eyebrow">AOI Review Workstation</span>
          <h1>PCB defect review</h1>
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
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <main className="workspace">
        <aside className="panel run-rail">
          <div className="rail-section rail-header">
            <div>
              <p className="eyebrow">Run browser</p>
              <h2>History</h2>
            </div>
            <button type="button" className="ghost-button" onClick={() => setRunFilters(RUN_FILTER_DEFAULTS)}>
              Reset
            </button>
          </div>
          <div className="rail-section rail-filters">
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
              <div className="empty-state">Loading runs…</div>
            ) : runs.length ? (
              runs.map((run) => (
                <RunCard key={run.id} run={run} active={run.id === selectedRunId} onSelect={setSelectedRunId} />
              ))
            ) : (
              <div className="empty-state">No runs matched the current filters.</div>
            )}
          </div>
        </aside>

        <section className="panel review-panel">
          <div className="review-topbar">
            <div className="review-runline">
              <div className="review-runline-main">
                <strong>{selectedRun?.pcb_id || 'No run selected'}</strong>
                {selectedRun ? <StatusChip value={selectedRun.status} /> : null}
                <span className="compact-meta">{selectedRun ? formatTimestamp(selectedRun.timestamp) : '-'}</span>
                <span className="compact-meta">{failCount} fail defects</span>
              </div>
              {selectedImage?.image_role === 'demo_full_board' ? (
                <div className="compact-note">Demo image active</div>
              ) : null}
            </div>
            <div className="review-controls">
              <select
                className="image-selector"
                value={effectiveSelectedImageId}
                onChange={(event) => setSelectedImageId(event.target.value)}
                disabled={!runImages.length}
              >
                {runImages.map((image) => (
                  <option key={image.id} value={image.id}>
                    {image.image_role?.replaceAll('_', ' ') || image.id}
                  </option>
                ))}
              </select>
              <button type="button" className="ghost-button" onClick={() => stepDefect(-1)}>
                Prev
              </button>
              <button type="button" className="ghost-button" onClick={() => stepDefect(1)}>
                Next
              </button>
            </div>
          </div>

          <div className="review-shell">
            <aside className="review-sidebar">
              <section className="review-card">
                <div className="review-card-header">
                  <p className="eyebrow">Defect filters</p>
                </div>
                <div className="sidebar-filters">
                  <FilterField
                    compact
                    label="Component"
                    value={detailFilters.component_id}
                    onChange={(value) => setDetailFilters((current) => ({ ...current, component_id: value }))}
                  />
                  <FilterField
                    compact
                    label="Type"
                    value={detailFilters.defect_type}
                    onChange={(value) => setDetailFilters((current) => ({ ...current, defect_type: value }))}
                  />
                  <FilterField
                    compact
                    label="Severity"
                    value={detailFilters.severity}
                    onChange={(value) => setDetailFilters((current) => ({ ...current, severity: value }))}
                    options={[
                      { label: 'All', value: '' },
                      { label: 'none', value: 'none' },
                      { label: 'minor', value: 'minor' },
                      { label: 'major', value: 'major' },
                      { label: 'critical', value: 'critical' },
                    ]}
                  />
                  <FilterField
                    compact
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
              </section>

              <section className="review-card defect-list-card">
                <div className="review-card-header">
                  <p className="eyebrow">Defects</p>
                  <span className="section-note">{visibleDefects.length}</span>
                </div>
                <div className="defect-list">
                  {!selectedRunId ? (
                    <div className="empty-state">Select a run to inspect defects.</div>
                  ) : detailLoading ? (
                    <div className="empty-state">Loading run detail…</div>
                  ) : visibleDefects.length ? (
                    visibleDefects.map((defect) => (
                      <DefectListItem
                        key={defect.id}
                        defect={defect}
                        active={defect.id === selectedDefect?.id}
                        hovered={defect.id === hoveredDefectId}
                        onSelect={setSelectedDefectId}
                        onHover={setHoveredDefectId}
                      />
                    ))
                  ) : (
                    <div className="empty-state">No defects matched the current filters.</div>
                  )}
                </div>
              </section>

              <section className="review-card inspector-card">
                <div className="review-card-header">
                  <p className="eyebrow">Inspector</p>
                </div>
                {selectedDefect ? (
                  <div className="inspector-grid">
                    <div><span className="eyebrow">Component</span><strong>{selectedDefect.component_id}</strong></div>
                    <div><span className="eyebrow">Type</span><strong>{selectedDefect.defect_type}</strong></div>
                    <div><span className="eyebrow">Severity</span><strong>{selectedDefect.severity}</strong></div>
                    <div><span className="eyebrow">Confidence</span><strong>{Number(selectedDefect.confidence_score ?? 0).toFixed(2)}</strong></div>
                  </div>
                ) : (
                  <div className="empty-state">Select a defect to inspect it.</div>
                )}
              </section>
            </aside>

            {!selectedRunId ? (
              <div className="viewer-empty"><div className="empty-state">Select a run to load the PCB review surface.</div></div>
            ) : detailLoading ? (
              <div className="viewer-empty"><div className="empty-state">Loading run detail…</div></div>
            ) : (
              <PcbViewer
                key={`${selectedRunId || 'none'}:${effectiveSelectedImageId}`}
                image={selectedImage}
                run={selectedRun}
                defects={visibleDefects}
                selectedDefect={selectedDefect}
                hoveredDefectId={hoveredDefectId}
                onHover={setHoveredDefectId}
                onSelectDefect={setSelectedDefectId}
              />
            )}
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
