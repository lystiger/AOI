import { DEFAULT_MANUAL_FIDUCIALS } from './constants'

export function formatFiducialLabel(index) {
  return `mark-${index + 1}`
}

export function buildManualFiducialsDraft(run) {
  if (run?.fiducials?.length) {
    return run.fiducials.map((fiducial, index) => ({
      id: fiducial.id || `fid-${index + 1}`,
      x: String(fiducial.x ?? ''),
      y: String(fiducial.y ?? ''),
      width: String(fiducial.width ?? ''),
      height: String(fiducial.height ?? ''),
    }))
  }
  return DEFAULT_MANUAL_FIDUCIALS.map((fiducial) => ({ ...fiducial }))
}

export function buildManualBarcodeDraft(run) {
  if (run?.barcode) {
    return {
      decoded_value: run.barcode.decoded_value || '',
      x: String(run.barcode.x ?? ''),
      y: String(run.barcode.y ?? ''),
      width: String(run.barcode.width ?? ''),
      height: String(run.barcode.height ?? ''),
    }
  }
  return {
    decoded_value: run?.pcb_id ? `${run.pcb_id}-LOT-01` : '',
    x: '0.72',
    y: '0.78',
    width: '0.16',
    height: '0.08',
  }
}

export function buildQuery(filters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined) {
      params.set(key, value)
    }
  })
  const query = params.toString()
  return query ? `?${query}` : ''
}

export async function fetchJson(url, signal) {
  const response = await fetch(url, { signal })
  const payload = await response.json()
  if (!response.ok || payload.status === 'error') {
    throw new Error(payload.message || 'Request failed')
  }
  return payload
}

export function formatTimestamp(timestamp) {
  if (!timestamp) {
    return '-'
  }
  return new Date(timestamp).toLocaleString()
}

export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

export function toNormalizedNumber(value, fallback = 0) {
  const parsed = Number(value)
  if (Number.isNaN(parsed)) {
    return fallback
  }
  return clamp(parsed, 0, 1)
}

export function toPositiveNormalizedNumber(value, fallback = 0.05) {
  const parsed = Number(value)
  if (Number.isNaN(parsed) || parsed <= 0) {
    return fallback
  }
  return clamp(parsed, 0.001, 1)
}

export function normalizeEditableBox(box, fallbackWidth = 0.05, fallbackHeight = 0.05) {
  const width = clamp(toPositiveNormalizedNumber(box.width, fallbackWidth), 0.001, 1)
  const height = clamp(toPositiveNormalizedNumber(box.height, fallbackHeight), 0.001, 1)
  const x = clamp(toNormalizedNumber(box.x), 0, 1 - width)
  const y = clamp(toNormalizedNumber(box.y), 0, 1 - height)
  return {
    ...box,
    x,
    y,
    width,
    height,
  }
}
