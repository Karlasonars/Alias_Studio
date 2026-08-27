import { useEffect, useState } from 'react'
import { listen } from '@tauri-apps/api/event'
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
//
// Push, not poll: Rust emits `queue-state` whenever the queue changes
// (enqueue, advance, exit, cancel-pending, pause). This view never asks on
// a timer — a 2s poll here once stacked up `uv run` subprocesses faster
// than they could answer. The one queueState() call below is the instant
// cached snapshot at mount.

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

  useEffect(() => {
    api.queueState().then(setState).catch(() => {})
    let disposed = false
    let un: (() => void) | null = null
    listen<QueueStateResult>('queue-state', ({ payload }) => setState(payload)).then((u) => {
      if (disposed) u()
      else un = u
    })
    return () => {
      disposed = true
      un?.()
    }
  }, [])

  const jobs = state?.jobs ?? []
  const pending = jobs.filter((j) => j.status === 'pending')
  const activeId = state?.active_job_id ?? null
  const idle = !activeId
  const loading = !state || !state.ready

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
            <button className="btn-primary" onClick={() => api.startQueue().catch(() => {})}>
              START QUEUE ({pending.length} waiting)
            </button>
          )}
          {!idle && (
            <button
              className={`opt ${state?.paused ? 'opt-on' : ''}`}
              onClick={() => api.setQueuePaused(!state?.paused).catch(() => {})}
            >
              {state?.paused ? 'paused after current job' : 'pause after current job'}
            </button>
          )}
        </div>
      </header>

      {jobs.length === 0 ? (
        <p className="queue-empty">{loading ? 'loading…' : 'nothing queued yet'}</p>
      ) : (
        <section className="queue-table">
          {jobs.map((job) => {
            // The listing can lag a spawn by a moment; the shell's
            // active_job_id is the fresher running signal.
            const runs = job.status === 'running' || job.id === activeId
            return (
              <div className="queue-row" key={job.id}>
                <span
                  className={`led ${runs ? 'led-on' : job.status === 'failed' ? 'led-err' : 'led-half'}`}
                />
                <span className="queue-row-name mono">{job.title ?? job.source}</span>
                <span className="queue-row-msg">
                  {runs ? 'running' : (STATUS_HINTS[job.status] ?? job.status)}
                  {job.status === 'failed' && job.error ? ` — ${job.error}` : ''}
                </span>
                {job.status === 'pending' && !runs && (
                  <button
                    className="btn-ghost"
                    title="cancel this queued job"
                    onClick={() => api.cancelPendingJob(job.id).catch(() => {})}
                  >
                    ✕
                  </button>
                )}
              </div>
            )
          })}
        </section>
      )}
    </div>
  )
}
