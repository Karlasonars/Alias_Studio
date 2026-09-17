import { useEffect, useState } from 'react'
import { api } from '../api'
import type { DeleteJobInfo } from '../types'

/* T-30 (E2-F01): the confirmation that names the consequence in numbers
 * (§28: "Dzēsīs 12 klipus un 4.2 GB"). Every number is python's, measured
 * off disk when the dialog opens — never estimated, never remembered from
 * an earlier look. The dialog is where the action started, so it is where
 * a refusal or a failure shows (§28), and it stays open on one: the rail
 * behind it still lists whatever is still there. KEEP calls nothing. */

interface Props {
  jobId: string
  title: string
  onClose: () => void
  /** the job is gone: the app re-reads the rail and drops what it held of it */
  onDeleted: (jobId: string) => void
}

/** MB or GB by magnitude, decimal units: one decimal above a gigabyte and
 * below ten megabytes, whole megabytes between. */
export function formatBytes(bytes: number): string {
  const gb = bytes / 1e9
  if (gb >= 1) return `${gb.toFixed(1)} GB`
  const mb = bytes / 1e6
  return `${mb >= 10 ? Math.round(mb) : mb.toFixed(1)} MB`
}

function clipsPhrase(clips: number): string {
  if (clips === 0) return 'this job'
  return `${clips} clip${clips === 1 ? '' : 's'}`
}

export default function DeleteJobDialog({ jobId, title, onClose, onDeleted }: Props) {
  const [info, setInfo] = useState<DeleteJobInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let live = true
    api
      .deleteJobInfo(jobId)
      .then((answer) => {
        if (live) setInfo(answer)
      })
      .catch((err) => {
        if (live) setError(String(err))
      })
    return () => {
      live = false
    }
  }, [jobId])

  const confirm = async () => {
    setBusy(true)
    setError(null)
    try {
      const result = await api.deleteJob(jobId)
      if (result.ok) onDeleted(jobId)
      else setError(result.error ?? 'The job could not be deleted.')
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-scrim" onClick={onClose}>
      <div className="modal delete-dialog" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <p className="audit-kicker">DELETE · {title}</p>
          <button className="btn-ghost" onClick={onClose}>
            close ✕
          </button>
        </header>
        {info === null && error === null && (
          <p className="resume-loading mono">measuring this job…</p>
        )}
        {info && !info.deletable && (
          <p className="delete-reason">{info.reason ?? 'This job cannot be deleted right now.'}</p>
        )}
        {info && info.deletable && (
          <>
            <p className="delete-question">
              {info.exists
                ? `Delete ${clipsPhrase(info.clips)} and ${formatBytes(info.bytes)}? This cannot be undone.`
                : 'Its folder is already gone. Remove this job from the records? This cannot be undone.'}
            </p>
            {info.linked_reels > 0 && (
              <p className="delete-note">
                {info.linked_reels === 1 ? '1 clip is' : `${info.linked_reels} clips are`} linked to
                posted Reels — their results stay in the Instagram loop.
              </p>
            )}
          </>
        )}
        {error && (
          <p className="delete-error" role="alert">
            {error}
          </p>
        )}
        <footer className="delete-foot">
          <button className="btn-secondary" onClick={onClose} disabled={busy}>
            KEEP
          </button>
          {info?.deletable && (
            <button className="btn-danger" onClick={confirm} disabled={busy}>
              {busy ? 'DELETING…' : 'DELETE'}
            </button>
          )}
        </footer>
      </div>
    </div>
  )
}
