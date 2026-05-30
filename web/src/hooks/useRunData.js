import { useCallback, useEffect, useMemo, useState } from 'react'

import { DEFAULT_IMAGE_ID, DETAIL_FILTER_DEFAULTS, RUN_FILTER_DEFAULTS } from '../app/constants'
import { buildQuery, fetchJson } from '../app/utils'

export function useRunData({
  selectedRunId,
  selectedImageId,
  dismissedSetupRuns,
  manualStepId,
  selectRun,
  onRunHydrated,
}) {
  const [runFilters, setRunFilters] = useState(RUN_FILTER_DEFAULTS)
  const [detailFilters, setDetailFilters] = useState(DETAIL_FILTER_DEFAULTS)
  const [runs, setRuns] = useState([])
  const [selectedRun, setSelectedRun] = useState(null)
  const [selectedDefectId, setSelectedDefectId] = useState(null)
  const [hoveredDefectId, setHoveredDefectId] = useState(null)
  const [runsLoading, setRunsLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')

  const hydrateRun = useCallback((nextRun) => {
    setSelectedRun(nextRun)
    onRunHydrated?.(nextRun)
  }, [onRunHydrated])

  useEffect(() => {
    const controller = new AbortController()

    async function loadRuns() {
      setRunsLoading(true)
      setError('')
      try {
        const payload = await fetchJson(`/runs${buildQuery(runFilters)}`, controller.signal)
        setRuns(payload.runs)
        if (!payload.runs.length) {
          hydrateRun(null)
          selectRun(null)
        }
        const validRunIds = new Set(payload.runs.map((run) => run.id))
        if (selectedRunId && !payload.runs.some((run) => run.id === selectedRunId)) {
          hydrateRun(null)
          selectRun(null)
        }
        if (Object.keys(dismissedSetupRuns).some((runId) => !validRunIds.has(runId))) {
          // cleanup stays in parent prefs state
        }
      } catch (loadError) {
        if (loadError.name === 'AbortError') {
          return
        }
        setError(loadError.message)
        setRuns([])
        hydrateRun(null)
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
  }, [dismissedSetupRuns, hydrateRun, runFilters, selectRun, selectedRunId])

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
        hydrateRun(payload.run)
      } catch (loadError) {
        if (loadError.name === 'AbortError') {
          return
        }
        setError(loadError.message)
        hydrateRun(null)
        selectRun(null)
      } finally {
        setDetailLoading(false)
      }
    }

    loadRunDetail()
    return () => controller.abort()
  }, [detailFilters, hydrateRun, selectRun, selectedRunId])

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

  const stepDefect = useCallback((direction) => {
    if (!visibleDefects.length) {
      return
    }
    const currentIndex = visibleDefects.findIndex((defect) => defect.id === effectiveSelectedDefectId)
    const safeIndex = currentIndex === -1 ? 0 : currentIndex
    const nextIndex = (safeIndex + direction + visibleDefects.length) % visibleDefects.length
    setSelectedDefectId(visibleDefects[nextIndex].id)
  }, [effectiveSelectedDefectId, visibleDefects])

  async function saveDefectReview(defectId, status) {
    if (!selectedRunId) return

    try {
      const response = await fetch(`/runs/${selectedRunId}/defects/${defectId}/review`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      const payload = await response.json()
      if (!response.ok || payload.status === 'error') {
        throw new Error(payload.message || 'Review save failed')
      }

      // Update local state for immediate feedback
      setSelectedRun((current) => {
        if (!current) return current
        return {
          ...current,
          defect_logs: current.defect_logs.map((d) =>
            d.id === defectId ? { ...d, operator_review: status } : d,
          ),
        }
      })
      return true
    } catch (err) {
      setError(`Review Error: ${err.message}`)
      return false
    }
  }

  const failCount = defects.filter((defect) => defect.inspection_result === 'FAIL').length
  const hasScan = runImages.length > 0
  const hasModel = Boolean(selectedRun?.model_name?.trim())
  const requiresFiducials = Boolean(selectedRun?.requires_fiducials)
  const fiducialStatus = selectedRun?.fiducial_status || 'not_required'
  const requiresBarcode = Boolean(selectedRun?.requires_barcode)
  const barcodeStatus = selectedRun?.barcode_status || 'not_required'
  const componentDetectionStatus = selectedRun?.component_detection_status || (hasScan ? 'empty' : 'blocked')
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
        id: 'component-scan',
        order: 3,
        label: 'Auto Detect Components',
        description: 'Run the automatic PCB component scan as soon as a board image is attached.',
        status:
          !selectedRunId || !hasScan
            ? 'blocked'
            : componentDetectionStatus === 'detected'
              ? 'done'
              : componentDetectionStatus === 'failed'
                ? 'needs_review'
                : componentDetectionStatus === 'empty'
                  ? 'ready'
                  : componentDetectionStatus,
        statusLabel:
          !selectedRunId || !hasScan
            ? 'Blocked'
            : componentDetectionStatus === 'detected'
              ? 'Done'
              : componentDetectionStatus === 'failed'
                ? 'Needs Review'
                : componentDetectionStatus === 'empty'
                  ? 'No Matches'
                  : componentDetectionStatus === 'blocked'
                    ? 'Blocked'
                    : 'Ready',
      },
      {
        id: 'enter-model',
        order: 4,
        label: 'Enter Model Name',
        description: 'Set the product context before optional automation steps are evaluated.',
        status: !selectedRunId ? 'blocked' : hasModel ? 'done' : 'ready',
        statusLabel: !selectedRunId ? 'Blocked' : hasModel ? 'Done' : 'Ready',
      },
      {
        id: 'fiducials',
        order: 5,
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
        order: 6,
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
        order: 7,
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
    barcodeStatus,
    fiducialStatus,
    hasModel,
    hasScan,
    isReviewReady,
    manualStepId,
    componentDetectionStatus,
    requiresBarcode,
    requiresFiducials,
    selectedRunId,
  ])

  const activeSetupStep = setupSteps.find((step) => step.active) || setupSteps[0]
  const showSetupMode =
    !selectedRun ||
    selectedRun.setup_status !== 'review_ready' ||
    (selectedRun.status === 'SETUP' && !dismissedSetupRuns[selectedRun.id])

  return {
    activeSetupStep,
    detailFilters,
    detailLoading,
    effectiveSelectedImageId,
    error,
    failCount,
    hoveredDefectId,
    isReviewReady,
    pendingRuns,
    reviewRuns,
    runFilters,
    runImages,
    runs,
    runsLoading,
    selectedDefect,
    selectedDefectId,
    selectedImage,
    selectedRun,
    setDetailFilters,
    setError,
    setHoveredDefectId,
    setRuns,
    setRunFilters,
    setSelectedDefectId,
    setSelectedRun,
    setupSteps,
    showSetupMode,
    stepDefect,
    summary,
    visibleDefects,
    hydrateRun,
    saveDefectReview,
  }
}
