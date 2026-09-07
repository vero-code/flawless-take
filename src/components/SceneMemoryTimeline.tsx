import { useEffect, useState } from 'react'
import { API_BASE, getMediaUrl } from '../config'
import type { SceneStateData } from '../types'

export function SceneMemoryTimeline({
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
