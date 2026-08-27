/* T-08's queue-view defects, pinned (see App.test.tsx for the set).
 *
 * Defect 3 (fixed in 647a263): the view polled queue_state every 2 s, and
 * each call spawned a `uv run` subprocess that answers slower than the
 * interval — processes stacked until Task Manager filled. The contract is
 * push, not poll: one ask at mount, then only `queue-state` events.
 * Defect 5 (fixed in 57cfc1a, partially pinnable): the view was a flat
 * history list — a waiting job indistinguishable from one cancelled days
 * ago. What a DOM test CAN assert: waiting jobs render in their own
 * position-numbered section, apart from history. What it cannot: whether
 * that layout is visually readable — that stays with the hand test.
 */
import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import QueueView from './QueueView'
import { callsTo, commands, resetTauri } from '../test/tauri'

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('../test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})
vi.mock('@tauri-apps/api/event', async () => {
  const t = await import('../test/tauri')
  return { listen: t.listenMock }
})

function job(id: string, status: string, created_at: number, error: string | null = null) {
  return { id, status, error, title: null, source: `C:/videos/${id}.mp4`, created_at, stages_done: 0 }
}

beforeEach(() => {
  resetTauri()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('the queue view never polls [defect 3]', () => {
  it('asks queue_state once at mount and never again on a timer', async () => {
    vi.useFakeTimers()
    commands.queue_state = () => ({ jobs: [], paused: false, active_job_id: null, ready: true })
    render(<QueueView onBack={() => {}} />)
    await act(async () => {})
    expect(callsTo('queue_state')).toBe(1)

    // a minute on the clock: the 2 s poll would have asked ~30 more times,
    // each one a spawned subprocess
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000)
    })
    expect(callsTo('queue_state')).toBe(1)
  })
})

describe('waiting jobs are the point of the view [defect 5]', () => {
  it('renders the queue in its own position-numbered section, apart from history', async () => {
    commands.queue_state = () => ({
      jobs: [
        // newest-first, as `--jsonl jobs` really returns them
        job('cancelled-old', 'cancelled', 60),
        job('pending-late', 'pending', 50),
        job('pending-early', 'pending', 40),
        job('running-now', 'running', 30),
        job('failed-old', 'failed', 20, 'boom'),
        job('done-old', 'done', 10)
      ],
      paused: false,
      active_job_id: 'running-now',
      ready: true
    })
    render(<QueueView onBack={() => {}} />)

    // the three questions, answerable without reading:
    expect(await screen.findByText('NOW')).toBeTruthy() // what is running
    expect(screen.getByText('UP NEXT (2)')).toBeTruthy() // how many wait
    expect(screen.getByText('#1')).toBeTruthy() // in what order
    expect(screen.getByText('#2')).toBeTruthy()
    // queue position is FIFO: the earlier enqueue is #1 despite the
    // listing arriving newest-first
    const rows = document.querySelectorAll('.queue-row-next .queue-row-name')
    expect(rows[0]?.textContent).toContain('pending-early')
    // history exists but is its own section, not interleaved
    expect(screen.getByText('HISTORY (3)')).toBeTruthy()
  })
})
