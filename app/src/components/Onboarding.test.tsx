/* E1-F02 — the gate that leads through (T-09). The gate itself is
 * deliberate (PRD §4.2, D-15) and none of these tests loosens it; they pin
 * that both doors now PROVE they work before opening, and that a closed
 * door leads somewhere instead of dead-ending.
 *
 * What these tests cannot do, and the PR's hand-test list owns: install
 * Ollama, pull a 5 GB model, or verify a real Gemini key against Google.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Onboarding from './Onboarding'
import { callsTo, commands, resetTauri } from '../test/tauri'

const opened = vi.hoisted(() => [] as string[])

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('../test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})
vi.mock('@tauri-apps/api/event', async () => {
  const t = await import('../test/tauri')
  return { listen: t.listenMock }
})
vi.mock('@tauri-apps/plugin-opener', () => ({
  openUrl: async (url: string) => {
    opened.push(url)
  }
}))

beforeEach(() => {
  resetTauri()
  opened.length = 0
  vi.useRealTimers()
})

const notRunning = () => ({ running: false, models: [] })

async function mountBrainStep() {
  render(<Onboarding onDone={() => {}} />)
  fireEvent.click(screen.getByText('Set it up'))
  await act(async () => {})
}

function continueButton(): HTMLButtonElement {
  return screen.getByText('Continue') as HTMLButtonElement
}

async function saveKey(status: string, reason: string | null = null) {
  commands.save_gemini_key = () => ({ status, reason })
  fireEvent.change(screen.getByPlaceholderText('AIza…'), { target: { value: 'AIzaSomething' } })
  await act(async () => {
    fireEvent.click(screen.getByText('Save & verify'))
  })
}

describe('the Gemini door proves the key before opening the gate', () => {
  it('a rejected key does not open the gate and says so', async () => {
    commands.check_ollama = notRunning
    await mountBrainStep()
    await saveKey('rejected')
    // "Saved ✓" used to mean "written to disk": a typo'd key opened the
    // gate here and failed twenty minutes later inside scoring.
    expect(screen.getByText(/rejected that key/)).toBeTruthy()
    expect(continueButton().disabled).toBe(true)
  })

  it('a valid key on an API-disabled project is not called a typo', async () => {
    // 403 is not one thing: SERVICE_DISABLED means the key is fine and
    // the fix is a console click. The gate stays closed either way, but
    // the message must name the real next step, not claim a bad key.
    commands.check_ollama = notRunning
    await mountBrainStep()
    await saveKey('rejected', 'SERVICE_DISABLED')
    expect(screen.getByText(/Generative Language API disabled/)).toBeTruthy()
    expect(screen.queryByText(/a typo/)).toBeNull()
    expect(continueButton().disabled).toBe(true)
  })

  it('a restricted key names the reason instead of claiming a typo', async () => {
    commands.check_ollama = notRunning
    await mountBrainStep()
    await saveKey('rejected', 'API_KEY_HTTP_REFERRER_BLOCKED')
    expect(screen.getByText(/API_KEY_HTTP_REFERRER_BLOCKED/)).toBeTruthy()
    expect(screen.queryByText(/a typo/)).toBeNull()
    expect(continueButton().disabled).toBe(true)
  })

  it('a key that cannot be checked still opens the gate, marked unverified (§5.9)', async () => {
    commands.check_ollama = notRunning
    await mountBrainStep()
    await saveKey('unverified')
    expect(screen.getByText(/could not be reached to verify/)).toBeTruthy()
    expect(continueButton().disabled).toBe(false)
  })

  it('a verified key opens the gate and says verified, not merely saved', async () => {
    commands.check_ollama = notRunning
    await mountBrainStep()
    await saveKey('verified')
    expect(screen.getByText('Verified ✓')).toBeTruthy()
    expect(continueButton().disabled).toBe(false)
  })
})

describe('the Ollama door leads through instead of dead-ending', () => {
  it('running without a chat model is not success and does not open the gate', async () => {
    // this state used to read as ready: the gate opened and scoring then
    // failed with "Ollama has no models" - after the expensive stages ran
    commands.check_ollama = () => ({ running: true, models: ['nomic-embed-text:latest'] })
    await mountBrainStep()
    expect(screen.getByText(/no chat model yet/)).toBeTruthy()
    expect(screen.getAllByText(/ollama pull llama3\.1:8b/).length).toBeGreaterThan(0)
    expect(continueButton().disabled).toBe(true)
  })

  it('the not-detected card offers a real download link', async () => {
    commands.check_ollama = notRunning
    await mountBrainStep()
    fireEvent.click(screen.getByText(/get Ollama/))
    await act(async () => {})
    expect(opened).toContain('https://ollama.com/download')
  })

  it('re-checks on focus and on demand, never on a timer', async () => {
    vi.useFakeTimers()
    commands.check_ollama = notRunning
    await mountBrainStep()
    expect(callsTo('check_ollama')).toBe(1)
    // a timer would poll here; T-08's 2 s poll stacked subprocesses
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000)
    })
    expect(callsTo('check_ollama')).toBe(1)
    // coming back from the installer window is the moment that matters
    await act(async () => {
      window.dispatchEvent(new Event('focus'))
    })
    expect(callsTo('check_ollama')).toBe(2)
    await act(async () => {
      fireEvent.click(screen.getByText(/check again/))
    })
    expect(callsTo('check_ollama')).toBe(3)
  })
})
