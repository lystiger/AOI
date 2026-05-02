import { useCallback, useEffect, useRef, useState } from 'react'

import { clamp } from '../app/utils'

export default function PcbViewer({
  image,
  run,
  defects,
  selectedDefect,
  hoveredDefectId,
  isKbNavEnabled = true,
  kbNavSensitivity = 1.0,
  isZenMode = false,
  onHover,
  onSelectDefect,
  onSaveReview,
  onNextDefect,
}) {
  const [viewerScale, setViewerScale] = useState(1)
  const [viewerOffset, setViewerOffset] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [imageDimensions, setImageDimensions] = useState({
    width: image?.image_width || 1600,
    height: image?.image_height || 900,
  })
  const dragRef = useRef({ startX: 0, startY: 0, offsetX: 0, offsetY: 0 })
  const viewerRef = useRef(null)

  function setScale(nextScale) {
    setViewerScale(clamp(nextScale, 0.5, 10))
  }

  const resetViewer = useCallback(() => {
    if (!viewerRef.current || !image) return
    const bounds = viewerRef.current.getBoundingClientRect()
    const padding = 40
    const availableWidth = bounds.width - padding
    const availableHeight = bounds.height - padding
    const imgWidth = imageDimensions.width
    const imgHeight = imageDimensions.height
    const scaleX = availableWidth / imgWidth
    const scaleY = availableHeight / imgHeight
    const nextScale = Math.min(scaleX, scaleY, 1.0)

    setViewerScale(nextScale)
    setViewerOffset({ x: 0, y: 0 })
  }, [image, imageDimensions.height, imageDimensions.width])

  function focusDefect(defectId) {
    const defect = defects.find((entry) => entry.id === defectId)
    if (!defect || !viewerRef.current || !image) {
      return
    }

    onSelectDefect(defect.id)

    const targetX = defect.overlay_x + defect.overlay_width / 2
    const targetY = defect.overlay_y + defect.overlay_height / 2
    const componentSize = Math.max(defect.overlay_width, defect.overlay_height)
    const nextScale = clamp(0.3 / (componentSize || 0.1), 1.5, 6)
    const imgWidth = imageDimensions.width
    const imgHeight = imageDimensions.height
    const offsetX = -(targetX - 0.5) * imgWidth * nextScale
    const offsetY = -(targetY - 0.5) * imgHeight * nextScale

    setViewerScale(nextScale)
    setViewerOffset({ x: offsetX, y: offsetY })
  }

  function startDrag(event) {
    setIsDragging(true)
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      offsetX: viewerOffset.x,
      offsetY: viewerOffset.y,
    }
    // Automatically focus the viewer on click so keyboard nav works immediately
    viewerRef.current?.focus()
  }

  function moveDrag(event) {
    if (!isDragging) {
      return
    }
    setViewerOffset({
      x: dragRef.current.offsetX + (event.clientX - dragRef.current.startX),
      y: dragRef.current.offsetY + (event.clientY - dragRef.current.startY),
    })
  }

  function stopDrag() {
    setIsDragging(false)
  }

  function handleWheel(event) {
    event.preventDefault()
    const delta = -event.deltaY
    const scaleFactor = Math.pow(1.1, delta / 100)
    setScale(viewerScale * scaleFactor)
  }

  async function handleKeyDown(event) {
    if (!isKbNavEnabled) return

    const baseNudge = 20 * kbNavSensitivity
    // Shift key for faster movement
    const nudge = event.shiftKey ? baseNudge * 3 : baseNudge

    if (isZenMode && selectedDefect) {
      if (event.key.toLowerCase() === 'p') {
        event.preventDefault()
        const success = await onSaveReview(selectedDefect.id, 'CONFIRMED_PASS')
        if (success) onNextDefect()
        return
      }
      if (event.key.toLowerCase() === 'f') {
        event.preventDefault()
        const success = await onSaveReview(selectedDefect.id, 'CONFIRMED_FAIL')
        if (success) onNextDefect()
        return
      }
    }

    switch (event.key) {
      case 'ArrowUp':
        event.preventDefault()
        setViewerOffset((prev) => ({ ...prev, y: prev.y + nudge }))
        break
      case 'ArrowDown':
        event.preventDefault()
        setViewerOffset((prev) => ({ ...prev, y: prev.y - nudge }))
        break
      case 'ArrowLeft':
        event.preventDefault()
        setViewerOffset((prev) => ({ ...prev, x: prev.x + nudge }))
        break
      case 'ArrowRight':
        event.preventDefault()
        setViewerOffset((prev) => ({ ...prev, x: prev.x - nudge }))
        break
      case '+':
      case '=':
        event.preventDefault()
        setScale(viewerScale * 1.1)
        break
      case '-':
      case '_':
        event.preventDefault()
        setScale(viewerScale * 0.9)
        break
      case '0':
        event.preventDefault()
        resetViewer()
        break
      default:
        break
    }
  }

  useEffect(() => {
    if (image?.id) {
      const timer = setTimeout(() => {
        resetViewer()
      }, 50)
      return () => clearTimeout(timer)
    }
    return undefined
  }, [image?.id, imageDimensions.width, imageDimensions.height, resetViewer])

  useEffect(() => {
    if (isZenMode) {
      viewerRef.current?.focus()
    }
  }, [isZenMode, selectedDefect?.id])

  return (
    <section className="viewer-panel">
      <div className="viewer-toolbar">
        <div className="viewer-toolbar-group">
          <button type="button" className="ghost-button" onClick={resetViewer}>
            Reset View
          </button>
          <button
            type="button"
            className="ghost-button"
            onClick={() => selectedDefect && focusDefect(selectedDefect.id)}
            disabled={!selectedDefect}
          >
            Center Defect
          </button>
        </div>
        <div className="viewer-toolbar-group">
          <button type="button" className="ghost-button" onClick={() => setScale(viewerScale * 0.8)}>
            -
          </button>
          <div className="zoom-readout">{Math.round(viewerScale * 100)}%</div>
          <button type="button" className="ghost-button" onClick={() => setScale(viewerScale * 1.25)}>
            +
          </button>
        </div>
      </div>

      <div
        ref={viewerRef}
        className={`viewer-surface${isDragging ? ' dragging' : ''} ${isZenMode ? 'zen-mode-active' : ''}`}
        tabIndex={0}
        onMouseDown={startDrag}
        onMouseMove={moveDrag}
        onMouseUp={stopDrag}
        onMouseLeave={stopDrag}
        onWheel={handleWheel}
        onKeyDown={handleKeyDown}
        style={{ outline: 'none' }}
      >
        {image ? (
          <div
            className="viewer-stage"
            style={{ transform: `translate(${viewerOffset.x}px, ${viewerOffset.y}px) scale(${viewerScale})` }}
          >
            {viewerScale > 1.5 ? (
              <div
                className="viewer-grid"
                style={{
                  position: 'absolute',
                  inset: 0,
                  backgroundImage:
                    'linear-gradient(to right, rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.05) 1px, transparent 1px)',
                  backgroundSize: '20px 20px',
                  pointerEvents: 'none',
                }}
              />
            ) : null}
            <img
              className="viewer-image"
              src={image.image_path}
              alt={`${run.pcb_id} board`}
              onLoad={(event) => {
                const nextWidth = event.currentTarget.naturalWidth || image?.image_width || 1600
                const nextHeight = event.currentTarget.naturalHeight || image?.image_height || 900
                setImageDimensions((current) =>
                  current.width === nextWidth && current.height === nextHeight
                    ? current
                    : { width: nextWidth, height: nextHeight },
                )
              }}
            />
            {defects.map((defect) => {
              const overlayState =
                defect.id === selectedDefect?.id
                  ? 'selected'
                  : defect.id === hoveredDefectId
                    ? 'hovered'
                    : defect.inspection_result === 'FAIL'
                      ? 'fail'
                      : 'pass'

              return (
                <button
                  key={defect.id}
                  type="button"
                  className={`overlay-box overlay-${overlayState}`}
                  style={{
                    left: `${defect.overlay_x * 100}%`,
                    top: `${defect.overlay_y * 100}%`,
                    width: `${defect.overlay_width * 100}%`,
                    height: `${defect.overlay_height * 100}%`,
                  }}
                  onClick={(event) => {
                    event.stopPropagation()
                    onSelectDefect(defect.id)
                  }}
                  onDoubleClick={(event) => {
                    event.stopPropagation()
                    focusDefect(defect.id)
                  }}
                  onMouseEnter={() => onHover(defect.id)}
                  onMouseLeave={() => onHover(null)}
                >
                  <span>{defect.component_id}</span>
                </button>
              )
            })}
          </div>
        ) : (
          <div className="empty-state">No inspection image.</div>
        )}
      </div>
    </section>
  )
}
