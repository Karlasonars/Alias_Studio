/* Test-day F6: with no network, a key saves and the gate opens — §5.9 as
 * designed. Onboarding says so on screen; this modal collapsed "unverified"
 * into a bare SAVED ✓, so the offline hand test read as a lie. Pins all
 * three save_gemini_key outcomes on the post-onboarding surface. */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { commands, resetTauri } from '../test/tauri'
import KeyModal from './KeyModal'

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('../test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})

beforeEach(() => {
  vi.restoreAllMocks()
  resetTauri()
  commands.get_setup_state = () => ({ has_gemini_key: false })
})

async function saveKey(status: string, reason: string | null = null) {
  commands.save_gemini_key = () => ({ status, reason })
  render(<KeyModal onClose={() => {}} />)
  fireEvent.change(screen.getByPlaceholderText(/AIza/), { target: { value: 'AIza-test' } })
  fireEvent.click(screen.getByText('SAVE KEY'))
  await waitFor(() => {
    expect(screen.queryByText('SAVE KEY')).toBeNull()
  })
}

describe('KeyModal (F6)', () => {
  it('a verified key reads SAVED with no caveat', async () => {
    await saveKey('verified')
    expect(screen.getByText('SAVED ✓')).toBeTruthy()
    expect(screen.queryByText(/could not be reached to verify/)).toBeNull()
  })

  it('an unverified key reads SAVED and says the check was impossible', async () => {
    await saveKey('unverified')
    expect(screen.getByText('SAVED ✓')).toBeTruthy()
    expect(screen.getByText(/could not be reached to verify/)).toBeTruthy()
    expect(screen.getByText(/checked on first use/)).toBeTruthy()
  })

  it('a rejected key reads REJECTED and saves nothing', async () => {
    await saveKey('rejected')
    expect(screen.getByText(/REJECTED/)).toBeTruthy()
    expect(screen.queryByText('SAVED ✓')).toBeNull()
    expect(screen.queryByText(/could not be reached to verify/)).toBeNull()
  })
})
