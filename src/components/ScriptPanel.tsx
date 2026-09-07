import React, { useRef, useState } from 'react'
import { SCRIPT_URL } from '../config'
import type { ScriptNotes } from '../types'

export function ScriptPanel({ onContext }: { onContext: (ctx: string) => void }) {
  const [open, setOpen] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [notes, setNotes] = useState<ScriptNotes | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    setUploadStatus('loading')
    setNotes(null)
    setErrorMsg('')
    onContext('')

    const body = new FormData()
    body.append('file', f)

    try {
      const res = await fetch(SCRIPT_URL, { method: 'POST', body })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
      const data = await res.json()
      const n: ScriptNotes = data.notes
      setNotes(n)
      setUploadStatus('done')
      // Build a compact context string to pass into check-take
      const ctxParts: string[] = []
      if (n.general_notes) ctxParts.push(`General notes: ${n.general_notes}`)
      n.characters.forEach(c => {
        if (c.appearance_notes) ctxParts.push(`${c.name}: ${c.appearance_notes}`)
      })
      n.scenes.forEach(s => {
        if (s.continuity_notes) ctxParts.push(`Scene ${s.scene_number} (${s.heading}): ${s.continuity_notes}`)
      })
      onContext(ctxParts.join('\n'))
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err))
      setUploadStatus('error')
    }
  }

  return (
    <div className="script-panel">
      <button type="button" className="script-toggle" onClick={() => setOpen(o => !o)}>
        <span className="script-toggle-icon">{open ? '▾' : '▸'}</span>
        Script grounding
        {notes && <span className="script-badge">active</span>}
      </button>

      {open && (
        <div className="script-body">
          <p className="script-hint">
            Upload a PDF shooting script to ground the continuity check against scene and character descriptions.
          </p>

          <div
            className="file-drop script-drop"
            onClick={() => inputRef.current?.click()}
          >
            {uploadStatus === 'loading'
              ? <span className="file-placeholder">Parsing script…</span>
              : uploadStatus === 'done' && notes
              ? <span className="file-placeholder script-ok">✓ {notes.scenes.length} scene{notes.scenes.length !== 1 ? 's' : ''} · {notes.characters.length} character{notes.characters.length !== 1 ? 's' : ''}</span>
              : <span className="file-placeholder">Tap to select PDF script</span>
            }
            <input ref={inputRef} type="file" accept="application/pdf" onChange={handleFile} />
          </div>

          {uploadStatus === 'error' && (
            <p className="script-error">{errorMsg}</p>
          )}

          {notes && notes.characters.length > 0 && (
            <div className="script-notes">
              {notes.general_notes && (
                <p className="script-note-item"><strong>General:</strong> {notes.general_notes}</p>
              )}
              {notes.characters.map((c, i) => c.appearance_notes && (
                <p key={i} className="script-note-item"><strong>{c.name}:</strong> {c.appearance_notes}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
