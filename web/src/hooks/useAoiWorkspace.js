import { useEffect, useRef, useState } from 'react'

import { DEFAULT_IMAGE_ID } from '../app/constants'
import { useRunData } from './useRunData'
import { useSetupActions } from './useSetupActions'
import { useWorkspacePrefs } from './useWorkspacePrefs'

export function useAoiWorkspace() {
  const [manualStepId, setManualStepId] = useState(null)
  const lastAutoFocusDefectIdRef = useRef(null)
  const prefs = useWorkspacePrefs(DEFAULT_IMAGE_ID)
  const { selectedImageId, setSelectedImageId } = prefs

  const runData = useRunData({
    selectedRunId: prefs.selectedRunId,
    selectedImageId: prefs.selectedImageId,
    dismissedSetupRuns: prefs.dismissedSetupRuns,
    manualStepId,
    selectRun: prefs.selectRun,
    onRunHydrated: null,
  })

  const actions = useSetupActions({
    detailFilters: runData.detailFilters,
    manualStepId,
    selectedRunId: prefs.selectedRunId,
    selectRun: prefs.selectRun,
    setDismissedSetupRuns: prefs.setDismissedSetupRuns,
    setError: runData.setError,
    setRuns: runData.setRuns,
    setSelectedDefectId: runData.setSelectedDefectId,
    setHoveredDefectId: runData.setHoveredDefectId,
    setManualStepId,
    updateSelectedRun: runData.hydrateRun,
  })
  const { syncSetupFromRun } = actions

  useEffect(() => {
    syncSetupFromRun(runData.selectedRun)
  }, [runData.selectedRun, syncSetupFromRun])

  useEffect(() => {
    if (!runData.selectedDefect?.run_image_id || !runData.selectedRun?.images?.length) {
      lastAutoFocusDefectIdRef.current = null
      return
    }
    const defectImage = runData.selectedRun.images.find((image) => image.id === runData.selectedDefect.run_image_id)
    if (!defectImage?.image_role?.startsWith('fov:')) {
      lastAutoFocusDefectIdRef.current = null
      return
    }
    if (lastAutoFocusDefectIdRef.current === runData.selectedDefect.id) {
      return
    }
    lastAutoFocusDefectIdRef.current = runData.selectedDefect.id
    if (selectedImageId === defectImage.id) {
      return
    }
    setSelectedImageId(defectImage.id)
  }, [selectedImageId, setSelectedImageId, runData.selectedDefect, runData.selectedRun])

  function openImagePicker() {
    if (actions.isUploading || !prefs.selectedRunId) {
      return
    }
    prefs.fileInputRef.current?.click()
  }

  return {
    activeSetupStep: runData.activeSetupStep,
    barcodeError: actions.barcodeError,
    createRunError: actions.createRunError,
    detailFilters: runData.detailFilters,
    detailLoading: runData.detailLoading,
    dismissedSetupRuns: prefs.dismissedSetupRuns,
    effectiveSelectedImageId: runData.effectiveSelectedImageId,
    error: runData.error,
    failCount: runData.failCount,
    fovError: actions.fovError,
    fiducialError: actions.fiducialError,
    fileInputRef: prefs.fileInputRef,
    handleConfirmBarcode: actions.handleConfirmBarcode,
    handleConfirmFiducials: actions.handleConfirmFiducials,
    handleContinueToReview: () => actions.handleContinueToReview(runData.isReviewReady),
    handleCreateRun: actions.handleCreateRun,
    handleDeleteRun: actions.handleDeleteRun,
    handleDetectBarcode: actions.handleDetectBarcode,
    handleDetectFiducials: actions.handleDetectFiducials,
    handleGenerateFovs: actions.handleGenerateFovs,
    handleImageUpload: actions.handleImageUpload,
    handleAddFovDraft: actions.handleAddFovDraft,
    handleManualFovChange: actions.handleManualFovChange,
    handleManualFovMetaChange: actions.handleManualFovMetaChange,
    handleManualBarcodeChange: actions.handleManualBarcodeChange,
    handleManualFiducialChange: actions.handleManualFiducialChange,
    handleRemoveFovDraft: actions.handleRemoveFovDraft,
    handleSaveManualBarcode: actions.handleSaveManualBarcode,
    handleSaveManualFiducials: actions.handleSaveManualFiducials,
    handleSaveFovs: actions.handleSaveFovs,
    handleSaveModel: actions.handleSaveModel,
    hoveredDefectId: runData.hoveredDefectId,
    hudGhostOpacity: prefs.hudGhostOpacity,
    isCreatingRun: actions.isCreatingRun,
    isDeletingRun: actions.isDeletingRun,
    isDetectingBarcode: actions.isDetectingBarcode,
    isDetectingFiducials: actions.isDetectingFiducials,
    isGeneratingFovs: actions.isGeneratingFovs,
    isFiltersOpen: prefs.isFiltersOpen,
    isIndustrialTheme: prefs.isIndustrialTheme,
    isKbNavEnabled: prefs.isKbNavEnabled,
    isReviewReady: runData.isReviewReady,
    isRunRailOpen: prefs.isRunRailOpen,
    isSavingManualBarcode: actions.isSavingManualBarcode,
    isSavingManualFiducials: actions.isSavingManualFiducials,
    isSavingFovs: actions.isSavingFovs,
    isSavingModel: actions.isSavingModel,
    isSettingsOpen: prefs.isSettingsOpen,
    isSidebarOpen: prefs.isSidebarOpen,
    isZenMode: prefs.isZenMode,
    isUploading: actions.isUploading,
    kbNavSensitivity: prefs.kbNavSensitivity,
    manualBarcodeDraft: actions.manualBarcodeDraft,
    manualFovDraft: actions.manualFovDraft,
    manualFiducialsDraft: actions.manualFiducialsDraft,
    modelDraft: actions.modelDraft,
    modelError: actions.modelError,
    openImagePicker,
    pendingRuns: runData.pendingRuns,
    requiresBarcodeDraft: actions.requiresBarcodeDraft,
    requiresFiducialsDraft: actions.requiresFiducialsDraft,
    reviewRuns: runData.reviewRuns,
    runFilters: runData.runFilters,
    runImages: runData.runImages,
    runs: runData.runs,
    runsLoading: runData.runsLoading,
    saveDefectReview: runData.saveDefectReview,
    selectedDefect: runData.selectedDefect,
    selectedDefectId: runData.selectedDefectId,
    selectedImage: runData.selectedImage,
    selectedImageId: prefs.selectedImageId,
    selectedRun: runData.selectedRun,
    selectedRunId: prefs.selectedRunId,
    setDetailFilters: runData.setDetailFilters,
    setDismissedSetupRuns: prefs.setDismissedSetupRuns,
    setHoveredDefectId: runData.setHoveredDefectId,
    setHudGhostOpacity: prefs.setHudGhostOpacity,
    setIsFiltersOpen: prefs.setIsFiltersOpen,
    setIsIndustrialTheme: prefs.setIsIndustrialTheme,
    setIsKbNavEnabled: prefs.setIsKbNavEnabled,
    setIsRunRailOpen: prefs.setIsRunRailOpen,
    setIsSettingsOpen: prefs.setIsSettingsOpen,
    setIsSidebarOpen: prefs.setIsSidebarOpen,
    setIsZenMode: prefs.setIsZenMode,
    setKbNavSensitivity: prefs.setKbNavSensitivity,
    setManualStepId,
    setModelDraft: actions.setModelDraft,
    setRequiresBarcodeDraft: actions.setRequiresBarcodeDraft,
    setRequiresFiducialsDraft: actions.setRequiresFiducialsDraft,
    setRunFilters: runData.setRunFilters,
    setSelectedDefectId: runData.setSelectedDefectId,
    setSelectedImageId: prefs.setSelectedImageId,
    setSelectedRunId: prefs.selectRun,
    setupSteps: runData.setupSteps,
    showSetupMode: runData.showSetupMode,
    stepDefect: runData.stepDefect,
    summary: runData.summary,
    uploadError: actions.uploadError,
    visibleDefects: runData.visibleDefects,
  }
}
