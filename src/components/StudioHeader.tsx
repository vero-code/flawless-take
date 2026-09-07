import { useEffect, useState } from 'react'
import { McpStatusBadge } from './McpStatusBadge'
import { BrandLogo } from './BrandLogo'

export function StudioHeader() {
  const [timecode, setTimecode] = useState('01:24:18:00')

  useEffect(() => {
    let frame = 0
    let sec = 18
    let min = 24
    const interval = setInterval(() => {
      frame = (frame + 1) % 24
      if (frame === 0) {
        sec = (sec + 1) % 60
        if (sec === 0) min = (min + 1) % 60
      }
      const pad = (n: number) => String(n).padStart(2, '0')
      setTimecode(`01:${pad(min)}:${pad(sec)}:${pad(frame)}`)
    }, 1000 / 24)
    return () => clearInterval(interval)
  }, [])

  return (
    <header className="studio-header">
      <div className="studio-header-left">
        <div className="studio-brand">
          <BrandLogo />
        </div>

        <div className="studio-prod-badge">
          <span className="studio-rec-dot"></span>
          <span className="studio-prod-name">PROD: "NEON HORIZON"</span>
          <span className="studio-prod-cam">A-CAM · ALEXA 35</span>
        </div>
      </div>

      <div className="studio-header-right">
        <div className="studio-timecode-hud">
          <span className="studio-tc-label">TC / 24 FPS</span>
          <span className="studio-tc-val">{timecode}</span>
        </div>

        <div className="studio-telemetry">
          <div className="studio-telemetry-item studio-telemetry-item--ai" title="Google GenAI / Vertex AI Engine">
            <span className="studio-dot studio-dot--ai"></span>
            <span>Gemini 3.8 Flash</span>
          </div>
          <div className="studio-telemetry-item studio-telemetry-item--confluent" title="Confluent Kafka Event Bus — Real-time Crew Alert Broadcasts">
            <span className="studio-dot studio-dot--confluent"></span>
            <span>Confluent Kafka</span>
          </div>
          <div className="studio-telemetry-item studio-telemetry-item--ibm" title="IBM Partner Track — Bob Architecture & Data Scaffolding">
            <span className="studio-dot studio-dot--ibm"></span>
            <span>IBM Bob</span>
          </div>
          <McpStatusBadge />
        </div>
      </div>
    </header>
  )
}
