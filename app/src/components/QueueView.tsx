import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { QueueStateResult } from '../types'

// The queue's data source is SQLite (via `--jsonl jobs`), not the job dirs:
// this is the one view that shows bookkeeping. The library rail stays
// filesystem-truth (list_job_dirs) — two views, two truths, deliberately.
//
// Shell: .queue follows the Loop/Settings pattern (a full-page flex column
// that owns its background), NOT Studio's .studio — that class is a
// two-track grid whose 264px first track belongs to a .rail this view does
// not have, and borrowing it crushed the whole view into that track.

const STATUS_HINTS: Record<string, string> = {
  pending: 'queued',
  running: 'running',
  done: 'done',
  failed: 'failed',
  cancelled: 'cancelled'
}

interface Props {
  onBack: () => void
}

export default function QueueView({ onBack }: Props) {
  const [state, setState] = useState<QueueStateResult | null>(null)

  const refresh = useCallback(() => {
    api.queueState().then(setState).catch(() => {})
  }, [])

  // Poll while open: the runner advances in Rust on its own schedule, and
  // two seconds of staleness is fine for a bookkeeping view.
  useEffect(() => {
    refresh()
    const t = window.setInterval(refresh, 2000)
    return () => window.clearInterval(t)
  }, [refresh])

  const jobs = state?.jobs ?? []
  const pending = jobs.filter((j) => j.status === 'pending')
  const idle = !state?.active_job_id

  return (
    <div className="queue">
      <div className="grain" />
      <header className="queue-head">
        <div className="queue-head-title">
          <h1 className="input-heading">
            THE<span className="amber"> QUEUE.</span>
          </h1>
          <button className="btn-ghost" onClick={onBack}>
            ← studio
          </button>
        </div>
        <div className="queue-head-actions">
          {/* idle ∧ pending is the whole "held" concept: after a cancel
              or a fresh launch nothing auto-starts, and this button is
              how the user re-arms it — and how they see it held. */}
          {idle && pending.length > 0 && (
            <button
              className="btn-primary"
              onClick={() => api.startQueue().then(refresh).catch(() => {})}
            >
              START QUEUE ({pending.length} waiting)
            </button>
          )}
          {!idle && (
            <button
              className={`opt ${state?.paused ? 'opt-on' : ''}`}
              onClick={() => api.setQueuePaused(!state?.paused).then(refresh).catch(() => {})}
            >
              {state?.paused ? 'paused after current job' : 'pause after current job'}
            </button>
          )}
        </div>
      </header>

      {jobs.length === 0 ? (
        <p className="queue-empty">{state === null ? 'loading…' : 'nothing queued yet'}</p>
      ) : (
        <section className="queue-table">
          {jobs.map((job) => (
            <div className="queue-row" key={job.id}>
              <span
                className={`led ${
                  job.status === 'running' ? 'led-on' : job.status === 'failed' ? 'led-err' : 'led-half'
                }`}
              />
              <span className="queue-row-name mono">{job.title ?? job.source}</span>
              <span className="queue-row-msg">
                {STATUS_HINTS[job.status] ?? job.status}
                {job.status === 'failed' && job.error ? ` — ${job.error}` : ''}
              </span>
              {job.status === 'pending' && (
                <button
                  className="btn-ghost"
                  title="cancel this queued job"
                  onClick={() => api.cancelPendingJob(job.id).then(refresh).catch(() => {})}
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </section>
      )}
    </div>
  )
}
