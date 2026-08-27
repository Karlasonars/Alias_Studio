import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { QueueStateResult } from '../types'

// The queue's data source is SQLite (via `--jsonl jobs`), not the job dirs:
// this is the one view that shows bookkeeping. The library rail stays
// filesystem-truth (list_job_dirs) — two views, two truths, deliberately.

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
    <div className="studio">
      <div className="grain" />
      <main className="stage-area">
        <div className="stage-main">
          <section className="input-block">
            <h1 className="input-heading">
              THE<span className="amber"> QUEUE.</span>
            </h1>
            <div className="run-options">
              <button className="btn-ghost" onClick={onBack}>
                ← back
              </button>
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
          </section>

          <section className="deck">
            {jobs.length === 0 && <p className="rail-empty">nothing queued yet</p>}
            {jobs.map((job) => (
              <div className="deck-row" key={job.id}>
                <span
                  className={`led ${
                    job.status === 'running' ? 'led-on' : job.status === 'failed' ? 'led-err' : 'led-half'
                  }`}
                />
                <span className="deck-name mono">{job.title ?? job.source}</span>
                <span className="deck-msg">
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
        </div>
      </main>
    </div>
  )
}
