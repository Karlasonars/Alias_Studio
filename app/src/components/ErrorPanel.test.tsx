/* T-13 (E14-F01): the failure shape as the user sees it — cause first,
 * actions as the way forward, the technical text behind a disclosure with
 * a copy button, and a legacy bare string rendering like the old block. */
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ErrorInfo } from '../types'
import ErrorPanel from './ErrorPanel'

vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: vi.fn(async () => {}) }))

const unknown: ErrorInfo = {
  code: 'unknown',
  cause: 'Something failed in the score step that this app does not have an explanation for yet.',
  actions: [
    'Resume the job from the rail — everything up to the failed step is saved.',
    'If it happens again, copy the technical details and open an issue.'
  ],
  stage: 'score',
  detail: 'Traceback (most recent call last):\n  File "~/x.py", line 1\nOSError: [Errno 22] Invalid argument',
  signature: 'OSError errno 22'
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('ErrorPanel (E14-F01)', () => {
  it('leads with the cause and lists every action', () => {
    render(<ErrorPanel error={unknown} />)
    expect(screen.getByText(/does not have an explanation/)).toBeTruthy()
    expect(screen.getByText(/Resume the job from the rail/)).toBeTruthy()
    expect(screen.getByText(/open an issue/)).toBeTruthy()
  })

  it('keeps the traceback behind a closed disclosure — never the headline', () => {
    const { container } = render(<ErrorPanel error={unknown} />)
    const details = container.querySelector('details.error-detail')
    expect(details).toBeTruthy()
    expect(details!.hasAttribute('open')).toBe(false)
    // the technical text exists for whoever opens it, with its signature
    expect(screen.getByText(/OSError: \[Errno 22\]/)).toBeTruthy()
    expect(screen.getByText(/technical details \(OSError errno 22\)/)).toBeTruthy()
  })

  it('copies stage, signature, cause and detail together', async () => {
    const writeText = vi.fn(async (_text: string) => {})
    Object.assign(navigator, { clipboard: { writeText } })
    render(<ErrorPanel error={unknown} />)
    fireEvent.click(screen.getByText('copy details'))
    expect(writeText).toHaveBeenCalledTimes(1)
    const copied = writeText.mock.calls[0][0]
    expect(copied).toContain('stage: score')
    expect(copied).toContain('signature: OSError errno 22')
    expect(copied).toContain('Invalid argument')
    expect(await screen.findByText('copied ✓')).toBeTruthy()
  })

  it('renders a legacy bare string exactly as a cause with nothing else', () => {
    const { container } = render(
      <ErrorPanel error={{ code: 'legacy', cause: 'score: something old', actions: [] }} />
    )
    expect(screen.getByText('score: something old')).toBeTruthy()
    expect(container.querySelector('.error-actions')).toBeNull()
    expect(container.querySelector('details')).toBeNull()
  })

  it('offers the docs link only when the entry carries one', () => {
    const { container, rerender } = render(<ErrorPanel error={unknown} />)
    expect(screen.queryByText(/more in the docs/)).toBeNull()
    rerender(<ErrorPanel error={{ ...unknown, docs: 'SPECIFICATION.md#20-troubleshooting' }} />)
    expect(screen.getByText(/more in the docs/)).toBeTruthy()
    expect(container.querySelectorAll('.error-cause').length).toBe(1)
  })
})
