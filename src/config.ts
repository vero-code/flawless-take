/**
 * config.ts - API Endpoints, Media Resolution, and PDF Export Helpers
 */

export const API_BASE = (typeof window !== 'undefined' && window.location.port !== '5173')
  ? window.location.origin
  : 'http://localhost:8000'
export const API_URL         = `${API_BASE}/api/check-take`
export const COMPARE_URL     = `${API_BASE}/api/compare-takes`
export const SCRIPT_URL      = `${API_BASE}/api/upload-script`
export const ALERTS_URL      = `${API_BASE}/api/alerts`
export const HISTORY_URL     = `${API_BASE}/api/history`
export const MCP_INFO_URL    = `${API_BASE}/api/mcp-info`
export const AGENT_QUERY_URL = `${API_BASE}/api/agent/query`

export const RISK_TOAST: Record<string, string> = {
  HIGH: 'toast--high',
  MEDIUM: 'toast--medium',
  LOW: 'toast--low',
}

export function getMediaUrl(url?: string | null): string | undefined {
  if (!url) return undefined
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `${API_BASE}${url.startsWith('/') ? '' : '/'}${url}`
}

export async function downloadPdf(recordId: number, filename?: string) {
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
