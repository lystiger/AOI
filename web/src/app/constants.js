export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || window.location.origin
export const GRAFANA_BASE_URL = import.meta.env.VITE_GRAFANA_BASE_URL || 'http://localhost:3000'
export const DEFAULT_IMAGE_ID = 'no-image-selected'
export const SELECTED_RUN_STORAGE_KEY = 'aoi:selected-run-id'
export const DISMISSED_SETUP_STORAGE_KEY = 'aoi:dismissed-setup-runs'
export const SELECTED_IMAGE_STORAGE_KEY = 'aoi:selected-images'
export const INDUSTRIAL_THEME_STORAGE_KEY = 'aoi:industrial-theme-enabled'
export const ZEN_MODE_STORAGE_KEY = 'aoi:zen-mode-enabled'

export const RUN_FILTER_DEFAULTS = {
  limit: '15',
  pcb_id: '',
  status: '',
  model_version: '',
  defect_type: '',
}

export const DETAIL_FILTER_DEFAULTS = {
  component_id: '',
  defect_type: '',
  severity: '',
  inspection_result: '',
}

export const DEFAULT_MANUAL_FIDUCIALS = [
  { id: 'fid-1', x: '0.08', y: '0.10', width: '0.035', height: '0.035' },
  { id: 'fid-2', x: '0.86', y: '0.12', width: '0.035', height: '0.035' },
  { id: 'fid-3', x: '0.12', y: '0.82', width: '0.035', height: '0.035' },
]

export const DEFAULT_MODEL_FOVS = [
  { id: 'fov-1', label: 'Power Entry', x: '0.06', y: '0.08', width: '0.22', height: '0.24' },
  { id: 'fov-2', label: 'Logic Core', x: '0.32', y: '0.18', width: '0.30', height: '0.30' },
  { id: 'fov-3', label: 'I/O Edge', x: '0.68', y: '0.12', width: '0.22', height: '0.34' },
]
