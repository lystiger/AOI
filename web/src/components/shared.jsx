import { formatTimestamp } from '../app/utils'

export function FilterField({ label, value, onChange, type = 'text', options, compact = false }) {
  return (
    <label className={`field${compact ? ' compact' : ''}`}>
      <span>{label}</span>
      {options ? (
        <select value={value} onChange={(event) => onChange(event.target.value)}>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
      )}
    </label>
  )
}

export function StatusChip({ value, kind = 'status' }) {
  return <span className={`chip ${kind} ${String(value).toLowerCase()}`}>{value}</span>
}

export function EmptyStateMessage({ title, body }) {
  return (
    <div className="empty-state empty-guidance">
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  )
}

export function RunCard({ run, active, onSelect }) {
  return (
    <button
      type="button"
      className={`run-card${active ? ' active' : ''}`}
      onClick={() => onSelect(run.id)}
    >
      <div className="run-card-top">
        <strong>{run.pcb_id}</strong>
        <StatusChip value={run.status} />
      </div>
      <div className="run-card-bottom">
        <span>{formatTimestamp(run.timestamp)}</span>
        <span>{run.event_count} events</span>
      </div>
    </button>
  )
}

export function DefectListItem({ defect, active, hovered, onSelect, onHover }) {
  return (
    <button
      type="button"
      className={`defect-list-item${active ? ' active' : ''}${hovered ? ' hovered' : ''}`}
      onClick={() => onSelect(defect.id)}
      onMouseEnter={() => onHover(defect.id)}
      onMouseLeave={() => onHover(null)}
    >
      <div className="defect-list-top">
        <strong>{defect.component_id}</strong>
        <StatusChip value={defect.severity} kind="severity" />
      </div>
      <div className="defect-list-meta">
        <span>{defect.defect_type}</span>
        <StatusChip value={defect.inspection_result} />
        <span>{Number(defect.confidence_score ?? 0).toFixed(2)}</span>
      </div>
    </button>
  )
}
