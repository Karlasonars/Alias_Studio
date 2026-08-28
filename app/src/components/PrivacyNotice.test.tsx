/* T-17 (E15-F03): the app shows the real PRIVACY.md, not a paraphrase.
 * The component imports the repository file at build time, so these tests
 * pin the two things that matter: the document the user sees carries the
 * load-bearing claims (the never-uploaded promise, the free-tier training
 * sentence, the hosts), and the Privacy tab in Settings actually reaches
 * it. The completeness of the document itself is pytest's job
 * (pipeline/tests/test_privacy_notice.py). */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { SettingsPayload } from '../types'
import { commands, resetTauri } from '../test/tauri'
import PrivacyNotice from './PrivacyNotice'
import Settings from './Settings'

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('../test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: vi.fn(async () => {}) }))

beforeEach(() => {
  vi.restoreAllMocks()
  resetTauri()
})

describe('PrivacyNotice (E15-F03)', () => {
  it('renders the repository document with its load-bearing claims intact', () => {
    const { container } = render(<PrivacyNotice />)
    const text = container.textContent ?? ''
    // the product's actual claim, first
    expect(text).toContain('never uploaded')
    // the single most important sentence (T-39's finding)
    expect(text).toContain('free-tier prompts')
    expect(text).toContain('improve its products')
    // one host per category proves the full document arrived, not a summary
    expect(text).toContain('generativelanguage.googleapis.com')
    expect(text).toContain('localhost:11434')
    expect(text).toContain('huggingface.co')
    expect(text).toContain('graph.instagram.com')
  })

  it('says plainly what refusing Gemini means, not just that it is optional', () => {
    const { container } = render(<PrivacyNotice />)
    const text = container.textContent ?? ''
    expect(text).toContain('Ollama')
    expect(text).toContain('local estimates')
  })
})

const payload: SettingsPayload = {
  ok: true,
  defaults: { caption_preset: 'classic' },
  factory: { caption_preset: 'classic' },
  schema: {
    groups: [
      { key: 'clips', label: 'Clips', help: '', cost: 'cheap', cost_note: '', fields: [] }
    ],
    caption_fields: [],
    fonts: [],
    builtin_presets: {}
  },
  presets: { classic: {} },
  preset_names: ['classic'],
  edited_presets: []
}

describe('Settings → Privacy tab (E15-F03)', () => {
  it('offers a Privacy tab that opens the notice', async () => {
    commands.settings_tool = () => payload
    const { container } = render(<Settings onBack={() => {}} />)
    const tab = await screen.findByText('Privacy')
    fireEvent.click(tab)
    await waitFor(() => {
      expect(container.querySelector('.privacy-doc')).toBeTruthy()
    })
    expect(container.textContent).toContain('never uploaded')
  })
})
