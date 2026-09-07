import React from 'react'

/**
 * Cinema Viewfinder Image Drop Zone with crosshair reticles and ARRI metadata overlay
 */
export function ImageDrop({
  id,
  label,
  preview,
  inputRef,
  onChange,
  onClear,
}: {
  id: string
  label: string
  preview: string | null
  inputRef: React.RefObject<HTMLInputElement | null>
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  onClear?: () => void
}) {
  return (
    <div className="viewfinder-wrapper">
      <div className="viewfinder-header">
        <span className="viewfinder-label">{label}</span>
        <span className="viewfinder-meta">ARRI RAW · 35mm T1.8 · ISO 800</span>
      </div>

      <div
        className={`viewfinder-drop ${preview ? 'viewfinder-drop--has-preview' : ''}`}
        onClick={() => inputRef.current?.click()}
      >
        {/* Cinema Reticle Frame Marks */}
        <div className="reticle-corner reticle-corner--tl"></div>
        <div className="reticle-corner reticle-corner--tr"></div>
        <div className="reticle-corner reticle-corner--bl"></div>
        <div className="reticle-corner reticle-corner--br"></div>
        <div className="reticle-crosshair"></div>

        {preview ? (
          <>
            <img src={preview} className="viewfinder-preview-img" alt={label} />
            <div className="viewfinder-hud">
              <span className="hud-badge hud-badge--rec">● LIVE FEED</span>
              <span className="hud-badge hud-badge--ratio">2.39:1 SCOPE</span>
            </div>
            {onClear && (
              <button
                type="button"
                className="viewfinder-clear-btn"
                onClick={(e) => {
                  e.stopPropagation()
                  onClear()
                }}
                title="Remove frame"
              >
                ✕
              </button>
            )}
          </>
        ) : (
          <div className="viewfinder-empty">
            <div className="viewfinder-cam-icon">📹</div>
            <span className="viewfinder-empty-title">TAP TO SELECT FRAME</span>
            <span className="viewfinder-empty-sub">or drop camera capture file</span>
          </div>
        )}

        <input
          ref={inputRef}
          id={id}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={onChange}
        />
      </div>
    </div>
  )
}
