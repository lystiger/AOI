import EditableOverlayPreview from './EditableOverlayPreview'
import { formatFiducialLabel, toNormalizedNumber, toPositiveNormalizedNumber } from '../app/utils'

function FiducialPreview({ image, fiducials, editableFiducials, onChangeFiducial }) {
  if (!image) {
    return <div className="empty-state">Upload a scan to preview fiducial detection.</div>
  }

  if (editableFiducials?.length && onChangeFiducial) {
    return (
      <EditableOverlayPreview
        image={image}
        overlays={editableFiducials}
        onChange={onChangeFiducial}
        kind="fiducial"
      />
    )
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

function BarcodePreview({ image, barcode, editableBarcode, onChangeBarcode }) {
  if (!image) {
    return <div className="empty-state">Upload a scan to preview barcode detection.</div>
  }
  if (editableBarcode && onChangeBarcode) {
    return (
      <EditableOverlayPreview
        image={image}
        overlays={[editableBarcode]}
        onChange={onChangeBarcode}
        kind="barcode"
      />
    )
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

function ComponentPreview({ image, components }) {
  if (!image) {
    return <div className="empty-state">Upload a scan to preview automatic component detection.</div>
  }

  if (!components?.length) {
    return <div className="empty-state">No component candidates were detected from the current board image.</div>
  }

  return (
    <div className="fiducial-preview">
      <img src={image.image_path} alt="Component preview" />
      {components.map((component) => (
        <div
          key={component.id}
          className="component-box"
          style={{
            left: `${component.x * 100}%`,
            top: `${component.y * 100}%`,
            width: `${component.width * 100}%`,
            height: `${component.height * 100}%`,
          }}
        >
          <span>{Math.round((component.confidence || 0) * 100)}%</span>
        </div>
      ))}
    </div>
  )
}

function FovPreview({ image, editableFovs, onChangeFov }) {
  if (!image) {
    return <div className="empty-state">Upload a scan to define field-of-view regions.</div>
  }

  return <EditableOverlayPreview image={image} overlays={editableFovs} onChange={onChangeFov} kind="fov" />
}

export default function SetupFlow({
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
  onSaveFovs,
  onGenerateFovs,
  onAddFov,
  onRemoveFov,
  onManualFovChange,
  onManualFovMetaChange,
  onDetectFiducials,
  onConfirmFiducials,
  onManualFiducialsChange,
  onSaveManualFiducials,
  onDetectBarcode,
  onConfirmBarcode,
  onManualBarcodeChange,
  onSaveManualBarcode,
  onContinueToReview,
  onStepClick,
  isContinueReady,
  isCreatingRun,
  isUploading,
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
  fovError,
  fiducialError,
  barcodeError,
  manualFovDraft,
  manualFiducialsDraft,
  manualBarcodeDraft,
}) {
  const editableFovs = manualFovDraft.map((fov, index) => ({
    id: fov.id || `fov-${index + 1}`,
    x: toNormalizedNumber(fov.x, 0.1),
    y: toNormalizedNumber(fov.y, 0.1),
    width: toPositiveNormalizedNumber(fov.width, 0.18),
    height: toPositiveNormalizedNumber(fov.height, 0.18),
    label: fov.label || `FOV ${index + 1}`,
  }))
  const editableFiducials = manualFiducialsDraft.map((fiducial, index) => ({
    id: fiducial.id || `fid-${index + 1}`,
    x: toNormalizedNumber(fiducial.x),
    y: toNormalizedNumber(fiducial.y),
    width: toPositiveNormalizedNumber(fiducial.width, 0.035),
    height: toPositiveNormalizedNumber(fiducial.height, 0.035),
    label: formatFiducialLabel(index),
  }))
  const editableBarcode = manualBarcodeDraft
    ? {
        id: 'barcode-1',
        x: toNormalizedNumber(manualBarcodeDraft.x, 0.72),
        y: toNormalizedNumber(manualBarcodeDraft.y, 0.78),
        width: toPositiveNormalizedNumber(manualBarcodeDraft.width, 0.16),
        height: toPositiveNormalizedNumber(manualBarcodeDraft.height, 0.08),
        label: manualBarcodeDraft.decoded_value || 'barcode',
      }
    : null

  return (
    <div className="setup-shell">
      <aside className="setup-steps">
        <div className="setup-steps-header">
          <p className="eyebrow">Pre-Program Setup</p>
          <h2>Prepare This Run</h2>
        </div>
        <div className="setup-step-list">
          {steps.map((step) => (
            <div
              key={step.id}
              className={`setup-step-card ${step.active ? 'active' : ''}`}
              onClick={() => onStepClick?.(step.id)}
              style={{ cursor: 'pointer' }}
            >
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
              {createRunError ? <div className="step-error-message">{createRunError}</div> : null}
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
              {uploadError ? <div className="step-error-message">{uploadError}</div> : null}
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
              {modelError ? <div className="step-error-message">{modelError}</div> : null}
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

          {activeStep.id === 'component-scan' ? (
            <div className="setup-action-card">
              <p>
                Component detection runs automatically after image upload. Review the candidate overlays here before
                proceeding with the rest of setup.
              </p>
              <ComponentPreview image={selectedImage} components={selectedRun?.components || []} />
              <div className="manual-setup-grid compact">
                <div className="manual-setup-item compact">
                  <strong>Detection Status</strong>
                  <span>{selectedRun?.component_detection_status || 'blocked'}</span>
                </div>
                <div className="manual-setup-item compact">
                  <strong>Detected Candidates</strong>
                  <span>{selectedRun?.components?.length || 0}</span>
                </div>
              </div>
            </div>
          ) : null}

          {activeStep.id === 'fovs' ? (
            <div className="setup-grid">
              {!selectedRun?.model_name?.trim() ? (
                <div className="empty-guidance">
                  <strong>Model name required</strong>
                  <p>Save the model name first so these FOV definitions are attached to the correct product.</p>
                </div>
              ) : !selectedImage ? (
                <div className="empty-guidance">
                  <strong>Board scan required</strong>
                  <p>Upload a full-board scan before defining mechanical field-of-view regions.</p>
                </div>
              ) : (
                <>
                  <div className="setup-action-card">
                    <p>
                      Define named field-of-view regions on the full board image, save them to the model, then
                      generate reusable crop surfaces for review and training.
                    </p>
                    {fovError ? <div className="step-error-message">{fovError}</div> : null}
                    <FovPreview image={selectedImage} editableFovs={editableFovs} onChangeFov={onManualFovChange} />
                    <div className="setup-button-row">
                      <button type="button" className="ghost-button" onClick={onAddFov}>
                        Add FOV
                      </button>
                      <button type="button" className="primary-button" onClick={onSaveFovs} disabled={isSavingFovs}>
                        {isSavingFovs ? 'Saving FOVs...' : 'Save FOV Layout'}
                      </button>
                      <button
                        type="button"
                        className="ghost-button"
                        onClick={onGenerateFovs}
                        disabled={isGeneratingFovs || !(selectedRun?.model_fovs?.length || 0)}
                      >
                        {isGeneratingFovs ? 'Generating Crops...' : 'Generate FOV Crops'}
                      </button>
                    </div>
                  </div>

                  <div className="setup-inspector">
                    <div className="manual-setup-card">
                      <strong>Named FOV Regions</strong>
                      <p>Drag the overlays to place them. Edit each label here so generated crop surfaces stay readable.</p>
                      <div className="manual-setup-list">
                        {editableFovs.map((fov) => (
                          <div key={fov.id} className="manual-setup-item">
                            <label className="field compact">
                              <span>Label</span>
                              <input
                                value={manualFovDraft.find((entry) => entry.id === fov.id)?.label || ''}
                                onChange={(event) => onManualFovMetaChange(fov.id, 'label', event.target.value)}
                              />
                            </label>
                            <span className="compact-meta">
                              x {fov.x.toFixed(3)} y {fov.y.toFixed(3)} w {fov.width.toFixed(3)} h {fov.height.toFixed(3)}
                            </span>
                            <button
                              type="button"
                              className="ghost-button slim-button"
                              onClick={() => onRemoveFov(fov.id)}
                              disabled={editableFovs.length <= 1}
                            >
                              Remove
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="manual-setup-card">
                      <strong>Generated Crop Surfaces</strong>
                      {(selectedRun?.images || []).some((image) => image.image_role?.startsWith('fov:')) ? (
                        <div className="fiducial-list">
                          {selectedRun.images
                            .filter((image) => image.image_role?.startsWith('fov:'))
                            .map((image) => (
                              <div key={image.id} className="fiducial-list-item">
                                <strong>{image.image_role.replace('fov:', '')}</strong>
                                <span>
                                  {image.image_width} x {image.image_height}
                                </span>
                              </div>
                            ))}
                        </div>
                      ) : (
                        <div className="empty-state">No FOV crop images generated yet.</div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          ) : null}

          {activeStep.id === 'fiducials' ? (
            <div className="setup-action-card">
              {!selectedRun?.requires_fiducials ? (
                <p>Fiducials are not required for this product. Enable them in the model step if the product needs alignment marks.</p>
              ) : (
                <>
                  <p>
                    Run automated fiducial search, review the overlay results, then confirm when the locations look
                    correct. If detection fails, enter the fiducial boxes manually and save them to recover setup.
                  </p>
                  {fiducialError ? <div className="step-error-message">{fiducialError}</div> : null}
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
                  <div className="manual-setup-card">
                    <strong>Manual Fiducial Recovery</strong>
                    <p>Drag a box to move it. Drag from an edge or corner to resize it. Use arrow keys to nudge, and `Alt` + arrow keys to resize from the keyboard.</p>
                    <FiducialPreview
                      image={selectedImage}
                      editableFiducials={editableFiducials}
                      onChangeFiducial={onManualFiducialsChange}
                    />
                    <div className="manual-setup-grid compact">
                      {editableFiducials.map((fiducial) => (
                        <div key={fiducial.id} className="manual-setup-item compact">
                          <strong>{fiducial.label}</strong>
                          <span>
                            x {fiducial.x.toFixed(3)} y {fiducial.y.toFixed(3)} w {fiducial.width.toFixed(3)} h {fiducial.height.toFixed(3)}
                          </span>
                        </div>
                      ))}
                    </div>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={onSaveManualFiducials}
                      disabled={isSavingManualFiducials || !selectedImage}
                    >
                      {isSavingManualFiducials ? 'Saving Manual Fiducials...' : 'Save Manual Fiducials'}
                    </button>
                  </div>
                  {selectedRun?.fiducials?.length ? (
                    <div className="fiducial-list">
                      {selectedRun.fiducials.map((fiducial, index) => (
                        <div key={fiducial.id} className="fiducial-list-item">
                          <strong>{formatFiducialLabel(index)}</strong>
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
                  <p>
                    Run automated barcode search, review the decoded result, then confirm when the location and value
                    are correct. If detection fails, enter the barcode box and decoded value manually.
                  </p>
                  {barcodeError ? <div className="step-error-message">{barcodeError}</div> : null}
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
                  <div className="manual-setup-card">
                    <strong>Manual Barcode Recovery</strong>
                    <p>Drag the barcode box to the correct region, update the decoded value if needed, then save.</p>
                    <BarcodePreview image={selectedImage} editableBarcode={editableBarcode} onChangeBarcode={onManualBarcodeChange} />
                    <div className="manual-setup-fields">
                      <label className="field compact">
                        <span>Decoded</span>
                        <input
                          value={manualBarcodeDraft.decoded_value}
                          onChange={(event) => onManualBarcodeChange('decoded_value', event.target.value)}
                        />
                      </label>
                    </div>
                    <div className="manual-setup-grid compact">
                      <div className="manual-setup-item compact">
                        <strong>barcode-1</strong>
                        <span>
                          x {editableBarcode?.x.toFixed(3)} y {editableBarcode?.y.toFixed(3)} w {editableBarcode?.width.toFixed(3)} h {editableBarcode?.height.toFixed(3)}
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={onSaveManualBarcode}
                      disabled={isSavingManualBarcode || !selectedImage}
                    >
                      {isSavingManualBarcode ? 'Saving Manual Barcode...' : 'Save Manual Barcode'}
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
              <button type="button" className="primary-button" onClick={onContinueToReview} disabled={!isContinueReady}>
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
            <span>Model FOVs</span>
            <strong>
              {(selectedRun?.model_fovs?.length || 0) > 0 ? `${selectedRun?.model_fovs?.length || 0} saved` : 'Unset'}
            </strong>
            <span>Components</span>
            <strong>
              {selectedRun?.images?.length
                ? `${selectedRun?.component_detection_status || 'blocked'} (${selectedRun?.components?.length || 0})`
                : 'Blocked'}
            </strong>
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
