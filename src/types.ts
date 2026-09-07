/**
 * types.ts - Shared TypeScript Definitions for Flawless Take UI
 */

export type Mode = 'single' | 'compare'
export type Status = 'idle' | 'loading' | 'success' | 'error'
export type Page = 'check' | 'agent' | 'voice' | 'history'
export type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking'

export type CheckResult = {
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

export type CompareResult = {
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

export type ScriptNotes = {
  scenes: {
    scene_number: string
    heading: string
    characters: string[]
    continuity_notes: string
  }[]
  characters: {
    name: string
    appearance_notes: string
  }[]
  general_notes: string
}

export type HistoryRecord = {
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

export type AlertEvent = {
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

export type Toast = AlertEvent & { id: number }

export type SceneTimelineItem = {
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

export type SceneStateData = {
  scene: string
  character: string
  total_takes: number
  drift_status: 'STABLE' | 'DRIFTING' | 'CRITICAL'
  baseline_take?: string | null
  timeline: SceneTimelineItem[]
  known_discrepancies: string[]
}

export type ToolTraceItem = {
  tool: string
  args: Record<string, any>
  result: any
}

export type DepartmentChecklist = {
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

export type AgentChatMessage = {
  id: string
  role: 'user' | 'agent'
  text: string
  toolCalls?: ToolTraceItem[]
  actionsTaken?: string[]
  timestamp: number
}

export type McpInfo = {
  server_name: string
  version: string
  tool_count: number
  sse_endpoint: string
  tools: string[]
  claude_desktop_config: object
}
