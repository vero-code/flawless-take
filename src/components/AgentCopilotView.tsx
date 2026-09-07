import React, { useEffect, useRef, useState } from 'react'
import { AGENT_QUERY_URL } from '../config'
import type { AgentChatMessage } from '../types'
import { Markdown } from './Markdown'
import { ToolTraceCard } from './ToolTraceCard'

export function AgentCopilotView({
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
