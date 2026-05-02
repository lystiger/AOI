import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  DEFAULT_IMAGE_ID,
  DETAIL_FILTER_DEFAULTS,
  DISMISSED_SETUP_STORAGE_KEY,
  RUN_FILTER_DEFAULTS,
  SELECTED_IMAGE_STORAGE_KEY,
  SELECTED_RUN_STORAGE_KEY,
} from '../app/constants'
import {
  buildManualBarcodeDraft,
  buildManualFiducialsDraft,
  buildQuery,
  fetchJson,
} from '../app/utils'

function normalizeRunPayload(run, selectedRun) {
  return {
    ...run,
    images: selectedRun?.images || [],
    defect_logs: selectedRun?.defect_logs || [],
    event_count: selectedRun?.event_count || 0,
  }
}

function readSelectedImageForRun(runId) {
  if (typeof window === 'undefined' || !runId) {
    return DEFAULT_IMAGE_ID
  }
  try {
    const rawValue = window.localStorage.getItem(SELECTED_IMAGE_STORAGE_KEY)
    const savedSelections = rawValue ? JSON.parse(rawValue) : {}
    return savedSelections[runId] || DEFAULT_IMAGE_ID
  } catch {
    return DEFAULT_IMAGE_ID
  }
}

export function useAoiWorkspace() {
  const [runFilters, setRunFilters] = useState(RUN_FILTER_DEFAULTS)
  const [detailFilters, setDetailFilters] = useState(DETAIL_FILTER_DEFAULTS)
  const [runs, setRuns] = useState([])
  const [selectedRunId, setSelectedRunId] = useState(() => {
    if (typeof window === 'undefined') {
      return null
    }
    return window.localStorage.getItem(SELECTED_RUN_STORAGE_KEY)
  })
  const [selectedRun, setSelectedRun] = useState(null)
  const [selectedImageId, setSelectedImageId] = useState(() => {
    if (typeof window === 'undefined') {
      return DEFAULT_IMAGE_ID
    }
    try {
      const selectedRun = window.localStorage.getItem(SELECTED_RUN_STORAGE_KEY)
      const rawValue = window.localStorage.getItem(SELECTED_IMAGE_STORAGE_KEY)
      if (!selectedRun || !rawValue) {
        return DEFAULT_IMAGE_ID
      }
      const savedSelections = JSON.parse(rawValue)
      return savedSelections[selectedRun] || DEFAULT_IMAGE_ID
    } catch {
      return DEFAULT_IMAGE_ID
    }
  })
  const [selectedDefectId, setSelectedDefectId] = useState(null)
  const [hoveredDefectId, setHoveredDefectId] = useState(null)
  const [runsLoading, setRunsLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')
  const [createRunError, setCreateRunError] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [modelError, setModelError] = useState('')
  const [fiducialError, setFiducialError] = useState('')
  const [barcodeError, setBarcodeError] = useState('')
  const [isRunRailOpen, setIsRunRailOpen] = useState(true)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [isFiltersOpen, setIsFiltersOpen] = useState(true)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [hudGhostOpacity, setHudGhostOpacity] = useState(0.2)
  const [isUploading, setIsUploading] = useState(false)
  const [isCreatingRun, setIsCreatingRun] = useState(false)
  const [isSavingModel, setIsSavingModel] = useState(false)
  const [isDetectingFiducials, setIsDetectingFiducials] = useState(false)
  const [isSavingManualFiducials, setIsSavingManualFiducials] = useState(false)
  const [isDetectingBarcode, setIsDetectingBarcode] = useState(false)
  const [isSavingManualBarcode, setIsSavingManualBarcode] = useState(false)
  const [isDeletingRun, setIsDeletingRun] = useState(false)
  const [manualStepId, setManualStepId] = useState(null)
  const [modelDraft, setModelDraft] = useState('')
  const [requiresFiducialsDraft, setRequiresFiducialsDraft] = useState(false)
  const [requiresBarcodeDraft, setRequiresBarcodeDraft] = useState(false)
  const [manualFiducialsDraft, setManualFiducialsDraft] = useState(() => buildManualFiducialsDraft(null))
  const [manualBarcodeDraft, setManualBarcodeDraft] = useState(() => buildManualBarcodeDraft(null))
  const [dismissedSetupRuns, setDismissedSetupRuns] = useState(() => {
    if (typeof window === 'undefined') {
      return {}
    }
    try {
      const rawValue = window.localStorage.getItem(DISMISSED_SETUP_STORAGE_KEY)
      return rawValue ? JSON.parse(rawValue) : {}
    } catch {
      return {}
    }
  })
  const fileInputRef = useRef(null)

  const clearRunDrafts = useCallback(() => {
    setModelDraft('')
    setRequiresFiducialsDraft(false)
    setRequiresBarcodeDraft(false)
    setManualFiducialsDraft(buildManualFiducialsDraft(null))
    setManualBarcodeDraft(buildManualBarcodeDraft(null))
    setManualStepId(null)
    setCreateRunError('')
    setUploadError('')
    setModelError('')
    setFiducialError('')
    setBarcodeError('')
    setSelectedDefectId(null)
    setHoveredDefectId(null)
  }, [])

  const applySelectedRun = useCallback((nextRun) => {
    setSelectedRun(nextRun)
    setModelDraft(nextRun?.model_name || '')
    setRequiresFiducialsDraft(Boolean(nextRun?.requires_fiducials))
    setRequiresBarcodeDraft(Boolean(nextRun?.requires_barcode))
    setManualFiducialsDraft(buildManualFiducialsDraft(nextRun))
    setManualBarcodeDraft(buildManualBarcodeDraft(nextRun))
    setManualStepId(null)
    setCreateRunError('')
    setUploadError('')
    setModelError('')
    setFiducialError('')
    setBarcodeError('')
  }, [])

  const selectRun = useCallback((nextRunId) => {
    setSelectedRunId(nextRunId)
    setSelectedImageId(readSelectedImageForRun(nextRunId))
    setSelectedDefectId(null)
    setHoveredDefectId(null)
    if (!nextRunId) {
      setSelectedRun(null)
      clearRunDrafts()
    }
  }, [clearRunDrafts])

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
    setUploadError('')
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

      const detailPayload = await fetchJson(`/runs/${selectedRunId}${buildQuery(detailFilters)}`)
      applySelectedRun(detailPayload.run)
      setRuns((currentRuns) =>
        currentRuns.map((run) => (run.id === detailPayload.run.id ? { ...run, ...detailPayload.run } : run)),
      )
    } catch (err) {
      setUploadError(`Upload Error: ${err.message}`)
    } finally {
      if (event.target) {
        event.target.value = ''
      }
      setIsUploading(false)
    }
  }

  async function handleCreateRun() {
    setIsCreatingRun(true)
    setCreateRunError('')
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
      selectRun(payload.run.id)
      applySelectedRun({ ...payload.run, images: [], defect_logs: [], event_count: 0 })
      setDismissedSetupRuns((current) => ({ ...current, [payload.run.id]: false }))
    } catch (err) {
      setCreateRunError(`Create Run Error: ${err.message}`)
    } finally {
      setIsCreatingRun(false)
    }
  }

  async function handleSaveModel() {
    if (!selectedRunId || !modelDraft.trim()) {
      return
    }

    setIsSavingModel(true)
    setModelError('')
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
      const nextRun = normalizeRunPayload(payload.run, selectedRun)
      applySelectedRun(nextRun)
      if (nextRun.setup_status !== 'review_ready') {
        setDismissedSetupRuns((current) => ({ ...current, [payload.run.id]: false }))
      }
      setRuns((currentRuns) =>
        currentRuns.map((run) => (run.id === payload.run.id ? { ...run, ...payload.run } : run)),
      )
    } catch (err) {
      setModelError(`Model Save Error: ${err.message}`)
    } finally {
      setIsSavingModel(false)
    }
  }

  async function handleDeleteRun() {
    if (!selectedRunId || isDeletingRun) {
      return
    }
    const confirmed = window.confirm(
      `Delete run ${selectedRun?.pcb_id || selectedRunId}? This removes its history and uploaded scan.`,
    )
    if (!confirmed) {
      return
    }

    setIsDeletingRun(true)
    setError('')
    try {
      const response = await fetch(`/runs/${selectedRunId}`, { method: 'DELETE' })
      const payload = await response.json()
      if (!response.ok || payload.status === 'error') {
        throw new Error(payload.message || 'Delete run failed')
      }

      setRuns((currentRuns) => currentRuns.filter((run) => run.id !== selectedRunId))
      setDismissedSetupRuns((current) => {
        const next = { ...current }
        delete next[selectedRunId]
        return next
      })
      selectRun(null)
    } catch (err) {
      setError(`Delete Run Error: ${err.message}`)
    } finally {
      setIsDeletingRun(false)
    }
  }

  async function updateSetupRun(path, method, body, errorPrefix, onSuccess, setLoading) {
    if (!selectedRunId) {
      return
    }
    if (setLoading) {
      setLoading(true)
    }
    try {
      const response = await fetch(path, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : JSON.stringify({}),
      })
      const payload = await response.json()
      if (!response.ok || payload.status === 'error') {
        throw new Error(payload.message || `${errorPrefix} failed`)
      }
      const nextRun = normalizeRunPayload(payload.run, selectedRun)
      applySelectedRun(nextRun)
      setRuns((currentRuns) =>
        currentRuns.map((run) => (run.id === payload.run.id ? { ...run, ...payload.run } : run)),
      )
      onSuccess?.(nextRun)
    } catch (err) {
      throw new Error(`${errorPrefix}: ${err.message}`)
    } finally {
      if (setLoading) {
        setLoading(false)
      }
    }
  }

  async function handleDetectFiducials() {
    setIsDetectingFiducials(true)
    setFiducialError('')
    try {
      await updateSetupRun(
        `/runs/${selectedRunId}/fiducials/detect`,
        'POST',
        {},
        'Fiducial Detection Error',
        (nextRun) => setManualFiducialsDraft(buildManualFiducialsDraft(nextRun)),
      )
    } catch (err) {
      setFiducialError(err.message)
    } finally {
      setIsDetectingFiducials(false)
    }
  }

  async function handleConfirmFiducials() {
    setFiducialError('')
    try {
      await updateSetupRun(
        `/runs/${selectedRunId}/fiducials/confirm`,
        'POST',
        {},
        'Fiducial Confirm Error',
        (nextRun) => setManualBarcodeDraft(buildManualBarcodeDraft(nextRun)),
      )
    } catch (err) {
      setFiducialError(err.message)
    }
  }

  function handleManualFiducialChange(fiducialId, nextBox) {
    setManualFiducialsDraft((current) =>
      current.map((fiducial, index) =>
        (fiducial.id || `fid-${index + 1}`) === fiducialId
          ? {
              ...fiducial,
              x: nextBox.x.toFixed(4),
              y: nextBox.y.toFixed(4),
              width: nextBox.width.toFixed(4),
              height: nextBox.height.toFixed(4),
            }
          : fiducial,
      ),
    )
  }

  async function handleSaveManualFiducials() {
    setIsSavingManualFiducials(true)
    setFiducialError('')
    try {
      await updateSetupRun(
        `/runs/${selectedRunId}/fiducials/manual`,
        'POST',
        {
          fiducials: manualFiducialsDraft.map((fiducial) => ({
            id: fiducial.id,
            x: Number(fiducial.x),
            y: Number(fiducial.y),
            width: Number(fiducial.width),
            height: Number(fiducial.height),
          })),
        },
        'Manual Fiducial Save Error',
        (nextRun) => setManualFiducialsDraft(buildManualFiducialsDraft(nextRun)),
      )
    } catch (err) {
      setFiducialError(err.message)
    } finally {
      setIsSavingManualFiducials(false)
    }
  }

  async function handleDetectBarcode() {
    setIsDetectingBarcode(true)
    setBarcodeError('')
    try {
      await updateSetupRun(
        `/runs/${selectedRunId}/barcode/detect`,
        'POST',
        {},
        'Barcode Detection Error',
      )
    } catch (err) {
      setBarcodeError(err.message)
    } finally {
      setIsDetectingBarcode(false)
    }
  }

  async function handleConfirmBarcode() {
    setBarcodeError('')
    try {
      await updateSetupRun(
        `/runs/${selectedRunId}/barcode/confirm`,
        'POST',
        {},
        'Barcode Confirm Error',
      )
    } catch (err) {
      setBarcodeError(err.message)
    }
  }

  function handleManualBarcodeChange(nextKeyOrId, nextValue) {
    if (typeof nextKeyOrId === 'string' && typeof nextValue === 'string') {
      setManualBarcodeDraft((current) => ({ ...current, [nextKeyOrId]: nextValue }))
      return
    }
    const nextBox = nextValue
    if (!nextBox) {
      return
    }
    setManualBarcodeDraft((current) => ({
      ...current,
      x: nextBox.x.toFixed(4),
      y: nextBox.y.toFixed(4),
      width: nextBox.width.toFixed(4),
      height: nextBox.height.toFixed(4),
    }))
  }

  async function handleSaveManualBarcode() {
    setIsSavingManualBarcode(true)
    setBarcodeError('')
    try {
      await updateSetupRun(
        `/runs/${selectedRunId}/barcode/manual`,
        'POST',
        {
          barcode: {
            decoded_value: manualBarcodeDraft.decoded_value,
            x: Number(manualBarcodeDraft.x),
            y: Number(manualBarcodeDraft.y),
            width: Number(manualBarcodeDraft.width),
            height: Number(manualBarcodeDraft.height),
          },
        },
        'Manual Barcode Save Error',
        (nextRun) => setManualBarcodeDraft(buildManualBarcodeDraft(nextRun)),
      )
    } catch (err) {
      setBarcodeError(err.message)
    } finally {
      setIsSavingManualBarcode(false)
    }
  }

  function handleContinueToReview() {
    if (!selectedRunId || !isReviewReady) {
      return
    }
    setDismissedSetupRuns((current) => ({ ...current, [selectedRunId]: true }))
  }

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    if (selectedRunId) {
      window.localStorage.setItem(SELECTED_RUN_STORAGE_KEY, selectedRunId)
      return
    }
    window.localStorage.removeItem(SELECTED_RUN_STORAGE_KEY)
  }, [selectedRunId])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    window.localStorage.setItem(DISMISSED_SETUP_STORAGE_KEY, JSON.stringify(dismissedSetupRuns))
  }, [dismissedSetupRuns])

  useEffect(() => {
    const controller = new AbortController()

    async function loadRuns() {
      setRunsLoading(true)
      setError('')
      try {
        const payload = await fetchJson(`/runs${buildQuery(runFilters)}`, controller.signal)
        setRuns(payload.runs)
        if (!payload.runs.length) {
          selectRun(null)
        }
        const validRunIds = new Set(payload.runs.map((run) => run.id))
        setDismissedSetupRuns((current) => {
          const next = Object.fromEntries(Object.entries(current).filter(([runId]) => validRunIds.has(runId)))
          return Object.keys(next).length === Object.keys(current).length ? current : next
        })
        if (selectedRunId && !payload.runs.some((run) => run.id === selectedRunId)) {
          selectRun(null)
        }
      } catch (loadError) {
        if (loadError.name === 'AbortError') {
          return
        }
        setError(loadError.message)
        setRuns([])
        selectRun(null)
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
  }, [runFilters, selectedRunId, selectRun])

  useEffect(() => {
    if (!selectedRunId) {
      return undefined
    }

    const controller = new AbortController()

    async function loadRunDetail() {
      setDetailLoading(true)
      setError('')
      try {
        const payload = await fetchJson(`/runs/${selectedRunId}${buildQuery(detailFilters)}`, controller.signal)
        applySelectedRun(payload.run)
      } catch (loadError) {
        if (loadError.name === 'AbortError') {
          return
        }
        setError(loadError.message)
        selectRun(null)
      } finally {
        setDetailLoading(false)
      }
    }

    loadRunDetail()
    return () => controller.abort()
  }, [selectedRunId, detailFilters, applySelectedRun, selectRun])

  const summary = useMemo(() => {
    const failRuns = runs.filter((run) => run.status === 'FAIL').length
    return {
      runs: runs.length,
      failRuns,
      events: runs.reduce((sum, run) => sum + Number(run.event_count || 0), 0),
    }
  }, [runs])

  const pendingRuns = useMemo(() => runs.filter((run) => run.setup_status !== 'review_ready'), [runs])
  const reviewRuns = useMemo(() => runs.filter((run) => run.setup_status === 'review_ready'), [runs])

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
    if (typeof window === 'undefined' || !selectedRunId) {
      return
    }
    try {
      const rawValue = window.localStorage.getItem(SELECTED_IMAGE_STORAGE_KEY)
      const savedSelections = rawValue ? JSON.parse(rawValue) : {}
      const nextSelections =
        effectiveSelectedImageId === DEFAULT_IMAGE_ID
          ? Object.fromEntries(Object.entries(savedSelections).filter(([runId]) => runId !== selectedRunId))
          : { ...savedSelections, [selectedRunId]: effectiveSelectedImageId }
      window.localStorage.setItem(SELECTED_IMAGE_STORAGE_KEY, JSON.stringify(nextSelections))
    } catch {
      // Ignore localStorage write failures and keep the UI responsive.
    }
  }, [selectedRunId, effectiveSelectedImageId])

  const requiresFiducials = Boolean(selectedRun?.requires_fiducials)
  const fiducialStatus = selectedRun?.fiducial_status || 'not_required'
  const requiresBarcode = Boolean(selectedRun?.requires_barcode)
  const barcodeStatus = selectedRun?.barcode_status || 'not_required'
  const isReviewReady = Boolean(
    selectedRunId &&
    hasScan &&
    hasModel &&
    (!requiresFiducials || fiducialStatus === 'confirmed') &&
    (!requiresBarcode || barcodeStatus === 'confirmed'),
  )

  const setupSteps = useMemo(() => {
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
                : fiducialStatus === 'failed'
                  ? 'Failed'
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
                : barcodeStatus === 'failed'
                  ? 'Failed'
                  : barcodeStatus === 'ready'
                    ? 'Ready'
                    : barcodeStatus === 'blocked'
                      ? 'Blocked'
                      : 'Ready',
      },
      {
        id: 'continue-review',
        order: 6,
        label: 'Continue To Review',
        description: 'Open the normal PCB review surface once required setup is complete.',
        status: isReviewReady ? 'ready' : 'blocked',
        statusLabel: isReviewReady ? 'Ready' : 'Blocked',
      },
    ]

    const autoStepId =
      baseSteps.find((step) => step.status === 'needs_review')?.id ||
      baseSteps.find((step) => step.status === 'ready')?.id ||
      baseSteps.find((step) => step.status === 'blocked')?.id ||
      baseSteps.at(-1)?.id

    const activeStepId = manualStepId && baseSteps.some((step) => step.id === manualStepId) ? manualStepId : autoStepId
    return baseSteps.map((step) => ({ ...step, active: step.id === activeStepId }))
  }, [
    selectedRunId,
    hasScan,
    hasModel,
    requiresFiducials,
    fiducialStatus,
    requiresBarcode,
    barcodeStatus,
    isReviewReady,
    manualStepId,
  ])

  const activeSetupStep = setupSteps.find((step) => step.active) || setupSteps[0]
  const showSetupMode =
    !selectedRun ||
    selectedRun.setup_status !== 'review_ready' ||
    (selectedRun.status === 'SETUP' && !dismissedSetupRuns[selectedRun.id])

  return {
    createRunError,
    detailFilters,
    detailLoading,
    dismissedSetupRuns,
    effectiveSelectedImageId,
    error,
    failCount,
    fileInputRef,
    handleConfirmBarcode,
    handleConfirmFiducials,
    handleContinueToReview,
    handleCreateRun,
    handleDeleteRun,
    handleDetectBarcode,
    handleDetectFiducials,
    handleImageUpload,
    handleManualBarcodeChange,
    handleManualFiducialChange,
    handleSaveManualBarcode,
    handleSaveManualFiducials,
    handleSaveModel,
    hoveredDefectId,
    hudGhostOpacity,
    isCreatingRun,
    isDeletingRun,
    isDetectingBarcode,
    isDetectingFiducials,
    isFiltersOpen,
    isReviewReady,
    isRunRailOpen,
    isSavingManualBarcode,
    isSavingManualFiducials,
    isSavingModel,
    isSettingsOpen,
    isSidebarOpen,
    isUploading,
    manualBarcodeDraft,
    manualFiducialsDraft,
    modelDraft,
    modelError,
    openImagePicker,
    pendingRuns,
    requiresBarcodeDraft,
    requiresFiducialsDraft,
    reviewRuns,
    runFilters,
    runImages,
    runs,
    runsLoading,
    selectedDefect,
    selectedDefectId,
    selectedImage,
    selectedImageId,
    selectedRun,
    selectedRunId,
    setDetailFilters,
    setDismissedSetupRuns,
    setHoveredDefectId,
    setHudGhostOpacity,
    setIsFiltersOpen,
    setIsRunRailOpen,
    setIsSettingsOpen,
    setIsSidebarOpen,
    setManualStepId,
    setModelDraft,
    setRequiresBarcodeDraft,
    setRequiresFiducialsDraft,
    setRunFilters,
    setSelectedDefectId,
    setSelectedImageId,
    setSelectedRunId: selectRun,
    setupSteps,
    showSetupMode,
    stepDefect,
    summary,
    uploadError,
    activeSetupStep,
    barcodeError,
    fiducialError,
    visibleDefects,
  }
}
