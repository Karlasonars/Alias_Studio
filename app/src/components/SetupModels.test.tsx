/* E1-F01 — the setup downloads (T-11). What these tests pin: the total is
 * on screen before a byte moves, completion is a redraw of disk truth (the
 * resume-after-kill story), a failure surfaces with a retry, and progress
 * events drive the item rows.
 *
 * What they cannot do, and the PR's hand-test list owns: download 2.4 GB,
 * kill a real process mid-transfer, or watch a .part file keep its offset.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SetupModels from './SetupModels'
import { callsTo, commands, emit, resetTauri } from '../test/tauri'

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('../test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})
vi.mock('@tauri-apps/api/event', async () => {
  const t = await import('../test/tauri')
  return { listen: t.listenMock }
})

beforeEach(resetTauri)

const missingWhisper = { id: 'whisper', label: 'Speech recognition', bytes: 1_621_672_079, present: false }
const missingPanns = { id: 'panns', label: 'Audio events', bytes: 312_000_000, present: false }
const presentCampplus = { id: 'campplus', label: 'Speaker embeddings', bytes: 28_000_000, present: true }

async function mount(items: object[], totalMissing: number) {
  commands.setup_status = () => ({ items, total_missing_bytes: totalMissing })
  render(<SetupModels />)
  await act(async () => {})
}

describe('the total is shown before anything downloads', () => {
  it('lists each missing item with its size and starts nothing on its own', async () => {
    await mount([missingWhisper, missingPanns], 1_933_672_079)
    expect(screen.getByText('1.6 GB')).toBeTruthy()
    expect(screen.getByText('312 MB')).toBeTruthy()
    expect(screen.getByText(/download now \(1\.9 GB\)/)).toBeTruthy()
    expect(callsTo('run_setup')).toBe(0)
  })
})

describe('completion is a redraw of disk truth (resume after a kill)', () => {
  it('items already on disk render ready with no run and no counter', async () => {
    // The app died mid-setup; on relaunch nothing is remembered — status
    // re-derives from the files, so finished items are simply "ready" and
    // the total counts only what is still missing.
    await mount([presentCampplus, missingPanns], 312_000_000)
    expect(screen.getByText('ready')).toBeTruthy()
    expect(screen.getByText(/download now \(312 MB\)/)).toBeTruthy()
    expect(callsTo('run_setup')).toBe(0)
  })

  it('a finished run re-asks the disk instead of trusting its own memory', async () => {
    commands.run_setup = () => undefined
    await mount([missingPanns], 312_000_000)
    await act(async () => {
      fireEvent.click(screen.getByText(/download now/))
    })
    expect(callsTo('run_setup')).toBe(1)
    await act(async () => {
      emit('setup-event', { event: 'result', ok: true, failures: [] })
    })
    expect(callsTo('setup_status')).toBe(2)
  })
})

describe('progress events drive the rows', () => {
  it('a downloading item shows its live fraction, then done', async () => {
    commands.run_setup = () => undefined
    await mount([missingPanns], 312_000_000)
    await act(async () => {
      fireEvent.click(screen.getByText(/download now/))
    })
    await act(async () => {
      emit('setup-event', {
        event: 'item', item: 'panns', state: 'downloading',
        fraction: 0.42, message: '131 of ~312 MB'
      })
    })
    expect(screen.getByText(/42% · 131 of ~312 MB/)).toBeTruthy()
    await act(async () => {
      emit('setup-event', { event: 'item', item: 'panns', state: 'done' })
    })
    expect(screen.getByText('ready')).toBeTruthy()
  })

  it('a failed item names its error and offers a retry that runs setup again', async () => {
    commands.run_setup = () => undefined
    await mount([missingPanns], 312_000_000)
    await act(async () => {
      fireEvent.click(screen.getByText(/download now/))
    })
    await act(async () => {
      emit('setup-event', {
        event: 'item', item: 'panns', state: 'failed', error: 'Checksum mismatch — please retry.'
      })
      emit('setup-event', { event: 'result', ok: false, failures: [{ item: 'panns', error: 'x' }] })
    })
    expect(screen.getByText(/Checksum mismatch/)).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByText(/retry the failed downloads/))
    })
    expect(callsTo('run_setup')).toBe(2)
  })
})

describe('a complete machine says so', () => {
  it('shows everything present and offers no download', async () => {
    await mount([presentCampplus], 0)
    expect(screen.getByText(/everything is already on this machine/)).toBeTruthy()
    expect(screen.queryByText(/download now/)).toBeNull()
  })
})
