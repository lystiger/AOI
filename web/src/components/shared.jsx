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
        <div className="run-card-titleblock">
          <strong>{run.pcb_id}</strong>
          <span className="run-card-id">{run.id}</span>
        </div>
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
        <div className="defect-list-titleblock">
          <strong>{defect.component_id}</strong>
          <span className="defect-list-type">{defect.defect_type}</span>
        </div>
        <StatusChip value={defect.severity} kind="severity" />
      </div>
      <div className="defect-list-meta">
        <StatusChip value={defect.inspection_result} />
        <span className="defect-confidence">{Number(defect.confidence_score ?? 0).toFixed(2)}</span>
        {defect.operator_review && defect.operator_review !== 'NONE' ? (
          <span className="defect-reviewed" title={`Reviewed as ${defect.operator_review}`}>
            Reviewed
          </span>
        ) : null}
      </div>
    </button>
  )
}
