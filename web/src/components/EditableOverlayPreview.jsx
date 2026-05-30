import { useEffect, useRef, useState } from 'react'

import { clamp, formatFiducialLabel, normalizeEditableBox } from '../app/utils'

export default function EditableOverlayPreview({ image, overlays, onChange, kind = 'fiducial' }) {
  const previewRef = useRef(null)
  const [editState, setEditState] = useState(null)
  const [selectedOverlayId, setSelectedOverlayId] = useState(null)

  function getPointerEditMode(event) {
    const bounds = event.currentTarget.getBoundingClientRect()
    const edgeThreshold = 12
    const nearLeft = event.clientX - bounds.left <= edgeThreshold
    const nearRight = bounds.right - event.clientX <= edgeThreshold
    const nearTop = event.clientY - bounds.top <= edgeThreshold
    const nearBottom = bounds.bottom - event.clientY <= edgeThreshold

    if (nearTop && nearLeft) return 'resize-nw'
    if (nearTop && nearRight) return 'resize-ne'
    if (nearBottom && nearLeft) return 'resize-sw'
    if (nearBottom && nearRight) return 'resize-se'
    if (nearLeft) return 'resize-w'
    if (nearRight) return 'resize-e'
    if (nearTop) return 'resize-n'
    if (nearBottom) return 'resize-s'
    return 'move'
  }

  useEffect(() => {
    if (!editState) {
      return undefined
    }

    function handlePointerMove(event) {
      if (!previewRef.current) {
        return
      }
      const bounds = previewRef.current.getBoundingClientRect()
      if (!bounds.width || !bounds.height) {
        return
      }
      const deltaX = (event.clientX - editState.startX) / bounds.width
      const deltaY = (event.clientY - editState.startY) / bounds.height
      const minSize = 0.01

      let nextBox = {
        x: editState.originX,
        y: editState.originY,
        width: editState.originWidth,
        height: editState.originHeight,
      }

      if (editState.mode === 'move') {
        nextBox.x = clamp(editState.originX + deltaX, 0, 1 - editState.originWidth)
        nextBox.y = clamp(editState.originY + deltaY, 0, 1 - editState.originHeight)
      } else if (editState.mode === 'resize-e') {
        nextBox.width = clamp(editState.originWidth + deltaX, minSize, 1 - editState.originX)
      } else if (editState.mode === 'resize-w') {
        const nextX = clamp(editState.originX + deltaX, 0, editState.originX + editState.originWidth - minSize)
        nextBox.x = nextX
        nextBox.width = clamp(editState.originWidth + (editState.originX - nextX), minSize, 1 - nextX)
      } else if (editState.mode === 'resize-n') {
        const nextY = clamp(editState.originY + deltaY, 0, editState.originY + editState.originHeight - minSize)
        nextBox.y = nextY
        nextBox.height = clamp(editState.originHeight + (editState.originY - nextY), minSize, 1 - nextY)
      } else if (editState.mode === 'resize-s') {
        nextBox.height = clamp(editState.originHeight + deltaY, minSize, 1 - editState.originY)
      } else if (editState.mode === 'resize-se') {
        nextBox.width = clamp(editState.originWidth + deltaX, minSize, 1 - editState.originX)
        nextBox.height = clamp(editState.originHeight + deltaY, minSize, 1 - editState.originY)
      } else if (editState.mode === 'resize-sw') {
        const nextX = clamp(editState.originX + deltaX, 0, editState.originX + editState.originWidth - minSize)
        nextBox.x = nextX
        nextBox.width = clamp(editState.originWidth + (editState.originX - nextX), minSize, 1 - nextX)
        nextBox.height = clamp(editState.originHeight + deltaY, minSize, 1 - editState.originY)
      } else if (editState.mode === 'resize-ne') {
        const nextY = clamp(editState.originY + deltaY, 0, editState.originY + editState.originHeight - minSize)
        nextBox.y = nextY
        nextBox.width = clamp(editState.originWidth + deltaX, minSize, 1 - editState.originX)
        nextBox.height = clamp(editState.originHeight + (editState.originY - nextY), minSize, 1 - nextY)
      } else if (editState.mode === 'resize-nw') {
        const nextX = clamp(editState.originX + deltaX, 0, editState.originX + editState.originWidth - minSize)
        const nextY = clamp(editState.originY + deltaY, 0, editState.originY + editState.originHeight - minSize)
        nextBox.x = nextX
        nextBox.y = nextY
        nextBox.width = clamp(editState.originWidth + (editState.originX - nextX), minSize, 1 - nextX)
        nextBox.height = clamp(editState.originHeight + (editState.originY - nextY), minSize, 1 - nextY)
      }

      onChange?.(editState.id, normalizeEditableBox(nextBox, minSize, minSize))
    }

    function handlePointerUp() {
      setEditState(null)
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', handlePointerUp)
    }
  }, [editState, onChange])

  const overlayClassName = kind === 'barcode' ? 'barcode-box' : kind === 'fov' ? 'fov-box' : 'fiducial-box'

  return (
    <div ref={previewRef} className="fiducial-preview editable-preview">
      <img src={image.image_path} alt={`${kind} preview`} />
      {overlays.map((overlay, index) => (
        <button
          key={overlay.id}
          type="button"
          className={`${overlayClassName} editable-box${selectedOverlayId === overlay.id ? ' selected' : ''}`}
          style={{
            left: `${overlay.x * 100}%`,
            top: `${overlay.y * 100}%`,
            width: `${overlay.width * 100}%`,
            height: `${overlay.height * 100}%`,
          }}
          onPointerDown={(event) => {
            event.preventDefault()
            event.stopPropagation()
            setSelectedOverlayId(overlay.id)
            setEditState({
              id: overlay.id,
              mode: getPointerEditMode(event),
              startX: event.clientX,
              startY: event.clientY,
              originX: overlay.x,
              originY: overlay.y,
              originWidth: overlay.width,
              originHeight: overlay.height,
            })
          }}
          onFocus={() => setSelectedOverlayId(overlay.id)}
          onClick={() => setSelectedOverlayId(overlay.id)}
          onKeyDown={(event) => {
            const baseStep = event.shiftKey ? 0.01 : 0.0025
            const currentBox = normalizeEditableBox(overlay, 0.01, 0.01)
            let nextBox = { ...currentBox }

            if (event.altKey) {
              if (event.key === 'ArrowLeft') {
                nextBox.width = clamp(currentBox.width - baseStep, 0.01, 1 - currentBox.x)
              } else if (event.key === 'ArrowRight') {
                nextBox.width = clamp(currentBox.width + baseStep, 0.01, 1 - currentBox.x)
              } else if (event.key === 'ArrowUp') {
                nextBox.height = clamp(currentBox.height - baseStep, 0.01, 1 - currentBox.y)
              } else if (event.key === 'ArrowDown') {
                nextBox.height = clamp(currentBox.height + baseStep, 0.01, 1 - currentBox.y)
              } else {
                return
              }
            } else {
              if (event.key === 'ArrowLeft') {
                nextBox.x = currentBox.x - baseStep
              } else if (event.key === 'ArrowRight') {
                nextBox.x = currentBox.x + baseStep
              } else if (event.key === 'ArrowUp') {
                nextBox.y = currentBox.y - baseStep
              } else if (event.key === 'ArrowDown') {
                nextBox.y = currentBox.y + baseStep
              } else {
                return
              }
            }

            event.preventDefault()
            onChange?.(overlay.id, normalizeEditableBox(nextBox, 0.01, 0.01))
          }}
          aria-label={`${kind} ${overlay.label || formatFiducialLabel(index)}`}
        >
          <span>{overlay.label}</span>
        </button>
      ))}
    </div>
  )
}
