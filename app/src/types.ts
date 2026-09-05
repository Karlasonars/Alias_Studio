/** T-13 (E14-F01): a failure as a value, not a string. Produced only by
 *  errors.describe() in Python — every field arrives redacted. `error` on
 *  the result event stays the flat cause string, so a producer that
 *  predates this shape (or an old job's DB row) still renders. */
export interface ErrorInfo {
  /** stable catalogue id, e.g. "gemini-key-rejected"; "unknown" is honest */
  code: string
  /** human-language cause — never a repr, never a traceback */
  cause: string
  /** at least one concrete step; may be empty only for legacy strings */
  actions: string[]
  /** repo-relative docs anchor, e.g. "SPECIFICATION.md#20-troubleshooting" */
  docs?: string | null
  stage?: string | null
  /** technical text (stderr tail / traceback), behind the disclosure */
  detail?: string | null
  /** exception class + errno — groups recurrences without claiming a cause */
  signature?: string | null
}

/** T-14 (E14-F02): one row of `jobs resume-info` — the resume picker's data.
 *  status is disk truth ('done' = the checkpoint exists), except 'failed',
 *  which comes from T-13's error.json. estimate_sec is the measured cost of
 *  re-running from this stage THROUGH THE END on this machine (T-10's
 *  medians × this job's duration); null whenever any stage in that tail has
 *  no measurement under the current hardware key — never an invented number. */
export interface ResumeStageInfo {
  name: string
  status: 'done' | 'failed' | 'missing'
  estimate_sec: number | null
}

export interface ResumeInfo {
  stages: ResumeStageInfo[]
  /** the failed stage to preselect; null for a job that did not fail */
  default_stage: string | null
  duration_sec: number | null
}

export interface PipelineEvent {
  event: string
  stage?: string
  fraction?: number
  message?: string
  job_id?: string
  ok?: boolean
  error?: string
  error_info?: ErrorInfo
  stderr?: string
  /** E1-F07 'disk' events only: 'warn' means the job starts anyway with
   *  `message` on screen; 'block' means the run fails before anything is
   *  written (its result event carries the same message as `error`). */
  action?: 'warn' | 'block'
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

/** E19-F02: `settings watermark-import` — the picked PNG copied into the
 *  app's own folder; `path` is what the job stores, never the picked one. */
export interface WatermarkImportResult {
  ok: boolean
  error?: string
  path?: string
  name?: string
  bytes?: number
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
  /** E18: this entry is a whole ranking video, not one clip's file. Its
   * `clip` is the rank-1 index so the audit panel shows the winning moment;
   * `ranks` is the global rank range it plays (1–5, then 6–10). */
  montage?: boolean
  ranks?: [number, number]
}

/** E18: one ranking video, as the render recorded it. */
export interface RankingMontage {
  path: string
  ranks: [number, number]
  rendered: number
  order: number[]
  title: string
  segments: { clip: number; rank: number; offset: number; duration: number }[]
}

/** E18: what a ranking render recorded about itself. Present on render.json
 * only when the job rendered in ranking mode. Since D-18 the clips are in
 * `outputs` as always, first; the montage entries follow them. */
export interface RankingSummary {
  count: number
  band: { top: number; line_h: number; boxed: boolean }
  montages: RankingMontage[]
  /** Why there is one video and not two, when that is the case. */
  note?: string | null
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
  render: {
    outputs: RenderOutput[]
    emoji_ok: boolean
    caption_preset: string
    // Clips a restyle deliberately left alone: their editor version has cuts
    // or bounds the whole-job render cannot reproduce.
    kept_from_editor?: number[]
    ranking?: RankingSummary
  } | null
  events: {
    counts: Record<string, number>
    timeline: unknown[]
    arousal_source: string
    /** T-38: why the DSP fallback ran, when it did. Absent on checkpoints
     * written before the field existed; null when SER ran. */
    arousal_fallback_reason?: string | null
  } | null
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
  cancelled: boolean
}

export interface QueueJob {
  id: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
  error: string | null
  title: string | null
  source: string
  created_at: number
  stages_done: number
}

export interface QueueStateResult {
  jobs: QueueJob[]
  paused: boolean
  active_job_id: string | null
  /** false while Rust's cache is still cold — render "loading", not "empty" */
  ready: boolean
}

export interface SetupState {
  has_gemini_key: boolean
  onboarded: boolean
}

/* ---------- E1-F01 setup downloads ---------- */

/** One entry of `publikclip setup status`: presence is derived from disk
 *  on every ask, never remembered — that is the whole resume story. */
export interface SetupItemStatus {
  id: string
  label: string
  /** expected download size; null = depends on the machine (ffmpeg) */
  bytes: number | null
  present: boolean
}

export interface SetupStatusResult {
  items: SetupItemStatus[]
  /** what E1-F01 shows BEFORE any download starts */
  total_missing_bytes: number
}

/** T-40: what the shell can say about the Python environment BEFORE python
 *  exists — packaged first launches must download it (~3.86 GB measured),
 *  and every number here is served by Rust because nothing else can run. */
export interface BootstrapStatus {
  ready: boolean
  /** compressed download for a cold bootstrap */
  env_download_bytes: number
  /** physical free space the bootstrap needs */
  env_disk_bytes: number
  /** the first-run models, approximate — itemized by setup once python runs */
  models_approx_bytes: number
  /** free bytes on the home volume; null = unreadable (§5.9: warn, never wall) */
  free_bytes: number | null
}

/** Tauri channel: bootstrap-event. 'progress' carries real bytes that
 *  appeared on disk (T-11's disk-truth rule — uv's output is not parsed). */
export interface BootstrapEvent {
  event: 'progress' | 'result'
  bytes?: number
  fraction?: number
  ok?: boolean
  stderr?: string
}

/** One line of the `setup run` JSONL stream (Tauri channel: setup-event).
 *  'item' rows carry per-download state; 'result' ends a run; 'exited' is
 *  the process dying unexpectedly; 'interrupted' is the shell killing
 *  setup because a job started (whose lazy fetches resume the partials). */
export interface SetupEvent {
  event: 'item' | 'result' | 'exited' | 'interrupted'
  item?: string
  state?: 'downloading' | 'done' | 'failed'
  /** -1 = indeterminate (a fetch with no honest fraction) */
  fraction?: number
  message?: string
  error?: string
  cached?: boolean
  ok?: boolean
  failures?: { item: string; error: string }[]
  code?: number | null
  stderr?: string
  by?: string
}

/** hardware_profile.json, written by python (job end + `hardware` verb),
 *  read by the shell as a plain file — never probed per view (T-10). */
export interface HardwareSummary {
  torch_device: string
  gpu: string
  vram_gb: number
  whisper_device: string
  whisper_compute: string
  onnx_providers: string[]
  cpu_threads: number
  forced: string | null
}

export interface HardwareProfile {
  /** absent when the shell built the object only to carry env_forced —
   *  a forced device with no profile file yet must still be visible */
  summary?: HardwareSummary | null
  key?: string
  /** processing seconds per source second under the CURRENT key; null
   *  until every stage has a measurement under it — honest, not blank */
  estimate_ratio?: number | null
  estimate_jobs?: number
  /** PUBLIKCLIP_DEVICE as the SHELL sees it right now — what the sidecar
   *  will inherit. The file's summary.forced lags until a job-end probe,
   *  which is how a forced session kept showing GPU numbers (F3/T-10). */
  env_forced?: 'cpu' | 'cuda'
}

/** save_gemini_key verifies with one cheap call before accepting (E1-F02).
 *  "rejected" means Google refused the key and nothing was written;
 *  "unverified" means the check itself was impossible (offline) — the key
 *  is saved and the gate must not become a wall (§5.9). */
export interface SaveKeyResult {
  status: 'verified' | 'unverified' | 'rejected'
  /** on rejection, Google's reason token (API_KEY_INVALID, SERVICE_DISABLED,
   *  …) — a 403 is not one thing, and the message must name the real next
   *  step rather than call a valid-but-unenabled key a typo */
  reason?: string | null
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

/* ---------- clip editor (edit_tool context / save_clip_edits) ---------- */

export interface Word { word: string; start: number; end: number; speaker?: number }
export interface Cut { start: number; end: number; kept: boolean; reason: string }
export interface OverlayItem {
  id: string; query: string; source: string; image_path: string
  start: number; end: number; x: number; y: number; scale: number
  animation: string; phrase: string
}
export interface EditState {
  start: number; end: number
  caption_preset: string | null; camera_mode: string | null
  gameplay_amount: number | null
  title: string
  title_variants: { text: string; style: string; why: string; chars: number }[]
  description: string
  description_meta: Record<string, unknown>
  /** E19-F01: the variant marked to burn into the clip, for its whole
   *  length; '' burns nothing. Separate from `title` (publishing copy),
   *  which never reaches the pixels. */
  burned_title: string
  remove_dead_space: boolean; disabled_cuts: number[]
  overlays: OverlayItem[]
  // Per-clip overrides of the re-render-cost settings. Partial patches:
  // anything absent inherits the job's value.
  pacing: Record<string, number>
  caption_overrides: Record<string, string | number | boolean>
  lufs_target: number | null
  true_peak_db: number | null
  letterbox_fill: string | null
}
export interface EditContext {
  ok: boolean
  window: { start: number; end: number }
  media_path: string
  probe: { width: number; height: number }
  trajectory: { fps: number; frames: number[][] } | null
  edit: EditState
  words: Word[]
  rms: number[]
  rms_grid: number
  events: { type: string; start: number; end: number }[]
  auto_cuts: Cut[]
  run_caption_preset: string
  // The job's values behind the per-clip overrides, so the editor can show
  // what "inherit" currently resolves to instead of a blank control.
  pacing: Record<string, number>
  caption_style: Record<string, string | number | boolean>
  audio: { lufs_target: number; true_peak_db: number }
  letterbox_fill: string
}
