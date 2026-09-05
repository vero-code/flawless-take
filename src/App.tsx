import { useRef, useState } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000/api/check-take'

type CheckResult = {
  scene: string
  take: string
  character: string
  filename: string
  size_bytes: number
  result: string
}

type Status = 'idle' | 'loading' | 'success' | 'error'

function App() {
  const [scene, setScene] = useState('')
  const [take, setTake] = useState('')
  const [character, setCharacter] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [result, setResult] = useState<CheckResult | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const chosen = e.target.files?.[0] ?? null
    setFile(chosen)
    if (chosen) {
      setPreview(URL.createObjectURL(chosen))
    } else {
      setPreview(null)
    }
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
            <label htmlFor="file">Photo</label>
            <div
              className="file-drop"
              onClick={() => fileInputRef.current?.click()}
            >
              {preview ? (
                <img src={preview} className="file-preview" alt="Selected photo" />
              ) : (
                <span className="file-placeholder">Tap to select image</span>
              )}
              <input
                ref={fileInputRef}
                id="file"
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
            <p className="result-label">Result</p>
            <p className="result-value">{result.result}</p>
            <ul className="result-meta">
              <li><span>Scene</span> {result.scene}</li>
              <li><span>Take</span> {result.take}</li>
              <li><span>Character</span> {result.character}</li>
              <li><span>File</span> {result.filename} ({(result.size_bytes / 1024).toFixed(1)} KB)</li>
            </ul>
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
