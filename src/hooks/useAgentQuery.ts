/**
 * useAgentQuery.ts — Shared hook for calling /api/agent/query
 *
 * Used by AgentCopilotView (chat mode) and VoiceModeView (voice mode)
 * to avoid duplicating the fetch logic.
 */
import { useState } from 'react'
import { AGENT_QUERY_URL } from '../config'
import type { ToolTraceItem } from '../types'

export interface AgentQueryPayload {
  prompt: string
  scene?: string
  character?: string
  script_context?: string
}

export interface AgentQueryResult {
  response: string
  tool_calls?: ToolTraceItem[]
  actions_taken?: string[]
}

export function useAgentQuery() {
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  async function query(payload: AgentQueryPayload): Promise<AgentQueryResult | null> {
    setLoading(true)
    setErrorMsg(null)
    try {
      const res = await fetch(AGENT_QUERY_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: payload.prompt,
          scene: (payload.scene ?? '').trim(),
          character: (payload.character ?? '').trim(),
          script_context: (payload.script_context ?? '').trim(),
        }),
      })
      if (!res.ok) {
        const errText = await res.text()
        throw new Error(`Server returned ${res.status}: ${errText}`)
      }
      const data = await res.json()
      return {
        response: (data.response as string) || 'Tools executed successfully.',
        tool_calls: data.tool_calls || [],
        actions_taken: data.actions_taken || [],
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMsg(msg)
      return null
    } finally {
      setLoading(false)
    }
  }

  return { query, loading, errorMsg, setErrorMsg }
}
