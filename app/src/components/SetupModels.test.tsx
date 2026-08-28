/* E1-F01 — the setup downloads (T-11), and since T-40 the Python
 * environment above them. What these tests pin: the total is on screen
 * before a byte moves, completion is a redraw of disk truth (the
 * resume-after-kill story), a failure surfaces with a retry, progress
 * events drive the item rows — and, T-40's reason to exist: on a machine
 * with no environment, the python one-shot is NEVER fired (it would
 * silently start a ~3.9 GB download behind a "checking" spinner), the env
 * is priced at the top of the list before a byte moves, and its progress
 * is real bytes, not an invented percentage.
 *
 * What they cannot do, and the PR's hand-test list owns: download
 * gigabytes, kill a real process mid-transfer, or watch a .part file keep
 * its offset.
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

const readyBoot = {
  ready: true,
  env_download_bytes: 3_857_000_000,
  env_disk_bytes: 9_500_000_000,
  models_approx_bytes: 2_390_000_000,
  free_bytes: 200_000_000_000
}

async function mount(items: object[], totalMissing: number) {
  commands.bootstrap_status = () => readyBoot
  commands.setup_status = () => ({ items, total_missing_bytes: totalMissing })
  render(<SetupModels />)
  await act(async () => {})
}

async function mountCold(free: number | null = 200_000_000_000) {
  commands.bootstrap_status = () => ({ ...readyBoot, ready: false, free_bytes: free })
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
    // two 'ready' rows: the env (T-40's first row) and campplus
    expect(screen.getAllByText('ready').length).toBe(2)
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
    expect(screen.getAllByText('ready').length).toBeGreaterThan(0)
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

describe('the environment bootstrap (T-40)', () => {
  it('never fires the python one-shot while the environment is missing', async () => {
    // The old behavior: setup_status on mount — which on a cold machine IS
    // the silent multi-gigabyte download, hidden behind "checking…".
    await mountCold()
    expect(callsTo('setup_status')).toBe(0)
    expect(callsTo('bootstrap_status')).toBe(1)
  })

  it('prices the environment at the top of the list before a byte moves', async () => {
    await mountCold()
    expect(screen.getByText(/Python environment/)).toBeTruthy()
    expect(screen.getByText('3.9 GB download')).toBeTruthy()
    // the models are named honestly as a second, not-yet-itemizable line
    expect(screen.getByText(/itemized once the environment is ready/)).toBeTruthy()
    expect(screen.getByText(/download now \(3\.9 GB \+ ~2\.4 GB models\)/)).toBeTruthy()
    expect(callsTo('run_bootstrap')).toBe(0)
  })

  it('shows real bytes while the bootstrap runs, never an invented number', async () => {
    commands.run_bootstrap = () => undefined
    await mountCold()
    await act(async () => {
      fireEvent.click(screen.getByText(/download now/))
    })
    expect(callsTo('run_bootstrap')).toBe(1)
    await act(async () => {
      emit('bootstrap-event', { event: 'progress', bytes: 2_100_000_000, fraction: 0.12 })
    })
    expect(screen.getByText(/12% · 2\.1 GB written/)).toBeTruthy()
  })

  it('chains into the model downloads the user already asked for', async () => {
    commands.run_bootstrap = () => undefined
    commands.run_setup = () => undefined
    await mountCold()
    await act(async () => {
      fireEvent.click(screen.getByText(/download now/))
    })
    // the env finishes; the same press carries through to the models
    commands.bootstrap_status = () => readyBoot
    commands.setup_status = () => ({ items: [missingPanns], total_missing_bytes: 312_000_000 })
    await act(async () => {
      emit('bootstrap-event', { event: 'result', ok: true })
    })
    expect(callsTo('setup_status')).toBe(1)
    expect(callsTo('run_setup')).toBe(1)
  })

  it('a failed bootstrap names its error and retries resumably', async () => {
    commands.run_bootstrap = () => undefined
    await mountCold()
    await act(async () => {
      fireEvent.click(screen.getByText(/download now/))
    })
    await act(async () => {
      emit('bootstrap-event', {
        event: 'result', ok: false,
        stderr: 'error: Failed to download torch\nCaused by: connection reset'
      })
    })
    expect(screen.getByText(/connection reset/)).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByText(/retry the failed downloads/))
    })
    expect(callsTo('run_bootstrap')).toBe(2)
  })

  it('warns when the drive cannot hold the first run', async () => {
    await mountCold(5_000_000_000)
    expect(screen.getByText(/disk space is tight/)).toBeTruthy()
    // a warning, never a wall (§5.9): the download stays offered
    expect(screen.getByText(/download now/)).toBeTruthy()
  })

  it('stays quiet when free space cannot be read (§5.9: no invented number)', async () => {
    await mountCold(null)
    expect(screen.queryByText(/disk space is tight/)).toBeNull()
    expect(screen.getByText(/download now/)).toBeTruthy()
  })
})
