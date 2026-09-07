import { useRef, useState } from 'react'
import './App.css'

import { API_URL, COMPARE_URL } from './config'
import type { CheckResult, CompareResult, Mode, Status, Page } from './types'
import {
  AlertFeed,
  ImageDrop,
  McpStatusBadge,
  ScriptPanel,
  HistoryTab,
  SceneMemoryTimeline,
  AgentCopilotView,
  VoiceModeView,
  TakeResultBox,
} from './components'

function App() {
  const [page, setPage] = useState<Page>('check')
  const [mode, setMode] = useState<Mode>('single')
  const [scene, setScene] = useState('')
  const [take, setTake] = useState('')
  const [takeRef, setTakeRef] = useState('')
  const [takeCurrent, setTakeCurrent] = useState('')
  const [character, setCharacter] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [refFile, setRefFile] = useState<File | null>(null)
  const [refPreview, setRefPreview] = useState<string | null>(null)
  const [curFile, setCurFile] = useState<File | null>(null)
  const [curPreview, setCurPreview] = useState<string | null>(null)
  const [scriptContext, setScriptContext] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [result, setResult] = useState<CheckResult | null>(null)
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [refreshCounter, setRefreshCounter] = useState(0)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const refInputRef = useRef<HTMLInputElement>(null)
  const curInputRef = useRef<HTMLInputElement>(null)

  function switchMode(m: Mode) {
    setMode(m)
    setStatus('idle')
    setResult(null)
    setCompareResult(null)
    setErrorMsg(null)
  }

  function makeFileHandler(
    setter: (f: File | null) => void,
    previewSetter: (u: string | null) => void,
  ) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0] ?? null
      setter(f)
      previewSetter(f ? URL.createObjectURL(f) : null)
    }
  }

  async function handleSingleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return
    setStatus('loading'); setResult(null); setErrorMsg(null)

    const body = new FormData()
    body.append('scene', scene)
    body.append('take', take)
    body.append('character', character)
    body.append('file', file)
    body.append('script_context', scriptContext)

    try {
      const res = await fetch(API_URL, { method: 'POST', body })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`)
      setResult(await res.json())
      setStatus('success')
      setRefreshCounter(c => c + 1)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }

  async function handleCompareSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!refFile || !curFile) return
    setStatus('loading'); setCompareResult(null); setErrorMsg(null)

    const body = new FormData()
    body.append('scene', scene)
    body.append('take_ref', takeRef)
    body.append('take_current', takeCurrent)
    body.append('character', character)
    body.append('reference', refFile)
    body.append('current', curFile)
    body.append('script_context', scriptContext)

    try {
      const res = await fetch(COMPARE_URL, { method: 'POST', body })
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`)
      setCompareResult(await res.json())
      setStatus('success')
      setRefreshCounter(c => c + 1)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }

  const isSingle = mode === 'single'
  const submitDisabled = status === 'loading' || (isSingle ? !file : !refFile || !curFile)

  return (
    <>
      <AlertFeed />
      <section id="center">
        <div>
          <h1>Flawless Take</h1>
          <p className="subtitle">Makeup continuity check — tablet view</p>
          <McpStatusBadge />
        </div>

        {/* Page navigation */}
        <div className="mode-toggle">
          <button type="button" className={`mode-btn ${page === 'check' ? 'mode-btn--active' : ''}`} onClick={() => setPage('check')}>
            Check
          </button>
          <button type="button" className={`mode-btn ${page === 'agent' ? 'mode-btn--active' : ''}`} onClick={() => setPage('agent')}>
            🤖 Agent Copilot
          </button>
          <button type="button" id="voice-mode-tab" className={`mode-btn ${page === 'voice' ? 'mode-btn--active' : ''}`} onClick={() => setPage('voice')}>
            🎤 Voice Mode
          </button>
          <button type="button" className={`mode-btn ${page === 'history' ? 'mode-btn--active' : ''}`} onClick={() => setPage('history')}>
            History
          </button>
        </div>

        {page === 'history' && <HistoryTab />}

        {page === 'agent' && (
          <AgentCopilotView
            scene={scene} character={character} scriptContext={scriptContext}
            onSceneChange={setScene} onCharacterChange={setCharacter}
          />
        )}

        {page === 'voice' && (
          <VoiceModeView
            scene={scene} character={character}
            onSceneChange={setScene} onCharacterChange={setCharacter}
          />
        )}

        {page === 'check' && (
          <>
            <div className="mode-toggle">
              <button type="button" className={`mode-btn ${isSingle ? 'mode-btn--active' : ''}`} onClick={() => switchMode('single')}>
                Single check
              </button>
              <button type="button" className={`mode-btn ${!isSingle ? 'mode-btn--active' : ''}`} onClick={() => switchMode('compare')}>
                Compare takes
              </button>
            </div>

            <form className="check-form" onSubmit={isSingle ? handleSingleSubmit : handleCompareSubmit}>
              <ScriptPanel onContext={setScriptContext} />

              <div className="form-row">
                <label htmlFor="scene">Scene</label>
                <input id="scene" type="text" placeholder="e.g. INT. BEDROOM – DAY" value={scene} onChange={e => setScene(e.target.value)} required />
              </div>

              <div className="form-row">
                <label htmlFor="character">Character</label>
                <input id="character" type="text" placeholder="e.g. Elena" value={character} onChange={e => setCharacter(e.target.value)} required />
              </div>

              <SceneMemoryTimeline
                scene={scene} character={character} refreshTrigger={refreshCounter}
                onSelectReferenceTake={(t) => { setMode('compare'); setTakeRef(t) }}
              />

              {isSingle ? (
                <>
                  <div className="form-row">
                    <label htmlFor="take">Take #</label>
                    <input id="take" type="text" placeholder="e.g. 3" value={take} onChange={e => setTake(e.target.value)} required />
                  </div>
                  <ImageDrop id="photo" label="Photo" preview={preview} inputRef={fileInputRef} onChange={makeFileHandler(setFile, setPreview)} />
                </>
              ) : (
                <>
                  <div className="form-row-pair">
                    <div className="form-row">
                      <label htmlFor="take-ref">Reference take #</label>
                      <input id="take-ref" type="text" placeholder="e.g. 2" value={takeRef} onChange={e => setTakeRef(e.target.value)} required />
                    </div>
                    <div className="form-row">
                      <label htmlFor="take-cur">Current take #</label>
                      <input id="take-cur" type="text" placeholder="e.g. 3" value={takeCurrent} onChange={e => setTakeCurrent(e.target.value)} required />
                    </div>
                  </div>
                  <div className="form-row-pair">
                    <ImageDrop id="ref-photo" label="Reference photo" preview={refPreview} inputRef={refInputRef} onChange={makeFileHandler(setRefFile, setRefPreview)} />
                    <ImageDrop id="cur-photo" label="Current photo" preview={curPreview} inputRef={curInputRef} onChange={makeFileHandler(setCurFile, setCurPreview)} />
                  </div>
                </>
              )}

              <button type="submit" className="submit-btn" disabled={submitDisabled}>
                {status === 'loading' ? 'Analysing…' : isSingle ? 'Check Take' : 'Compare Takes'}
              </button>
            </form>

            <TakeResultBox status={status} result={result} compareResult={compareResult} errorMsg={errorMsg} />
          </>
        )}
      </section>

      <div className="ticks"></div>
      <section id="spacer"></section>
    </>
  )
}

export default App
