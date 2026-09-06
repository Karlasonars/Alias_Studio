/* The Settings panel's image control (E20-F06): the channel avatar is a
 * stored path picked through a dialog and python's `avatar-import`, never
 * a typed path and never the watermark's folder. Pinned here because it
 * is the first control in the panel that talks to the shell for its
 * value — the seam T-36 mocks, exercised for a new command. */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Settings from './Settings'
import { commands, invokeMock, resetTauri } from '../test/tauri'

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('../test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})
vi.mock('@tauri-apps/api/event', async () => {
  const t = await import('../test/tauri')
  return { listen: t.listenMock }
})
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: async () => {} }))
const { dialogOpen } = vi.hoisted(() => ({ dialogOpen: vi.fn(async (): Promise<string | null> => null) }))
vi.mock('@tauri-apps/plugin-dialog', () => ({ open: dialogOpen }))

const STORED = 'C:/home/avatars/me-0123abcd.png'

function payload(avatar: string) {
  const defaults = { caption_preset: 'classic', story: { channel_name: 'Alias', avatar } }
  return {
    ok: true,
    defaults,
    factory: { caption_preset: 'classic', story: { channel_name: '', avatar: '' } },
    schema: {
      groups: [
        {
          key: 'story',
          label: 'Stories',
          help: 'the story format',
          cost: 'cheap',
          cost_note: 're-renders',
          fields: [
            { key: 'story.channel_name', label: 'Channel name', type: 'text', help: 'the name on the card' },
            {
              key: 'story.avatar', label: 'Channel avatar', type: 'image', import: 'avatar',
              help: 'the picture on the card'
            }
          ]
        }
      ],
      caption_fields: [],
      fonts: [],
      builtin_presets: {}
    },
    presets: {},
    preset_names: [],
    edited_presets: []
  }
}

function settingsCommands(avatar = '') {
  const sets: string[] = []
  const imports: string[] = []
  commands.settings_tool = (args) => {
    const a = args?.args as string[]
    if (a[0] === 'get') return payload(avatar)
    if (a[0] === 'set') {
      sets.push(a[1])
      return payload(JSON.parse(a[1]).story.avatar)
    }
    if (a[0] === 'avatar-import') {
      imports.push(a[1])
      return { ok: true, path: STORED, name: 'me-0123abcd.png' }
    }
    if (a[0] === 'watermark-import') throw new Error('the avatar must never go to the watermark folder')
    throw new Error(`unexpected settings verb ${a[0]}`)
  }
  return { sets, imports }
}

beforeEach(() => {
  resetTauri()
  dialogOpen.mockReset()
  dialogOpen.mockResolvedValue(null)
})

async function mountStory() {
  render(<Settings onBack={() => {}} initialGroup="story" />)
  await screen.findByText('Channel avatar')
  await act(async () => {})
}

describe('the channel avatar is an image control in Settings (E20-F06)', () => {
  it('shows none, picks a PNG through the avatar import, and saves the stored path', async () => {
    const { sets, imports } = settingsCommands()
    dialogOpen.mockResolvedValue('C:/pictures/me.png')
    await mountStory()
    expect(screen.getByText('none')).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByText('choose…'))
    })
    expect(imports).toEqual(['C:/pictures/me.png'])
    expect(screen.getByText('me-0123abcd.png')).toBeTruthy()
    // the debounced autosave writes the STORED path, never the picked one
    await waitFor(() => expect(sets.length).toBe(1))
    expect(JSON.parse(sets[0]).story.avatar).toBe(STORED)
    expect(sets[0]).not.toContain('C:/pictures')
  })

  it('names the stored file and clears it to none', async () => {
    const { sets } = settingsCommands(STORED)
    await mountStory()
    expect(screen.getByText('me-0123abcd.png')).toBeTruthy()
    expect(screen.queryByText('none')).toBeNull()
    fireEvent.click(screen.getByText('clear'))
    expect(screen.getByText('none')).toBeTruthy()
    await waitFor(() => expect(sets.length).toBe(1))
    expect(JSON.parse(sets[0]).story.avatar).toBe('')
  })

  it('a cancelled dialog changes nothing and writes nothing', async () => {
    const { sets, imports } = settingsCommands()
    await mountStory()
    await act(async () => {
      fireEvent.click(screen.getByText('choose…'))
    })
    expect(imports).toEqual([])
    expect(screen.getByText('none')).toBeTruthy()
    await act(async () => {
      await new Promise((r) => setTimeout(r, 500))
    })
    expect(sets).toEqual([])
    expect(invokeMock.mock.calls.filter(([cmd]) => cmd === 'settings_tool').length).toBe(1) // the GET
  })
})
