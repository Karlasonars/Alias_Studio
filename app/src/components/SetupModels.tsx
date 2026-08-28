import { useCallback, useEffect, useState } from 'react'
import { listen } from '@tauri-apps/api/event'
import { api } from '../api'
import type { BootstrapEvent, BootstrapStatus, SetupEvent, SetupStatusResult } from '../types'

/**
 * E1-F01 + T-40: everything a first run downloads, made visible up front —
 * INCLUDING the Python environment, which happens first, is the biggest
 * single piece (~3.9 GB on Windows; torch alone is 3.5 GB), and used to be
 * completely invisible: the setup_status one-shot silently triggered the
 * whole download behind "checking what is already on this machine…".
 *
 * The order of operations is the fix. bootstrap_status (Rust, instant,
 * disk-truth) answers first; the python one-shot fires ONLY once the env
 * is ready, so no multi-gigabyte download ever hides behind a "checking"
 * spinner. The env renders as the first row of the same list the models
 * use, its progress is T-11's disk-watcher pattern (real bytes on disk,
 * never uv's parsed output), and a killed bootstrap resumes at wheel
 * granularity from uv's cache.
 *
 * Everything below the env row is display over disk truth exactly as
 * before: `setup status` re-derives presence from the files themselves.
 */

interface ItemLive {
  state: 'downloading' | 'done' | 'failed'
  fraction: number
  message: string
  error?: string
}

interface BootLive {
  state: 'idle' | 'running' | 'failed'
  bytes: number
  fraction: number
  error?: string
}

function fmtBytes(n: number): string {
  return n >= 1e9 ? `${(n / 1e9).toFixed(1)} GB` : `${Math.max(1, Math.round(n / 1e6))} MB`
}

const HEADROOM = 512 * 1e6 // matches disk.py's slack above the estimate

export default function SetupModels() {
  // undefined = asking (instant — Rust reads the disk); null = the ask failed
  const [boot, setBoot] = useState<BootstrapStatus | null | undefined>(undefined)
  const [bootLive, setBootLive] = useState<BootLive>({ state: 'idle', bytes: 0, fraction: 0 })
  // undefined = not asked yet / asking; null = the ask itself failed
  const [status, setStatus] = useState<SetupStatusResult | null | undefined>(undefined)
  const [live, setLive] = useState<Record<string, ItemLive>>({})
  // 'starting' spans pressing Download until the first event arrives.
  const [phase, setPhase] = useState<'idle' | 'starting' | 'running'>('idle')
  const [note, setNote] = useState<string | null>(null)

  const refresh = useCallback(() => {
    api
      .setupStatus()
      .then(setStatus)
      .catch(() => setStatus(null))
  }, [])

  // The env question comes first, and the python one-shot waits for its
  // answer: asking python on a cold machine IS the download (T-40).
  const refreshBoot = useCallback(() => {
    api
      .bootstrapStatus()
      .then((b) => {
        setBoot(b)
        if (b.ready) refresh()
      })
      .catch(() => setBoot(null))
  }, [refresh])

  useEffect(() => {
    refreshBoot()
  }, [refreshBoot])

  useEffect(() => {
    let disposed = false
    let un: (() => void) | null = null
    listen<BootstrapEvent>('bootstrap-event', ({ payload }) => {
      if (payload.event === 'progress') {
        setBootLive({
          state: 'running',
          bytes: payload.bytes ?? 0,
          fraction: payload.fraction ?? 0
        })
      } else if (payload.event === 'result') {
        if (payload.ok) {
          setBootLive({ state: 'idle', bytes: 0, fraction: 0 })
          // completion is re-derived from disk, then setup takes over the
          // model downloads the user already asked for with the same press
          api
            .bootstrapStatus()
            .then((b) => {
              setBoot(b)
              if (b.ready) {
                refresh()
                setPhase('starting')
                api.runSetup().catch((err) => {
                  setPhase('idle')
                  setNote(`Could not start the model downloads: ${String(err)}`)
                })
              }
            })
            .catch(() => setBoot(null))
        } else {
          setBootLive({
            state: 'failed',
            bytes: 0,
            fraction: 0,
            error: payload.stderr?.split('\n').filter(Boolean).pop() ?? 'install failed'
          })
        }
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
    if (boot && !boot.ready) {
      setBootLive({ state: 'running', bytes: 0, fraction: 0 })
      api.runBootstrap().catch((err) => {
        setBootLive({ state: 'failed', bytes: 0, fraction: 0, error: String(err) })
      })
      return
    }
    setPhase('starting')
    api.runSetup().catch((err) => {
      setPhase('idle')
      setNote(`Could not start setup: ${String(err)}`)
    })
  }

  if (boot === undefined) {
    return <p className="setup-note mono">checking what is already on this machine…</p>
  }
  if (boot === null) {
    return (
      <p className="setup-note mono">
        <span className="led led-err" /> could not check this machine{' '}
        <button className="btn-ghost" onClick={refreshBoot}>
          ↻ check again
        </button>
      </p>
    )
  }

  // The environment is the first row: it downloads first, and it is the
  // single biggest piece. Its size was measured, not guessed (T-40).
  const envRow = (() => {
    if (boot.ready) return { led: 'led-on', right: 'ready' }
    if (bootLive.state === 'running') {
      const pct = Math.round(bootLive.fraction * 100)
      return { led: 'led-run', right: `${pct}% · ${fmtBytes(bootLive.bytes)} written` }
    }
    if (bootLive.state === 'failed') return { led: 'led-err', right: bootLive.error ?? 'failed' }
    return { led: 'led-off', right: `${fmtBytes(boot.env_download_bytes)} download` }
  })()

  const rows = (status?.items ?? []).map((item) => {
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
  const allDone = boot.ready && status != null && rows.every((r) => r.led === 'led-on')
  const anyFailed = bootLive.state === 'failed' || rows.some((r) => r.led === 'led-err')
  const busy = phase !== 'idle' || bootLive.state === 'running'

  const firstRunNeed = boot.env_disk_bytes + boot.models_approx_bytes
  const spaceTight =
    !boot.ready && boot.free_bytes != null && boot.free_bytes < firstRunNeed + HEADROOM

  const buttonLabel = anyFailed
    ? '⇣ retry the failed downloads'
    : boot.ready
      ? `⇣ download now (${fmtBytes(status?.total_missing_bytes ?? 0)})`
      : `⇣ download now (${fmtBytes(boot.env_download_bytes)} + ~${fmtBytes(boot.models_approx_bytes)} models)`

  return (
    <div className="setup-models">
      <p className="setup-row mono">
        <span className={`led ${envRow.led}`} />
        <span className="setup-label">Python environment (PyTorch, Whisper, the pipeline)</span>
        <span className="setup-right">{envRow.right}</span>
      </p>
      {rows.map((row) => (
        <p className="setup-row mono" key={row.id}>
          <span className={`led ${row.led}`} />
          <span className="setup-label">{row.label}</span>
          <span className="setup-right">{row.right}</span>
        </p>
      ))}
      {!boot.ready && status === undefined && (
        <p className="setup-note mono">
          + speech & audio models, itemized once the environment is ready (about{' '}
          {fmtBytes(boot.models_approx_bytes)})
        </p>
      )}
      {status === null && boot.ready && (
        <p className="setup-note mono">
          <span className="led led-err" /> could not check the models on this machine{' '}
          <button className="btn-ghost" onClick={refresh}>
            ↻ check again
          </button>
        </p>
      )}
      {spaceTight && (
        <p className="setup-note mono">
          <span className="led led-err" /> disk space is tight: the first-time download needs
          about {fmtBytes(firstRunNeed)} free and this drive has {fmtBytes(boot.free_bytes!)}.
        </p>
      )}
      {phase === 'starting' && <p className="setup-note mono">starting the model downloads…</p>}
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
              {buttonLabel}
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
