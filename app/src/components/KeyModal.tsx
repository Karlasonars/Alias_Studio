import { useEffect, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'

/** Post-onboarding key management — the onboarding-only input was a gap. */

interface Props {
  onClose: () => void
}

function PexelsField() {
  const [key, setKey] = useState('')
  const [saved, setSaved] = useState(false)
  return (
    <div className="ig-form">
      <input
        placeholder="Pexels API key (free — pexels.com/api)"
        type="password"
        value={key}
        onChange={(e) => setKey(e.target.value)}
        className="mono"
      />
      <button
        className="btn-secondary"
        disabled={!key.trim()}
        onClick={async () => {
          await invoke('save_pexels_key', { key })
          setSaved(true)
        }}
      >
        {saved ? 'saved ✓' : 'save'}
      </button>
    </div>
  )
}

export default function KeyModal({ onClose }: Props) {
  const [key, setKey] = useState('')
  const [hasKey, setHasKey] = useState<boolean | null>(null)
  const [saved, setSaved] = useState(false)
  const [rejected, setRejected] = useState(false)
  const [unverified, setUnverified] = useState(false)

  useEffect(() => {
    invoke<{ has_gemini_key: boolean }>('get_setup_state').then((s) =>
      setHasKey(s.has_gemini_key)
    )
  }, [])

  async function save() {
    if (!key.trim()) return
    // save_gemini_key verifies first and refuses a rejected key (E1-F02) -
    // claiming SAVED for a key Rust never wrote would be the old lie back.
    const res = await invoke<{ status: string }>('save_gemini_key', { key })
    if (res.status === 'rejected') {
      setRejected(true)
      setSaved(false)
      setUnverified(false)
      return
    }
    setRejected(false)
    // "unverified" means saved WITHOUT the check (offline) — collapsing it
    // into a bare SAVED ✓ made the copy lie during the offline hand test:
    // onboarding said so, this modal did not (test-day F6). Same wording as
    // onboarding, so the two surfaces cannot tell different stories.
    setUnverified(res.status === 'unverified')
    setSaved(true)
    setHasKey(true)
  }

  return (
    <div className="modal-scrim" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <p className="audit-kicker">THE BRAIN</p>
          <button className="btn-ghost" onClick={onClose}>close ✕</button>
        </header>
        <p className="ig-intro">
          Gemini scores your moments at full quality. A free-tier key works —
          rate-limited, and Google may train on free-tier prompts; the paid tier
          runs ~<span className="mono">$1.20</span>/hr of source. The key lives in <span className="mono">~/.publikclip/secrets.json</span>,
          chmod 600, and never goes anywhere but Google.{' '}
          {hasKey && <strong>A key is currently saved{saved ? ' — updated ✓' : ''}.</strong>}
        </p>
        <div className="ig-form">
          <input
            placeholder="AIza… (aistudio.google.com → Get API key)"
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && save()}
            className="mono"
          />
          <button className="btn-primary" onClick={save} disabled={!key.trim()}>
            {rejected ? 'REJECTED ✗ — RETRY' : saved ? 'SAVED ✓' : 'SAVE KEY'}
          </button>
        </div>
        {unverified && (
          <p className="ig-message mono">
            Saved — but Google could not be reached to verify it (offline?). It
            will be checked on first use.
          </p>
        )}
        <p className="audit-label" style={{ marginTop: 22 }}>PEXELS (STOCK VISUALS)</p>
        <PexelsField />
        <p className="ig-message mono">
          Applies to new runs; a job mid-flight keeps the brain it started with.
        </p>
      </div>
    </div>
  )
}
