export interface PipelineEvent {
  event: string
  stage?: string
  fraction?: number
  message?: string
  job_id?: string
  ok?: boolean
  error?: string
  stderr?: string
  [key: string]: unknown
}

export interface LogLine {
  id: number
  time: string
  text: string
}

/* ---------- copywriting ---------- */

export interface TitleVariant {
  text: string
  style: string
  why: string
  grounded_in: string
  chars: number
  rejected_because?: string
}

export interface TitlesResult {
  ok: boolean
  error?: string
  titles: TitleVariant[]
  rejected: TitleVariant[]
}

export interface DescriptionResult {
  ok: boolean
  error?: string
  /** the caption body, without hashtags */
  description: string
  hashtags: string[]
  /** description + hashtags, ready to paste — what the copy button uses */
  full: string
  grounded_in: string
  /** what the filter changed after the model answered (trimmed, emoji removed…) */
  warnings: string[]
  chars: number
}

export interface HookCandidate {
  start: number
  hook_type: string
  strength: number
  why: string
  risk: string
}

export interface HookResult {
  ok: boolean
  error?: string
  candidates: HookCandidate[]
  text_hook: string
  current_start: number
  current_strength: number | null
  improves?: boolean
  note?: string
}

/* ---------- settings ---------- */

export interface SettingsField {
  key: string
  label: string
  type: 'number' | 'bool' | 'select' | 'color' | 'text' | 'multiselect'
  help: string
  min?: number
  max?: number
  step?: number
  unit?: string
  options?: { value: string; label: string }[]
  options_from?: 'presets' | 'fonts'
}

export interface SettingsMatrix {
  key: string
  label: string
  help: string
  columns: string[]
  column_help: Record<string, string>
  min: number
  max: number
  step: number
}

export interface SettingsGroup {
  key: string
  label: string
  help: string
  cost: 'cheap' | 'moderate' | 'high'
  cost_note: string
  fields: SettingsField[]
  matrix?: SettingsMatrix
}

export type CaptionPreset = Record<string, string | number | boolean>

export interface SettingsPayload {
  ok: boolean
  error?: string
  defaults: Record<string, unknown>
  factory: Record<string, unknown>
  schema: {
    groups: SettingsGroup[]
    caption_fields: SettingsField[]
    fonts: string[]
    builtin_presets: Record<string, CaptionPreset>
  }
  presets: Record<string, CaptionPreset>
  preset_names: string[]
  edited_presets: string[]
}

export interface Adjustment {
  rule: string
  factor: number
  reason: string
}

export interface MusicBrief {
  genre: string
  instruments: string[]
  mood: string
  theme: string
  energy: string
  bpm_range: string
  duck_intensity: string
  mood_prior?: string
  alternatives: { genre: string; mood: string; bpm_range: string }[]
}

export interface Clip {
  start: number
  end: number
  score: number
  best_platform: string
  platform_scores: Record<string, number>
  subscores: Record<string, number>
  adjustments: Adjustment[]
  signals_fired: string[]
  signals_missing: string[]
  confidence: string
  summary: string
  arousal_pct: number
  heatmap_pct: number | null
  curve_score: number
  music: MusicBrief | null
  t1_raw?: Record<string, unknown>
}

export interface RenderOutput {
  clip: number
  path: string
  score: number
  best_platform: string
  duration: number
  words: number
  event_tags: number
}

export interface JobResults {
  job_id: string
  dir: string
  ingest: {
    title: string
    heatmap: unknown[] | null
    probe: { duration_sec: number; width: number; height: number }
  } | null
  score: { clips: Clip[]; llm_mode: string; model: string; scored_count: number } | null
  render: { outputs: RenderOutput[]; emoji_ok: boolean; caption_preset: string } | null
  events: { counts: Record<string, number>; timeline: unknown[]; arousal_source: string } | null
  candidates: { count: number; effective_weights: Record<string, number>; heatmap_present: boolean } | null
  camera: {
    trajectories: Record<string, string>
    stats: { clip: number; tracks: number; switch_cuts: number; shot_cuts: number; punches: number }[]
    camera_settings: {
      speaker_change: string
      pan_duration_s: number
      deadzone_frac: number
      punch_in: boolean
      punch_in_sensitivity: number
      zoom_lock_per_scene: boolean
      gameplay_amount: number
    }
  } | null
}

export interface JobSummary {
  id: string
  title: string | null
  ingested: boolean
  rendered: boolean
}

export interface SetupState {
  has_gemini_key: boolean
  onboarded: boolean
}

/* ---------- the Instagram loop ---------- */

export interface LoopMetrics {
  views?: number | null
  reach?: number | null
  likes?: number | null
  comments?: number | null
  saved?: number | null
  shares?: number | null
  reposts?: number | null
  total_interactions?: number | null
  ig_reels_avg_watch_time?: number | null
  ig_reels_video_view_total_time?: number | null
  reels_skip_rate?: number | null
}

export interface LoopLinked {
  job_id: string
  clip_index: number
  media_id: string | null
  link_source: string
  linked_at: number
  score: number
  reels_score: number
  config_version: number
  subscores: Record<string, number> | null
  adjustments: Adjustment[] | null
  signals_fired: string[] | null
  signals_missing: string[] | null
  summary: string
  clip_duration: number | null
  clip_thumb: string | null
  ig_thumb: string | null
  permalink: string | null
  caption: string | null
  posted_at: number | null
  media_deleted: boolean
  media_age_hours: number | null
  settling: boolean
  metrics: LoopMetrics | null
  snapshots: { age_hours: number | null; views: number | null }[]
  snapshot_count: number
}

export interface LoopSuggestion {
  media_id: string
  job_id: string
  clip_index: number
  confidence: number
  clip_summary: string
  clip_duration: number | null
  clip_thumb: string | null
  clip_reels_score: number | null
}

export interface LoopUnlinked {
  media_id: string
  thumb: string | null
  permalink: string | null
  caption: string
  posted_at: number | null
  duration_s: number | null
  copyright_flagged: boolean
  suggestion: LoopSuggestion | null
}

export interface LoopClip {
  job_id: string
  clip_index: number
  summary: string
  duration: number | null
  reels_score: number | null
  thumb: string | null
  linked: boolean
}

export interface CalibrationVersion {
  version: number
  constants: Record<string, number>
  fitted_from_n?: number | null
  spearman_rho?: number | null
  pairwise_acc?: number | null
  note?: string | null
  created_at?: number | null
}

export interface LoopReport {
  pairs: number
  ready: boolean
  note?: string
  spearman_rho?: number | null
  pairwise_accuracy?: number | null
  kendall_tau?: number | null
}

export interface LoopOverview {
  connected: boolean
  username: string | null
  last_synced_at: number | null
  linked: LoopLinked[]
  unlinked: LoopUnlinked[]
  clip_library: LoopClip[]
  report: LoopReport
  calibration: {
    active: CalibrationVersion
    history: CalibrationVersion[]
    qualifying_outcomes: number
    recomputable_outcomes: number
    threshold: number
  }
}

export interface SyncSummary {
  ok: boolean
  error?: string
  username?: string
  new_media?: number
  thumbs_cached?: number
  snapshots_pulled?: number
  tombstoned?: number
  fit?: { applied: boolean; version?: number; reason?: string }
}
