import { useEffect, useState } from 'react'
import { api } from '../api'
import Markdown from './Markdown'

/**
 * Settings → About → updates (E15-F01 / T-16). The whole update flow in
 * one place: check, changelog BEFORE install (the release notes ride in
 * latest.json's body), install-and-restart, and the launch-check toggle.
 *
 * Two guards shape it:
 *  - install refuses while a job is running — the installer replaces
 *    resources/pipeline while the sidecar is executing from it, and a
 *    half-swapped pipeline mid-job is a mixed-version crash nobody can
 *    diagnose. Finish or cancel first; the running check is asked at
 *    click time, not cached.
 *  - every check failure is quiet where it should be (a dev build or an
 *    offline machine is not an error state) and named where the user
 *    explicitly asked (the manual check shows what went wrong).
 *
 * The updater plugin verifies the payload's minisign signature against
 * the pubkey baked into tauri.conf.json and refuses anything unsigned —
 * that is a separate mechanism from Windows code-signing, which this
 * app deliberately does not have (SmartScreen will warn on first
 * install; README says so up front).
 */

type Avail = {
  version: string
  notes: string
  install: () => Promise<void>
}

type Phase = 'idle' | 'checking' | 'none' | 'available' | 'installing' | 'error'

export default function UpdatePanel() {
  const [enabled, setEnabled] = useState<boolean | null>(null)
  const [phase, setPhase] = useState<Phase>('idle')
  const [avail, setAvail] = useState<Avail | null>(null)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    api
      .updateChecksEnabled()
      .then(setEnabled)
      .catch(() => setEnabled(null))
  }, [])

  async function doCheck() {
    setPhase('checking')
    setNote(null)
    try {
      const { check } = await import('@tauri-apps/plugin-updater')
      const update = await check()
      if (!update) {
        setPhase('none')
        return
      }
      setAvail({
        version: update.version,
        notes: update.body ?? '',
        install: async () => {
          await update.downloadAndInstall()
          // Windows never reaches this line (the installer takes over and
          // restarts the app); macOS needs the explicit relaunch.
          const { relaunch } = await import('@tauri-apps/plugin-process')
          await relaunch()
        }
      })
      setPhase('available')
    } catch (err) {
      setPhase('error')
      setNote(String(err))
    }
  }

  async function doInstall() {
    if (!avail) return
    try {
      const qs = await api.queueState()
      if (qs.active_job_id) {
        setNote('A job is running — let it finish or cancel it, then install.')
        return
      }
    } catch {
      // if the shell cannot answer, do not wall the user off
    }
    setNote(null)
    setPhase('installing')
    try {
      await avail.install()
    } catch (err) {
      setPhase('available')
      setNote(String(err))
    }
  }

  return (
    <div className="update-panel">
      <h2>Updates</h2>
      <p>
        Updates are signed: the app verifies each one against its own public key
        and refuses anything else. Checking asks github.com for the latest
        release — nothing about you or your work is sent.
      </p>

      <div className="update-actions">
        <button
          className="btn-secondary"
          onClick={doCheck}
          disabled={phase === 'checking' || phase === 'installing'}
        >
          {phase === 'checking' ? 'CHECKING…' : 'CHECK FOR UPDATES'}
        </button>
        {enabled !== null && (
          <button
            className="opt"
            onClick={() => {
              const next = !enabled
              setEnabled(next)
              api.setUpdateChecks(next).catch(() => setEnabled(!next))
            }}
          >
            check at launch: {enabled ? 'on' : 'off'}
          </button>
        )}
      </div>

      {phase === 'none' && <p className="update-note mono">up to date</p>}
      {phase === 'error' && (
        <p className="update-note mono">could not check: {note}</p>
      )}
      {(phase === 'available' || phase === 'installing') && avail && (
        <div className="update-avail">
          <p className="update-note">
            <strong>Version {avail.version} is available.</strong> What changed:
          </p>
          <div className="update-changelog">
            <Markdown text={avail.notes || '(no release notes)'} />
          </div>
          <button
            className="btn-primary"
            onClick={doInstall}
            disabled={phase === 'installing'}
          >
            {phase === 'installing' ? 'INSTALLING…' : 'INSTALL & RESTART'}
          </button>
          {note && <p className="update-note update-blocked">{note}</p>}
        </div>
      )}
    </div>
  )
}
