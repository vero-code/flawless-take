import React from 'react'

/**
 * Minimal markdown renderer — h3, bold, italic, bullets, hr
 */
export function Markdown({ text }: { text: string }) {
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
        <h3
          key={elements.length}
          className="md-h3"
          dangerouslySetInnerHTML={{ __html: inlineFormat(line.replace(/^#{1,3}\s/, '')) }}
        />
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
        <p
          key={elements.length}
          className="md-p"
          dangerouslySetInnerHTML={{ __html: inlineFormat(line) }}
        />
      )
    }
  }
  flushList()
  return <div className="md-body">{elements}</div>
}
