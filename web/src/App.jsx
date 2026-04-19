import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || window.location.origin
const GRAFANA_BASE_URL = import.meta.env.VITE_GRAFANA_BASE_URL || 'http://localhost:3000'
const DEFAULT_IMAGE_ID = 'demo-full-board'
const DEFAULT_IMAGE = {
  id: DEFAULT_IMAGE_ID,
  image_path: '/mock/pcb-example.png',
  image_role: 'demo_full_board',
  image_width: 1920,
  image_height: 1080,
  is_demo: true,
}

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
    const nextScale = 2.25
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
    const deltaX = event.clientX - dragRef.current.startX
    const deltaY = event.clientY - dragRef.current.startY
    setViewerOffset({
      x: dragRef.current.offsetX + deltaX,
      y: dragRef.current.offsetY + deltaY,
    })
  }

  function stopDrag() {
    setIsDragging(false)
  }

  function handleWheel(event) {
    event.preventDefault()
    const delta = event.deltaY < 0 ? 0.18 : -0.18
    setScale(viewerScale + delta)
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
          <button
            type="button"
            className="ghost-button"
            onClick={() => setScale(viewerScale - 0.2)}
          >
            Zoom -
          </button>
          <div className="zoom-readout">{Math.round(viewerScale * 100)}%</div>
          <button
            type="button"
            className="ghost-button"
            onClick={() => setScale(viewerScale + 0.2)}
          >
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
            style={{
              transform: `translate(${viewerOffset.x}px, ${viewerOffset.y}px) scale(${viewerScale})`,
            }}
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

function buildFallbackOverlay(index) {
  const columns = 4
  const column = index % columns
  const row = Math.floor(index / columns)
  return {
    x: 0.16 + column * 0.17,
    y: 0.2 + (row % 3) * 0.18,
    width: 0.075,
    height: 0.06,
  }
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
    const passRuns = runs.filter((run) => run.status === 'PASS').length
    const totalEvents = runs.reduce((sum, run) => sum + Number(run.event_count || 0), 0)
    return {
      recentRuns: runs.length,
      failRuns,
      passRuns,
      totalEvents,
    }
  }, [runs])

  const runImages = useMemo(() => {
    if (!selectedRun) {
      return []
    }
    if (Array.isArray(selectedRun.images) && selectedRun.images.length > 0) {
      return selectedRun.images
    }
    return [DEFAULT_IMAGE]
  }, [selectedRun])

  const defects = useMemo(() => {
    if (!selectedRun?.defect_logs) {
      return []
    }

    const fallbackImageId = runImages[0]?.id || DEFAULT_IMAGE_ID
    return selectedRun.defect_logs.map((defect, index) => {
      const fallback = buildFallbackOverlay(index)
      return {
        ...defect,
        run_image_id: defect.run_image_id || fallbackImageId,
        overlay_shape: defect.overlay_shape || 'rect',
        overlay_x: defect.overlay_x ?? fallback.x,
        overlay_y: defect.overlay_y ?? fallback.y,
        overlay_width: defect.overlay_width ?? fallback.width,
        overlay_height: defect.overlay_height ?? fallback.height,
      }
    })
  }, [runImages, selectedRun])

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
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">AOI Monitoring Console</p>
          <h1>Production inspection, now with a visual review surface.</h1>
          <p className="hero-text">
            This skeleton adds the operator-facing PCB review layout: synced defect
            navigation, a zoomable image stage, and clickable overlay regions. Real image
            wiring can drop into the same structure later.
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

            <div className="section-note run-note">Auto-refreshes every 10 seconds.</div>

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
          <div className="panel-header review-header">
            <div>
              <p className="eyebrow">Review</p>
              <h2>PCB defect inspection</h2>
            </div>
            <div className="review-header-tools">
              {selectedRun ? <StatusChip value={selectedRun.status} /> : null}
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
                Prev defect
              </button>
              <button type="button" className="ghost-button" onClick={() => stepDefect(1)}>
                Next defect
              </button>
            </div>
          </div>

          <div className="panel-body review-body">
            {!selectedRunId ? (
              <div className="empty-state">Select a run to load the PCB review surface.</div>
            ) : detailLoading ? (
              <div className="empty-state">Loading run detail…</div>
            ) : selectedRun ? (
              <div className="review-shell">
                <aside className="review-sidebar">
                  <section className="review-card">
                    <div className="review-card-header">
                      <p className="eyebrow">Run summary</p>
                    </div>
                    <div className="summary-grid">
                      <div className="detail-card">
                        <span className="eyebrow">Board</span>
                        <strong>{selectedRun.pcb_id}</strong>
                      </div>
                      <div className="detail-card">
                        <span className="eyebrow">Status</span>
                        <strong>{selectedRun.status}</strong>
                      </div>
                      <div className="detail-card">
                        <span className="eyebrow">Timestamp</span>
                        <strong>{formatTimestamp(selectedRun.timestamp)}</strong>
                      </div>
                      <div className="detail-card">
                        <span className="eyebrow">Fail defects</span>
                        <strong>{failCount}</strong>
                      </div>
                    </div>
                    {selectedImage?.is_demo ? (
                      <div className="info-banner">
                        Demo PCB image in use until run image metadata is wired into the API.
                      </div>
                    ) : null}
                  </section>

                  <section className="review-card">
                    <div className="review-card-header">
                      <p className="eyebrow">Defect filters</p>
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={() => setDetailFilters(DETAIL_FILTER_DEFAULTS)}
                      >
                        Reset
                      </button>
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
                  </section>

                  <section className="review-card defect-list-card">
                    <div className="review-card-header">
                      <div>
                        <p className="eyebrow">Defect list</p>
                        <div className="section-note">{visibleDefects.length} overlays on this image</div>
                      </div>
                    </div>
                    <div className="defect-list">
                      {visibleDefects.length ? (
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
                        <div className="empty-state">
                          No defect records matched the current image and filters.
                        </div>
                      )}
                    </div>
                  </section>

                  <section className="review-card">
                    <div className="review-card-header">
                      <p className="eyebrow">Selected defect</p>
                    </div>
                    {selectedDefect ? (
                      <div className="selected-defect-grid">
                        <div className="detail-card">
                          <span className="eyebrow">Component</span>
                          <strong>{selectedDefect.component_id}</strong>
                        </div>
                        <div className="detail-card">
                          <span className="eyebrow">Type</span>
                          <strong>{selectedDefect.defect_type}</strong>
                        </div>
                        <div className="detail-card">
                          <span className="eyebrow">Severity</span>
                          <strong>{selectedDefect.severity}</strong>
                        </div>
                        <div className="detail-card">
                          <span className="eyebrow">Confidence</span>
                          <strong>{Number(selectedDefect.confidence_score ?? 0).toFixed(2)}</strong>
                        </div>
                      </div>
                    ) : (
                      <div className="empty-state">Select a defect to inspect its overlay.</div>
                    )}
                  </section>
                </aside>

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
              </div>
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
