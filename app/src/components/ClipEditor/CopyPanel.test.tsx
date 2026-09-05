/* E19-F01: the burned title is the variant the user marks IN THE EDITOR —
 * no automatic choice — so the titles panel is where the mark is made,
 * shown, moved and cleared. Pinned here because the mark is a write to
 * `burned_title`, which the next render puts into the pixels: a panel that
 * wrote the wrong field, or nothing, would fail silently in the video. */
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { resetTauri } from '../../test/tauri'
import type { EditState } from '../../types'
import CopyPanel from './CopyPanel'

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('../../test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})
vi.mock('@tauri-apps/plugin-dialog', () => ({ open: async () => null }))

beforeEach(() => {
  resetTauri()
})

const FLEW = { text: 'Why the bath bomb flew', style: 'question', why: 'asks it', chars: 22 }
const INCIDENT = { text: 'The bath bomb incident', style: 'direct', why: 'says it', chars: 22 }

function edit(overrides: Partial<EditState> = {}): EditState {
  return {
    start: 10, end: 40,
    caption_preset: null, camera_mode: null, gameplay_amount: null,
    title: '', title_variants: [FLEW, INCIDENT], description: '', description_meta: {},
    burned_title: '',
    remove_dead_space: false, disabled_cuts: [], overlays: [],
    pacing: {}, caption_overrides: {}, lufs_target: null, true_peak_db: null,
    letterbox_fill: null,
    ...overrides
  }
}

function mount(state: EditState) {
  const persist = vi.fn(async () => {})
  render(
    <CopyPanel
      jobId="j"
      clipIndex={0}
      edit={state}
      setEdit={() => {}}
      persist={persist}
      setError={() => {}}
    />
  )
  return persist
}

describe('marking a variant to burn (E19-F01)', () => {
  it('the saved variants are listed without regenerating, and burn marks one', () => {
    const persist = mount(edit())
    // saved on the clip, shown without a paid regenerate
    expect(screen.getByText('Why the bath bomb flew')).toBeTruthy()
    expect(screen.getByText('The bath bomb incident')).toBeTruthy()
    expect(screen.queryByText('burned')).toBeNull()
    fireEvent.click(screen.getAllByText('burn')[1])
    expect(persist).toHaveBeenCalledWith(
      expect.objectContaining({ burned_title: 'The bath bomb incident', title: '' })
    )
  })

  it('a burned title is shown as such, and the mark can be cleared from either place', () => {
    const persist = mount(edit({ burned_title: 'The bath bomb incident' }))
    expect(screen.getByText('burned')).toBeTruthy()
    expect(screen.getAllByText('The bath bomb incident').length).toBe(2) // the tag line and the variant
    expect(screen.getByText('burning')).toBeTruthy()
    expect(screen.getAllByText('burn').length).toBe(1) // the other variant is still offered
    fireEvent.click(screen.getByText('burning'))
    expect(persist).toHaveBeenLastCalledWith(expect.objectContaining({ burned_title: '' }))
    fireEvent.click(screen.getByTitle('burn nothing into this clip'))
    expect(persist).toHaveBeenLastCalledWith(expect.objectContaining({ burned_title: '' }))
  })

  it('choosing a variant for publishing does not burn it — the two marks are separate', () => {
    const persist = mount(edit({ burned_title: 'The bath bomb incident' }))
    fireEvent.click(screen.getByText('Why the bath bomb flew'))
    expect(persist).toHaveBeenLastCalledWith(
      expect.objectContaining({ title: 'Why the bath bomb flew', burned_title: 'The bath bomb incident' })
    )
  })
})
