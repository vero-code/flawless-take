import React, { useEffect, useState } from 'react'
import { HISTORY_URL, downloadPdf, getMediaUrl } from '../config'
import type { HistoryRecord } from '../types'
import { Markdown } from './Markdown'
import { MatchBadge } from './MatchBadge'

export function HistoryTab() {
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
