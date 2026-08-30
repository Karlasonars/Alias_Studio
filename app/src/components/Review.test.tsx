/* T-38: the DSP-arousal degradation must be visible where a user looks.
 * rubric.py has recorded `ser_model (dsp proxy used)` in every score's
 * missing list since day one, and this panel rendered it as an unlabeled
 * chip nobody could read as "your shock scores ran on a fallback signal".
 * Pinned here: the header says it in words, the chip gets a human label,
 * and a job whose arousal came from SER shows neither. */
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Clip, JobResults, RenderOutput } from '../types'
import { resetTauri } from '../test/tauri'
import Review from './Review'

vi.mock('@tauri-apps/api/core', async () => {
  const t = await import('../test/tauri')
  return { invoke: t.invokeMock, convertFileSrc: (p: string) => p }
})
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: vi.fn(async () => {}) }))

const clip: Clip = {
  start: 12,
  end: 42,
  score: 72,
  best_platform: 'tiktok',
  platform_scores: { tiktok: 72 },
  subscores: { hook: 6.5, shock: 2.4 },
  adjustments: [],
  signals_fired: ['laughter'],
  signals_missing: ['ser_model (dsp proxy used)'],
  confidence: 'medium',
  summary: 'a decent moment',
  arousal_pct: 0.35,
  heatmap_pct: null,
  curve_score: 0.5,
  music: null
}

const output: RenderOutput = {
  clip: 0,
  path: 'C:/jobs/job-1/clip0.mp4',
  score: 72,
  best_platform: 'tiktok',
  duration: 30,
  words: 80,
  event_tags: 2
}

function results(arousalSource: string, signalsMissing: string[]): JobResults {
  return {
    job_id: 'job-1',
    dir: 'C:/jobs/job-1',
    ingest: {
      title: 'Episode 12',
      heatmap: null,
      probe: { duration_sec: 100, width: 1920, height: 1080 }
    },
    score: {
      clips: [{ ...clip, signals_missing: signalsMissing }],
      llm_mode: 'gemini',
      model: 'gemini-3.6-flash',
      scored_count: 1
    },
    render: { outputs: [output], emoji_ok: true, caption_preset: 'classic' },
    events: { counts: {}, timeline: [], arousal_source: arousalSource },
    candidates: { count: 1, effective_weights: {}, heatmap_present: false },
    camera: null
  }
}

beforeEach(() => {
  vi.restoreAllMocks()
  resetTauri()
})

describe('Review — the T-38 fallback disclosure', () => {
  it('says in the header that shock ran on fallback arousal', () => {
    render(
      <Review
        results={results('dsp-proxy', ['ser_model (dsp proxy used)'])}
        onBack={() => {}}
        onRestyle={() => {}}
      />
    )
    expect(screen.getByText(/shock scored on fallback arousal/)).toBeTruthy()
  })

  it('labels the missing-signal chip in words, not the raw audit string', () => {
    render(
      <Review
        results={results('dsp-proxy', ['ser_model (dsp proxy used)'])}
        onBack={() => {}}
        onRestyle={() => {}}
      />
    )
    expect(screen.getByText('arousal model (DSP fallback used)')).toBeTruthy()
    expect(screen.queryByText('ser_model (dsp proxy used)')).toBeNull()
  })

  it('shows neither when arousal came from the real model', () => {
    render(
      <Review results={results('ser', [])} onBack={() => {}} onRestyle={() => {}} />
    )
    expect(screen.queryByText(/fallback arousal/)).toBeNull()
    expect(screen.queryByText(/DSP fallback/)).toBeNull()
  })
})
