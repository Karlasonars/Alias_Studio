/* E18: the review bay with ONE output — the ranking montage. The header
 * says what it is and how long it runs (E18-F02's "the total length is
 * shown"), and the clip editor is not offered: its re-render makes a
 * standalone clip file that has nothing to do with the montage.
 */
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Review from './components/Review'
import { resetTauri } from './test/tauri'
import type { JobResults } from './types'

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('./test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})
vi.mock('@tauri-apps/api/event', async () => {
  const t = await import('./test/tauri')
  return { listen: t.listenMock }
})
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: async () => {} }))

beforeEach(() => {
  resetTauri()
})

const clip = (start: number, score: number) => ({
  start,
  end: start + 4,
  score,
  best_platform: 'tiktok',
  platform_scores: { tiktok: score },
  subscores: { hook: 7 },
  summary: 'a moment',
  adjustments: [],
  signals_fired: [],
  signals_missing: [],
  confidence: 'standard',
  music: null
})

function results(ranking: boolean): JobResults {
  const clips = [clip(12, 90), clip(6, 80), clip(0, 70)]
  const outputs = ranking
    ? [{ clip: 0, path: 'C:/j/clips/ranking.mp4', score: 90, best_platform: 'tiktok', duration: 12, words: 0, event_tags: 0, montage: true }]
    : clips.map((c, i) => ({ clip: i, path: `C:/j/clips/clip_0${i}.mp4`, score: c.score, best_platform: 'tiktok', duration: 4, words: 0, event_tags: 0 }))
  return {
    job_id: 'j',
    dir: 'C:/j',
    ingest: { title: 'A stream', heatmap: null, probe: { duration_sec: 20, width: 1280, height: 720 } },
    score: { clips, llm_mode: 'gemini', model: 'gemini-x', scored_count: 3 },
    render: {
      outputs,
      emoji_ok: true,
      caption_preset: 'classic',
      ...(ranking
        ? {
            ranking: {
              count: 3, rendered: 3, order: [2, 1, 0], title: 'TOP 3',
              segments: [], band: { top: 160, line_h: 70, boxed: false }
            }
          }
        : {})
    },
    events: null,
    candidates: null,
    camera: null
  } as unknown as JobResults
}

describe('the review bay with a ranking video (E18)', () => {
  it('names the format and its total length, and offers no clip editor', () => {
    render(<Review results={results(true)} onBack={() => {}} onRestyle={() => {}} />)
    expect(screen.getByText(/ranking video · 3 moments · 0:12/)).toBeTruthy()
    expect(screen.getByText('TOP 3')).toBeTruthy()
    expect(screen.queryByText(/EDIT CLIP/)).toBeNull()
    expect(screen.getByText('EXPORT MP4')).toBeTruthy()
  })

  it('a clip job still counts its clips and keeps the editor', () => {
    render(<Review results={results(false)} onBack={() => {}} onRestyle={() => {}} />)
    expect(screen.getByText(/3 clips/)).toBeTruthy()
    expect(screen.getByText(/EDIT CLIP/)).toBeTruthy()
  })
})
