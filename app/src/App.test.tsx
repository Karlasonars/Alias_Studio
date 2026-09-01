/* T-08's hand-found defects, pinned. Each test here failed against the
 * pre-fix commit it names (verified by checking out that revision of the
 * file and running the suite — the procedure is in the T-36 PR).
 *
 * Defect 7 (fixed in 9925b5f): running never returned to true on a queue
 * advance, so every job after the first had NO Cancel button — T-07's
 * process-tree kill unreachable for exactly the jobs the queue exists to
 * run. §5.12: a job start is one transition, wherever it came from.
 * Defect 6 (same commit): an advanced job inherited the previous job's
 * stage bars and log.
 * Defect 1 (fixed in c3cb8f9): enqueueing while busy changed nothing on
 * screen — six presses queued six invisible jobs.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { callsTo, commands, emit, idleAppCommands, invokeMock, resetTauri } from './test/tauri'

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('./test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})
vi.mock('@tauri-apps/api/event', async () => {
  const t = await import('./test/tauri')
  return { listen: t.listenMock }
})
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: async () => {} }))

beforeEach(() => {
  resetTauri()
  idleAppCommands()
})

async function mountStudio() {
  render(<App />)
  await screen.findByText(/FEED IT/)
  // flush the mount-effect promises (setup state, jobs, queue seed, listen)
  await act(async () => {})
}

function pipelineEvent(payload: Record<string, unknown>) {
  return act(async () => {
    emit('pipeline-event', payload)
  })
}

describe('a job start is one transition, wherever it came from (§5.12)', () => {
  it('keeps the Cancel button available for an auto-advanced job [defect 7]', async () => {
    await mountStudio()
    await pipelineEvent({ event: 'job', job_id: 'job-one' })
    expect(screen.getByText('■ CANCEL')).toBeTruthy()

    await pipelineEvent({ event: 'result', ok: false, error: 'stage blew up' })
    // the queue advances on its own: no click precedes this 'job' event
    await pipelineEvent({ event: 'job', job_id: 'job-two' })

    // Without the §5.12 reset, `running` stayed false here and the Cancel
    // control never rendered — T-07 unreachable from the UI for job two.
    expect(screen.getByText('■ CANCEL')).toBeTruthy()
    // and the previous job's failure must not haunt the new job's screen
    expect(screen.queryByText(/stage blew up/)).toBeNull()
  })

  it('does not carry the previous job\'s stage bars or log into an advance [defect 6]', async () => {
    await mountStudio()
    await pipelineEvent({ event: 'job', job_id: 'job-one' })
    await pipelineEvent({ event: 'progress', stage: 'render', fraction: 1, message: 'encoded 4 clips' })
    expect(document.querySelectorAll('.deck-row.done').length).toBe(1)

    await pipelineEvent({ event: 'result', ok: false, error: 'boom' })
    await pipelineEvent({ event: 'job', job_id: 'job-two' })

    // job two has not run RENDER; a green bar for it belongs to job one
    expect(document.querySelectorAll('.deck-row.done').length).toBe(0)
    expect(screen.queryByText(/encoded 4 clips/)).toBeNull()
  })
})

describe('a rail resume goes through the picker (T-14)', () => {
  it('opens the picker with the failed stage preselected, and resumes with the choice', async () => {
    commands.list_job_dirs = () => [
      { id: 'job-one', title: 'My video', rendered: false, cancelled: false }
    ]
    let resolveInfo!: (v: unknown) => void
    commands.resume_info = () => new Promise((resolve) => (resolveInfo = resolve))
    commands.resume_job = () => undefined
    await mountStudio()

    fireEvent.click(screen.getByText('My video'))
    // the picker answers immediately; plain resume is available before the
    // one-shot does (§5.9 — an unreadable answer must never block resume)
    expect(screen.getByText('continue from where it stopped')).toBeTruthy()
    expect(callsTo('resume_job')).toBe(0) // choosing, not yet resuming

    await act(async () => {
      resolveInfo({
        stages: [
          { name: 'asr', status: 'done', estimate_sec: null },
          { name: 'score', status: 'failed', estimate_sec: null }
        ],
        default_stage: 'score',
        duration_sec: 600
      })
    })
    expect(document.querySelector('.resume-option.opt-on')?.textContent).toContain('JUDGE')

    await act(async () => {
      fireEvent.click(screen.getByText('RESUME'))
    })
    expect(callsTo('resume_job')).toBe(1)
    const args = invokeMock.mock.calls.find(([c]) => c === 'resume_job')?.[1] as Record<
      string,
      unknown
    >
    expect(args.jobId).toBe('job-one')
    expect(args.fromStage).toBe('score')
  })
})

describe('a described failure survives the exited fallback (T-13)', () => {
  it('renders error_info actions and does not let exited stomp the described error', async () => {
    await mountStudio()
    await pipelineEvent({ event: 'job', job_id: 'job-one' })
    await pipelineEvent({
      event: 'result',
      ok: false,
      job_id: 'job-one',
      error: 'Gemini rejected the API key. Check it in Settings.',
      error_info: {
        code: 'gemini-key-rejected',
        cause: 'Gemini rejected the API key. Check it in Settings.',
        actions: ['Check the key in Settings — re-paste it from aistudio.google.com.'],
        stage: 'score'
      }
    })
    expect(screen.getByText(/re-paste it from aistudio/)).toBeTruthy()
    // Rust emits 'exited' on EVERY nonzero exit, after the result event.
    // Before T-13 this overwrote the good message with the generic crash
    // text — the described error must win.
    await pipelineEvent({ event: 'exited', code: 1, stderr: 'noise' })
    // (the console log line still records the exit — the PANEL must not)
    const cause = document.querySelector('.error-cause')
    expect(cause?.textContent).toContain('Gemini rejected the API key')
    expect(cause?.textContent).not.toContain('exited unexpectedly')
  })

  it('still explains a crash that produced no result event', async () => {
    await mountStudio()
    await pipelineEvent({ event: 'job', job_id: 'job-one' })
    await pipelineEvent({ event: 'exited', code: 1, stderr: 'RuntimeError: ~ is gone' })
    expect(screen.getByText(/The pipeline exited unexpectedly/)).toBeTruthy()
    expect(screen.getByText(/continues from its last checkpoint/)).toBeTruthy()
  })
})

describe('the disk pre-flight reaches the screen (E1-F07 / T-12)', () => {
  it('shows a warn notice while the job keeps running, Cancel intact', async () => {
    await mountStudio()
    await pipelineEvent({ event: 'job', job_id: 'job-one' })
    await pipelineEvent({
      event: 'disk',
      action: 'warn',
      message: 'Disk space is tight: this job may need up to 12.4 GB on C:\\ and 9.1 GB is free.'
    })
    // a warning, not a verdict: the run continues and stays cancellable
    expect(screen.getAllByText(/may need up to 12.4 GB/).length).toBeGreaterThan(0)
    expect(screen.getByText('■ CANCEL')).toBeTruthy()
  })

  it('shows a blocked start as the job\'s failure, with the numbers', async () => {
    await mountStudio()
    await pipelineEvent({ event: 'job', job_id: 'job-one' })
    const message =
      'Not enough disk space: this job needs roughly 4.1–18.0 GB free on C:\\ and only 1.2 GB is free. ' +
      'Nothing was written — free up space and resume this job from the rail.'
    await pipelineEvent({ event: 'disk', action: 'block', message })
    await pipelineEvent({ event: 'result', ok: false, job_id: 'job-one', error: message })
    // the user can tell WHICH happened: the message names the block and the
    // way out, and the run is over (no Cancel for a job that never started)
    expect(screen.getAllByText(/free up space and resume/).length).toBeGreaterThan(0)
    expect(screen.queryByText('■ CANCEL')).toBeNull()
  })

  it('does not carry a warning into the next job (§5.12)', async () => {
    await mountStudio()
    await pipelineEvent({ event: 'job', job_id: 'job-one' })
    await pipelineEvent({ event: 'disk', action: 'warn', message: 'Disk space is tight: 9.1 GB free.' })
    await pipelineEvent({ event: 'result', ok: false, error: 'render: out of space' })
    // the queue advances on its own; job two got the space job one freed
    await pipelineEvent({ event: 'job', job_id: 'job-two' })
    expect(screen.queryByText(/Disk space is tight/)).toBeNull()
  })
})

describe('the studio rail shows the measured hardware expectation (T-10)', () => {
  it('renders the estimate from the profile file, or admits there is none', async () => {
    commands.get_hardware_profile = () => ({
      summary: {
        torch_device: 'cuda',
        gpu: 'NVIDIA GeForce RTX 4070',
        vram_gb: 12,
        whisper_device: 'cuda',
        whisper_compute: 'float16',
        onnx_providers: ['CUDAExecutionProvider', 'CPUExecutionProvider'],
        cpu_threads: 16,
        forced: null
      },
      key: 'k',
      estimate_ratio: 0.15,
      estimate_jobs: 3
    })
    await mountStudio()
    expect(screen.getByText(/RTX 4070 · 12 GB/)).toBeTruthy()
    expect(screen.getByText('60 min video ≈ 9 min')).toBeTruthy()
  })
})

describe('enqueue while a job is running answers on screen [defect 1]', () => {
  it('acknowledges the press, then shows the true waiting count', async () => {
    await mountStudio()
    // start the first job the way a user does — through the button — so
    // this test exercises the same path on pre-fix code, where only the
    // click handler ever set `running`
    commands.enqueue_job = () => 'job-one'
    const input = screen.getByPlaceholderText(/YouTube URL or a path/)
    fireEvent.change(input, { target: { value: 'C:/videos/first.mp4' } })
    await act(async () => {
      fireEvent.click(screen.getByText('CUT IT'))
    })
    await pipelineEvent({ event: 'job', job_id: 'job-one' })
    await pipelineEvent({ event: 'progress', stage: 'asr', fraction: 0.5, message: 'transcribing' })

    let finishEnqueue!: () => void
    commands.enqueue_job = () =>
      new Promise((resolve) => {
        finishEnqueue = () => resolve('job-two')
      })

    fireEvent.change(input, { target: { value: 'C:/videos/second.mp4' } })
    fireEvent.click(screen.getByText('QUEUE IT'))

    // the press must register before any subprocess answers
    expect(await screen.findByText('adding to queue…')).toBeTruthy()

    await act(async () => {
      finishEnqueue()
    })
    // Rust pushes the new state after the enqueue lands
    await act(async () => {
      emit('queue-state', {
        jobs: [
          { id: 'job-one', status: 'running', error: null, title: null, source: 'a.mp4', created_at: 1, stages_done: 1 },
          { id: 'job-two', status: 'pending', error: null, title: null, source: 'C:/videos/second.mp4', created_at: 2, stages_done: 0 }
        ],
        paused: false,
        active_job_id: 'job-one',
        ready: true
      })
    })
    expect(screen.getByText(/1 waiting in the queue/)).toBeTruthy()

    // the constraint from the same defect: the running job's screen is
    // untouched — its stage bar and cancel control survive the enqueue
    // (the message shows in both the deck row and the console log)
    expect(screen.getAllByText(/transcribing/).length).toBeGreaterThan(0)
    expect(screen.getByText('■ CANCEL')).toBeTruthy()
  })
})

describe('the letterbox fill is decided before CUT IT (E6-F09)', () => {
  it('the edges control exists only where bars can exist', async () => {
    await mountStudio()
    // podcast framing crops to exactly 9:16 — bars never exist, and a
    // control that changes nothing would be a §5.2 lie
    expect(screen.queryByText('edges')).toBeNull()
    fireEvent.click(screen.getByText('gameplay'))
    expect(screen.getByText('edges')).toBeTruthy()
    expect(screen.getByText('blurred')).toBeTruthy()
    fireEvent.click(screen.getByText('podcast'))
    expect(screen.queryByText('edges')).toBeNull()
  })

  it('CUT IT carries the chosen fill into the enqueue', async () => {
    await mountStudio()
    commands.enqueue_job = () => 'job-fill'
    fireEvent.click(screen.getByText('gameplay'))
    fireEvent.click(screen.getByText('blurred'))
    fireEvent.change(screen.getByPlaceholderText(/YouTube URL or a path/), {
      target: { value: 'C:/videos/gameplay.mp4' }
    })
    await act(async () => {
      fireEvent.click(screen.getByText('CUT IT'))
    })
    const call = invokeMock.mock.calls.find(([cmd]) => cmd === 'enqueue_job')
    expect(call?.[1]).toMatchObject({ gameplayAmount: 1, letterboxFill: 'blur' })
  })
})
