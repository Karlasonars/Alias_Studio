import { useEffect, useState } from 'react'
import { listen } from '@tauri-apps/api/event'
import { api } from '../api'
import type { QueueJob, QueueStateResult } from '../types'

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
//
// A queue view answers three questions without reading: what is running,
// what is next, how many are waiting. The first cut of this view was a
// flat history list — 17 interleaved rows, pending/done/cancelled all on
// the same LED — and the owner could not find the queue in it. Hence the
// three sections: NOW, UP NEXT (the point of the view — position order,
// oldest first, matching next_pending's FIFO), then history below where it
// can never push the queue off screen.

interface Props {
  onBack: () => void
}

// A row must be tellable apart from its siblings. Before ingest there is
// no title, and six YouTube enqueues all truncate to the same URL prefix —
// which is exactly how six duplicate jobs went unnoticed. Distill the part
// that differs: video id for YouTube, basename for files, host+tail else.
function jobLabel(job: QueueJob): string {
  if (job.title) return job.title
  const src = job.source
  if (!/^https?:\/\//i.test(src)) {
    const base = src.split(/[\\/]/).filter(Boolean).pop()
    return base ?? src
  }
  try {
    const u = new URL(src)
    const v = u.searchParams.get('v')
    if (v) return `youtube · ${v}`
    const tail = u.pathname.split('/').filter(Boolean).pop()
    const host = u.hostname.replace(/^www\./, '')
    return tail ? `${host} · ${tail}` : host
  } catch {
    return src
  }
}

function addedAt(job: QueueJob): string {
  const d = new Date(job.created_at * 1000)
  const today = new Date().toDateString() === d.toDateString()
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
  return today ? time : `${d.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${time}`
}

const HIST_LED: Record<string, string> = {
  done: 'led-on',
  failed: 'led-err',
  cancelled: 'led-off'
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
  const activeId = state?.active_job_id ?? null
  // The listing can lag a spawn by a moment; the shell's active_job_id is
  // the fresher running signal.
  const running = jobs.find((j) => j.id === activeId || j.status === 'running')
  // The listing arrives newest-first; queue position is oldest-first
  // (next_pending orders created_at ASC), so re-order for display.
  const pending = jobs
    .filter((j) => j.status === 'pending' && j !== running)
    .sort((a, b) => a.created_at - b.created_at)
  const history = jobs
    .filter((j) => j !== running && j.status !== 'pending' && j.status !== 'running')
  const idle = !running
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

      {running && (
        <section>
          <p className="queue-label mono">NOW</p>
          <div className="queue-now">
            <span className="led led-run" />
            <span className="queue-row-name mono">{jobLabel(running)}</span>
            <span className="queue-row-msg">running — watch it in the studio</span>
          </div>
        </section>
      )}

      <section>
        <p className="queue-label mono">UP NEXT ({pending.length})</p>
        {pending.length === 0 ? (
          <p className="queue-empty">{loading ? 'loading…' : 'nothing waiting'}</p>
        ) : (
          <div className="queue-table">
            {pending.map((job, i) => (
              <div className="queue-row queue-row-next" key={job.id}>
                <span className="queue-pos mono">#{i + 1}</span>
                <span className="led led-half" />
                <span className="queue-row-name mono">{jobLabel(job)}</span>
                <span className="queue-time mono">added {addedAt(job)}</span>
                <button
                  className="btn-ghost"
                  title="cancel this queued job"
                  onClick={() => api.cancelPendingJob(job.id).catch(() => {})}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {history.length > 0 && (
        <section>
          <p className="queue-label mono">HISTORY ({history.length})</p>
          {/* Bounded on purpose: 30 finished jobs must never push the
              queue off screen. History scrolls inside its own box. */}
          <div className="queue-table queue-history">
            {history.map((job) => (
              <div className="queue-row queue-row-hist" key={job.id}>
                <span className={`led ${HIST_LED[job.status] ?? 'led-off'}`} />
                <span className="queue-row-name mono">{jobLabel(job)}</span>
                <span className="queue-row-msg">
                  {job.status}
                  {job.status === 'failed' && job.error ? ` — ${job.error}` : ''}
                </span>
                <span className="queue-time mono">{addedAt(job)}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
