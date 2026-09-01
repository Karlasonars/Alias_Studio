import { useCallback, useEffect, useRef, useState, type ReactElement } from 'react'
import { listen } from '@tauri-apps/api/event'
import { api } from './api'
import type { ErrorInfo, HardwareProfile, JobResults, JobSummary, LogLine, PipelineEvent, QueueStateResult, SetupState } from './types'
import Onboarding from './components/Onboarding'
import Studio from './components/Studio'
import Review from './components/Review'
import Loop from './components/Loop'
import QueueView from './components/QueueView'
import Settings from './components/Settings'
import ThemeSwitcher from './components/ThemeSwitcher'
import './styles.css'

type View = 'boot' | 'onboarding' | 'studio' | 'review' | 'loop' | 'settings' | 'queue'

const LOG_LIMIT = 2000

// T-13: every failure renders through one shape. A bare string (an old DB
// row, a producer that predates error_info) becomes a cause with no
// actions — exactly the old error block, through the new panel.
function asErrorInfo(text: string, info?: ErrorInfo): ErrorInfo {
  if (info && info.cause) return info
  return { code: 'legacy', cause: text, actions: [] }
}

// One readable line per pipeline-event, for the raw console feed — this is
// deliberately separate from `stages` (which keeps only the latest message
// per stage, for the progress bars). Returns null for events with nothing
// worth showing verbatim.
function formatLogLine(payload: PipelineEvent): string | null {
  switch (payload.event) {
    case 'job':
      return `job ${payload.job_id ?? '?'} started`
    case 'progress': {
      const stage = (payload.stage ?? '?').toUpperCase()
      const pct = typeof payload.fraction === 'number' && payload.fraction >= 0
        ? ` (${Math.round(payload.fraction * 100)}%)`
        : ''
      return `[${stage}]${pct} ${payload.message ?? ''}`.trimEnd()
    }
    case 'result':
      return payload.ok ? 'job finished' : `job failed: ${payload.error ?? 'unknown error'}`
    case 'disk':
      return `disk: ${payload.message ?? ''}`.trimEnd()
    case 'cancelled':
      return 'job cancelled — checkpoints kept'
    case 'exited':
      return `pipeline exited unexpectedly (code ${payload.code ?? '?'})`
    default:
      return null
  }
}

export default function App() {
  const [view, setView] = useState<View>('boot')
  const [updateAvail, setUpdateAvail] = useState<string | null>(null)
  const [settingsFocus, setSettingsFocus] = useState<string | undefined>(undefined)
  const [setup, setSetup] = useState<SetupState | null>(null)
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [activeJob, setActiveJob] = useState<string | null>(null)
  const [results, setResults] = useState<JobResults | null>(null)
  const [stages, setStages] = useState<Record<string, { fraction: number; message: string }>>({})
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<ErrorInfo | null>(null)
  const [cancelled, setCancelled] = useState(false)
  // E1-F07: the pre-flight's warn-level notice ("this may need up to N GB").
  // A block-level result rides the existing error path instead — one place
  // per severity, so a warning can never be mistaken for a dead job.
  const [diskNotice, setDiskNotice] = useState<string | null>(null)
  const [log, setLog] = useState<LogLine[]>([])
  // Enqueue-while-running feedback: six silent QUEUE IT presses once
  // enqueued six invisible jobs. `enqueueing` acknowledges the press the
  // moment it happens; `queuedCount` is the real pending count, pushed
  // from Rust's queue-state event whenever the queue changes.
  const [enqueueing, setEnqueueing] = useState(0)
  const [queuedCount, setQueuedCount] = useState(0)
  const [hardware, setHardware] = useState<HardwareProfile | null>(null)
  const unlistenRef = useRef<(() => void) | null>(null)
  const activeJobRef = useRef<string | null>(null)
  const runningRef = useRef(false)
  const logIdRef = useRef(0)
  activeJobRef.current = activeJob
  runningRef.current = running

  const appendLog = useCallback((payload: PipelineEvent) => {
    const text = formatLogLine(payload)
    if (!text) return
    setLog((prev) => {
      const line: LogLine = {
        id: ++logIdRef.current,
        time: new Date().toLocaleTimeString([], { hour12: false }),
        text
      }
      const next = prev.length >= LOG_LIMIT ? prev.slice(prev.length - LOG_LIMIT + 1) : prev.slice()
      next.push(line)
      return next
    })
  }, [])

  const refreshJobs = useCallback(() => {
    api.listJobs().then(setJobs).catch(() => setJobs([]))
  }, [])

  // A plain file read (never a probe): python rewrites the profile at the
  // end of every successful job, so re-read it whenever a run ends.
  const refreshHardware = useCallback(() => {
    api.hardwareProfile().then(setHardware).catch(() => {})
  }, [])

  // Seed once from the instant cached snapshot, then ride the push: Rust
  // emits queue-state at every mutation, so no view ever polls for it.
  useEffect(() => {
    // The listing can lag a spawn: SQLite flips a job to 'running' only
    // when run_stages starts, seconds after the shell spawned it - so a
    // snapshot taken around the spawn still shows that job as 'pending'.
    // The shell knows the id it just started (active_job_id rides every
    // push); a count that excludes it is honest - the same derivation the
    // queue view uses for its UP NEXT list. Not a "minus one": if the
    // snapshot already saw the flip, nothing is excluded.
    const count = (s: QueueStateResult) =>
      setQueuedCount(
        s.jobs.filter((j) => j.status === 'pending' && j.id !== s.active_job_id).length
      )
    api.queueState().then(count).catch(() => {})
    let disposed = false
    let un: (() => void) | null = null
    listen<QueueStateResult>('queue-state', ({ payload }) => count(payload)).then((u) => {
      if (disposed) u()
      else un = u
    })
    return () => {
      disposed = true
      un?.()
    }
  }, [])

  useEffect(() => {
    api.setupState().then((s) => {
      setSetup(s)
      setView(s.onboarded ? 'studio' : 'onboarding')
    })
    refreshJobs()
    refreshHardware()
  }, [refreshJobs, refreshHardware])

  // T-16: the launch update check (E15-F01) — on by default, switchable in
  // Settings → About, where the whole install flow lives. One GET for
  // latest.json; every failure path is silent, because a dev build, an
  // offline machine or a repo with no release yet are not error states.
  useEffect(() => {
    ;(async () => {
      try {
        if (!(await api.updateChecksEnabled())) return
        const { check } = await import('@tauri-apps/plugin-updater')
        const update = await check()
        if (update) setUpdateAvail(update.version)
      } catch {
        /* quiet by design */
      }
    })()
  }, [])

  // Instagram loop: opportunistic sync on launch + hourly while open
  // (decision #12 — no background process, the app's own uptime is the
  // schedule). Fire-and-forget; the Loop screen re-reads on entry.
  useEffect(() => {
    const kick = () => {
      api
        .igStatus()
        .then((s) => (s.connected ? api.igSync() : null))
        .catch(() => null)
    }
    kick()
    const timer = window.setInterval(kick, 60 * 60 * 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    let disposed = false
    listen<PipelineEvent>('pipeline-event', ({ payload }) => {
      if (payload.event === 'job' && payload.job_id) {
        // Starting a job is ONE transition with one meaning, however it
        // was triggered - enqueue-while-idle, queue advance, START QUEUE,
        // or rail resume - so the per-job screen reset lives HERE, where
        // the transition is observed, not at each trigger. When only the
        // explicit triggers reset, an auto-advanced job inherited the
        // previous job's stage bars and log, ran with running=false (no
        // Cancel button - T-07 unreachable for queued jobs), and a
        // busy-enqueue would have wrongly taken the idle path.
        setActiveJob(payload.job_id)
        setResults(null)
        setStages({})
        setLog([])
        setRunError(null)
        setCancelled(false)
        setDiskNotice(null)
        setRunning(true)
      }
      appendLog(payload)
      if (payload.event === 'progress' && payload.stage) {
        setStages((prev) => ({
          ...prev,
          [payload.stage!]: {
            fraction: payload.fraction ?? -1,
            message: payload.message ?? ''
          }
        }))
      } else if (payload.event === 'result') {
        setRunning(false)
        refreshJobs()
        refreshHardware()
        if (payload.ok && activeJobRef.current) {
          api.jobResults(activeJobRef.current).then((r) => {
            setResults(r)
            setView('review')
          })
        } else if (!payload.ok) {
          setRunError(asErrorInfo(String(payload.error ?? 'Pipeline failed'), payload.error_info))
        }
      } else if (payload.event === 'disk') {
        // Warn: the job continues, so keep the notice up beside the deck.
        // Block: the run's own failed result lands next and takes the
        // error path — duplicating it here would show the message twice.
        if (payload.action === 'warn') setDiskNotice(String(payload.message ?? ''))
      } else if (payload.event === 'cancelled') {
        // A deliberate stop: must never read as the 'exited' crash below.
        setRunning(false)
        setRunError(null)
        setCancelled(true)
        refreshJobs()
      } else if (payload.event === 'exited') {
        setRunning(false)
        // Fallback only: Rust emits 'exited' on EVERY nonzero exit, which
        // also follows a result event that already described the failure.
        // Overwriting here used to stomp every good StageError message
        // with the generic crash text — the described error wins (T-13).
        const detail = payload.stderr?.trim()
        setRunError(
          (prev) =>
            prev ?? {
              code: 'pipeline-exited',
              cause: 'The pipeline exited unexpectedly.',
              actions: [
                'Resume the job from the rail — it continues from its last checkpoint.',
                'If it happens again, copy the technical details and open an issue.'
              ],
              detail: detail || null
            }
        )
      }
    }).then((un) => {
      if (disposed) un()
      else unlistenRef.current = un
    })
    return () => {
      disposed = true
      unlistenRef.current?.()
    }
  }, [refreshJobs, appendLog, refreshHardware])

  const startRun = useCallback(
    async (source: string, llm: string, captions: string, gameplayAmount: number, letterboxFill: string) => {
      // While a job is running this only enqueues - the running job's log
      // and stage bars must not be cleared out from under it.
      const wasIdle = !runningRef.current
      if (wasIdle) {
        setRunning(true)
        setLog([])
        setRunError(null)
        setCancelled(false)
        setStages({})
        setResults(null)
        setActiveJob(null)
      }
      setEnqueueing((n) => n + 1)
      try {
        await api.enqueueJob(source, llm, captions, gameplayAmount, letterboxFill)
        if (!wasIdle) {
          // A busy-enqueue used to change nothing on screen - the rail
          // refreshes only on run events, so six presses queued six
          // invisible jobs. The count Studio shows arrives by push.
          refreshJobs()
        }
      } catch (err) {
        // A swallowed enqueue error is the same silence: surface it the
        // way run errors are surfaced.
        if (wasIdle) setRunning(false)
        setRunError(asErrorInfo(`Could not add to the queue: ${String(err)}`))
      } finally {
        setEnqueueing((n) => n - 1)
      }
    },
    [refreshJobs]
  )

  const openJob = useCallback(async (jobId: string) => {
    const r = await api.jobResults(jobId)
    setActiveJob(jobId)
    setResults(r)
    if (r.render?.outputs?.length) setView('review')
  }, [])

  let content: ReactElement

  if (view === 'boot') {
    content = <div className="boot" />
  } else if (view === 'onboarding' && setup) {
    content = (
      <Onboarding
        onDone={() => {
          api.markOnboarded()
          setSetup({ ...setup, onboarded: true })
          setView('studio')
        }}
      />
    )
  } else if (view === 'loop') {
    content = <Loop onBack={() => setView('studio')} />
  } else if (view === 'settings') {
    content = <Settings onBack={() => setView('studio')} initialGroup={settingsFocus} />
  } else if (view === 'queue') {
    content = <QueueView onBack={() => setView('studio')} />
  } else if (view === 'review' && results) {
    content = (
      <Review
        results={results}
        onBack={() => {
          setView('studio')
          refreshJobs()
        }}
        onRestyle={(captions, camera, gameplayAmount) => {
          setRunning(true)
          setRunError(null)
          setCancelled(false)
          setStages({})
          setLog([])
          setActiveJob(results.job_id)
          setView('studio')
          api.resumeJob(results.job_id, undefined, captions, camera, gameplayAmount)
        }}
      />
    )
  } else {
    content = (
      <Studio
        jobs={jobs}
        running={running}
        stages={stages}
        error={runError}
        errorJobId={activeJob}
        cancelled={cancelled}
        diskNotice={diskNotice}
        log={log}
        enqueueing={enqueueing > 0}
        queued={queuedCount}
        hardware={hardware}
        onCancel={() => {
          api.cancelJob().catch(() => {})
        }}
        onRun={startRun}
        onOpenLoop={() => setView('loop')}
        onOpenSettings={() => {
          setSettingsFocus(undefined)
          setView('settings')
        }}
        onOpenQueue={() => setView('queue')}
        onOpenJob={openJob}
        onResume={(id, fromStage) => {
          setRunning(true)
          setRunError(null)
          setCancelled(false)
          setStages({})
          setLog([])
          setActiveJob(id)
          api.resumeJob(id, undefined, undefined, undefined, undefined, fromStage)
        }}
      />
    )
  }

  return (
    <>
      {content}
      {updateAvail && view === 'studio' && (
        <div className="update-banner">
          <span>
            Update <span className="mono">{updateAvail}</span> is available.
          </span>
          <button
            className="btn-secondary"
            onClick={() => {
              setSettingsFocus('__about')
              setView('settings')
            }}
          >
            VIEW
          </button>
          <button
            className="btn-ghost"
            title="dismiss until next launch"
            onClick={() => setUpdateAvail(null)}
          >
            ✕
          </button>
        </div>
      )}
      {view !== 'boot' && <ThemeSwitcher />}
    </>
  )
}
