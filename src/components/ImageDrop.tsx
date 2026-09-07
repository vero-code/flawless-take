import React from 'react'

/**
 * Reusable image drop zone with camera capture support
 */
export function ImageDrop({
  id,
  label,
  preview,
  inputRef,
  onChange,
}: {
  id: string
  label: string
  preview: string | null
  inputRef: React.RefObject<HTMLInputElement | null>
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
}) {
  return (
    <div className="form-row">
      <label htmlFor={id}>{label}</label>
      <div className="file-drop" onClick={() => inputRef.current?.click()}>
        {preview ? (
          <img src={preview} className="file-preview" alt={label} />
        ) : (
          <span className="file-placeholder">Tap to select image</span>
        )}
        <input
          ref={inputRef}
          id={id}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={onChange}
          required
        />
      </div>
    </div>
  )
}
