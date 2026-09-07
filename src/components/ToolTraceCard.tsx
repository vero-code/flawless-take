import { useState } from 'react'
import { downloadPdf } from '../config'
import type { DepartmentChecklist, ToolTraceItem } from '../types'
import { DepartmentChecklistCard } from './DepartmentChecklistCard'

export function ToolTraceCard({ trace }: { trace: ToolTraceItem }) {
  const [open, setOpen] = useState(false)

  const toolIcons: Record<string, string> = {
    get_scene_continuity_state:    '🎬',
    query_take_records:            '🔍',
    get_take_full_report:          '📋',
    check_script_continuity:       '📜',
    compare_recorded_takes:        '⚖️',
    emit_crew_alert:               '🚨',
    export_continuity_pdf:         '📄',
    generate_department_checklist: '✅',
  }
  const icon = toolIcons[trace.tool] || '⚙️'

  const isPdf        = trace.tool === 'export_continuity_pdf'
  const isAlert      = trace.tool === 'emit_crew_alert'
  const isState      = trace.tool === 'get_scene_continuity_state'
  const isChecklist  = trace.tool === 'generate_department_checklist'

  return (
    <div className="tool-trace-card">
      <div className="tool-trace-header" onClick={() => setOpen(prev => !prev)}>
        <span className="tool-trace-badge">
          <span className="tool-trace-icon">{icon}</span>
          <span className="tool-trace-name">{trace.tool}</span>
        </span>
        <div className="tool-trace-meta">
          {isAlert     && <span className="trace-status-pill trace-status-pill--alert">BROADCASTED</span>}
          {isPdf       && <span className="trace-status-pill trace-status-pill--pdf">PDF READY</span>}
          {isChecklist && <span className="trace-status-pill trace-status-pill--checklist">CHECKLIST READY</span>}
          {isState && trace.result?.drift_status && (
            <span className={`trace-status-pill trace-status-pill--${String(trace.result.drift_status).toLowerCase()}`}>
              {trace.result.drift_status}
            </span>
          )}
          <span className="tool-trace-caret">{open ? '▴' : '▾'}</span>
        </div>
      </div>

      {/* Direct Action Bars */}
      {isPdf && trace.result?.record_id && (
        <div className="tool-trace-action-bar">
          <button
            type="button"
            className="agent-download-pdf-btn"
            onClick={() => downloadPdf(Number(trace.result.record_id), trace.result.filename)}
          >
            📄 Download Continuity PDF #{trace.result.record_id}
          </button>
        </div>
      )}

      {isAlert && trace.result?.broadcast_via_sse && (
        <div className="tool-trace-alert-broadcast">
          <span className="tool-trace-radio-icon">📡</span>
          <span>
            Alert delivered to Kafka topic &amp; <strong>#{trace.args?.department || 'crew'}</strong> radio
          </span>
        </div>
      )}

      {/* Inline Department Checklist — always visible when checklist tool ran */}
      {isChecklist && trace.result?.departments && !trace.result?.error && (
        <DepartmentChecklistCard checklist={trace.result as DepartmentChecklist} />
      )}

      {open && (
        <div className="tool-trace-body">
          <div className="tool-trace-section">
            <span className="tool-trace-section-title">Arguments:</span>
            <pre className="tool-trace-code">{JSON.stringify(trace.args, null, 2)}</pre>
          </div>
          {!isChecklist && (
            <div className="tool-trace-section">
              <span className="tool-trace-section-title">Output Result:</span>
              <pre className="tool-trace-code">{JSON.stringify(trace.result, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
