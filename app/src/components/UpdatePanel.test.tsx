/* T-16 (E15-F01): what is pinnable about the updater without publishing
 * two releases — the flow around the plugin, with the plugin mocked at
 * the module seam like every other Tauri boundary:
 *   - the changelog is shown BEFORE install, with install as a separate
 *     explicit step (a PRD acceptance criterion);
 *   - install refuses while a job is running, asked at click time;
 *   - the launch-check toggle round-trips through the shell command;
 *   - the launch check surfaces the banner in App, and only when the
 *     preference allows it.
 * What only a real release proves is listed in the T-16 PR: signature
 * verification, the installer swap, relaunch, and data survival. */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { callsTo, commands, idleAppCommands, resetTauri } from '../test/tauri'
import UpdatePanel from './UpdatePanel'

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('../test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})
vi.mock('@tauri-apps/api/event', async () => {
  const t = await import('../test/tauri')
  return { listen: t.listenMock }
})
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: async () => {} }))

// The updater plugin, mocked at the seam. `nextUpdate` is what check()
// resolves to; tests set it per case.
const downloadAndInstall = vi.fn(async () => {})
let nextUpdate: { version: string; body: string; downloadAndInstall: typeof downloadAndInstall } | null = null
vi.mock('@tauri-apps/plugin-updater', () => ({
  check: async () => nextUpdate
}))
vi.mock('@tauri-apps/plugin-process', () => ({ relaunch: vi.fn(async () => {}) }))

beforeEach(() => {
  resetTauri()
  downloadAndInstall.mockClear()
  nextUpdate = null
  commands.update_checks_enabled = () => true
  commands.set_update_checks = () => undefined
  commands.queue_state = () => ({ jobs: [], paused: false, active_job_id: null, ready: true })
})

describe('UpdatePanel (E15-F01)', () => {
  it('shows the changelog before install, as its own step', async () => {
    nextUpdate = { version: '9.9.9', body: '- fixes the frobnicator', downloadAndInstall }
    render(<UpdatePanel />)
    fireEvent.click(await screen.findByText('CHECK FOR UPDATES'))
    await screen.findByText(/Version 9\.9\.9 is available/)
    // the changelog is on screen while install has NOT happened
    expect(screen.getByText(/fixes the frobnicator/)).toBeTruthy()
    expect(downloadAndInstall).not.toHaveBeenCalled()
    expect(screen.getByText('INSTALL & RESTART')).toBeTruthy()
  })

  it('refuses to install while a job is running, and says so', async () => {
    nextUpdate = { version: '9.9.9', body: 'notes', downloadAndInstall }
    commands.queue_state = () => ({
      jobs: [],
      paused: false,
      active_job_id: 'job-running',
      ready: true
    })
    render(<UpdatePanel />)
    fireEvent.click(await screen.findByText('CHECK FOR UPDATES'))
    fireEvent.click(await screen.findByText('INSTALL & RESTART'))
    await screen.findByText(/A job is running/)
    expect(downloadAndInstall).not.toHaveBeenCalled()
  })

  it('installs when nothing is running', async () => {
    nextUpdate = { version: '9.9.9', body: 'notes', downloadAndInstall }
    render(<UpdatePanel />)
    fireEvent.click(await screen.findByText('CHECK FOR UPDATES'))
    fireEvent.click(await screen.findByText('INSTALL & RESTART'))
    await act(async () => {})
    expect(downloadAndInstall).toHaveBeenCalledTimes(1)
  })

  it('round-trips the launch-check toggle through the shell', async () => {
    render(<UpdatePanel />)
    const toggle = await screen.findByText(/check at launch: on/)
    fireEvent.click(toggle)
    await screen.findByText(/check at launch: off/)
    expect(callsTo('set_update_checks')).toBe(1)
  })

  it('says "up to date" when the check finds nothing', async () => {
    nextUpdate = null
    render(<UpdatePanel />)
    fireEvent.click(await screen.findByText('CHECK FOR UPDATES'))
    await screen.findByText('up to date')
  })
})

describe('the launch check (App banner)', () => {
  it('surfaces an available update as a dismissible banner', async () => {
    idleAppCommands()
    commands.update_checks_enabled = () => true
    nextUpdate = { version: '9.9.9', body: 'notes', downloadAndInstall }
    render(<App />)
    await screen.findByText(/FEED IT/)
    await act(async () => {})
    await screen.findByText(/is available/)
    fireEvent.click(screen.getByTitle('dismiss until next launch'))
    expect(screen.queryByText(/is available/)).toBeNull()
  })

  it('stays silent when launch checks are switched off', async () => {
    idleAppCommands() // update_checks_enabled -> false
    nextUpdate = { version: '9.9.9', body: 'notes', downloadAndInstall }
    render(<App />)
    await screen.findByText(/FEED IT/)
    await act(async () => {})
    expect(screen.queryByText(/is available/)).toBeNull()
  })
})
