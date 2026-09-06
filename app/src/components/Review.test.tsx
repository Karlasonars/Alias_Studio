/* T-38: the DSP-arousal degradation must be visible where a user looks.
 * rubric.py has recorded `ser_model (dsp proxy used)` in every score's
 * missing list since day one, and this panel rendered it as an unlabeled
 * chip nobody could read as "your shock scores ran on a fallback signal".
 * Pinned here: the header says it in words, the chip gets a human label,
 * and a job whose arousal came from SER shows neither. */
import { fireEvent, render, screen } from '@testing-library/react'
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

/* E20 (D-20): a story job's render.json holds one story entry under the
 * clips render's name. The review must show it as a story — its title, no
 * score, no clip editor, a captions-only restyle — not as a clip with a
 * NaN score and an audit for a clip that does not exist. */
function storyResults(): JobResults {
  return {
    job_id: 'job-story',
    dir: 'C:/jobs/job-story',
    ingest: { title: 'parkour', heatmap: null, probe: { duration_sec: 12, width: 1920, height: 1080 } },
    narrate: {
      title: 'The chair',
      duration_sec: 41.2,
      title_end_sec: 1.4,
      word_count: 120,
      settings_used: { voice: 'bm_george', speed: 1.1 }
    },
    score: null,
    render: {
      outputs: [
        {
          clip: 0,
          story: true,
          title: 'The chair',
          path: 'C:/jobs/job-story/clips/story.mp4',
          score: 0,
          best_platform: '',
          duration: 41.8,
          words: 118,
          event_tags: 0
        }
      ],
      emoji_ok: true,
      caption_preset: 'story'
    },
    events: null,
    candidates: null,
    camera: null
  }
}

describe('Review — a story job (E20)', () => {
  it('shows the story by its title, without a score, an editor or a camera restyle', () => {
    const onRestyle = vi.fn()
    render(<Review results={storyResults()} onBack={() => {}} onRestyle={onRestyle} />)
    expect(screen.getByText('The chair', { selector: 'h1' })).toBeTruthy()
    expect(screen.getByText(/narrated by bm_george at 1.1×/)).toBeTruthy()
    expect(screen.getByText('STORY')).toBeTruthy()
    expect(document.body.textContent).not.toContain('NaN')
    expect(screen.queryByText(/EDIT CLIP/)).toBeNull()
    expect(screen.queryByText('camera')).toBeNull()
    expect(screen.getByText('EXPORT MP4')).toBeTruthy()
    // a restyle carries the captions alone
    fireEvent.click(screen.getByText('beast'))
    fireEvent.click(screen.getByText('RESTYLE + RE-RENDER'))
    expect(onRestyle).toHaveBeenCalledWith('beast')
  })
})
