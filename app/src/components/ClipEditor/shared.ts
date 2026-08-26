/** Constants and helpers shared by the ClipEditor's pieces. UI-only — the
 *  sidecar contract types live in src/types.ts, where api.ts can reach them. */

/** The re-render-cost knobs, surfaced here so a clip can be tuned where the
 *  result is visible instead of in the global settings panel. Ranges and help
 *  text mirror settings_schema.py; kept short deliberately — this is the
 *  "while I'm looking at the clip" subset, not the whole panel. */
export const PACING_FIELDS: { key: string; label: string; min: number; max: number; step: number; help: string }[] = [
  { key: 'min_cut_gap', label: 'shortest silence to cut', min: 0.1, max: 5, step: 0.05,
    help: 'Silences shorter than this are always kept. Lower = tighter edit.' },
  { key: 'breath_pad', label: 'breathing room', min: 0, max: 1, step: 0.05,
    help: "Kept on each side of a cut so it doesn't clip the start of words." },
  { key: 'event_protect_s', label: 'protect around reactions', min: 0, max: 6, step: 0.1,
    help: 'Pauses this close to laughter are comedic timing and never trimmed.' },
  { key: 'natural_pause_max', label: 'natural pause limit', min: 0, max: 4, step: 0.1,
    help: 'Post-sentence pauses up to this long read as normal cadence.' }
]

export const CAPTION_QUICK: { key: string; label: string; type: 'number' | 'color' | 'bool'; min?: number; max?: number; step?: number; help: string }[] = [
  { key: 'size', label: 'font size', type: 'number', min: 20, max: 200, step: 2,
    help: 'Cap height in a 1080x1920 frame.' },
  { key: 'margin_v', label: 'distance from bottom', type: 'number', min: 0, max: 1400, step: 10,
    help: 'Keep clear of platform UI — and of the letterbox bar at high gameplay framing.' },
  { key: 'max_words', label: 'words per caption', type: 'number', min: 1, max: 12, step: 1,
    help: 'Fewer words = faster turnover, more urgent feel.' },
  { key: 'active', label: 'active word', type: 'color', help: 'The karaoke highlight colour.' },
  { key: 'primary', label: 'word colour', type: 'color', help: 'Base colour of inactive words.' },
  { key: 'uppercase', label: 'uppercase', type: 'bool', help: 'Force capitals.' }
]

export const PRESETS = ['classic', 'beast', 'hormozi', 'minimal', 'karaoke-pop']
export const CAMERAS = ['cut', 'pan', 'locked']
export const ANIMS = ['none', 'pop', 'ping']

export function fmt(t: number): string {
  const m = Math.floor(t / 60)
  const s = (t % 60).toFixed(1)
  return `${m}:${s.padStart(4, '0')}`
}
