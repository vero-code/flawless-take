import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8000'
const API_URL = `${API_BASE}/api/check-take`
const COMPARE_URL = `${API_BASE}/api/compare-takes`
const SCRIPT_URL = `${API_BASE}/api/upload-script`
const ALERTS_URL = `${API_BASE}/api/alerts`
const HISTORY_URL = `${API_BASE}/api/history`

function getMediaUrl(url?: string | null): string | undefined {
  if (!url) return undefined
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `${API_BASE}${url.startsWith('/') ? '' : '/'}${url}`
}

async function downloadPdf(recordId: number, filename?: string) {
  try {
    const res = await fetch(`${API_BASE}/api/history/${recordId}/pdf`)
    if (!res.ok) {
      const errText = await res.text()
      throw new Error(`Server returned ${res.status}: ${errText}`)
    }
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || `continuity_log_${recordId}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (err) {
    alert(`Failed to export PDF: ${err instanceof Error ? err.message : String(err)}`)
  }
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type CheckResult = {
  id?: number
  scene: string
  take: string
  character: string
  filename: string
  size_bytes: number
  result: string
  script_grounded: boolean
  preview_url?: string | null
}

type CompareResult = {
  id?: number
  scene: string
  take_ref: string
  take_current: string
  character: string
  ref_filename: string
  cur_filename: string
  differences: string
  risk_level: string
  match_score: string
  script_grounded: boolean
  preview_ref_url?: string | null
  preview_cur_url?: string | null
}


type ScriptNotes = {
  scenes: { scene_number: string; heading: string; characters: string[]; continuity_notes: string }[]
  characters: { name: string; appearance_notes: string }[]
  general_notes: string
}

type Mode = 'single' | 'compare'
type Status = 'idle' | 'loading' | 'success' | 'error'

// ---------------------------------------------------------------------------
// History record type
// ---------------------------------------------------------------------------
type HistoryRecord = {
  id: number
  kind: 'check' | 'comparison'
  created_at: number
  scene: string
  character: string
  take?: string
  take_ref?: string
  take_current?: string
  risk_level: string
  match_score?: string
  script_grounded: number
  report: string
  preview_ref_url?: string
  preview_cur_url?: string
}

// ---------------------------------------------------------------------------
// Minimal markdown renderer — h3, bold, italic, bullets, hr
// ---------------------------------------------------------------------------
function Markdown({ text }: { text: string }) {
  const lines = text.split('\n')
  const elements: React.ReactNode[] = []
  let listBuffer: string[] = []

  function flushList() {
    if (listBuffer.length === 0) return
    elements.push(
      <ul key={elements.length} className="md-list">
        {listBuffer.map((item, i) => (
          <li key={i} dangerouslySetInnerHTML={{ __html: inlineFormat(item) }} />
        ))}
      </ul>
    )
    listBuffer = []
  }

  function inlineFormat(s: string): string {
    return s
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
  }

  for (const raw of lines) {
    const line = raw.trimEnd()
    if (/^#{1,3}\s/.test(line)) {
      flushList()
      elements.push(
        <h3 key={elements.length} className="md-h3"
          dangerouslySetInnerHTML={{ __html: inlineFormat(line.replace(/^#{1,3}\s/, '')) }} />
      )
    } else if (/^(\*|-)\s/.test(line)) {
      listBuffer.push(line.replace(/^(\*|-)\s/, ''))
    } else if (/^---+$/.test(line)) {
      flushList()
      elements.push(<hr key={elements.length} className="md-hr" />)
    } else if (line === '') {
      flushList()
    } else {
      flushList()
      elements.push(
        <p key={elements.length} className="md-p"
          dangerouslySetInnerHTML={{ __html: inlineFormat(line) }} />
      )
    }
  }
  flushList()
  return <div className="md-body">{elements}</div>
}

// ---------------------------------------------------------------------------
// Script panel — upload PDF, show extracted notes, return context string
// ---------------------------------------------------------------------------
function ScriptPanel({ onContext }: { onContext: (ctx: string) => void }) {
  const [open, setOpen] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [notes, setNotes] = useState<ScriptNotes | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    setUploadStatus('loading')
    setNotes(null)
    setErrorMsg('')
    onContext('')

    const body = new FormData()
    body.append('file', f)

    try {
      const res = await fetch(SCRIPT_URL, { method: 'POST', body })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const data = await res.json()
      const n: ScriptNotes = data.notes
      setNotes(n)
      setUploadStatus('done')
      // Build a compact context string to pass into check-take
      const ctxParts: string[] = []
      if (n.general_notes) ctxParts.push(`General notes: ${n.general_notes}`)
      n.characters.forEach(c => {
        if (c.appearance_notes) ctxParts.push(`${c.name}: ${c.appearance_notes}`)
      })
      n.scenes.forEach(s => {
        if (s.continuity_notes) ctxParts.push(`Scene ${s.scene_number} (${s.heading}): ${s.continuity_notes}`)
      })
      onContext(ctxParts.join('\n'))
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err))
      setUploadStatus('error')
    }
  }

  return (
    <div className="script-panel">
      <button type="button" className="script-toggle" onClick={() => setOpen(o => !o)}>
        <span className="script-toggle-icon">{open ? '▾' : '▸'}</span>
        Script grounding
        {notes && <span className="script-badge">active</span>}
      </button>

      {open && (
        <div className="script-body">
          <p className="script-hint">
            Upload a PDF shooting script to ground the continuity check against scene and character descriptions.
          </p>

          <div
            className="file-drop script-drop"
            onClick={() => inputRef.current?.click()}
          >
            {uploadStatus === 'loading'
              ? <span className="file-placeholder">Parsing script…</span>
              : uploadStatus === 'done' && notes
              ? <span className="file-placeholder script-ok">✓ {notes.scenes.length} scene{notes.scenes.length !== 1 ? 's' : ''} · {notes.characters.length} character{notes.characters.length !== 1 ? 's' : ''}</span>
              : <span className="file-placeholder">Tap to select PDF script</span>
            }
            <input ref={inputRef} type="file" accept="application/pdf" onChange={handleFile} />
          </div>

          {uploadStatus === 'error' && (
            <p className="script-error">{errorMsg}</p>
          )}

          {notes && notes.characters.length > 0 && (
            <div className="script-notes">
              {notes.general_notes && (
                <p className="script-note-item"><strong>General:</strong> {notes.general_notes}</p>
              )}
              {notes.characters.map((c, i) => c.appearance_notes && (
                <p key={i} className="script-note-item"><strong>{c.name}:</strong> {c.appearance_notes}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Alert feed — SSE consumer + toast overlay
// ---------------------------------------------------------------------------
type AlertEvent = {
  event: string
  scene?: string
  take?: string
  take_ref?: string
  take_current?: string
  character?: string
  risk_level?: string
  match_score?: string
  script_grounded?: boolean
  timestamp?: number
  department?: string
  message?: string
  source?: string
}

type Toast = AlertEvent & { id: number }

const RISK_TOAST: Record<string, string> = {
  HIGH: 'toast--high',
  MEDIUM: 'toast--medium',
  LOW: 'toast--low',
}

// ---------------------------------------------------------------------------
// History tab
// ---------------------------------------------------------------------------
function HistoryTab() {
  const [records, setRecords] = useState<HistoryRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')
  const [expanded, setExpanded] = useState<number | null>(null)
  const [sceneFilter, setSceneFilter] = useState('')
  const [charFilter, setCharFilter] = useState('')

  const load = async (scene = sceneFilter, char = charFilter) => {
    setLoading(true)
    setErrorMsg('')
    try {
      const params = new URLSearchParams()
      if (scene.trim()) params.set('scene', scene.trim())
      if (char.trim()) params.set('character', char.trim())
      const res = await fetch(`${HISTORY_URL}?${params}`)
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const data = await res.json()
      setRecords(data)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let ignore = false
    const fetchInitial = async () => {
      setLoading(true)
      try {
        const res = await fetch(HISTORY_URL)
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
        const data = await res.json()
        if (!ignore) setRecords(data)
      } catch (err) {
        if (!ignore) setErrorMsg(err instanceof Error ? err.message : String(err))
      } finally {
        if (!ignore) setLoading(false)
      }
    }
    void fetchInitial()
    return () => { ignore = true }
  }, [])

  const handleDelete = async (id: number) => {
    if (!window.confirm('Delete this record from history?')) return
    try {
      const res = await fetch(`${HISTORY_URL}/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      setRecords(prev => prev.filter(r => r.id !== id))
      if (expanded === id) setExpanded(null)
    } catch (err) {
      alert(`Failed to delete record: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void load()
  }

  const handleReset = () => {
    setSceneFilter('')
    setCharFilter('')
    void load('', '')
  }

  return (
    <div className="history-tab">
      <form className="history-filters" onSubmit={handleSearchSubmit}>
        <input className="history-filter-input" type="text" placeholder="Filter by scene…"
          value={sceneFilter} onChange={e => setSceneFilter(e.target.value)} />
        <input className="history-filter-input" type="text" placeholder="Filter by character…"
          value={charFilter} onChange={e => setCharFilter(e.target.value)} />
        <button type="submit" className="history-refresh-btn" disabled={loading}>
          {loading ? 'Searching…' : 'Search'}
        </button>
        {(sceneFilter || charFilter) && (
          <button type="button" className="history-clear-btn" onClick={handleReset} disabled={loading}>
            Reset
          </button>
        )}
      </form>

      {errorMsg && (
        <p className="script-error">{errorMsg}</p>
      )}

      {records.length === 0 && !loading && !errorMsg && (
        <p className="history-empty">No records found. Run a check or comparison to see history here.</p>
      )}

      <div className="history-list">
        {records.map(r => (
          <div key={r.id} className="history-card">
            <div className="history-card-header" onClick={() => setExpanded(expanded === r.id ? null : r.id)}>
              <div className="history-header-top">
                <div className="history-card-meta">
                  <span className={`alert-risk risk--${r.risk_level?.toLowerCase()}`}>{r.risk_level}</span>
                  {r.match_score && <MatchBadge score={r.match_score} />}
                  <span className="history-kind">{r.kind === 'comparison' ? '⇄ Compare' : '● Check'}</span>
                </div>
                <div className="history-header-actions">
                  <span className="history-card-date">
                    {new Date(r.created_at * 1000).toLocaleString()}
                  </span>
                  <button
                    type="button"
                    className="history-delete-btn"
                    title="Delete record"
                    onClick={(e) => {
                      e.stopPropagation()
                      void handleDelete(r.id)
                    }}
                  >
                    ✕
                  </button>
                </div>
              </div>
              <div className="history-card-title">
                {r.character} · {r.scene}
                {r.kind === 'check' && ` · Take ${r.take}`}
                {r.kind === 'comparison' && ` · Take ${r.take_ref} vs ${r.take_current}`}
              </div>
            </div>

            {expanded === r.id && (
              <div className="history-card-body">
                {/* Previews */}
                {(r.preview_ref_url || r.preview_cur_url) && (
                  <div className="history-previews">
                    {r.preview_ref_url && (
                      <img src={getMediaUrl(r.preview_ref_url)} className="history-preview-img"
                        alt={r.kind === 'comparison' ? 'Reference' : 'Photo'} />
                    )}
                    {r.preview_cur_url && (
                      <img src={getMediaUrl(r.preview_cur_url)} className="history-preview-img" alt="Current" />
                    )}
                  </div>
                )}
                {/* Report */}
                <Markdown text={r.report} />

                <div className="pdf-export-row">
                  <button
                    type="button"
                    className="pdf-export-btn"
                    onClick={() => downloadPdf(r.id, `continuity_${r.scene}_take_${r.take || `${r.take_ref}_vs_${r.take_current}`}.pdf`)}
                  >
                    📄 Export Continuity Log (PDF)
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}


function AlertFeed() {
  const [toasts, setToasts] = useState<Toast[]>([])
  const counterRef = useRef(0)

  useEffect(() => {
    const es = new EventSource(ALERTS_URL)

    es.onmessage = (e) => {
      try {
        const payload: AlertEvent = JSON.parse(e.data)
        if (
          payload.event !== 'continuity_check' &&
          payload.event !== 'takes_comparison' &&
          payload.event !== 'autonomous_agent_alert'
        ) return
        const id = ++counterRef.current
        setToasts(prev => [...prev.slice(-4), { ...payload, id }])
        // auto-dismiss after 8 s
        setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 8000)
      } catch {
        // ignore malformed messages
      }
    }

    es.onerror = () => {
      // browser will reconnect automatically; nothing to do
    }

    return () => es.close()
  }, [])

  if (toasts.length === 0) return null

  return (
    <div className="alert-feed" aria-live="polite">
      {toasts.map(t => (
        <div
          key={t.id}
          className={`alert-toast ${RISK_TOAST[t.risk_level ?? ''] ?? ''}`}
          onClick={() => setToasts(prev => prev.filter(x => x.id !== t.id))}
        >
          <span className="alert-tag">
            {t.event === 'autonomous_agent_alert'
              ? '🤖 Agent Alert'
              : t.event === 'takes_comparison'
              ? '⇄ Compare'
              : '● Check'}
          </span>
          <span className="alert-scene">
            {t.department ? `[${t.department.toUpperCase()}] ` : ''}
            {t.character ? `${t.character} · ` : ''}{t.scene}
            {t.event === 'takes_comparison'
              ? ` · Take ${t.take_ref} vs ${t.take_current}`
              : t.take ? ` · Take ${t.take}` : ''}
            {t.message ? ` — ${t.message}` : ''}
          </span>
          <span className="alert-meta">
            {t.risk_level && <span className={`alert-risk risk--${t.risk_level?.toLowerCase()}`}>{t.risk_level}</span>}
            {t.match_score && <span className="alert-score">{t.match_score}</span>}
          </span>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Reusable image drop zone
// ---------------------------------------------------------------------------
function ImageDrop({
  id, label, preview, inputRef, onChange,
}: {
  id: string
  label: string
  preview: string | null
  inputRef: React.RefObject<HTMLInputElement | null>
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
}) {
  return (
    <div className="form-row">
      <label htmlFor={id}>{label}</label>
      <div className="file-drop" onClick={() => inputRef.current?.click()}>
        {preview
          ? <img src={preview} className="file-preview" alt={label} />
          : <span className="file-placeholder">Tap to select image</span>
        }
        <input ref={inputRef} id={id} type="file" accept="image/*"
          capture="environment" onChange={onChange} required />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Match score badge
// ---------------------------------------------------------------------------
const SCORE_CLASS: Record<string, string> = {
  GOOD: 'badge--good',
  FAIR: 'badge--fair',
  POOR: 'badge--poor',
}

function MatchBadge({ score }: { score: string }) {
  return (
    <span className={`match-badge ${SCORE_CLASS[score] ?? ''}`}>{score}</span>
  )
}

// ---------------------------------------------------------------------------
// Scene Memory Timeline (State Tracking)
// ---------------------------------------------------------------------------
type SceneTimelineItem = {
  id: number
  kind: 'check' | 'comparison'
  take_label: string
  take?: string
  take_ref?: string
  take_current?: string
  risk_level: string
  match_score?: string
  created_at: number
  summary: string
  preview_ref_url?: string | null
  preview_cur_url?: string | null
}

type SceneStateData = {
  scene: string
  character: string
  total_takes: number
  drift_status: 'STABLE' | 'DRIFTING' | 'CRITICAL'
  baseline_take?: string | null
  timeline: SceneTimelineItem[]
  known_discrepancies: string[]
}

function SceneMemoryTimeline({
  scene,
  character,
  refreshTrigger = 0,
  onSelectReferenceTake,
}: {
  scene: string
  character: string
  refreshTrigger?: number
  onSelectReferenceTake?: (take: string) => void
}) {
  const [data, setData] = useState<SceneStateData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const s = scene.trim()
    const c = character.trim()
    if (!s || !c) {
      setData(null)
      return
    }

    let active = true
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await fetch(
          `${API_BASE}/api/scene-state?scene=${encodeURIComponent(s)}&character=${encodeURIComponent(c)}`
        )
        if (res.ok && active) {
          const json: SceneStateData = await res.json()
          setData(json)
        }
      } catch (err) {
        console.error('Failed to load scene state:', err)
      } finally {
        if (active) setLoading(false)
      }
    }, 350)

    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [scene, character, refreshTrigger])

  if (!scene.trim() || !character.trim()) {
    return null
  }

  if (loading && !data) {
    return (
      <div className="scene-memory-card scene-memory-card--loading">
        <span className="scene-memory-spinner"></span>
        <span>Recalling scene continuity history for {character}…</span>
      </div>
    )
  }

  if (!data || data.total_takes === 0) {
    return (
      <div className="scene-memory-card scene-memory-card--baseline">
        <div className="scene-memory-header">
          <span className="scene-memory-tag">🎬 Scene Memory</span>
          <span className="status-pill status--stable">★ Baseline Setup</span>
        </div>
        <p className="scene-memory-note">
          No previous takes recorded for <strong>{character}</strong> in <strong>{scene}</strong>.
          This check will establish the scene continuity baseline.
        </p>
      </div>
    )
  }

  const statusClass =
    data.drift_status === 'CRITICAL'
      ? 'status--critical'
      : data.drift_status === 'DRIFTING'
      ? 'status--drifting'
      : 'status--stable'

  const statusLabel =
    data.drift_status === 'CRITICAL'
      ? '✖ CRITICAL DRIFT'
      : data.drift_status === 'DRIFTING'
      ? '▲ DRIFTING'
      : '● STABLE'

  return (
    <div className="scene-memory-card">
      <div className="scene-memory-header">
        <div className="scene-memory-title-wrap">
          <span className="scene-memory-tag">🎬 Scene Memory</span>
          <span className={`status-pill ${statusClass}`}>{statusLabel}</span>
          {data.baseline_take && (
            <span className="scene-memory-baseline">
              Baseline: Take {data.baseline_take}
            </span>
          )}
        </div>
        <span className="scene-memory-count">
          {data.total_takes} take{data.total_takes === 1 ? '' : 's'} recorded
        </span>
      </div>

      {data.known_discrepancies.length > 0 && (
        <div className="scene-drift-strip">
          <span className="scene-drift-label">Drift flags:</span>
          <div className="scene-drift-tags">
            {data.known_discrepancies.map((issue, idx) => (
              <span key={idx} className="scene-drift-chip" title={issue}>
                {issue}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="scene-timeline-strip">
        {data.timeline.map((item) => {
          const riskClass = `risk--${(item.risk_level || 'unknown').toLowerCase()}`
          const refTake = item.take || item.take_current || item.take_ref || ''
          const previewImg = getMediaUrl(item.preview_cur_url || item.preview_ref_url)

          return (
            <div key={item.id} className="scene-take-chip">
              <div className="scene-take-top">
                <span className="scene-take-label">
                  {item.kind === 'comparison' ? `⇄ ${item.take_label}` : `Take ${item.take_label}`}
                </span>
                <span className={`alert-risk ${riskClass}`}>{item.risk_level}</span>
              </div>
              {previewImg && (
                <div className="scene-take-thumb-wrap">
                  <img src={previewImg} className="scene-take-thumb" alt={item.take_label} />
                </div>
              )}
              {item.summary && (
                <p className="scene-take-summary" title={item.summary}>
                  {item.summary}
                </p>
              )}
              {onSelectReferenceTake && refTake && (
                <button
                  type="button"
                  className="scene-take-use-btn"
                  onClick={() => onSelectReferenceTake(refTake)}
                  title={`Use Take ${refTake} as reference for comparison`}
                >
                  Use as Ref ⮂
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Phase 4 Step 2 & 3: Agent Copilot Types & Components
// ---------------------------------------------------------------------------
const AGENT_QUERY_URL = `${API_BASE}/api/agent/query`

type ToolTraceItem = {
  tool: string
  args: Record<string, any>
  result: any
}

type DepartmentChecklist = {
  next_take: string
  scene: string
  character: string
  priority: 'HIGH' | 'MEDIUM' | 'LOW'
  departments: {
    makeup: string[]
    wardrobe: string[]
    hair: string[]
    props: string[]
  }
  generated_at?: number
  status?: string
}

type AgentChatMessage = {
  id: string
  role: 'user' | 'agent'
  text: string
  toolCalls?: ToolTraceItem[]
  actionsTaken?: string[]
  timestamp: number
}

// ---------------------------------------------------------------------------
// DepartmentChecklistCard — renders structured fix checklist per department
// ---------------------------------------------------------------------------
const DEPT_META: Record<string, { icon: string; label: string }> = {
  makeup:   { icon: '💄', label: 'Makeup' },
  wardrobe: { icon: '👔', label: 'Wardrobe' },
  hair:     { icon: '💇', label: 'Hair' },
  props:    { icon: '🎭', label: 'Props' },
}

function DepartmentChecklistCard({ checklist }: { checklist: DepartmentChecklist }) {
  const priorityClass = {
    HIGH:   'dept-priority--high',
    MEDIUM: 'dept-priority--medium',
    LOW:    'dept-priority--low',
  }[checklist.priority] ?? 'dept-priority--low'

  const depts = checklist.departments || {}
  const hasAnyFix = Object.values(depts).some(items => items.length > 0)

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
          const items: string[] = (depts as any)[dept] || []
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

function ToolTraceCard({ trace }: { trace: ToolTraceItem }) {
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

function AgentCopilotView({
  scene,
  character,
  scriptContext,
  onSceneChange,
  onCharacterChange,
}: {
  scene: string
  character: string
  scriptContext: string
  onSceneChange: (s: string) => void
  onCharacterChange: (c: string) => void
}) {
  const [messages, setMessages] = useState<AgentChatMessage[]>([
    {
      id: 'welcome',
      role: 'agent',
      text: '👋 **Agent Copilot online!** I am your autonomous on-set AI continuity supervisor powered by Google GenAI. I can autonomously invoke tools: query the SQLite takes database, verify script guidelines, compare takes, generate official Hollywood Continuity PDFs, and dispatch real-time radio alerts to Confluent Kafka / SSE.\n\nAsk a question or select a quick action below.',
      timestamp: Date.now(),
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function handleSend(promptText?: string) {
    const textToSend = (promptText ?? input).trim()
    if (!textToSend || loading) return

    setInput('')
    setErrorMsg(null)

    const userMsg: AgentChatMessage = {
      id: 'user-' + Date.now(),
      role: 'user',
      text: textToSend,
      timestamp: Date.now(),
    }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await fetch(AGENT_QUERY_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: textToSend,
          scene: scene.trim(),
          character: character.trim(),
          script_context: scriptContext.trim(),
        }),
      })

      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Server returned ${res.status}: ${errText}`)
      }

      const data = await res.json()
      const agentMsg: AgentChatMessage = {
        id: 'agent-' + Date.now(),
        role: 'agent',
        text: data.response || 'Tools executed successfully.',
        toolCalls: data.tool_calls || [],
        actionsTaken: data.actions_taken || [],
        timestamp: Date.now(),
      }
      setMessages(prev => [...prev, agentMsg])
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  const promptChips = [
    {
      label: '🔍 Check Scene Continuity',
      text: `Check current continuity status and take history for scene "${scene || 'EXT. ROOFTOP - NIGHT'}" and character "${character || 'Alice'}".`,
    },
    {
      label: '🚨 Alert Makeup Crew',
      text: `Dispatch an alert to the makeup department regarding continuity discrepancies in scene "${scene || 'EXT. ROOFTOP - NIGHT'}" for character "${character || 'Alice'}".`,
    },
    {
      label: '📄 Generate Continuity PDF',
      text: `Generate an official Continuity Log PDF for the latest take in scene "${scene || 'EXT. ROOFTOP - NIGHT'}".`,
    },
    {
      label: '⚖️ Compare Latest Takes',
      text: `Compare Take 1 and Take 2 in scene "${scene || 'EXT. ROOFTOP - NIGHT'}" for ${character || 'Alice'} and highlight continuity risks.`,
    },
    {
      label: '📋 Generate Fix Checklist',
      text: `Check continuity for "${character || 'Alice'}" in scene "${scene || 'EXT. ROOFTOP - NIGHT'}", identify all discrepancies, and generate a department action checklist for the crew before the next take.`,
    },
  ]

  return (
    <div className="agent-copilot-container">
      {/* Context bar */}
      <div className="agent-context-strip">
        <div className="agent-context-field">
          <label htmlFor="agent-scene">Active Scene:</label>
          <input
            id="agent-scene"
            type="text"
            placeholder="e.g. EXT. ROOFTOP - NIGHT"
            value={scene}
            onChange={e => onSceneChange(e.target.value)}
          />
        </div>
        <div className="agent-context-field">
          <label htmlFor="agent-char">Character:</label>
          <input
            id="agent-char"
            type="text"
            placeholder="e.g. Alice"
            value={character}
            onChange={e => onCharacterChange(e.target.value)}
          />
        </div>
        <div className="agent-context-badge">
          {scriptContext ? '📜 Script Grounded' : '📄 No Script PDF'}
        </div>
      </div>

      {/* Suggested prompts chips */}
      <div className="agent-chips-wrap">
        <span className="agent-chips-label">Quick Actions:</span>
        <div className="agent-chips-list">
          {promptChips.map((chip, idx) => (
            <button
              key={idx}
              type="button"
              className="agent-chip-btn"
              disabled={loading}
              onClick={() => handleSend(chip.text)}
            >
              {chip.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chat Messages */}
      <div className="agent-chat-window">
        {messages.map(m => (
          <div
            key={m.id}
            className={`agent-bubble-row ${m.role === 'user' ? 'bubble-row--user' : 'bubble-row--agent'}`}
          >
            <div className={`agent-bubble ${m.role === 'user' ? 'agent-bubble--user' : 'agent-bubble--agent'}`}>
              <div className="agent-bubble-sender">
                {m.role === 'user' ? '👤 Supervisor' : '🤖 Agent Copilot'}
              </div>

              <Markdown text={m.text} />

              {/* Tool Execution Trace */}
              {m.toolCalls && m.toolCalls.length > 0 && (
                <div className="agent-tools-trace-box">
                  <div className="agent-tools-trace-heading">
                    <span className="trace-heading-icon">🛠️</span>
                    <span>Autonomous Tool Execution ({m.toolCalls.length})</span>
                  </div>
                  <div className="agent-tools-trace-list">
                    {m.toolCalls.map((tc, i) => (
                      <ToolTraceCard key={i} trace={tc} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="agent-bubble-row bubble-row--agent">
            <div className="agent-bubble agent-bubble--agent agent-bubble--thinking">
              <div className="agent-thinking-spinner"></div>
              <span>Agent Copilot is analyzing context, querying database, and invoking tools…</span>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {errorMsg && (
        <div className="agent-error-banner">
          <span>⚠️ {errorMsg}</span>
          <button type="button" onClick={() => setErrorMsg(null)}>✕</button>
        </div>
      )}

      {/* Input area */}
      <form
        className="agent-input-form"
        onSubmit={e => {
          e.preventDefault()
          void handleSend()
        }}
      >
        <input
          type="text"
          className="agent-input-field"
          placeholder="Ask the agent (e.g. 'Check Alice\'s takes and alert the makeup department')..."
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={loading}
        />
        <button type="submit" className="agent-send-btn" disabled={loading || !input.trim()}>
          {loading ? '…' : 'Send ⮞'}
        </button>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Phase 4 Step 4: Hands-Free Voice Mode
// ---------------------------------------------------------------------------
type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking'

function VoiceModeView({
  scene,
  character,
  onSceneChange,
  onCharacterChange,
}: {
  scene: string
  character: string
  onSceneChange: (s: string) => void
  onCharacterChange: (c: string) => void
}) {
  const [voiceState, setVoiceState]       = useState<VoiceState>('idle')
  const [transcript, setTranscript]       = useState('')
  const [agentReply, setAgentReply]       = useState('')
  const [toolCalls, setToolCalls]         = useState<ToolTraceItem[]>([])
  const [drawerOpen, setDrawerOpen]       = useState(false)
  const [voices, setVoices]               = useState<SpeechSynthesisVoice[]>([])
  const [selectedVoice, setSelectedVoice] = useState('')
  const [errorMsg, setErrorMsg]           = useState<string | null>(null)
  const [autoRearm, setAutoRearm]         = useState(true)

  const recognitionRef = useRef<any>(null)
  const transcriptRef  = useRef('')

  // Load TTS voices
  useEffect(() => {
    const load = () => {
      const v = window.speechSynthesis.getVoices()
      setVoices(v)
      if (v.length > 0 && !selectedVoice) {
        const en = v.find(x => x.lang.startsWith('en'))
        if (en) setSelectedVoice(en.name)
      }
    }
    load()
    window.speechSynthesis.onvoiceschanged = load
    return () => { window.speechSynthesis.onvoiceschanged = null }
  }, [])

  function startListening() {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) {
      setErrorMsg('Speech recognition is not supported in this browser. Use Chrome or Edge.')
      return
    }
    setErrorMsg(null)
    setTranscript('')
    setAgentReply('')
    setToolCalls([])
    transcriptRef.current = ''

    const rec = new SR()
    rec.lang = 'en-US'
    rec.continuous = false
    rec.interimResults = true
    recognitionRef.current = rec

    rec.onstart = () => setVoiceState('listening')

    rec.onresult = (e: any) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const results: any[] = Array.from(e.results)
      const t = results.map((r: any) => r[0].transcript).join('')
      setTranscript(t)
      transcriptRef.current = t
    }

    rec.onend = () => {
      const spoken = transcriptRef.current.trim()
      if (spoken) {
        void runAgentWithVoice(spoken)
      } else {
        setVoiceState('idle')
      }
    }

    rec.onerror = (e: any) => {
      if (e.error !== 'no-speech') {
        setErrorMsg(`Mic error: ${e.error}`)
      }
      setVoiceState('idle')
    }

    rec.start()
    setVoiceState('listening')
  }

  function stopAll() {
    recognitionRef.current?.stop()
    window.speechSynthesis.cancel()
    setVoiceState('idle')
  }

  async function runAgentWithVoice(text: string) {
    setVoiceState('processing')
    try {
      const res = await fetch(AGENT_QUERY_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: text,
          scene: scene.trim(),
          character: character.trim(),
        }),
      })
      if (!res.ok) throw new Error(`Server ${res.status}: ${await res.text()}`)
      const data = await res.json()
      const reply = (data.response as string) || 'Analysis complete.'
      setAgentReply(reply)
      setToolCalls(data.tool_calls || [])
      speakReply(reply)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err))
      setVoiceState('idle')
    }
  }

  function speakReply(text: string) {
    setVoiceState('speaking')
    window.speechSynthesis.cancel()
    // Strip markdown for cleaner TTS
    const clean = text
      .replace(/^#{1,6}\s/gm, '')
      .replace(/\*\*/g, '')
      .replace(/\*/g, '')
      .replace(/`/g, '')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .slice(0, 1200) // cap at ~1200 chars to avoid very long reads

    const utter = new SpeechSynthesisUtterance(clean)
    utter.rate  = 0.95
    utter.pitch = 1.0
    if (selectedVoice) {
      const v = voices.find(x => x.name === selectedVoice)
      if (v) utter.voice = v
    }
    utter.onend = () => {
      setVoiceState('idle')
      if (autoRearm) setTimeout(startListening, 1200)
    }
    utter.onerror = () => setVoiceState('idle')
    window.speechSynthesis.speak(utter)
  }

  const isIdle       = voiceState === 'idle'
  const isListening  = voiceState === 'listening'
  const isProcessing = voiceState === 'processing'
  const isSpeaking   = voiceState === 'speaking'

  const STATE_LABEL: Record<VoiceState, string> = {
    idle:       'Tap to speak',
    listening:  'Listening…',
    processing: 'Agent processing…',
    speaking:   'Agent speaking…',
  }

  return (
    <div className="voice-mode-container">

      {/* Shared context bar */}
      <div className="agent-context-strip">
        <div className="agent-context-field">
          <label htmlFor="voice-scene">Active Scene:</label>
          <input
            id="voice-scene"
            type="text"
            placeholder="e.g. EXT. ROOFTOP - NIGHT"
            value={scene}
            onChange={e => onSceneChange(e.target.value)}
          />
        </div>
        <div className="agent-context-field">
          <label htmlFor="voice-char">Character:</label>
          <input
            id="voice-char"
            type="text"
            placeholder="e.g. Alice"
            value={character}
            onChange={e => onCharacterChange(e.target.value)}
          />
        </div>
      </div>

      {/* Voice settings row */}
      <div className="voice-settings-row">
        {voices.length > 0 && (
          <div className="voice-selector-wrap">
            <label htmlFor="voice-select">🔊 Voice:</label>
            <select
              id="voice-select"
              value={selectedVoice}
              onChange={e => setSelectedVoice(e.target.value)}
            >
              {voices
                .filter(v => v.lang.startsWith('en'))
                .map(v => (
                  <option key={v.name} value={v.name}>{v.name} ({v.lang})</option>
                ))}
            </select>
          </div>
        )}
        <label className="voice-rearm-toggle">
          <input
            type="checkbox"
            checked={autoRearm}
            onChange={e => setAutoRearm(e.target.checked)}
          />
          Auto-rearm
        </label>
      </div>

      {/* Mic button + status */}
      <div className="voice-main-area">
        <div className={`voice-mic-wrap${isListening ? ' voice-mic-wrap--listening' : ''}`}>
          {isListening && (
            <>
              <div className="voice-pulse-ring voice-pulse-ring--1" />
              <div className="voice-pulse-ring voice-pulse-ring--2" />
              <div className="voice-pulse-ring voice-pulse-ring--3" />
            </>
          )}
          <button
            type="button"
            id="voice-mic-btn"
            className={`voice-mic-btn voice-mic-btn--${voiceState}`}
            onClick={isIdle ? startListening : stopAll}
            disabled={isProcessing}
            aria-label={isIdle ? 'Start listening' : 'Stop'}
          >
            <span className="voice-mic-icon">
              {isProcessing ? '⚙️' : isSpeaking ? '🔊' : isListening ? '⏹' : '🎤'}
            </span>
          </button>
        </div>

        <div className={`voice-state-label voice-state-label--${voiceState}`}>
          {STATE_LABEL[voiceState]}
        </div>

        {isIdle && !agentReply && (
          <p className="voice-hint">
            Say: <em>“Check continuity for Alice and alert the makeup crew”</em>
          </p>
        )}
      </div>

      {/* Live transcript */}
      {transcript && (
        <div className="voice-transcript">
          <span className="voice-transcript-label">🎤 You said:</span>
          <p className="voice-transcript-text">&ldquo;{transcript}&rdquo;</p>
        </div>
      )}

      {/* Agent text reply */}
      {agentReply && (
        <div className={`voice-reply-card${isSpeaking ? ' voice-reply-card--speaking' : ''}`}>
          <div className="voice-reply-header">
            <span>🤖 Agent Copilot</span>
            {isSpeaking && <span className="voice-speaking-dot" />}
          </div>
          <Markdown text={agentReply} />
        </div>
      )}

      {/* Tool trace collapsible */}
      {toolCalls.length > 0 && (
        <div className="voice-tool-drawer">
          <button
            type="button"
            className="voice-tool-drawer-toggle"
            onClick={() => setDrawerOpen(o => !o)}
          >
            <span>🛠️ {toolCalls.length} tool{toolCalls.length !== 1 ? 's' : ''} called autonomously</span>
            <span>{drawerOpen ? '▴' : '▾'}</span>
          </button>
          {drawerOpen && (
            <div className="voice-tool-drawer-list">
              {toolCalls.map((tc, i) => (
                <ToolTraceCard key={i} trace={tc} />
              ))}
            </div>
          )}
        </div>
      )}

      {errorMsg && (
        <div className="agent-error-banner">
          <span>⚠️ {errorMsg}</span>
          <button type="button" onClick={() => setErrorMsg(null)}>✕</button>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main app
// ---------------------------------------------------------------------------
type Page = 'check' | 'agent' | 'voice' | 'history'

function App() {
  const [page, setPage] = useState<Page>('check')
  const [mode, setMode] = useState<Mode>('single')
  const [scene, setScene] = useState('')
  const [take, setTake] = useState('')
  const [takeRef, setTakeRef] = useState('')
  const [takeCurrent, setTakeCurrent] = useState('')
  const [character, setCharacter] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [refFile, setRefFile] = useState<File | null>(null)
  const [refPreview, setRefPreview] = useState<string | null>(null)
  const [curFile, setCurFile] = useState<File | null>(null)
  const [curPreview, setCurPreview] = useState<string | null>(null)
  const [scriptContext, setScriptContext] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [result, setResult] = useState<CheckResult | null>(null)
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [refreshCounter, setRefreshCounter] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const refInputRef = useRef<HTMLInputElement>(null)
  const curInputRef = useRef<HTMLInputElement>(null)

  function switchMode(m: Mode) {
    setMode(m)
    setStatus('idle')
    setResult(null)
    setCompareResult(null)
    setErrorMsg(null)
  }

  function makeFileHandler(
    setter: (f: File | null) => void,
    previewSetter: (u: string | null) => void,
  ) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0] ?? null
      setter(f)
      previewSetter(f ? URL.createObjectURL(f) : null)
    }
  }

  async function handleSingleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return
    setStatus('loading'); setResult(null); setErrorMsg(null)
    const body = new FormData()
    body.append('scene', scene)
    body.append('take', take)
    body.append('character', character)
    body.append('file', file)
    body.append('script_context', scriptContext)
    try {
      const res = await fetch(API_URL, { method: 'POST', body })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`)
      setResult(await res.json())
      setStatus('success')
      setRefreshCounter(c => c + 1)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }

  async function handleCompareSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!refFile || !curFile) return
    setStatus('loading'); setCompareResult(null); setErrorMsg(null)
    const body = new FormData()
    body.append('scene', scene)
    body.append('take_ref', takeRef)
    body.append('take_current', takeCurrent)
    body.append('character', character)
    body.append('reference', refFile)
    body.append('current', curFile)
    body.append('script_context', scriptContext)
    try {
      const res = await fetch(COMPARE_URL, { method: 'POST', body })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`)
      setCompareResult(await res.json())
      setStatus('success')
      setRefreshCounter(c => c + 1)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }

  const isSingle = mode === 'single'
  const submitDisabled = status === 'loading' ||
    (isSingle ? !file : !refFile || !curFile)

  return (
    <>
      <AlertFeed />
      <section id="center">
        <div>
          <h1>Flawless Take</h1>
          <p className="subtitle">Makeup continuity check — tablet view</p>
        </div>

        {/* Page nav */}
        <div className="mode-toggle">
          <button type="button"
            className={`mode-btn ${page === 'check' ? 'mode-btn--active' : ''}`}
            onClick={() => setPage('check')}>
            Check
          </button>
          <button type="button"
            className={`mode-btn ${page === 'agent' ? 'mode-btn--active' : ''}`}
            onClick={() => setPage('agent')}>
            🤖 Agent Copilot
          </button>
          <button type="button"
            id="voice-mode-tab"
            className={`mode-btn ${page === 'voice' ? 'mode-btn--active' : ''}`}
            onClick={() => setPage('voice')}>
            🎤 Voice Mode
          </button>
          <button type="button"
            className={`mode-btn ${page === 'history' ? 'mode-btn--active' : ''}`}
            onClick={() => setPage('history')}>
            History
          </button>
        </div>

        {/* History page */}
        {page === 'history' && <HistoryTab />}

        {/* Agent Copilot page */}
        {page === 'agent' && (
          <AgentCopilotView
            scene={scene}
            character={character}
            scriptContext={scriptContext}
            onSceneChange={setScene}
            onCharacterChange={setCharacter}
          />
        )}

        {/* Voice Mode page */}
        {page === 'voice' && (
          <VoiceModeView
            scene={scene}
            character={character}
            onSceneChange={setScene}
            onCharacterChange={setCharacter}
          />
        )}

        {/* Check page */}
        {page === 'check' && <>
        {/* Mode toggle */}
        <div className="mode-toggle">
          <button type="button"
            className={`mode-btn ${isSingle ? 'mode-btn--active' : ''}`}
            onClick={() => switchMode('single')}>
            Single check
          </button>
          <button type="button"
            className={`mode-btn ${!isSingle ? 'mode-btn--active' : ''}`}
            onClick={() => switchMode('compare')}>
            Compare takes
          </button>
        </div>

        <form className="check-form"
          onSubmit={isSingle ? handleSingleSubmit : handleCompareSubmit}>
          <ScriptPanel onContext={setScriptContext} />

          {/* Common fields */}
          <div className="form-row">
            <label htmlFor="scene">Scene</label>
            <input id="scene" type="text" placeholder="e.g. INT. BEDROOM – DAY"
              value={scene} onChange={e => setScene(e.target.value)} required />
          </div>

          <div className="form-row">
            <label htmlFor="character">Character</label>
            <input id="character" type="text" placeholder="e.g. Elena"
              value={character} onChange={e => setCharacter(e.target.value)} required />
          </div>

          <SceneMemoryTimeline
            scene={scene}
            character={character}
            refreshTrigger={refreshCounter}
            onSelectReferenceTake={(t) => {
              setMode('compare')
              setTakeRef(t)
            }}
          />

          {/* Single mode */}
          {isSingle && <>
            <div className="form-row">
              <label htmlFor="take">Take #</label>
              <input id="take" type="text" placeholder="e.g. 3"
                value={take} onChange={e => setTake(e.target.value)} required />
            </div>
            <ImageDrop id="photo" label="Photo" preview={preview}
              inputRef={fileInputRef}
              onChange={makeFileHandler(setFile, setPreview)} />
          </>}

          {/* Compare mode */}
          {!isSingle && <>
            <div className="form-row-pair">
              <div className="form-row">
                <label htmlFor="take-ref">Reference take #</label>
                <input id="take-ref" type="text" placeholder="e.g. 2"
                  value={takeRef} onChange={e => setTakeRef(e.target.value)} required />
              </div>
              <div className="form-row">
                <label htmlFor="take-cur">Current take #</label>
                <input id="take-cur" type="text" placeholder="e.g. 3"
                  value={takeCurrent} onChange={e => setTakeCurrent(e.target.value)} required />
              </div>
            </div>
            <div className="form-row-pair">
              <ImageDrop id="ref-photo" label="Reference photo"
                preview={refPreview} inputRef={refInputRef}
                onChange={makeFileHandler(setRefFile, setRefPreview)} />
              <ImageDrop id="cur-photo" label="Current photo"
                preview={curPreview} inputRef={curInputRef}
                onChange={makeFileHandler(setCurFile, setCurPreview)} />
            </div>
          </>}

          <button type="submit" className="submit-btn" disabled={submitDisabled}>
            {status === 'loading'
              ? 'Analysing…'
              : isSingle ? 'Check Take' : 'Compare Takes'}
          </button>
        </form>

        {/* Single result */}
        {status === 'success' && result && (
          <div className="result-box result-box--ok">
            <p className="result-label">
              Continuity report — {result.character} · Scene {result.scene} · Take {result.take}
              {result.script_grounded && <span className="grounded-badge"> · script grounded</span>}
            </p>
            {result.preview_url && (
              <div className="result-preview-container">
                <img src={getMediaUrl(result.preview_url)} className="result-preview-img" alt={`Take ${result.take}`} />
              </div>
            )}
            <Markdown text={result.result} />
            <p className="result-meta-line">
              {result.filename} · {(result.size_bytes / 1024).toFixed(1)} KB
            </p>
            {result.id && (
              <div className="pdf-export-row">
                <button
                  type="button"
                  className="pdf-export-btn"
                  onClick={() => downloadPdf(result.id!, `continuity_${result.scene}_take_${result.take}.pdf`)}
                >
                  📄 Export Continuity Log (PDF)
                </button>
              </div>
            )}
          </div>
        )}

        {/* Compare result */}
        {status === 'success' && compareResult && (
          <div className="result-box result-box--ok">
            <p className="result-label">
              Comparison — {compareResult.character} · Scene {compareResult.scene}
              · Take {compareResult.take_ref} vs {compareResult.take_current}
              {' '}<MatchBadge score={compareResult.match_score} />
              {compareResult.script_grounded && <span className="grounded-badge"> · script grounded</span>}
            </p>
            {(compareResult.preview_ref_url || compareResult.preview_cur_url) && (
              <div className="history-previews">
                {compareResult.preview_ref_url && (
                  <img src={getMediaUrl(compareResult.preview_ref_url)} className="history-preview-img" alt="Reference take" />
                )}
                {compareResult.preview_cur_url && (
                  <img src={getMediaUrl(compareResult.preview_cur_url)} className="history-preview-img" alt="Current take" />
                )}
              </div>
            )}
            <Markdown text={compareResult.differences} />
            <p className="result-meta-line">
              REF: {compareResult.ref_filename} · CUR: {compareResult.cur_filename}
            </p>
            {compareResult.id && (
              <div className="pdf-export-row">
                <button
                  type="button"
                  className="pdf-export-btn"
                  onClick={() => downloadPdf(compareResult.id!, `continuity_${compareResult.scene}_take_${compareResult.take_ref}_vs_${compareResult.take_current}.pdf`)}
                >
                  📄 Export Continuity Log (PDF)
                </button>
              </div>
            )}
          </div>
        )}

        {status === 'error' && errorMsg && (
          <div className="result-box result-box--err">
            <p className="result-label">Error</p>
            <p className="result-value">{errorMsg}</p>
          </div>
        )}
        </>}
      </section>

      <div className="ticks"></div>
      <section id="spacer"></section>
    </>
  )
}

export default App
