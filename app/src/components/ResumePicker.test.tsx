/* T-14 (E14-F02): the resume picker's states. Plain resume stays the first
 * option and the default for a job that did not fail; a failed job arrives
 * with its failed stage preselected; the cost line shows measured numbers
 * when present and says nothing when absent (§5.9). */
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ResumeInfo } from '../types'
import ResumePicker from './ResumePicker'

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('../test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: async () => {} }))

const info = (overrides: Partial<ResumeInfo> = {}): ResumeInfo => ({
  stages: [
    { name: 'ingest', status: 'done', estimate_sec: 900 },
    { name: 'asr', status: 'done', estimate_sec: 780 },
    { name: 'score', status: 'failed', estimate_sec: null },
    { name: 'render', status: 'missing', estimate_sec: 120 }
  ],
  default_stage: null,
  duration_sec: 600,
  ...overrides
})

describe('ResumePicker (E14-F02)', () => {
  it('shows every stage with its status, done and failed apart', () => {
    render(<ResumePicker title="t" info={info()} onGo={() => {}} onClose={() => {}} />)
    expect(screen.getByText('TRANSCRIBE')).toBeTruthy()
    expect(screen.getAllByText('done').length).toBe(2)
    expect(screen.getByText('failed')).toBeTruthy()
  })

  it('preselects the failed stage for a failed job', () => {
    render(
      <ResumePicker
        title="t"
        info={info({ default_stage: 'score' })}
        onGo={() => {}}
        onClose={() => {}}
      />
    )
    const selected = document.querySelector('.resume-option.opt-on')
    expect(selected?.textContent).toContain('JUDGE')
  })

  it('preselects plain resume for a job that did not fail', () => {
    const onGo = vi.fn()
    render(<ResumePicker title="t" info={info()} onGo={onGo} onClose={() => {}} />)
    const selected = document.querySelector('.resume-option.opt-on')
    expect(selected?.textContent).toContain('continue from where it stopped')
    fireEvent.click(screen.getByText('RESUME'))
    expect(onGo).toHaveBeenCalledWith(null) // plain resume, unchanged behaviour
  })

  it('shows the measured cost for a chosen stage, in minutes', () => {
    render(<ResumePicker title="t" info={info()} onGo={() => {}} onClose={() => {}} />)
    fireEvent.click(screen.getByText('TRANSCRIBE'))
    expect(screen.getByText(/re-running from TRANSCRIBE takes about 13 min/)).toBeTruthy()
  })

  it('says nothing where there is no measurement (§5.9), and passes the choice', () => {
    const onGo = vi.fn()
    render(
      <ResumePicker
        title="t"
        info={info({ default_stage: 'score' })}
        onGo={onGo}
        onClose={() => {}}
      />
    )
    // score is selected and has no estimate: no cost line, no invented number
    expect(document.querySelector('.resume-cost')).toBeNull()
    fireEvent.click(screen.getByText('RESUME'))
    expect(onGo).toHaveBeenCalledWith('score')
  })

  it('still offers plain resume while the one-shot is answering or unreadable', () => {
    const onGo = vi.fn()
    const { rerender } = render(
      <ResumePicker title="t" info={null} onGo={onGo} onClose={() => {}} />
    )
    expect(screen.getByText(/reading this job/)).toBeTruthy()
    fireEvent.click(screen.getByText('RESUME'))
    expect(onGo).toHaveBeenCalledWith(null)
    // an unreadable answer degrades to an empty list: no stages, no trap
    rerender(
      <ResumePicker
        title="t"
        info={{ stages: [], default_stage: null, duration_sec: null }}
        onGo={onGo}
        onClose={() => {}}
      />
    )
    expect(document.querySelector('.resume-stages')).toBeNull()
    expect(screen.getByText('RESUME')).toBeTruthy()
  })
})
