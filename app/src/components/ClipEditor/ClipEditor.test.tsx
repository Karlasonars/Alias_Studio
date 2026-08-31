/* Test-day F4: `edit context` reports failures as {ok:false,error} JSON,
 * and the Rust edit_tool returns any JSON line as a successful invoke — so
 * a failure payload used to be stored as the context, leaving the editor
 * on "loading timeline…" forever with the error swallowed. The installed
 * build's eternal loading screen was one instance; ANY JSON-shaped failure
 * on this path was invisible (T-13's principle, in a path T-13 did not
 * cover). */
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { commands, resetTauri } from '../../test/tauri'
import ClipEditor from './index'

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('../../test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})
vi.mock('@tauri-apps/api/event', async () => {
  const t = await import('../../test/tauri')
  return { listen: t.listenMock }
})

beforeEach(() => {
  vi.restoreAllMocks()
  resetTauri()
})

describe('ClipEditor context failures (F4)', () => {
  it('a {ok:false} context payload surfaces its error instead of loading forever', async () => {
    commands.edit_tool = () => ({ ok: false, error: 'no job 20260831-000000-abcdef' })
    render(
      <ClipEditor jobId="20260831-000000-abcdef" clipIndex={0} onClose={() => {}} onRendered={() => {}} />
    )
    await waitFor(() => {
      expect(screen.getByText(/no job 20260831-000000-abcdef/)).toBeTruthy()
    })
    expect(screen.queryByText(/loading timeline/)).toBeNull()
  })

  it('a payload without the context shape still gets a message, not a spinner', async () => {
    commands.edit_tool = () => ({ unexpected: true })
    render(<ClipEditor jobId="j" clipIndex={0} onClose={() => {}} onRendered={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText(/could not load the timeline/)).toBeTruthy()
    })
  })

  it('a rejected invoke still surfaces as before', async () => {
    commands.edit_tool = () => {
      throw new Error('edit tool produced no JSON: boom')
    }
    render(<ClipEditor jobId="j" clipIndex={0} onClose={() => {}} onRendered={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText(/produced no JSON/)).toBeTruthy()
    })
  })
})
