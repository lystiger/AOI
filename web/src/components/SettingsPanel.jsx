export default function SettingsPanel({
  isOpen,
  onClose,
  hudGhostOpacity,
  onHudGhostOpacityChange,
  isKbNavEnabled,
  onKbNavEnabledChange,
  kbNavSensitivity,
  onKbNavSensitivityChange,
  openImagePicker,
  isUploading,
  selectedRunId,
}) {
  if (!isOpen) {
    return null
  }

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-panel" onClick={(event) => event.stopPropagation()}>
        <div className="settings-header">
          <h2>System Settings</h2>
          <button type="button" className="ghost-button" onClick={onClose}>Close</button>
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
                  onChange={(event) => onHudGhostOpacityChange(parseFloat(event.target.value))}
                />
              </div>
            </div>
            <div className="settings-row">
              <span>Show Coordinate Grid</span>
              <input type="checkbox" checked readOnly />
            </div>
            <div className="settings-row">
              <span>Industrial Dark Theme</span>
              <input type="checkbox" checked readOnly />
            </div>
          </section>

          <section className="settings-section">
            <p className="eyebrow">Keyboard Navigation</p>
            <div className="settings-row">
              <span>Enable Keyboard Roaming</span>
              <input
                type="checkbox"
                checked={isKbNavEnabled}
                onChange={(event) => onKbNavEnabledChange(event.target.checked)}
              />
            </div>
            <div className="settings-row">
              <span>Sensitivity</span>
              <div className="settings-control">
                <span className="value-label">{kbNavSensitivity.toFixed(1)}x</span>
                <input
                  type="range"
                  min="0.1"
                  max="5"
                  step="0.1"
                  value={kbNavSensitivity}
                  onChange={(event) => onKbNavSensitivityChange(parseFloat(event.target.value))}
                  disabled={!isKbNavEnabled}
                />
              </div>
            </div>
            <div className="settings-row">
              <span className="compact-note">Use Arrow Keys to pan the PCB viewer when focused.</span>
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
              <input type="checkbox" checked readOnly />
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
