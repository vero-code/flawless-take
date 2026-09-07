import { useEffect, useState } from 'react'
import { MCP_INFO_URL } from '../config'
import type { McpInfo } from '../types'

/**
 * MCP Status Badge — displays connection details and Claude Desktop config drawer
 */
export function McpStatusBadge() {
  const [info, setInfo] = useState<McpInfo | null>(null)
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    fetch(MCP_INFO_URL)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setInfo(d))
      .catch(() => {
        /* backend not running */
      })
  }, [])

  if (!info) return null

  const configJson = JSON.stringify(info.claude_desktop_config, null, 2)

  function copyConfig() {
    navigator.clipboard.writeText(configJson).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="mcp-badge-wrap">
      <button
        type="button"
        className={`mcp-badge${open ? ' mcp-badge--open' : ''}`}
        onClick={() => setOpen((o) => !o)}
        title="Studio MCP Server — click for connection details"
      >
        <span className="mcp-badge-dot" />
        <span>🔌 MCP</span>
        <span className="mcp-badge-count">{info.tool_count} tools</span>
        <span className="mcp-badge-caret">{open ? '▴' : '▾'}</span>
      </button>

      {open && (
        <div className="mcp-drawer">
          <div className="mcp-drawer-header">
            <span className="mcp-drawer-title">{info.server_name}</span>
            <span className="mcp-drawer-version">v{info.version}</span>
          </div>
          <div className="mcp-drawer-endpoint">
            <span className="mcp-endpoint-label">SSE endpoint:</span>
            <code className="mcp-endpoint-url">http://localhost:8000{info.sse_endpoint}</code>
          </div>
          <div className="mcp-drawer-tools">
            {info.tools.map((t) => (
              <span key={t} className="mcp-tool-chip">
                {t}
              </span>
            ))}
          </div>
          <div className="mcp-drawer-config-label">
            Claude Desktop <code>mcp.json</code>:
          </div>
          <pre className="mcp-config-pre">{configJson}</pre>
          <button type="button" className="mcp-copy-btn" onClick={copyConfig}>
            {copied ? '✅ Copied!' : '📋 Copy config'}
          </button>
        </div>
      )}
    </div>
  )
}
