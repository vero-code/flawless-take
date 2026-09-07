import { useRef, useState } from 'react'
import './App.css'

import { API_URL, COMPARE_URL } from './config'
import type { CheckResult, CompareResult, Mode, Status, Page } from './types'
import {
  AlertFeed,
  ImageDrop,
  StudioHeader,
  ScriptPanel,
  HistoryTab,
  SceneMemoryTimeline,
  AgentCopilotView,
  VoiceModeView,
  TakeResultBox,
} from './components'

function App() {
  const [page, setPage] = useState<Page>('check')
  const [mode, setMode] = useState<Mode>('compare')
  const [scene, setScene] = useState('Scene 14A')
  const [take, setTake] = useState('2')
  const [takeRef, setTakeRef] = useState('1')
  const [takeCurrent, setTakeCurrent] = useState('2')
  const [character, setCharacter] = useState('Detective Miller')
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
    <div className="studio-app">
      <AlertFeed />
      <StudioHeader />

      {/* Main Studio Navigation Switcher */}
      <nav className="studio-nav">
        <button
          type="button"
          className={`studio-nav-btn ${page === 'check' ? 'studio-nav-btn--active' : ''}`}
          onClick={() => setPage('check')}
        >
          <span className="studio-nav-icon">🎬</span>
          <span>Take Inspector</span>
        </button>

        <button
          type="button"
          className={`studio-nav-btn ${page === 'agent' ? 'studio-nav-btn--active' : ''}`}
          onClick={() => setPage('agent')}
        >
          <span className="studio-nav-icon">🤖</span>
          <span>Agent Copilot</span>
        </button>

        <button
          type="button"
          id="voice-mode-tab"
          className={`studio-nav-btn ${page === 'voice' ? 'studio-nav-btn--active' : ''}`}
          onClick={() => setPage('voice')}
        >
          <span className="studio-nav-icon">🎙️</span>
          <span>Voice Assistant</span>
        </button>

        <button
          type="button"
          className={`studio-nav-btn ${page === 'history' ? 'studio-nav-btn--active' : ''}`}
          onClick={() => setPage('history')}
        >
          <span className="studio-nav-icon">📋</span>
          <span>Continuity Logs</span>
        </button>
      </nav>

      {/* Page Content */}
      <main className="studio-main">
        {page === 'history' && <HistoryTab />}

        {page === 'agent' && (
          <AgentCopilotView
            scene={scene}
            character={character}
            scriptContext={scriptContext}
            onSceneChange={setScene}
            onCharacterChange={setCharacter}
          />
        )}

        {page === 'voice' && (
          <VoiceModeView
            scene={scene}
            character={character}
            onSceneChange={setScene}
            onCharacterChange={setCharacter}
          />
        )}

        {page === 'check' && (
          <div className="studio-cockpit">
            {/* Left Column: Slate & Parameter Controls */}
            <aside className="cockpit-sidebar">
              <div className="slate-card">
                <div className="slate-header">
                  <div className="slate-title-box">
                    <span className="slate-clapper">🎬</span>
                    <span className="slate-title">PRODUCTION SLATE</span>
                  </div>
                </div>

                <div className="slate-fields">
                  <div className="slate-field">
                    <label htmlFor="scene">SCENE</label>
                    <input
                      id="scene"
                      type="text"
                      placeholder="e.g. INT. BEDROOM – DAY"
                      value={scene}
                      onChange={e => setScene(e.target.value)}
                      required
                    />
                  </div>

                  <div className="slate-field">
                    <label htmlFor="character">CHARACTER</label>
                    <input
                      id="character"
                      type="text"
                      placeholder="e.g. Elena"
                      value={character}
                      onChange={e => setCharacter(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </div>

              <ScriptPanel onContext={setScriptContext} />

              <SceneMemoryTimeline
                scene={scene}
                character={character}
                refreshTrigger={refreshCounter}
                onSelectReferenceTake={(t) => { setMode('compare'); setTakeRef(t) }}
              />
            </aside>

            {/* Right Column: Viewfinder Deck & Inspection */}
            <section className="cockpit-deck">
              {/* Inspection Mode Switcher */}
              <div className="deck-mode-bar">
                <div className="deck-mode-group">
                  <button
                    type="button"
                    className={`deck-mode-btn ${!isSingle ? 'deck-mode-btn--active' : ''}`}
                    onClick={() => switchMode('compare')}
                  >
                    Dual-Take Differential Compare
                  </button>
                  <button
                    type="button"
                    className={`deck-mode-btn ${isSingle ? 'deck-mode-btn--active' : ''}`}
                    onClick={() => switchMode('single')}
                  >
                    Single Take Verification
                  </button>
                </div>
              </div>

              <form
                className="deck-form"
                onSubmit={isSingle ? handleSingleSubmit : handleCompareSubmit}
              >
                {isSingle ? (
                  <div className="deck-viewfinder-grid deck-viewfinder-grid--single">
                    <div className="deck-take-badge-row">
                      <div className="slate-take-input">
                        <label htmlFor="take">TAKE #</label>
                        <input
                          id="take"
                          type="text"
                          placeholder="e.g. 3"
                          value={take}
                          onChange={e => setTake(e.target.value)}
                          required
                        />
                      </div>
                    </div>
                    <ImageDrop
                      id="photo"
                      label="CAMERA A · LIVE TAKE"
                      preview={preview}
                      inputRef={fileInputRef}
                      onChange={makeFileHandler(setFile, setPreview)}
                      onClear={() => { setFile(null); setPreview(null) }}
                    />
                  </div>
                ) : (
                  <div className="deck-viewfinder-grid deck-viewfinder-grid--compare">
                    <div className="viewfinder-col">
                      <div className="deck-take-badge-row">
                        <div className="slate-take-input">
                          <label htmlFor="take-ref">REFERENCE TAKE #</label>
                          <input
                            id="take-ref"
                            type="text"
                            placeholder="e.g. 1"
                            value={takeRef}
                            onChange={e => setTakeRef(e.target.value)}
                            required
                          />
                        </div>
                      </div>
                      <ImageDrop
                        id="ref-photo"
                        label="APPROVED BASELINE"
                        preview={refPreview}
                        inputRef={refInputRef}
                        onChange={makeFileHandler(setRefFile, setRefPreview)}
                        onClear={() => { setRefFile(null); setRefPreview(null) }}
                      />
                    </div>

                    <div className="viewfinder-col">
                      <div className="deck-take-badge-row">
                        <div className="slate-take-input">
                          <label htmlFor="take-cur">CURRENT TAKE #</label>
                          <input
                            id="take-cur"
                            type="text"
                            placeholder="e.g. 2"
                            value={takeCurrent}
                            onChange={e => setTakeCurrent(e.target.value)}
                            required
                          />
                        </div>
                      </div>
                      <ImageDrop
                        id="cur-photo"
                        label="CURRENT TAKE"
                        preview={curPreview}
                        inputRef={curInputRef}
                        onChange={makeFileHandler(setCurFile, setCurPreview)}
                        onClear={() => { setCurFile(null); setCurPreview(null) }}
                      />
                    </div>
                  </div>
                )}

                <button
                  type="submit"
                  className="studio-run-btn"
                  disabled={submitDisabled}
                >
                  {status === 'loading' ? (
                    <span className="studio-run-loading">
                      <span className="studio-spinner"></span>
                      GEMINI 3.8 FLASH ANALYSING MULTIMODAL FRAMES...
                    </span>
                  ) : (
                    <span>
                      {isSingle
                        ? '⚡ RUN SINGLE-TAKE CONTINUITY INSPECTION'
                        : '⚡ RUN DUAL-TAKE DIFFERENTIAL ANALYSIS'}
                    </span>
                  )}
                </button>
              </form>

              <TakeResultBox
                status={status}
                result={result}
                compareResult={compareResult}
                errorMsg={errorMsg}
              />
            </section>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
