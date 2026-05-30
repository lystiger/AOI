import SetupFlow from './SetupFlow'
import PcbViewer from './PcbViewer'
import { DefectListItem, EmptyStateMessage, FilterField, StatusChip } from './shared'
import { formatTimestamp } from '../app/utils'

export default function ReviewWorkspace({ workspace }) {
  const {
    selectedRun,
    selectedRunId,
    selectedImage,
    selectedDefect,
    hoveredDefectId,
    setHoveredDefectId,
    setSelectedDefectId,
    detailLoading,
    failCount,
    fovError,
    showSetupMode,
    runImages,
    effectiveSelectedImageId,
    setSelectedImageId,
    isUploading,
    openImagePicker,
    handleDeleteRun,
    isDeletingRun,
    stepDefect,
    setupSteps,
    activeSetupStep,
    modelDraft,
    setModelDraft,
    requiresFiducialsDraft,
    setRequiresFiducialsDraft,
    requiresBarcodeDraft,
    setRequiresBarcodeDraft,
    handleCreateRun,
    handleSaveModel,
    handleSaveFovs,
    handleGenerateFovs,
    handleAddFovDraft,
    handleRemoveFovDraft,
    handleManualFovChange,
    handleManualFovMetaChange,
    handleDetectFiducials,
    handleConfirmFiducials,
    handleManualFiducialChange,
    handleSaveManualFiducials,
    handleDetectBarcode,
    handleConfirmBarcode,
    handleManualBarcodeChange,
    handleSaveManualBarcode,
    handleContinueToReview,
    setManualStepId,
    isReviewReady,
    isCreatingRun,
    isSavingModel,
    isSavingFovs,
    isGeneratingFovs,
    isDetectingFiducials,
    isSavingManualFiducials,
    isDetectingBarcode,
    isSavingManualBarcode,
    createRunError,
    uploadError,
    modelError,
    fiducialError,
    barcodeError,
    manualFiducialsDraft,
    manualBarcodeDraft,
    manualFovDraft,
    isSidebarOpen,
    isFiltersOpen,
    detailFilters,
    setDetailFilters,
    visibleDefects,
    hudGhostOpacity,
    setDismissedSetupRuns,
  } = workspace
  const hasVisibleDefects = visibleDefects.length > 0
  const isDefectListEmpty = !selectedRunId || !hasVisibleDefects
  const visibleComponents = (selectedRun?.components || []).filter(
    (component) => component.run_image_id === effectiveSelectedImageId,
  )
  const setupImage = runImages.find((image) => image.image_role === 'full_board') || selectedImage

  return (
    <section className="panel review-panel">
      <div className="review-topbar">
        <div className="review-context">
          <div className="review-context-head">
            <p className="eyebrow">Active Review Surface</p>
            {selectedRun ? <StatusChip value={selectedRun.status} /> : null}
          </div>
          <div className="review-runline">
            <div className="review-runline-main">
              <strong>{selectedRun?.pcb_id || 'No run selected'}</strong>
              <span className="compact-meta">{selectedRun ? formatTimestamp(selectedRun.timestamp) : '-'}</span>
              <span className="compact-meta">{failCount} fail defects</span>
            </div>
            {detailLoading ? <span className="loading-indicator">Updating...</span> : null}
          </div>
        </div>
        <div className="review-controls">
          {!showSetupMode ? (
            <div className="review-selectors">
              <button
                type="button"
                className="ghost-button setup-edit-button"
                onClick={() => setDismissedSetupRuns((current) => ({ ...current, [selectedRunId]: false }))}
                disabled={!selectedRunId}
              >
                Edit Setup
              </button>
              <label className="review-image-select field compact">
                <span>Surface</span>
                <select
                  className="image-selector"
                  value={effectiveSelectedImageId}
                  onChange={(event) => setSelectedImageId(event.target.value)}
                  disabled={!runImages.length}
                >
                  {runImages.map((image) => (
                    <option key={image.id} value={image.id}>
                      {image.image_role
                        ? image.image_role
                            .replaceAll('_', ' ')
                            .split(' ')
                            .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
                            .join(' ')
                        : image.id}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          ) : null}
          <div className="review-actions">
            <button
              type="button"
              className={`ghost-button upload-button ${isUploading ? 'loading' : ''}`}
              onClick={openImagePicker}
              disabled={isUploading || !selectedRunId}
            >
              {isUploading ? 'Uploading Scan...' : 'Upload PCB Scan'}
            </button>
            <button
              type="button"
              className="ghost-button delete-button"
              onClick={handleDeleteRun}
              disabled={!selectedRunId || isDeletingRun}
            >
              {isDeletingRun ? 'Deleting Run...' : 'Delete Run'}
            </button>
            {!showSetupMode ? (
              <div className="review-stepper" role="group" aria-label="Step defects">
                <button type="button" className="ghost-button review-nav-button" onClick={() => stepDefect(-1)}>
                  &lt;
                </button>
                <button type="button" className="ghost-button review-nav-button" onClick={() => stepDefect(1)}>
                  &gt;
                </button>
              </div>
            ) : null}
          </div>
          {!selectedRunId ? <span className="upload-helper">Select a run from History to enable upload.</span> : null}
        </div>
      </div>

      {showSetupMode ? (
        <SetupFlow
          steps={setupSteps}
          activeStep={activeSetupStep}
          selectedRun={selectedRun}
          selectedImage={setupImage}
          modelDraft={modelDraft}
          requiresFiducialsDraft={requiresFiducialsDraft}
          requiresBarcodeDraft={requiresBarcodeDraft}
          onModelDraftChange={setModelDraft}
          onRequiresFiducialsChange={setRequiresFiducialsDraft}
          onRequiresBarcodeChange={setRequiresBarcodeDraft}
          onCreateRun={handleCreateRun}
          onUploadScan={openImagePicker}
          onSaveModel={handleSaveModel}
          onSaveFovs={handleSaveFovs}
          onGenerateFovs={handleGenerateFovs}
          onAddFov={handleAddFovDraft}
          onRemoveFov={handleRemoveFovDraft}
          onManualFovChange={handleManualFovChange}
          onManualFovMetaChange={handleManualFovMetaChange}
          onDetectFiducials={handleDetectFiducials}
          onConfirmFiducials={handleConfirmFiducials}
          onManualFiducialsChange={handleManualFiducialChange}
          onSaveManualFiducials={handleSaveManualFiducials}
          onDetectBarcode={handleDetectBarcode}
          onConfirmBarcode={handleConfirmBarcode}
          onManualBarcodeChange={handleManualBarcodeChange}
          onSaveManualBarcode={handleSaveManualBarcode}
          onContinueToReview={handleContinueToReview}
          onStepClick={setManualStepId}
          isContinueReady={isReviewReady}
          isCreatingRun={isCreatingRun}
          isUploading={isUploading}
          isSavingModel={isSavingModel}
          isSavingFovs={isSavingFovs}
          isGeneratingFovs={isGeneratingFovs}
          isDetectingFiducials={isDetectingFiducials}
          isSavingManualFiducials={isSavingManualFiducials}
          isDetectingBarcode={isDetectingBarcode}
          isSavingManualBarcode={isSavingManualBarcode}
          createRunError={createRunError}
          uploadError={uploadError}
          modelError={modelError}
          fovError={fovError}
          fiducialError={fiducialError}
          barcodeError={barcodeError}
          manualFovDraft={manualFovDraft}
          manualFiducialsDraft={manualFiducialsDraft}
          manualBarcodeDraft={manualBarcodeDraft}
        />
      ) : (
        <div className={`review-shell ${!isSidebarOpen ? 'sidebar-collapsed' : ''}`}>
          <aside className="review-sidebar">
            {isFiltersOpen ? (
              <section className="review-card">
                <div className="review-card-header">
                  <div className="review-card-heading">
                    <p className="eyebrow">Defect filters</p>
                    <span className="section-note">Slice the active defect queue</span>
                  </div>
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
                    onChange={(value) => setDetailFilters((current) => ({ ...current, inspection_result: value }))}
                    options={[
                      { label: 'All', value: '' },
                      { label: 'PASS', value: 'PASS' },
                      { label: 'FAIL', value: 'FAIL' },
                    ]}
                  />
                </div>
              </section>
            ) : null}

            <section className={`review-card defect-list-card${isDefectListEmpty ? ' is-empty' : ''}`}>
              <div className="review-card-header">
                <div className="review-card-heading">
                  <p className="eyebrow">Defects</p>
                  <span className="section-note">Live issue stack</span>
                </div>
                <span className="section-note review-count-badge">{visibleDefects.length}</span>
              </div>
              <div className="defect-list">
                {!selectedRunId ? (
                  <EmptyStateMessage
                    title="No defect list yet"
                    body="Choose a run from History first. Defects are loaded per run, so this panel stays empty until one is selected."
                  />
                ) : hasVisibleDefects ? (
                  visibleDefects.map((defect) => (
                    <DefectListItem
                      key={defect.id}
                      defect={defect}
                      active={defect.id === selectedDefect?.id}
                      hovered={defect.id === workspace.hoveredDefectId}
                      onSelect={setSelectedDefectId}
                      onHover={setHoveredDefectId}
                    />
                  ))
                ) : (
                  <div className="empty-state review-empty-inline">No defects matched the current filters.</div>
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
                  components={visibleComponents}
                  defects={visibleDefects}
                  selectedDefect={selectedDefect}
                  hoveredDefectId={hoveredDefectId}
                  isKbNavEnabled={workspace.isKbNavEnabled}
                  kbNavSensitivity={workspace.kbNavSensitivity}
                  isZenMode={workspace.isZenMode}
                  onHover={setHoveredDefectId}
                  onSelectDefect={setSelectedDefectId}
                  onSaveReview={workspace.saveDefectReview}
                  onNextDefect={() => workspace.stepDefect(1)}
                />
                {selectedDefect ? (
                  <div className="floating-inspector" style={{ '--ghost-opacity': hudGhostOpacity }}>
                    <div className="inspector-header">
                      <div className="inspector-heading">
                        <p className="eyebrow">Defect Inspector</p>
                        <strong>{selectedDefect.component_id}</strong>
                      </div>
                      <StatusChip value={selectedDefect.inspection_result} />
                    </div>
                    <div className="inspector-grid">
                      <div className="inspector-item">
                        <span className="eyebrow">Reference</span>
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
                      {selectedDefect.operator_review && selectedDefect.operator_review !== 'NONE' ? (
                        <div className="inspector-item inspector-item-wide">
                          <span className="eyebrow">Human Review</span>
                          <StatusChip value={selectedDefect.operator_review} />
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
