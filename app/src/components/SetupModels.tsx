import { useCallback, useEffect, useState } from 'react'
import { listen } from '@tauri-apps/api/event'
import { api } from '../api'
import type { SetupEvent, SetupStatusResult } from '../types'

/**
 * E1-F01: the downloads a first job would hide, made visible up front.
 *
 * Everything here is display over disk truth: `setup status` re-derives
 * what is present from the files themselves, so killing the app mid-setup
 * and relaunching shows completed items as done and resumable partials
 * carry their byte offset — no remembered counter, because the app is the
 * thing that died. The total is shown BEFORE anything starts, and setup
 * is a better default, never a gate: the studio stays reachable and a job
 * started mid-download takes over with its own (resuming) lazy fetches.
 */

interface ItemLive {
  state: 'downloading' | 'done' | 'failed'
  fraction: number
  message: string
  error?: string
}

function fmtBytes(n: number): string {
  return n >= 1e9 ? `${(n / 1e9).toFixed(1)} GB` : `${Math.max(1, Math.round(n / 1e6))} MB`
}

export default function SetupModels() {
  // undefined = still asking (the one-shot pays uv's re-sync, seconds);
  // null = the ask itself failed
  const [status, setStatus] = useState<SetupStatusResult | null | undefined>(undefined)
  const [live, setLive] = useState<Record<string, ItemLive>>({})
  // 'starting' spans pressing Download until the first event arrives — the
  // honest face of `uv sync` preparing the Python env (no invented %).
  const [phase, setPhase] = useState<'idle' | 'starting' | 'running'>('idle')
  const [note, setNote] = useState<string | null>(null)

  const refresh = useCallback(() => {
    api
      .setupStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    let disposed = false
    let un: (() => void) | null = null
    listen<SetupEvent>('setup-event', ({ payload }) => {
      if (payload.event === 'item' && payload.item) {
        setPhase('running')
        setLive((prev) => ({
          ...prev,
          [payload.item!]: {
            state: payload.state ?? 'downloading',
            fraction: payload.fraction ?? -1,
            message: payload.message ?? '',
            error: payload.error
          }
        }))
      } else if (payload.event === 'result') {
        setPhase('idle')
        refresh() // completion is re-derived from disk, not trusted from memory
      } else if (payload.event === 'exited') {
        setPhase('idle')
        setNote('Setup stopped unexpectedly — press download to resume where it left off.')
        refresh()
      } else if (payload.event === 'interrupted') {
        setPhase('idle')
        setNote('A job started — it takes over the remaining downloads and resumes the partial files.')
        refresh()
      }
    }).then((u) => {
      if (disposed) u()
      else un = u
    })
    return () => {
      disposed = true
      un?.()
    }
  }, [refresh])

  const start = () => {
    setNote(null)
    setPhase('starting')
    api.runSetup().catch((err) => {
      setPhase('idle')
      setNote(`Could not start setup: ${String(err)}`)
    })
  }

  if (status === undefined) {
    return <p className="setup-note mono">checking what is already on this machine…</p>
  }
  if (status === null) {
    return (
      <p className="setup-note mono">
        <span className="led led-err" /> could not check the models on this machine{' '}
        <button className="btn-ghost" onClick={refresh}>
          ↻ check again
        </button>
      </p>
    )
  }

  const rows = status.items.map((item) => {
    const l = live[item.id]
    if (l?.state === 'downloading') {
      const pct = l.fraction >= 0 ? `${Math.round(l.fraction * 100)}%` : ''
      return { ...item, led: 'led-run', right: [pct, l.message].filter(Boolean).join(' · ') || '…' }
    }
    if (l?.state === 'failed') {
      return { ...item, led: 'led-err', right: l.error ?? 'failed' }
    }
    if (l?.state === 'done' || item.present) {
      return { ...item, led: 'led-on', right: 'ready' }
    }
    return { ...item, led: 'led-off', right: item.bytes != null ? fmtBytes(item.bytes) : 'checked at download' }
  })
  const allDone = rows.every((r) => r.led === 'led-on')
  const anyFailed = rows.some((r) => r.led === 'led-err')
  const busy = phase !== 'idle'

  return (
    <div className="setup-models">
      {rows.map((row) => (
        <p className="setup-row mono" key={row.id}>
          <span className={`led ${row.led}`} />
          <span className="setup-label">{row.label}</span>
          <span className="setup-right">{row.right}</span>
        </p>
      ))}
      {phase === 'starting' && (
        <p className="setup-note mono">preparing the Python environment…</p>
      )}
      {note && <p className="setup-note mono">{note}</p>}
      {allDone ? (
        <p className="setup-note mono">
          <span className="led led-on" /> everything is already on this machine
        </p>
      ) : (
        <>
          {/* The E1-F01 contract: the size is on screen before a byte moves. */}
          {!busy && (
            <button className="btn-secondary" onClick={start}>
              {anyFailed
                ? '⇣ retry the failed downloads'
                : `⇣ download now (${fmtBytes(status.total_missing_bytes)})`}
            </button>
          )}
          <p className="setup-note">
            Optional — you can open the studio right away; anything missing simply
            downloads during your first job instead.
          </p>
        </>
      )}
    </div>
  )
}
