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
import { commands, emit, idleAppCommands, resetTauri } from './test/tauri'

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
