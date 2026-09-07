import { useEffect, useRef, useState } from 'react'
import { ALERTS_URL, RISK_TOAST } from '../config'
import type { AlertEvent, Toast } from '../types'

/**
 * Alert feed — SSE consumer + toast overlay for real-time Kafka & SSE continuity events
 */
export function AlertFeed() {
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
        )
          return
        const id = ++counterRef.current
        setToasts((prev) => [...prev.slice(-4), { ...payload, id }])
        // auto-dismiss after 8 s
        setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 8000)
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
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`alert-toast ${RISK_TOAST[t.risk_level ?? ''] ?? ''}`}
          onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
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
            {t.character ? `${t.character} · ` : ''}
            {t.scene}
            {t.event === 'takes_comparison'
              ? ` · Take ${t.take_ref} vs ${t.take_current}`
              : t.take
              ? ` · Take ${t.take}`
              : ''}
            {t.message ? ` — ${t.message}` : ''}
          </span>
          <span className="alert-meta">
            {t.risk_level && (
              <span className={`alert-risk risk--${t.risk_level?.toLowerCase()}`}>
                {t.risk_level}
              </span>
            )}
            {t.match_score && <span className="alert-score">{t.match_score}</span>}
          </span>
        </div>
      ))}
    </div>
  )
}
