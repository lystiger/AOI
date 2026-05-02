import { useEffect, useState } from 'react'

import { DEFAULT_IMAGE_ID } from '../app/constants'
import { useRunData } from './useRunData'
import { useSetupActions } from './useSetupActions'
import { useWorkspacePrefs } from './useWorkspacePrefs'

export function useAoiWorkspace() {
  const [manualStepId, setManualStepId] = useState(null)
  const prefs = useWorkspacePrefs(DEFAULT_IMAGE_ID)

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
    fiducialError: actions.fiducialError,
    fileInputRef: prefs.fileInputRef,
    handleConfirmBarcode: actions.handleConfirmBarcode,
    handleConfirmFiducials: actions.handleConfirmFiducials,
    handleContinueToReview: () => actions.handleContinueToReview(runData.isReviewReady),
    handleCreateRun: actions.handleCreateRun,
    handleDeleteRun: actions.handleDeleteRun,
    handleDetectBarcode: actions.handleDetectBarcode,
    handleDetectFiducials: actions.handleDetectFiducials,
    handleImageUpload: actions.handleImageUpload,
    handleManualBarcodeChange: actions.handleManualBarcodeChange,
    handleManualFiducialChange: actions.handleManualFiducialChange,
    handleSaveManualBarcode: actions.handleSaveManualBarcode,
    handleSaveManualFiducials: actions.handleSaveManualFiducials,
    handleSaveModel: actions.handleSaveModel,
    hoveredDefectId: runData.hoveredDefectId,
    hudGhostOpacity: prefs.hudGhostOpacity,
    isCreatingRun: actions.isCreatingRun,
    isDeletingRun: actions.isDeletingRun,
    isDetectingBarcode: actions.isDetectingBarcode,
    isDetectingFiducials: actions.isDetectingFiducials,
    isFiltersOpen: prefs.isFiltersOpen,
    isIndustrialTheme: prefs.isIndustrialTheme,
    isKbNavEnabled: prefs.isKbNavEnabled,
    isReviewReady: runData.isReviewReady,
    isRunRailOpen: prefs.isRunRailOpen,
    isSavingManualBarcode: actions.isSavingManualBarcode,
    isSavingManualFiducials: actions.isSavingManualFiducials,
    isSavingModel: actions.isSavingModel,
    isSettingsOpen: prefs.isSettingsOpen,
    isSidebarOpen: prefs.isSidebarOpen,
    isZenMode: prefs.isZenMode,
    isUploading: actions.isUploading,
    kbNavSensitivity: prefs.kbNavSensitivity,
    manualBarcodeDraft: actions.manualBarcodeDraft,
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
