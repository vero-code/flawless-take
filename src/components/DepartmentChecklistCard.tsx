import type { DepartmentChecklist } from '../types'

type DeptKey = keyof DepartmentChecklist['departments']

const DEPT_META: Record<DeptKey, { icon: string; label: string }> = {
  makeup:   { icon: '💄', label: 'Makeup' },
  wardrobe: { icon: '👔', label: 'Wardrobe' },
  hair:     { icon: '💇', label: 'Hair' },
  props:    { icon: '🎭', label: 'Props' },
}

export function DepartmentChecklistCard({ checklist }: { checklist: DepartmentChecklist }) {
  const priorityClass = {
    HIGH:   'dept-priority--high',
    MEDIUM: 'dept-priority--medium',
    LOW:    'dept-priority--low',
  }[checklist.priority] ?? 'dept-priority--low'

  const depts = checklist.departments || {}
  const hasAnyFix = Object.values(depts).some((items: string[]) => items && items.length > 0)

  return (
    <div className="dept-checklist-card">
      <div className="dept-checklist-header">
        <div className="dept-checklist-title">
          <span className="dept-checklist-icon">📋</span>
          <span>Department Action Checklist</span>
        </div>
        <div className="dept-checklist-badges">
          {checklist.next_take && (
            <span className="dept-badge dept-badge--take">Before Take {checklist.next_take}</span>
          )}
          <span className={`dept-badge dept-priority ${priorityClass}`}>{checklist.priority}</span>
        </div>
      </div>

      {checklist.scene && (
        <div className="dept-checklist-meta">
          🎬 {checklist.scene} · 👤 {checklist.character}
        </div>
      )}

      {!hasAnyFix && (
        <div className="dept-no-issues">✅ No department fixes required — continuity is intact.</div>
      )}

      <div className="dept-sections">
        {(Object.keys(DEPT_META) as Array<keyof typeof DEPT_META>).map(dept => {
          const items: string[] = depts[dept] || []
          const meta = DEPT_META[dept]
          return (
            <div key={dept} className={`dept-section ${items.length === 0 ? 'dept-section--empty' : ''}`}>
              <div className="dept-section-header">
                <span className="dept-section-icon">{meta.icon}</span>
                <span className="dept-section-label">{meta.label}</span>
                {items.length > 0 && (
                  <span className="dept-section-count">{items.length} fix{items.length > 1 ? 'es' : ''}</span>
                )}
              </div>
              {items.length > 0 ? (
                <ul className="dept-items">
                  {items.map((item, i) => (
                    <li key={i} className="dept-item">
                      <span className="dept-item-checkbox">☐</span>
                      <span className="dept-item-text">{item}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="dept-empty">No issues for this department.</p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
