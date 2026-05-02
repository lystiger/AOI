import { useCallback, useRef, useState } from 'react'

import { buildManualBarcodeDraft, buildManualFiducialsDraft, buildQuery, fetchJson } from '../app/utils'

function normalizeRunPayload(run, selectedRun) {
  return {
    ...run,
    images: selectedRun?.images || [],
    defect_logs: selectedRun?.defect_logs || [],
    event_count: selectedRun?.event_count || 0,
  }
}

export function useSetupActions({
  detailFilters,
  manualStepId,
  selectedRunId,
  selectRun,
  setDismissedSetupRuns,
  setError,
  setRuns,
  setSelectedDefectId,
  setHoveredDefectId,
  setManualStepId,
  updateSelectedRun,
}) {
  const selectedRunRef = useRef(null)
  const [createRunError, setCreateRunError] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [modelError, setModelError] = useState('')
  const [fiducialError, setFiducialError] = useState('')
  const [barcodeError, setBarcodeError] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [isCreatingRun, setIsCreatingRun] = useState(false)
  const [isSavingModel, setIsSavingModel] = useState(false)
  const [isDetectingFiducials, setIsDetectingFiducials] = useState(false)
  const [isSavingManualFiducials, setIsSavingManualFiducials] = useState(false)
  const [isDetectingBarcode, setIsDetectingBarcode] = useState(false)
  const [isSavingManualBarcode, setIsSavingManualBarcode] = useState(false)
  const [isDeletingRun, setIsDeletingRun] = useState(false)
  const [modelDraft, setModelDraft] = useState('')
  const [requiresFiducialsDraft, setRequiresFiducialsDraft] = useState(false)
  const [requiresBarcodeDraft, setRequiresBarcodeDraft] = useState(false)
  const [manualFiducialsDraft, setManualFiducialsDraft] = useState(() => buildManualFiducialsDraft(null))
  const [manualBarcodeDraft, setManualBarcodeDraft] = useState(() => buildManualBarcodeDraft(null))

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
    selectedRunRef.current = null
  }, [setHoveredDefectId, setManualStepId, setSelectedDefectId])

  const syncSetupFromRun = useCallback((nextRun) => {
    selectedRunRef.current = nextRun
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
  }, [setManualStepId])

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
      updateSelectedRun(detailPayload.run)
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
      const nextRun = { ...payload.run, images: [], defect_logs: [], event_count: 0 }
      setRuns((currentRuns) => [payload.run, ...currentRuns])
      selectRun(payload.run.id)
      updateSelectedRun(nextRun)
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
      const nextRun = normalizeRunPayload(payload.run, selectedRunRef.current)
      updateSelectedRun(nextRun)
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
      `Delete run ${selectedRunRef.current?.pcb_id || selectedRunId}? This removes its history and uploaded scan.`,
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
      updateSelectedRun(null)
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
      const nextRun = normalizeRunPayload(payload.run, selectedRunRef.current)
      updateSelectedRun(nextRun)
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
      await updateSetupRun(`/runs/${selectedRunId}/barcode/detect`, 'POST', {}, 'Barcode Detection Error')
    } catch (err) {
      setBarcodeError(err.message)
    } finally {
      setIsDetectingBarcode(false)
    }
  }

  async function handleConfirmBarcode() {
    setBarcodeError('')
    try {
      await updateSetupRun(`/runs/${selectedRunId}/barcode/confirm`, 'POST', {}, 'Barcode Confirm Error')
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

  function handleContinueToReview(isReviewReady) {
    if (!selectedRunId || !isReviewReady) {
      return
    }
    setDismissedSetupRuns((current) => ({ ...current, [selectedRunId]: true }))
  }

  return {
    barcodeError,
    clearRunDrafts,
    createRunError,
    fiducialError,
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
    isCreatingRun,
    isDeletingRun,
    isDetectingBarcode,
    isDetectingFiducials,
    isSavingManualBarcode,
    isSavingManualFiducials,
    isSavingModel,
    isUploading,
    manualBarcodeDraft,
    manualFiducialsDraft,
    manualStepId,
    modelDraft,
    modelError,
    requiresBarcodeDraft,
    requiresFiducialsDraft,
    setBarcodeError,
    setCreateRunError,
    setManualStepId,
    setModelDraft,
    setRequiresBarcodeDraft,
    setRequiresFiducialsDraft,
    syncSetupFromRun,
    uploadError,
  }
}
