import { useEffect, useRef, useState } from 'react'
import { AGENT_QUERY_URL } from '../config'
import type { ToolTraceItem, VoiceState } from '../types'
import { Markdown } from './Markdown'
import { ToolTraceCard } from './ToolTraceCard'

export function VoiceModeView({
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
