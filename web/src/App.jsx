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

function EmptyStateMessage({ title, body }) {
  return (
    <div className="empty-state empty-guidance">
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  )
}

function FiducialPreview({ image, fiducials }) {
  if (!image) {
    return <div className="empty-state">Upload a scan to preview fiducial detection.</div>
  }

  return (
    <div className="fiducial-preview">
      <img src={image.image_path} alt="Fiducial preview" />
      {fiducials.map((fiducial) => (
        <div
          key={fiducial.id}
          className="fiducial-box"
          style={{
            left: `${fiducial.x * 100}%`,
            top: `${fiducial.y * 100}%`,
            width: `${fiducial.width * 100}%`,
            height: `${fiducial.height * 100}%`,
          }}
        >
          <span>{Math.round(fiducial.confidence * 100)}%</span>
        </div>
      ))}
    </div>
  )
}

function BarcodePreview({ image, barcode }) {
  if (!image) {
    return <div className="empty-state">Upload a scan to preview barcode detection.</div>
  }
  if (!barcode) {
    return <div className="empty-state">Run barcode detection to preview the detected region.</div>
  }

  return (
    <div className="fiducial-preview">
      <img src={image.image_path} alt="Barcode preview" />
      <div
        className="barcode-box"
        style={{
          left: `${barcode.x * 100}%`,
          top: `${barcode.y * 100}%`,
          width: `${barcode.width * 100}%`,
          height: `${barcode.height * 100}%`,
        }}
      >
        <span>{barcode.decoded_value}</span>
      </div>
    </div>
  )
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
  const [imageDimensions, setImageDimensions] = useState({
    width: image?.image_width || 1600,
    height: image?.image_height || 900,
  })
  const dragRef = useRef({ startX: 0, startY: 0, offsetX: 0, offsetY: 0 })
  const viewerRef = useRef(null)

  function setScale(nextScale) {
    setViewerScale(clamp(nextScale, 0.5, 10))
  }

  function resetViewer() {
    if (!viewerRef.current || !image) return
    const bounds = viewerRef.current.getBoundingClientRect()
    // Calculate scale to fit the image into the workspace with some padding
    const padding = 40
    const availableWidth = bounds.width - padding
    const availableHeight = bounds.height - padding

    // Use image metadata dimensions for calculation
    const imgWidth = imageDimensions.width
    const imgHeight = imageDimensions.height

    const scaleX = availableWidth / imgWidth
    const scaleY = availableHeight / imgHeight
    const nextScale = Math.min(scaleX, scaleY, 1.0)

    setViewerScale(nextScale)
    setViewerOffset({ x: 0, y: 0 })
  }

  function focusDefect(defectId) {
    const defect = defects.find((entry) => entry.id === defectId)
    if (!defect || !viewerRef.current || !image) {
      return
    }

    onSelectDefect(defect.id)

    // Industrial Centering Math
    // 1. Find the target center in normalized coordinates (0 to 1)
    const targetX = defect.overlay_x + defect.overlay_width / 2
    const targetY = defect.overlay_y + defect.overlay_height / 2

    // 2. Set a comfortable zoom level for component inspection
    // We target a scale that makes the component roughly 30% of the screen
    const componentSize = Math.max(defect.overlay_width, defect.overlay_height)
    const nextScale = clamp(0.3 / (componentSize || 0.1), 1.5, 6)

    // 3. Calculate offset relative to the IMAGE CENTER (0.5, 0.5)
    // Since CSS centers the stage, offset {0,0} is the image center.
    // We need to shift the stage by the distance from center to target, negated.
    const imgWidth = imageDimensions.width
    const imgHeight = imageDimensions.height

    const offsetX = -(targetX - 0.5) * imgWidth * nextScale
    const offsetY = -(targetY - 0.5) * imgHeight * nextScale

    setViewerScale(nextScale)
    setViewerOffset({ x: offsetX, y: offsetY })
  }

  function startDrag(event) {
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
    const zoomSpeed = 0.001
    const delta = -event.deltaY
    const scaleFactor = Math.pow(1.1, delta / 100)
    setScale(viewerScale * scaleFactor)
  }

  useEffect(() => {
    if (image?.id) {
      // Only auto-fit if it's a DIFFERENT image than before
      const timer = setTimeout(resetViewer, 50)
      return () => clearTimeout(timer)
    }
  }, [image?.id, imageDimensions.width, imageDimensions.height])

  useEffect(() => {
    setImageDimensions({
      width: image?.image_width || 1600,
      height: image?.image_height || 900,
    })
  }, [image?.id, image?.image_width, image?.image_height])

  return (
    <section className="viewer-panel">
      <div className="viewer-toolbar">
        <div className="viewer-toolbar-group">
          <button type="button" className="ghost-button" onClick={resetViewer}>
            Reset View
          </button>
          <button
            type="button"
            className="ghost-button"
            onClick={() => selectedDefect && focusDefect(selectedDefect.id)}
            disabled={!selectedDefect}
          >
            Center Defect
          </button>
        </div>
        <div className="viewer-toolbar-group">
          <button type="button" className="ghost-button" onClick={() => setScale(viewerScale * 0.8)}>
            -
          </button>
          <div className="zoom-readout">{Math.round(viewerScale * 100)}%</div>
          <button type="button" className="ghost-button" onClick={() => setScale(viewerScale * 1.25)}>
            +
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
            {viewerScale > 1.5 && (
              <div
                className="viewer-grid"
                style={{
                  position: 'absolute',
                  inset: 0,
                  backgroundImage:
                    'linear-gradient(to right, rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.05) 1px, transparent 1px)',
                  backgroundSize: '20px 20px',
                  pointerEvents: 'none',
                }}
              />
            )}
            <img
              className="viewer-image"
              src={image.image_path}
              alt={`${run.pcb_id} board`}
              onLoad={(event) => {
                const nextWidth = event.currentTarget.naturalWidth || image?.image_width || 1600
                const nextHeight = event.currentTarget.naturalHeight || image?.image_height || 900
                setImageDimensions((current) =>
                  current.width === nextWidth && current.height === nextHeight
                    ? current
                    : { width: nextWidth, height: nextHeight },
                )
              }}
            />
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
          <div className="empty-state">No inspection image.</div>
        )}
      </div>
    </section>
  )
}

function SetupFlow({
  steps,
  activeStep,
  selectedRun,
  selectedImage,
  modelDraft,
  requiresFiducialsDraft,
  requiresBarcodeDraft,
  onModelDraftChange,
  onRequiresFiducialsChange,
  onRequiresBarcodeChange,
  onCreateRun,
  onUploadScan,
  onSaveModel,
  onDetectFiducials,
  onConfirmFiducials,
  onDetectBarcode,
  onConfirmBarcode,
  onContinueToReview,
  isCreatingRun,
  isUploading,
  isSavingModel,
  isDetectingFiducials,
  isDetectingBarcode,
}) {
  return (
    <div className="setup-shell">
      <aside className="setup-steps">
        <div className="setup-steps-header">
          <p className="eyebrow">Pre-Program Setup</p>
          <h2>Prepare This Run</h2>
        </div>
        <div className="setup-step-list">
          {steps.map((step) => (
            <div key={step.id} className={`setup-step-card ${step.active ? 'active' : ''}`}>
              <div className="setup-step-index">{step.order}</div>
              <div className="setup-step-copy">
                <strong>{step.label}</strong>
                <p>{step.description}</p>
              </div>
              <span className={`setup-step-status ${step.status}`}>{step.statusLabel}</span>
            </div>
          ))}
        </div>
      </aside>

      <section className="setup-panel">
        <div className="setup-panel-header">
          <p className="eyebrow">Current Step</p>
          <h2>{activeStep.label}</h2>
          <p>{activeStep.description}</p>
        </div>

        <div className="setup-panel-body">
          {activeStep.id === 'create-run' ? (
            <div className="setup-action-card">
              <p>Create a new setup run before uploading assets or entering model data.</p>
              <button type="button" className="primary-button" onClick={onCreateRun} disabled={isCreatingRun}>
                {isCreatingRun ? 'Creating Run...' : 'Create Run'}
              </button>
            </div>
          ) : null}

          {activeStep.id === 'upload-scan' ? (
            <div className="setup-action-card">
              <p>
                Attach one PCB scan to <strong>{selectedRun?.pcb_id || 'the current run'}</strong>. Fiducial and
                barcode setup cannot start until an image exists.
              </p>
              <button type="button" className="primary-button" onClick={onUploadScan} disabled={isUploading}>
                {isUploading ? 'Uploading Scan...' : 'Upload PCB Scan'}
              </button>
            </div>
          ) : null}

          {activeStep.id === 'enter-model' ? (
            <div className="setup-action-card">
              <label className="field">
                <span>Model Name</span>
                <input value={modelDraft} onChange={(event) => onModelDraftChange(event.target.value)} />
              </label>
              <label className="setup-checkbox">
                <input
                  type="checkbox"
                  checked={requiresFiducialsDraft}
                  onChange={(event) => onRequiresFiducialsChange(event.target.checked)}
                />
                <span>Require fiducial alignment for this product</span>
              </label>
              <label className="setup-checkbox">
                <input
                  type="checkbox"
                  checked={requiresBarcodeDraft}
                  onChange={(event) => onRequiresBarcodeChange(event.target.checked)}
                />
                <span>Require barcode validation for this product</span>
              </label>
              <p>Set the model name now so later steps can decide whether fiducials or barcode validation are required.</p>
              <button
                type="button"
                className="primary-button"
                onClick={onSaveModel}
                disabled={isSavingModel || !modelDraft.trim()}
              >
                {isSavingModel ? 'Saving Model...' : 'Save Model Name'}
              </button>
            </div>
          ) : null}

          {activeStep.id === 'fiducials' ? (
            <div className="setup-action-card">
              {!selectedRun?.requires_fiducials ? (
                <p>Fiducials are not required for this product. Enable them in the model step if the product needs alignment marks.</p>
              ) : (
                <>
                  <p>Run automated fiducial search, review the overlay results, then confirm when the locations look correct.</p>
                  <FiducialPreview image={selectedImage} fiducials={selectedRun?.fiducials || []} />
                  <div className="setup-button-row">
                    <button
                      type="button"
                      className="primary-button"
                      onClick={onDetectFiducials}
                      disabled={isDetectingFiducials || !selectedImage}
                    >
                      {isDetectingFiducials ? 'Detecting...' : 'Detect Fiducials'}
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={onConfirmFiducials}
                      disabled={selectedRun?.fiducial_status !== 'needs_review'}
                    >
                      Confirm Fiducials
                    </button>
                  </div>
                  {selectedRun?.fiducials?.length ? (
                    <div className="fiducial-list">
                      {selectedRun.fiducials.map((fiducial) => (
                        <div key={fiducial.id} className="fiducial-list-item">
                          <strong>{fiducial.id}</strong>
                          <span>{Math.round(fiducial.confidence * 100)}% confidence</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </>
              )}
            </div>
          ) : null}

          {activeStep.id === 'barcode' ? (
            <div className="setup-action-card">
              {!selectedRun?.requires_barcode ? (
                <p>Barcode validation is not required for this product. Enable it in the model step if the product needs barcode confirmation.</p>
              ) : (
                <>
                  <p>Run automated barcode search, review the decoded result, then confirm when the location and value are correct.</p>
                  <BarcodePreview image={selectedImage} barcode={selectedRun?.barcode} />
                  <div className="setup-button-row">
                    <button
                      type="button"
                      className="primary-button"
                      onClick={onDetectBarcode}
                      disabled={isDetectingBarcode || !selectedImage}
                    >
                      {isDetectingBarcode ? 'Detecting...' : 'Detect Barcode'}
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={onConfirmBarcode}
                      disabled={selectedRun?.barcode_status !== 'needs_review'}
                    >
                      Confirm Barcode
                    </button>
                  </div>
                  {selectedRun?.barcode ? (
                    <div className="fiducial-list">
                      <div className="fiducial-list-item">
                        <strong>{selectedRun.barcode.id}</strong>
                        <span>{selectedRun.barcode.decoded_value}</span>
                      </div>
                    </div>
                  ) : null}
                </>
              )}
            </div>
          ) : null}

          {activeStep.id === 'continue-review' ? (
            <div className="setup-action-card">
              <p>Required setup is complete. Continue to the standard PCB review surface for this run.</p>
              <button type="button" className="primary-button" onClick={onContinueToReview}>
                Continue To Review
              </button>
            </div>
          ) : null}
        </div>
      </section>

      <aside className="setup-summary">
        <div className="setup-summary-card">
          <p className="eyebrow">Run Summary</p>
          <div className="setup-summary-grid">
            <span>Run</span>
            <strong>{selectedRun?.pcb_id || 'Not created'}</strong>
            <span>Scan</span>
            <strong>{selectedRun?.images?.length ? 'Attached' : 'Missing'}</strong>
            <span>Model</span>
            <strong>{selectedRun?.model_name || 'Unset'}</strong>
            <span>Fiducials</span>
            <strong>{selectedRun?.requires_fiducials ? selectedRun?.fiducial_status || 'Required' : 'Not required'}</strong>
            <span>Barcode</span>
            <strong>{selectedRun?.requires_barcode ? selectedRun?.barcode_status || 'Required' : 'Not required'}</strong>
            <span>Setup</span>
            <strong>{selectedRun?.setup_status || 'Not started'}</strong>
          </div>
        </div>
      </aside>
    </div>
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

  // Layout toggles initialized
  const [isRunRailOpen, setIsRunRailOpen] = useState(true)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [isFiltersOpen, setIsFiltersOpen] = useState(true)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [hudGhostOpacity, setHudGhostOpacity] = useState(0.2)
  const [isUploading, setIsUploading] = useState(false)
  const [isCreatingRun, setIsCreatingRun] = useState(false)
  const [isSavingModel, setIsSavingModel] = useState(false)
  const [isDetectingFiducials, setIsDetectingFiducials] = useState(false)
  const [isDetectingBarcode, setIsDetectingBarcode] = useState(false)
  const [modelDraft, setModelDraft] = useState('')
  const [requiresFiducialsDraft, setRequiresFiducialsDraft] = useState(false)
  const [requiresBarcodeDraft, setRequiresBarcodeDraft] = useState(false)
  const [dismissedSetupRuns, setDismissedSetupRuns] = useState({})
  const fileInputRef = useRef(null)

  function openImagePicker() {
    if (isUploading || !selectedRunId) {
      return
    }
    fileInputRef.current?.click()
  }

  async function handleImageUpload(event) {
    const file = event.target.files?.[0]
    if (!file || !selectedRunId) return

    setIsUploading(true)
    setError('')
    try {
      const response = await fetch(`/runs/${selectedRunId}/images`, {
        method: 'POST',
        headers: { 'Content-Type': file.type },
        body: file,
      })

      const payload = await response.json()
      if (!response.ok || payload.status === 'error') {
        throw new Error(payload.message || 'Upload failed')
      }

      // Refresh the run detail to show the new image immediately
      const detailPayload = await fetchJson(`/runs/${selectedRunId}${buildQuery(detailFilters)}`)
      setSelectedRun(detailPayload.run)
      setRuns((currentRuns) =>
        currentRuns.map((run) => (run.id === detailPayload.run.id ? { ...run, ...detailPayload.run } : run)),
      )
    } catch (err) {
      setError(`Upload Error: ${err.message}`)
    } finally {
      if (event.target) {
        event.target.value = ''
      }
      setIsUploading(false)
    }
  }

  async function handleCreateRun() {
    setIsCreatingRun(true)
    setError('')
    try {
      const response = await fetch('/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      const payload = await response.json()
      if (!response.ok || payload.status === 'error') {
        throw new Error(payload.message || 'Create run failed')
      }
      setRuns((currentRuns) => [payload.run, ...currentRuns])
      setSelectedRunId(payload.run.id)
      setSelectedRun({ ...payload.run, images: [], defect_logs: [], event_count: 0 })
      setDismissedSetupRuns((current) => ({ ...current, [payload.run.id]: false }))
    } catch (err) {
      setError(`Create Run Error: ${err.message}`)
    } finally {
      setIsCreatingRun(false)
    }
  }

  async function handleSaveModel() {
    if (!selectedRunId || !modelDraft.trim()) {
      return
    }

    setIsSavingModel(true)
    setError('')
    try {
      const response = await fetch(`/runs/${selectedRunId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_name: modelDraft.trim(),
          requires_fiducials: requiresFiducialsDraft,
          requires_barcode: requiresBarcodeDraft,
        }),
      })
      const payload = await response.json()
      if (!response.ok || payload.status === 'error') {
        throw new Error(payload.message || 'Save model failed')
      }
      const nextRun = {
        ...payload.run,
        images: selectedRun?.images || [],
        defect_logs: selectedRun?.defect_logs || [],
        event_count: selectedRun?.event_count || 0,
      }
      setSelectedRun(nextRun)
      setRuns((currentRuns) =>
        currentRuns.map((run) => (run.id === payload.run.id ? { ...run, ...payload.run } : run)),
      )
    } catch (err) {
      setError(`Model Save Error: ${err.message}`)
    } finally {
      setIsSavingModel(false)
    }
  }

  async function handleDetectFiducials() {
    if (!selectedRunId) {
      return
    }
    setIsDetectingFiducials(true)
    setError('')
    try {
      const response = await fetch(`/runs/${selectedRunId}/fiducials/detect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      const payload = await response.json()
      if (!response.ok || payload.status === 'error') {
        throw new Error(payload.message || 'Fiducial detection failed')
      }
      const nextRun = {
        ...payload.run,
        images: selectedRun?.images || [],
        defect_logs: selectedRun?.defect_logs || [],
        event_count: selectedRun?.event_count || 0,
      }
      setSelectedRun(nextRun)
      setRuns((currentRuns) => currentRuns.map((run) => (run.id === payload.run.id ? { ...run, ...payload.run } : run)))
    } catch (err) {
      setError(`Fiducial Detection Error: ${err.message}`)
    } finally {
      setIsDetectingFiducials(false)
    }
  }

  async function handleConfirmFiducials() {
    if (!selectedRunId) {
      return
    }
    setError('')
    try {
      const response = await fetch(`/runs/${selectedRunId}/fiducials/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      const payload = await response.json()
      if (!response.ok || payload.status === 'error') {
        throw new Error(payload.message || 'Fiducial confirmation failed')
      }
      const nextRun = {
        ...payload.run,
        images: selectedRun?.images || [],
        defect_logs: selectedRun?.defect_logs || [],
        event_count: selectedRun?.event_count || 0,
      }
      setSelectedRun(nextRun)
      setRuns((currentRuns) => currentRuns.map((run) => (run.id === payload.run.id ? { ...run, ...payload.run } : run)))
    } catch (err) {
      setError(`Fiducial Confirm Error: ${err.message}`)
    }
  }

  async function handleDetectBarcode() {
    if (!selectedRunId) {
      return
    }
    setIsDetectingBarcode(true)
    setError('')
    try {
      const response = await fetch(`/runs/${selectedRunId}/barcode/detect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      const payload = await response.json()
      if (!response.ok || payload.status === 'error') {
        throw new Error(payload.message || 'Barcode detection failed')
      }
      const nextRun = {
        ...payload.run,
        images: selectedRun?.images || [],
        defect_logs: selectedRun?.defect_logs || [],
        event_count: selectedRun?.event_count || 0,
      }
      setSelectedRun(nextRun)
      setRuns((currentRuns) => currentRuns.map((run) => (run.id === payload.run.id ? { ...run, ...payload.run } : run)))
    } catch (err) {
      setError(`Barcode Detection Error: ${err.message}`)
    } finally {
      setIsDetectingBarcode(false)
    }
  }

  async function handleConfirmBarcode() {
    if (!selectedRunId) {
      return
    }
    setError('')
    try {
      const response = await fetch(`/runs/${selectedRunId}/barcode/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      const payload = await response.json()
      if (!response.ok || payload.status === 'error') {
        throw new Error(payload.message || 'Barcode confirmation failed')
      }
      const nextRun = {
        ...payload.run,
        images: selectedRun?.images || [],
        defect_logs: selectedRun?.defect_logs || [],
        event_count: selectedRun?.event_count || 0,
      }
      setSelectedRun(nextRun)
      setRuns((currentRuns) => currentRuns.map((run) => (run.id === payload.run.id ? { ...run, ...payload.run } : run)))
    } catch (err) {
      setError(`Barcode Confirm Error: ${err.message}`)
    }
  }

  function handleContinueToReview() {
    if (!selectedRunId) {
      return
    }
    setDismissedSetupRuns((current) => ({ ...current, [selectedRunId]: true }))
  }

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
          return null
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
      setSelectedRun(null)
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

  const pendingRuns = useMemo(
    () => runs.filter((run) => run.setup_status !== 'review_ready'),
    [runs],
  )
  const reviewRuns = useMemo(
    () => runs.filter((run) => run.setup_status === 'review_ready'),
    [runs],
  )

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
  const hasScan = runImages.length > 0
  const hasModel = Boolean(selectedRun?.model_name?.trim())

  useEffect(() => {
    setModelDraft(selectedRun?.model_name || '')
    setRequiresFiducialsDraft(Boolean(selectedRun?.requires_fiducials))
    setRequiresBarcodeDraft(Boolean(selectedRun?.requires_barcode))
  }, [selectedRun?.id, selectedRun?.model_name, selectedRun?.requires_fiducials, selectedRun?.requires_barcode])

  const setupSteps = useMemo(() => {
    const requiresFiducials = Boolean(selectedRun?.requires_fiducials)
    const fiducialStatus = selectedRun?.fiducial_status || 'not_required'
    const requiresBarcode = Boolean(selectedRun?.requires_barcode)
    const barcodeStatus = selectedRun?.barcode_status || 'not_required'
    const baseSteps = [
      {
        id: 'create-run',
        order: 1,
        label: 'Create Run',
        description: 'Create the working record that later scan and model data will attach to.',
        status: selectedRunId ? 'done' : 'ready',
        statusLabel: selectedRunId ? 'Done' : 'Ready',
      },
      {
        id: 'upload-scan',
        order: 2,
        label: 'Upload PCB Scan',
        description: 'Attach one board image for the current run.',
        status: !selectedRunId ? 'blocked' : hasScan ? 'done' : 'ready',
        statusLabel: !selectedRunId ? 'Blocked' : hasScan ? 'Done' : 'Ready',
      },
      {
        id: 'enter-model',
        order: 3,
        label: 'Enter Model Name',
        description: 'Set the product context before optional automation steps are evaluated.',
        status: !selectedRunId ? 'blocked' : hasModel ? 'done' : 'ready',
        statusLabel: !selectedRunId ? 'Blocked' : hasModel ? 'Done' : 'Ready',
      },
      {
        id: 'fiducials',
        order: 4,
        label: 'Find Fiducial Marks',
        description: 'Detect and confirm fiducial marks when the selected model requires alignment setup.',
        status: !requiresFiducials ? 'not_required' : fiducialStatus === 'confirmed' ? 'done' : fiducialStatus,
        statusLabel:
          !requiresFiducials
            ? 'Not Required'
            : fiducialStatus === 'confirmed'
              ? 'Done'
              : fiducialStatus === 'needs_review'
                ? 'Needs Review'
                : fiducialStatus === 'ready'
                  ? 'Ready'
                  : fiducialStatus === 'blocked'
                    ? 'Blocked'
                    : 'Ready',
      },
      {
        id: 'barcode',
        order: 5,
        label: 'Find Barcode',
        description: 'Detect and confirm barcode position and decoded value when the selected model requires barcode validation.',
        status: !requiresBarcode ? 'not_required' : barcodeStatus === 'confirmed' ? 'done' : barcodeStatus,
        statusLabel:
          !requiresBarcode
            ? 'Not Required'
            : barcodeStatus === 'confirmed'
              ? 'Done'
              : barcodeStatus === 'needs_review'
                ? 'Needs Review'
                : barcodeStatus === 'ready'
                  ? 'Ready'
                  : barcodeStatus === 'blocked'
                    ? 'Blocked'
                    : 'Ready',
      },
    ]

    const isReviewReady = Boolean(
      selectedRunId &&
      hasScan &&
      hasModel &&
      (!requiresFiducials || fiducialStatus === 'confirmed') &&
      (!requiresBarcode || barcodeStatus === 'confirmed'),
    )
    baseSteps.push({
      id: 'continue-review',
      order: 6,
      label: 'Continue To Review',
      description: 'Open the normal PCB review surface once required setup is complete.',
      status: isReviewReady ? 'ready' : 'blocked',
      statusLabel: isReviewReady ? 'Ready' : 'Blocked',
    })

    const activeStepId =
      baseSteps.find((step) => step.status === 'needs_review')?.id ||
      baseSteps.find((step) => step.status === 'ready')?.id ||
      baseSteps.find((step) => step.status === 'blocked')?.id ||
      baseSteps.at(-1)?.id

    return baseSteps.map((step) => ({ ...step, active: step.id === activeStepId }))
  }, [selectedRunId, hasScan, hasModel])

  const activeSetupStep = setupSteps.find((step) => step.active) || setupSteps[0]
  const showSetupMode = !selectedRun || (selectedRun.status === 'SETUP' && !dismissedSetupRuns[selectedRun.id])

  return (
    <div className="app-shell">
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
            className={`dock-button ${isRunRailOpen ? 'active' : ''}`}
            onClick={() => setIsRunRailOpen(!isRunRailOpen)}
            title="Toggle Run History"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="10" x2="21" y2="10"></line><line x1="9" y1="22" x2="9" y2="10"></line></svg>
          </button>
          <button
            type="button"
            className={`dock-button ${isSidebarOpen ? 'active' : ''}`}
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            title="Toggle Defect List"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
          </button>
          <button
            type="button"
            className={`dock-button ${isFiltersOpen ? 'active' : ''}`}
            onClick={() => setIsFiltersOpen(!isFiltersOpen)}
            title="Toggle Defect Filters"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>
          </button>
          <button
            type="button"
            className={`dock-button ${isSettingsOpen ? 'active' : ''}`}
            onClick={() => setIsSettingsOpen(!isSettingsOpen)}
            title="System Settings"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
          </button>
        </div>
      </header>

      {isSettingsOpen && (
        <div className="settings-overlay" onClick={() => setIsSettingsOpen(false)}>
          <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
            <div className="settings-header">
              <h2>System Settings</h2>
              <button className="ghost-button" onClick={() => setIsSettingsOpen(false)}>Close</button>
            </div>
            <div className="settings-content">
              <section className="settings-section">
                <p className="eyebrow">Display</p>
                <div className="settings-row">
                  <span>HUD Ghost Opacity</span>
                  <div className="settings-control">
                    <span className="value-label">{Math.round(hudGhostOpacity * 100)}%</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={hudGhostOpacity}
                      onChange={(e) => setHudGhostOpacity(parseFloat(e.target.value))}
                    />
                  </div>
                </div>
                <div className="settings-row">
                  <span>Show Coordinate Grid</span>
                  <input type="checkbox" checked={true} readOnly />
                </div>
                <div className="settings-row">
                  <span>Industrial Dark Theme</span>
                  <input type="checkbox" checked={true} readOnly />
                </div>
              </section>

              <section className="settings-section">
                <p className="eyebrow">Asset Management</p>
                <div className="settings-row">
                  <span>Upload Scan for Current Run</span>
                  <button
                    type="button"
                    className={`ghost-button upload-label ${isUploading ? 'loading' : ''}`}
                    onClick={openImagePicker}
                    disabled={isUploading || !selectedRunId}
                  >
                    {isUploading ? 'Uploading...' : 'Select File'}
                  </button>
                </div>
              </section>

              <section className="settings-section">
                <p className="eyebrow">Inference</p>
                <div className="settings-row">
                  <span>Mock Event Stream</span>
                  <input type="checkbox" checked={true} readOnly />
                </div>
              </section>
            </div>
          </div>
        </div>
      )}

      {error ? <div className="error-banner">{error}</div> : null}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleImageUpload}
        hidden
        disabled={isUploading || !selectedRunId}
      />

      <main className={`workspace ${!isRunRailOpen ? 'rail-collapsed' : ''}`}>
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

        <section className="panel review-panel">
          <div className="review-topbar">
            <div className="review-runline">
              <div className="review-runline-main">
                <strong>{selectedRun?.pcb_id || 'No run selected'}</strong>
                {selectedRun ? <StatusChip value={selectedRun.status} /> : null}
                <span className="compact-meta">{selectedRun ? formatTimestamp(selectedRun.timestamp) : '-'}</span>
                <span className="compact-meta">{failCount} fail defects</span>
                {detailLoading && <span className="loading-indicator">Updating...</span>}
              </div>
              {selectedImage?.image_role === 'demo_full_board' ? (
                <div className="compact-note">Demo image active</div>
              ) : null}
            </div>
            <div className="review-controls">
              {!showSetupMode ? (
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
              ) : null}
              <button
                type="button"
                className={`ghost-button upload-button ${isUploading ? 'loading' : ''}`}
                onClick={openImagePicker}
                disabled={isUploading || !selectedRunId}
              >
                {isUploading ? 'Uploading Scan...' : 'Upload PCB Scan'}
              </button>
              {!selectedRunId ? (
                <span className="upload-helper">Select a run from History to enable upload.</span>
              ) : null}
              {!showSetupMode ? (
                <>
                  <button type="button" className="ghost-button" onClick={() => stepDefect(-1)}>
                    &lt;
                  </button>
                  <button type="button" className="ghost-button" onClick={() => stepDefect(1)}>
                    &gt;
                  </button>
                </>
              ) : null}
            </div>
          </div>

          {showSetupMode ? (
            <SetupFlow
              steps={setupSteps}
              activeStep={activeSetupStep}
              selectedRun={selectedRun}
              selectedImage={selectedImage}
              modelDraft={modelDraft}
              requiresFiducialsDraft={requiresFiducialsDraft}
              requiresBarcodeDraft={requiresBarcodeDraft}
              onModelDraftChange={setModelDraft}
              onRequiresFiducialsChange={setRequiresFiducialsDraft}
              onRequiresBarcodeChange={setRequiresBarcodeDraft}
              onCreateRun={handleCreateRun}
              onUploadScan={openImagePicker}
              onSaveModel={handleSaveModel}
              onDetectFiducials={handleDetectFiducials}
              onConfirmFiducials={handleConfirmFiducials}
              onDetectBarcode={handleDetectBarcode}
              onConfirmBarcode={handleConfirmBarcode}
              onContinueToReview={handleContinueToReview}
              isCreatingRun={isCreatingRun}
              isUploading={isUploading}
              isSavingModel={isSavingModel}
              isDetectingFiducials={isDetectingFiducials}
              isDetectingBarcode={isDetectingBarcode}
            />
          ) : (
          <div className={`review-shell ${!isSidebarOpen ? 'sidebar-collapsed' : ''}`}>
            <aside className="review-sidebar">
              {isFiltersOpen && (
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
              )}

              <section className="review-card defect-list-card">
                <div className="review-card-header">
                  <p className="eyebrow">Defects</p>
                  <span className="section-note">{visibleDefects.length}</span>
                </div>
                <div className="defect-list">
                  {!selectedRunId ? (
                    <EmptyStateMessage
                      title="No defect list yet"
                      body="Choose a run from History first. Defects are loaded per run, so this panel stays empty until one is selected."
                    />
                  ) : (
                    visibleDefects.length ? (
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
                    )
                  )}
                </div>
              </section>
            </aside>

            <div className="viewer-container">
              {!selectedRunId ? (
                <div className="viewer-empty">
                  <EmptyStateMessage
                    title="No run selected"
                    body="Select a run from the History rail to load its PCB review surface. Upload becomes available after a run is selected."
                  />
                </div>
              ) : !selectedImage ? (
                <div className="viewer-empty">
                  <div className="empty-state upload-prompt">
                    <p>No scan image available for this run.</p>
                    <p>Use the upload control in the header to attach a PCB scan.</p>
                  </div>
                </div>
              ) : (
                <>
                  <PcbViewer
                    key={`${selectedRunId || 'none'}`}
                    image={selectedImage}
                    run={selectedRun}
                    defects={visibleDefects}
                    selectedDefect={selectedDefect}
                    hoveredDefectId={hoveredDefectId}
                    onHover={setHoveredDefectId}
                    onSelectDefect={setSelectedDefectId}
                  />
                  {selectedDefect ? (
                    <div
                      className="floating-inspector"
                      style={{ '--ghost-opacity': hudGhostOpacity }}
                    >
                      <div className="inspector-header">
                        <p className="eyebrow">Defect Inspector</p>
                        <StatusChip value={selectedDefect.inspection_result} />
                      </div>
                      <div className="inspector-grid">
                        <div className="inspector-item">
                          <span className="eyebrow">Component</span>
                          <strong>{selectedDefect.component_id}</strong>
                        </div>
                        <div className="inspector-item">
                          <span className="eyebrow">Type</span>
                          <strong>{selectedDefect.defect_type}</strong>
                        </div>
                        <div className="inspector-item">
                          <span className="eyebrow">Severity</span>
                          <strong>{selectedDefect.severity}</strong>
                        </div>
                        <div className="inspector-item">
                          <span className="eyebrow">Confidence</span>
                          <strong>{Number(selectedDefect.confidence_score ?? 0).toFixed(2)}</strong>
                        </div>
                      </div>
                    </div>
                  ) : null}
                </>
              )}
            </div>
          </div>
          )}
        </section>
      </main>
    </div>
  )
}

export default App
