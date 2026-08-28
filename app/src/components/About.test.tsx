/* T-18 (E16-F03): the AGPL surface. What these pin: the version on
 * screen is whatever getVersion() answers — never a literal in app/src
 * (the pytest guard holds the other half of that); the source link
 * resolves to the exact commit or tag baked into the build; a build
 * with no git identity says so instead of showing a dead link; and the
 * three one-source documents (LICENSE, VENDORED-LICENSES.md, README's
 * modification statement) actually arrive on screen. */
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { commands, resetTauri } from '../test/tauri'
import About, { modificationsSection } from './About'

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('../test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})
vi.mock('@tauri-apps/api/app', () => ({
  getVersion: async () => '9.9.9-test'
}))
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: vi.fn(async () => {}) }))

const commit = 'abcdef0123456789abcdef0123456789abcdef01'

beforeEach(() => {
  resetTauri()
  // About hosts UpdatePanel (T-16), which loads the launch-check pref.
  commands.update_checks_enabled = () => true
})

describe('About (E16-F03)', () => {
  it('shows the runtime version and links the exact commit of the build', async () => {
    const { container } = render(
      <About build={{ commit, tag: '', dirty: false }} />
    )
    // the version is the API's answer — a value no source file contains,
    // so a hardcoded version could never pass this
    await screen.findByText(/version 9\.9\.9-test/)
    expect(container.textContent).toContain('commit abcdef012345')
    const link = screen.getByTitle(
      `https://github.com/Karlasonars/Alias_Studio/tree/${commit}`
    )
    expect(link.textContent).toContain('exactly this build')
  })

  it('prefers the release page when the build is a tagged release', async () => {
    render(<About build={{ commit, tag: 'v9.9.9', dirty: false }} />)
    await screen.findByText(/version 9\.9\.9-test/)
    expect(
      screen.getByTitle('https://github.com/Karlasonars/Alias_Studio/releases/tag/v9.9.9')
    ).toBeTruthy()
  })

  it('admits a local build with no recorded commit instead of linking nowhere', async () => {
    const { container } = render(<About build={{ commit: '', tag: '', dirty: false }} />)
    await screen.findByText(/version 9\.9\.9-test/)
    expect(container.textContent).toContain('no commit recorded')
    expect(container.textContent).toContain('the source tree it was built from')
    expect(container.querySelector('[title*="/tree/"]')).toBeNull()
  })

  it('carries the licence, the attributions and the modification statement', () => {
    const { container } = render(
      <About build={{ commit, tag: '', dirty: false }} />
    )
    const text = container.textContent ?? ''
    // LICENSE itself, not a summary
    expect(text).toContain('GNU AFFERO GENERAL PUBLIC LICENSE')
    expect(text).toContain('Version 3, 19 November 2007')
    // VENDORED-LICENSES.md itself — one row proves the tables render
    expect(text).toContain('clip-forge')
    expect(text).toContain('Vendored code provenance')
    // README's "What this build adds" — AGPL's modification statement.
    // An empty extraction (renamed heading) must fail loudly here.
    expect(modificationsSection().length).toBeGreaterThan(200)
    expect(text).toContain('What this build adds')
    // upstream is named
    expect(text).toContain('publikclip')
  })
})
