import { useRef, useState } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000/api/check-take'
const SCRIPT_URL = 'http://localhost:8000/api/upload-script'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type CheckResult = {
  scene: string
  take: string
  character: string
  filename: string
  size_bytes: number
  result: string
  script_grounded: boolean
}

type ScriptNotes = {
  scenes: { scene_number: string; heading: string; characters: string[]; continuity_notes: string }[]
  characters: { name: string; appearance_notes: string }[]
  general_notes: string
}

type Status = 'idle' | 'loading' | 'success' | 'error'

// ---------------------------------------------------------------------------
// Minimal markdown renderer — h3, bold, italic, bullets, hr
// ---------------------------------------------------------------------------
function Markdown({ text }: { text: string }) {
  const lines = text.split('\n')
  const elements: React.ReactNode[] = []
  let listBuffer: string[] = []

  function flushList() {
    if (listBuffer.length === 0) return
    elements.push(
      <ul key={elements.length} className="md-list">
        {listBuffer.map((item, i) => (
          <li key={i} dangerouslySetInnerHTML={{ __html: inlineFormat(item) }} />
        ))}
      </ul>
    )
    listBuffer = []
  }

  function inlineFormat(s: string): string {
    return s
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
  }

  for (const raw of lines) {
    const line = raw.trimEnd()
    if (/^#{1,3}\s/.test(line)) {
      flushList()
      elements.push(
        <h3 key={elements.length} className="md-h3"
          dangerouslySetInnerHTML={{ __html: inlineFormat(line.replace(/^#{1,3}\s/, '')) }} />
      )
    } else if (/^(\*|-)\s/.test(line)) {
      listBuffer.push(line.replace(/^(\*|-)\s/, ''))
    } else if (/^---+$/.test(line)) {
      flushList()
      elements.push(<hr key={elements.length} className="md-hr" />)
    } else if (line === '') {
      flushList()
    } else {
      flushList()
      elements.push(
        <p key={elements.length} className="md-p"
          dangerouslySetInnerHTML={{ __html: inlineFormat(line) }} />
      )
    }
  }
  flushList()
  return <div className="md-body">{elements}</div>
}

// ---------------------------------------------------------------------------
// Script panel — upload PDF, show extracted notes, return context string
// ---------------------------------------------------------------------------
function ScriptPanel({ onContext }: { onContext: (ctx: string) => void }) {
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

// ---------------------------------------------------------------------------
// Main app
// ---------------------------------------------------------------------------
function App() {
  const [scene, setScene] = useState('')
  const [take, setTake] = useState('')
  const [character, setCharacter] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [scriptContext, setScriptContext] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [result, setResult] = useState<CheckResult | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const chosen = e.target.files?.[0] ?? null
    setFile(chosen)
    setPreview(chosen ? URL.createObjectURL(chosen) : null)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return

    setStatus('loading')
    setResult(null)
    setErrorMsg(null)

    const body = new FormData()
    body.append('scene', scene)
    body.append('take', take)
    body.append('character', character)
    body.append('file', file)
    body.append('script_context', scriptContext)

    try {
      const res = await fetch(API_URL, { method: 'POST', body })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(`${res.status} ${res.statusText}: ${text}`)
      }
      const data: CheckResult = await res.json()
      setResult(data)
      setStatus('success')
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }

  return (
    <>
      <section id="center">
        <div>
          <h1>Flawless Take</h1>
          <p className="subtitle">Makeup continuity check — tablet view</p>
        </div>

        <form className="check-form" onSubmit={handleSubmit}>
          <ScriptPanel onContext={setScriptContext} />

          <div className="form-row">
            <label htmlFor="scene">Scene</label>
            <input
              id="scene"
              type="text"
              placeholder="e.g. INT. BEDROOM – DAY"
              value={scene}
              onChange={e => setScene(e.target.value)}
              required
            />
          </div>

          <div className="form-row">
            <label htmlFor="take">Take #</label>
            <input
              id="take"
              type="text"
              placeholder="e.g. 3"
              value={take}
              onChange={e => setTake(e.target.value)}
              required
            />
          </div>

          <div className="form-row">
            <label htmlFor="character">Character</label>
            <input
              id="character"
              type="text"
              placeholder="e.g. Elena"
              value={character}
              onChange={e => setCharacter(e.target.value)}
              required
            />
          </div>

          <div className="form-row">
            <label htmlFor="photo">Photo</label>
            <div className="file-drop" onClick={() => fileInputRef.current?.click()}>
              {preview
                ? <img src={preview} className="file-preview" alt="Selected photo" />
                : <span className="file-placeholder">Tap to select image</span>
              }
              <input
                ref={fileInputRef}
                id="photo"
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleFileChange}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="submit-btn"
            disabled={status === 'loading' || !file}
          >
            {status === 'loading' ? 'Checking…' : 'Check Take'}
          </button>
        </form>

        {status === 'success' && result && (
          <div className="result-box result-box--ok">
            <p className="result-label">
              Continuity report — {result.character} · Scene {result.scene} · Take {result.take}
              {result.script_grounded && <span className="grounded-badge"> · script grounded</span>}
            </p>
            <Markdown text={result.result} />
            <p className="result-meta-line">
              {result.filename} · {(result.size_bytes / 1024).toFixed(1)} KB
            </p>
          </div>
        )}

        {status === 'error' && errorMsg && (
          <div className="result-box result-box--err">
            <p className="result-label">Error</p>
            <p className="result-value">{errorMsg}</p>
          </div>
        )}
      </section>

      <div className="ticks"></div>
      <section id="spacer"></section>
    </>
  )
}

export default App
