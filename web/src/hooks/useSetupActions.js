import { useCallback, useRef, useState } from 'react'

import { buildManualBarcodeDraft, buildManualFiducialsDraft, buildManualFovDraft, buildQuery, fetchJson } from '../app/utils'
import { useToast } from '../components/toastContext'

function normalizeRunPayload(run, selectedRun) {
  return {
    ...run,
    images: Array.isArray(run?.images) ? run.images : selectedRun?.images || [],
    defect_logs: Array.isArray(run?.defect_logs) ? run.defect_logs : selectedRun?.defect_logs || [],
    event_count: typeof run?.event_count === 'number' ? run.event_count : selectedRun?.event_count || 0,
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
  const toast = useToast()
  const [createRunError, setCreateRunError] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [modelError, setModelError] = useState('')
  const [fovError, setFovError] = useState('')
  const [fiducialError, setFiducialError] = useState('')
  const [barcodeError, setBarcodeError] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isInspecting, setIsInspecting] = useState(false)
  const analyzeTimerRef = useRef(null)
  const [isCreatingRun, setIsCreatingRun] = useState(false)
  const [isSavingModel, setIsSavingModel] = useState(false)
  const [isSavingFovs, setIsSavingFovs] = useState(false)
  const [isGeneratingFovs, setIsGeneratingFovs] = useState(false)
  const [isDetectingFiducials, setIsDetectingFiducials] = useState(false)
  const [isSavingManualFiducials, setIsSavingManualFiducials] = useState(false)
  const [isDetectingBarcode, setIsDetectingBarcode] = useState(false)
  const [isSavingManualBarcode, setIsSavingManualBarcode] = useState(false)
  const [isDeletingRun, setIsDeletingRun] = useState(false)
  const [modelDraft, setModelDraft] = useState('')
  const [requiresFovsDraft, setRequiresFovsDraft] = useState(false)
  const [requiresFiducialsDraft, setRequiresFiducialsDraft] = useState(false)
  const [requiresBarcodeDraft, setRequiresBarcodeDraft] = useState(false)
  const [manualFovDraft, setManualFovDraft] = useState(() => buildManualFovDraft(null))
  const [manualFiducialsDraft, setManualFiducialsDraft] = useState(() => buildManualFiducialsDraft(null))
  const [manualBarcodeDraft, setManualBarcodeDraft] = useState(() => buildManualBarcodeDraft(null))

  const clearRunDrafts = useCallback(() => {
    setModelDraft('')
    setRequiresFovsDraft(false)
    setRequiresFiducialsDraft(false)
    setRequiresBarcodeDraft(false)
    setManualFovDraft(buildManualFovDraft(null))
    setManualFiducialsDraft(buildManualFiducialsDraft(null))
    setManualBarcodeDraft(buildManualBarcodeDraft(null))
    setManualStepId(null)
    setCreateRunError('')
    setUploadError('')
    setModelError('')
    setFovError('')
    setFiducialError('')
    setBarcodeError('')
    setSelectedDefectId(null)
    setHoveredDefectId(null)
    selectedRunRef.current = null
  }, [setHoveredDefectId, setManualStepId, setSelectedDefectId])

  const syncSetupFromRun = useCallback((nextRun) => {
    selectedRunRef.current = nextRun
    setModelDraft(nextRun?.model_name || '')
    setRequiresFovsDraft(Boolean(nextRun?.requires_fovs))
    setRequiresFiducialsDraft(Boolean(nextRun?.requires_fiducials))
    setRequiresBarcodeDraft(Boolean(nextRun?.requires_barcode))
    setManualFovDraft(buildManualFovDraft(nextRun))
    setManualFiducialsDraft(buildManualFiducialsDraft(nextRun))
    setManualBarcodeDraft(buildManualBarcodeDraft(nextRun))
    setManualStepId(null)
    setCreateRunError('')
    setUploadError('')
    setModelError('')
    setFovError('')
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
      toast.success('PCB scan uploaded successfully')

      // Poll for component detection completion so the UI shows "Analyzing..." feedback.
      if (analyzeTimerRef.current) {
        clearInterval(analyzeTimerRef.current)
      }
      setIsAnalyzing(true)
      let pollCount = 0
      analyzeTimerRef.current = setInterval(async () => {
        pollCount += 1
        try {
          const pollPayload = await fetchJson(`/runs/${selectedRunId}${buildQuery(detailFilters)}`)
          const status = pollPayload.run?.component_detection_status
          if (status === 'detected' || status === 'failed' || pollCount >= 10) {
            clearInterval(analyzeTimerRef.current)
            analyzeTimerRef.current = null
            setIsAnalyzing(false)
            updateSelectedRun(pollPayload.run)
            setRuns((currentRuns) =>
              currentRuns.map((run) => (run.id === pollPayload.run.id ? { ...run, ...pollPayload.run } : run)),
            )
          }
        } catch {
          clearInterval(analyzeTimerRef.current)
          analyzeTimerRef.current = null
          setIsAnalyzing(false)
        }
      }, 2000)
    } catch (err) {
      setUploadError(`Upload Error: ${err.message}`)
      toast.error(`Upload failed: ${err.message}`)
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
      toast.success('New setup run created')
    } catch (err) {
      setCreateRunError(`Create Run Error: ${err.message}`)
      toast.error(`Failed to create run: ${err.message}`)
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
          requires_fovs: requiresFovsDraft,
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
      toast.success('Model configuration saved')
    } catch (err) {
      setModelError(`Model Save Error: ${err.message}`)
      toast.error(`Failed to save model: ${err.message}`)
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
      toast.success('Run deleted successfully')
    } catch (err) {
      setError(`Delete Run Error: ${err.message}`)
      toast.error(`Failed to delete run: ${err.message}`)
    } finally {
      setIsDeletingRun(false)
    }
  }

  function handleManualFovChange(fovId, nextBox) {
    setManualFovDraft((current) =>
      current.map((fov, index) =>
        (fov.id || `fov-${index + 1}`) === fovId
          ? {
              ...fov,
              x: nextBox.x.toFixed(4),
              y: nextBox.y.toFixed(4),
              width: nextBox.width.toFixed(4),
              height: nextBox.height.toFixed(4),
            }
          : fov,
      ),
    )
  }

  function handleManualFovMetaChange(fovId, key, value) {
    setManualFovDraft((current) =>
      current.map((fov, index) =>
        (fov.id || `fov-${index + 1}`) === fovId
          ? {
              ...fov,
              [key]: value,
            }
          : fov,
      ),
    )
  }

  function handleAddFovDraft() {
    setManualFovDraft((current) => [
      ...current,
      {
        id: `fov-${current.length + 1}`,
        label: `FOV ${current.length + 1}`,
        x: '0.15',
        y: '0.15',
        width: '0.18',
        height: '0.18',
      },
    ])
  }

  function handleRemoveFovDraft(fovId) {
    setManualFovDraft((current) => (current.length > 1 ? current.filter((fov) => fov.id !== fovId) : current))
  }

  async function handleSaveFovs() {
    if (!selectedRunId) {
      return
    }
    const modelName = (selectedRunRef.current?.model_name || modelDraft || '').trim()
    if (!modelName) {
      setFovError('Save FOV Error: model name is required before saving FOVs')
      return
    }

    setIsSavingFovs(true)
    setFovError('')
    try {
      const response = await fetch(`/models/${encodeURIComponent(modelName)}/fovs`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fovs: manualFovDraft.map((fov, index) => ({
            id: fov.id || `fov-${index + 1}`,
            label: (fov.label || '').trim(),
            x: Number(fov.x),
            y: Number(fov.y),
            width: Number(fov.width),
            height: Number(fov.height),
          })),
        }),
      })
      const payload = await response.json()
      if (!response.ok || payload.status === 'error') {
        throw new Error(payload.message || 'Save FOVs failed')
      }

      const nextRun = {
        ...normalizeRunPayload(selectedRunRef.current, selectedRunRef.current),
        model_name: modelName,
        model_fovs: payload.fovs,
      }
      updateSelectedRun(nextRun)
      setManualFovDraft(buildManualFovDraft(nextRun))
      toast.success('Model FOVs saved')
    } catch (err) {
      setFovError(`Save FOV Error: ${err.message}`)
      toast.error(`Failed to save FOVs: ${err.message}`)
    } finally {
      setIsSavingFovs(false)
    }
  }

  async function handleGenerateFovs() {
    if (!selectedRunId) {
      return
    }
    setIsGeneratingFovs(true)
    setFovError('')
    try {
      await updateSetupRun(`/runs/${selectedRunId}/fovs/generate`, 'POST', {}, 'FOV Generate Error', (nextRun) => {
        setManualFovDraft(buildManualFovDraft(nextRun))
        toast.success('FOV crops generated')
      })
    } catch (err) {
      setFovError(err.message)
      toast.error(err.message)
    } finally {
      setIsGeneratingFovs(false)
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
        (nextRun) => {
          setManualFiducialsDraft(buildManualFiducialsDraft(nextRun))
          toast.success('Fiducials detected successfully')
        },
      )
    } catch (err) {
      setFiducialError(err.message)
      toast.error(err.message)
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
        (nextRun) => {
          setManualBarcodeDraft(buildManualBarcodeDraft(nextRun))
          toast.success('Fiducial alignment confirmed')
        },
      )
    } catch (err) {
      setFiducialError(err.message)
      toast.error(err.message)
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
        (nextRun) => {
          setManualFiducialsDraft(buildManualFiducialsDraft(nextRun))
          toast.success('Manual fiducials saved')
        },
      )
    } catch (err) {
      setFiducialError(err.message)
      toast.error(err.message)
    } finally {
      setIsSavingManualFiducials(false)
    }
  }

  async function handleDetectBarcode() {
    setIsDetectingBarcode(true)
    setBarcodeError('')
    try {
      await updateSetupRun(`/runs/${selectedRunId}/barcode/detect`, 'POST', {}, 'Barcode Detection Error', () => {
        toast.success('Barcode detected successfully')
      })
    } catch (err) {
      setBarcodeError(err.message)
      toast.error(err.message)
    } finally {
      setIsDetectingBarcode(false)
    }
  }

  async function handleConfirmBarcode() {
    setBarcodeError('')
    try {
      await updateSetupRun(`/runs/${selectedRunId}/barcode/confirm`, 'POST', {}, 'Barcode Confirm Error', () => {
        toast.success('Barcode alignment confirmed')
      })
    } catch (err) {
      setBarcodeError(err.message)
      toast.error(err.message)
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
        (nextRun) => {
          setManualBarcodeDraft(buildManualBarcodeDraft(nextRun))
          toast.success('Manual barcode saved')
        },
      )
    } catch (err) {
      setBarcodeError(err.message)
      toast.error(err.message)
    } finally {
      setIsSavingManualBarcode(false)
    }
  }

  function handleContinueToReview(isReviewReady) {
    if (!selectedRunId || !isReviewReady) {
      return
    }
    setDismissedSetupRuns((current) => ({ ...current, [selectedRunId]: true }))
    toast.info('Transitioning to normal review mode')
  }

  async function handleRunInspection() {
    if (!selectedRunId || isInspecting) {
      return
    }
    setIsInspecting(true)
    setError('')
    try {
      await updateSetupRun(`/runs/${selectedRunId}/inspect`, 'POST', {}, 'Inspection Error', (nextRun) => {
        const failCount = (nextRun.defect_logs || []).filter(
          (defect) => defect.inspection_result === 'FAIL',
        ).length
        toast.success(
          failCount > 0
            ? `Inspection complete: ${failCount} defect${failCount === 1 ? '' : 's'} found`
            : 'Inspection complete: board passed',
        )
      })
    } catch (err) {
      setError(err.message)
      toast.error(err.message)
    } finally {
      setIsInspecting(false)
    }
  }

  return {
    barcodeError,
    clearRunDrafts,
    createRunError,
    fovError,
    fiducialError,
    handleAddFovDraft,
    handleConfirmBarcode,
    handleConfirmFiducials,
    handleContinueToReview,
    handleCreateRun,
    handleDeleteRun,
    handleDetectBarcode,
    handleDetectFiducials,
    handleGenerateFovs,
    handleImageUpload,
    handleManualFovChange,
    handleManualFovMetaChange,
    handleManualBarcodeChange,
    handleManualFiducialChange,
    handleRemoveFovDraft,
    handleRunInspection,
    handleSaveManualBarcode,
    handleSaveManualFiducials,
    handleSaveFovs,
    handleSaveModel,
    isAnalyzing,
    isCreatingRun,
    isDeletingRun,
    isDetectingBarcode,
    isDetectingFiducials,
    isGeneratingFovs,
    isInspecting,
    isSavingManualBarcode,
    isSavingManualFiducials,
    isSavingFovs,
    isSavingModel,
    isUploading,
    manualBarcodeDraft,
    manualFovDraft,
    manualFiducialsDraft,
    manualStepId,
    modelDraft,
    modelError,
    requiresBarcodeDraft,
    requiresFovsDraft,
    requiresFiducialsDraft,
    setBarcodeError,
    setCreateRunError,
    setManualStepId,
    setModelDraft,
    setRequiresBarcodeDraft,
    setRequiresFovsDraft,
    setRequiresFiducialsDraft,
    syncSetupFromRun,
    uploadError,
  }
}
