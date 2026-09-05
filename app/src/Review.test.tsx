/* E18: the review bay of a ranking job. Since D-18 its outputs are the
 * clips, as always, followed by the ranking videos: the header counts
 * both, a montage card names its video and rank range, the clips keep the
 * editor (E18-F05), and a montage does not offer it — its re-render makes
 * a standalone clip file that has nothing to do with the montage.
 */
import { fireEvent, render, screen } from '@testing-library/react'
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
  const clipOutputs = clips.map((c, i) => ({
    clip: i, path: `C:/j/clips/clip_0${i}.mp4`, score: c.score, best_platform: 'tiktok', duration: 4, words: 0, event_tags: 0
  }))
  const montage = {
    clip: 0, path: 'C:/j/clips/ranking_1-3.mp4', score: 90, best_platform: 'tiktok', duration: 12, words: 0, event_tags: 0,
    montage: true, ranks: [1, 3] as [number, number]
  }
  return {
    job_id: 'j',
    dir: 'C:/j',
    ingest: { title: 'A stream', heatmap: null, probe: { duration_sec: 20, width: 1280, height: 720 } },
    score: { clips, llm_mode: 'gemini', model: 'gemini-x', scored_count: 3 },
    render: {
      // D-18: the clips first, as always; the ranking video after them
      outputs: ranking ? [...clipOutputs, montage] : clipOutputs,
      emoji_ok: true,
      caption_preset: 'classic',
      ...(ranking
        ? {
            ranking: {
              count: 3,
              band: { top: 160, line_h: 70, boxed: false },
              montages: [
                { path: montage.path, ranks: [1, 3], rendered: 3, order: [2, 1, 0], title: 'TOP 3', segments: [] }
              ],
              note: 'The second ranking video needs 6 finalists with a camera pass; this job has 3, so one ranking video was made.'
            }
          }
        : {})
    },
    events: null,
    candidates: null,
    camera: null
  } as unknown as JobResults
}

describe('the review bay with ranking videos (E18, D-18)', () => {
  it('counts the clips and the ranking videos, and says why there is one', () => {
    render(<Review results={results(true)} onBack={() => {}} onRestyle={() => {}} />)
    expect(screen.getByText(/3 clips · 1 ranking video/)).toBeTruthy()
    expect(screen.getByText(/needs 6 finalists/)).toBeTruthy()
    expect(screen.getByText('TOP 3 · 1–3')).toBeTruthy()
  })

  it('the clips keep the editor; the ranking video does not offer it', () => {
    render(<Review results={results(true)} onBack={() => {}} onRestyle={() => {}} />)
    // clip 0 is the first card and selected by default: a clip, so the
    // editor is there (E18-F05)
    expect(screen.getByText(/EDIT CLIP/)).toBeTruthy()
    fireEvent.click(screen.getByText('TOP 3 · 1–3'))
    expect(screen.queryByText(/EDIT CLIP/)).toBeNull()
    expect(screen.getByText('EXPORT MP4')).toBeTruthy()
  })

  it('a clip job still counts its clips and keeps the editor', () => {
    render(<Review results={results(false)} onBack={() => {}} onRestyle={() => {}} />)
    expect(screen.getByText(/3 clips/)).toBeTruthy()
    expect(screen.queryByText(/ranking video/)).toBeNull()
    expect(screen.getByText(/EDIT CLIP/)).toBeTruthy()
  })
})
