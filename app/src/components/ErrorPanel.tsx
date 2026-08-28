import { useState } from 'react'
import { openUrl } from '@tauri-apps/plugin-opener'
import type { ErrorInfo } from '../types'

/* T-13 (E14-F01): the one place a job failure is rendered. Cause as the
 * headline, actions as the way forward, the technical text behind a
 * disclosure with a copy button — never a traceback first. Legacy bare
 * strings (old DB rows, producers that predate error_info) arrive as
 * { cause } with no actions and render exactly as the old error block. */

const DOCS_BASE = 'https://github.com/Karlasonars/Alias_Studio/blob/main/'

interface Props {
  error: ErrorInfo
}

export default function ErrorPanel({ error }: Props) {
  const [copied, setCopied] = useState(false)

  const copyDetails = () => {
    const text = [
      error.stage ? `stage: ${error.stage}` : null,
      error.signature ? `signature: ${error.signature}` : null,
      error.cause,
      error.detail
    ]
      .filter(Boolean)
      .join('\n\n')
    navigator.clipboard
      ?.writeText(text)
      .then(() => setCopied(true))
      .catch(() => {})
  }

  return (
    <section className="error-block error-panel">
      <p className="error-cause">
        <span className="led led-err" />
        {error.cause}
      </p>
      {error.actions.length > 0 && (
        <ul className="error-actions">
          {error.actions.map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ul>
      )}
      {error.docs && (
        <button className="btn-ghost" onClick={() => openUrl(DOCS_BASE + error.docs).catch(() => {})}>
          ↗ more in the docs
        </button>
      )}
      {error.detail && (
        <details className="error-detail">
          <summary>technical details{error.signature ? ` (${error.signature})` : ''}</summary>
          <pre className="mono">{error.detail}</pre>
          {/* no ⧉ here: U+29C9 sits in a block the Windows font fallback
              never routes anywhere and draws a box (see the rail's note) */}
          <button className="btn-ghost" onClick={copyDetails}>
            {copied ? 'copied ✓' : 'copy details'}
          </button>
        </details>
      )}
    </section>
  )
}
