import { useCallback, useEffect, useRef, useState, type ReactElement } from 'react'
import { listen } from '@tauri-apps/api/event'
import { api } from './api'
import type { JobResults, JobSummary, LogLine, PipelineEvent, QueueStateResult, SetupState } from './types'
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
  const [setup, setSetup] = useState<SetupState | null>(null)
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [activeJob, setActiveJob] = useState<string | null>(null)
  const [results, setResults] = useState<JobResults | null>(null)
  const [stages, setStages] = useState<Record<string, { fraction: number; message: string }>>({})
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [cancelled, setCancelled] = useState(false)
  const [log, setLog] = useState<LogLine[]>([])
  // Enqueue-while-running feedback: six silent QUEUE IT presses once
  // enqueued six invisible jobs. `enqueueing` acknowledges the press the
  // moment it happens; `queuedCount` is the real pending count, pushed
  // from Rust's queue-state event whenever the queue changes.
  const [enqueueing, setEnqueueing] = useState(0)
  const [queuedCount, setQueuedCount] = useState(0)
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

  // Seed once from the instant cached snapshot, then ride the push: Rust
  // emits queue-state at every mutation, so no view ever polls for it.
  useEffect(() => {
    const count = (s: QueueStateResult) =>
      setQueuedCount(s.jobs.filter((j) => j.status === 'pending').length)
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
  }, [refreshJobs])

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
      appendLog(payload)
      if (payload.event === 'job' && payload.job_id) {
        setActiveJob(payload.job_id)
        setResults(null)
      } else if (payload.event === 'progress' && payload.stage) {
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
        if (payload.ok && activeJobRef.current) {
          api.jobResults(activeJobRef.current).then((r) => {
            setResults(r)
            setView('review')
          })
        } else if (!payload.ok) {
          setRunError(String(payload.error ?? 'Pipeline failed'))
        }
      } else if (payload.event === 'cancelled') {
        // A deliberate stop: must never read as the 'exited' crash below.
        setRunning(false)
        setRunError(null)
        setCancelled(true)
        refreshJobs()
      } else if (payload.event === 'exited') {
        setRunning(false)
        const detail = payload.stderr?.trim()
        setRunError(
          'The pipeline exited unexpectedly. Resume the job to continue from its last checkpoint.' +
            (detail ? `\n\n${detail}` : '')
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
  }, [refreshJobs, appendLog])

  const startRun = useCallback(
    async (source: string, llm: string, captions: string, gameplayAmount: number) => {
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
        await api.enqueueJob(source, llm, captions, gameplayAmount)
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
        setRunError(`Could not add to the queue: ${String(err)}`)
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
    content = <Settings onBack={() => setView('studio')} />
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
        cancelled={cancelled}
        log={log}
        enqueueing={enqueueing > 0}
        queued={queuedCount}
        onCancel={() => {
          api.cancelJob().catch(() => {})
        }}
        onRun={startRun}
        onOpenLoop={() => setView('loop')}
        onOpenSettings={() => setView('settings')}
        onOpenQueue={() => setView('queue')}
        onOpenJob={openJob}
        onResume={(id, llm) => {
          setRunning(true)
          setRunError(null)
          setCancelled(false)
          setStages({})
          setLog([])
          setActiveJob(id)
          api.resumeJob(id, llm)
        }}
      />
    )
  }

  return (
    <>
      {content}
      {view !== 'boot' && <ThemeSwitcher />}
    </>
  )
}
