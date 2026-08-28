import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import type {
  BootstrapStatus,
  CaptionPreset,
  DescriptionResult,
  EditContext,
  EditState,
  HardwareProfile,
  HookResult,
  JobResults,
  JobSummary,
  LoopOverview,
  QueueStateResult,
  ResumeInfo,
  SaveKeyResult,
  SettingsPayload,
  SetupState,
  SetupStatusResult,
  SyncSummary,
  TitlesResult
} from './types'

export const api = {
  enqueueJob: (source: string, llm: string, captions: string, gameplayAmount: number) =>
    invoke<string>('enqueue_job', { source, llm, captions, gameplayAmount }),
  startQueue: () => invoke<void>('start_queue'),
  setQueuePaused: (paused: boolean) => invoke<void>('set_queue_paused', { paused }),
  queueState: () => invoke<QueueStateResult>('queue_state'),
  cancelPendingJob: (jobId: string) =>
    invoke<{ marked: boolean }>('cancel_pending_job', { jobId }),
  resumeJob: (
    jobId: string,
    llm?: string,
    captions?: string,
    camera?: string,
    gameplayAmount?: number,
    fromStage?: string
  ) => invoke<void>('resume_job', { jobId, llm, captions, camera, gameplayAmount, fromStage }),
  resumeInfo: (jobId: string) => invoke<ResumeInfo>('resume_info', { jobId }),
  // T-15: builds the redacted bundle and lands it in Downloads; resolves to
  // the destination path. No network anywhere behind this.
  diagnoseJob: (jobId: string) => invoke<string>('diagnose_job', { jobId }),
  cancelJob: () => invoke<void>('cancel_job'),
  jobResults: (jobId: string) => invoke<JobResults>('job_results', { jobId }),
  listJobs: () => invoke<JobSummary[]>('list_job_dirs'),
  saveGeminiKey: (key: string) => invoke<SaveKeyResult>('save_gemini_key', { key }),
  setupState: () => invoke<SetupState>('get_setup_state'),
  setupStatus: () => invoke<SetupStatusResult>('setup_status'),
  runSetup: () => invoke<void>('run_setup'),
  // T-40: the pre-python surface. bootstrapStatus is instant, Rust-only
  // disk truth; runBootstrap is the visible `uv sync` (progress on the
  // bootstrap-event channel). Callers must not fire setupStatus — a python
  // one-shot that silently triggers the whole download — until
  // bootstrapStatus says ready.
  bootstrapStatus: () => invoke<BootstrapStatus>('bootstrap_status'),
  runBootstrap: () => invoke<void>('run_bootstrap'),
  hardwareProfile: () => invoke<HardwareProfile | null>('get_hardware_profile'),
  probeHardware: () => invoke<HardwareProfile>('probe_hardware'),
  markOnboarded: () => invoke<void>('mark_onboarded'),
  // T-16: the launch update-check preference — a PUBLIKCLIP_HOME marker
  // owned by the shell, on by default, switchable in Settings → About.
  updateChecksEnabled: () => invoke<boolean>('update_checks_enabled'),
  setUpdateChecks: (enabled: boolean) => invoke<void>('set_update_checks', { enabled }),
  checkOllama: () => invoke<{ running: boolean; models: string[] }>('check_ollama'),
  exportClip: (path: string, title?: string) =>
    invoke<string>('export_clip', { path, title }),
  igStatus: () => invoke<{ connected: boolean; username?: string }>('ig_status'),
  igSync: () => invoke<SyncSummary>('ig_tool', { args: ['sync'] }),
  igOverview: () => invoke<LoopOverview>('ig_tool', { args: ['overview'] }),
  igLink: (jobId: string, clip: number, mediaId: string, source: 'manual' | 'match_confirmed') =>
    invoke<{ ok: boolean }>('ig_tool', {
      args: ['link', jobId, String(clip), mediaId, '--source', source]
    }),
  igUnlink: (mediaId: string) =>
    invoke<{ ok: boolean }>('ig_tool', { args: ['unlink', mediaId] }),
  igReject: (mediaId: string, jobId: string, clip: number) =>
    invoke<{ ok: boolean }>('ig_tool', { args: ['reject', mediaId, jobId, String(clip)] }),
  fileUrl: (path: string) => convertFileSrc(path),

  /* ---------- copywriting ---------- */
  clipTitles: (jobId: string, clip: number) =>
    invoke<TitlesResult>('edit_tool', { args: ['titles', jobId, String(clip)] }),
  clipDescription: (jobId: string, clip: number) =>
    invoke<DescriptionResult>('edit_tool', { args: ['description', jobId, String(clip)] }),
  clipHook: (jobId: string, clip: number) =>
    invoke<HookResult>('edit_tool', { args: ['hook', jobId, String(clip)] }),

  /* ---------- clip editor ---------- */
  editContext: (jobId: string, clip: number) =>
    invoke<EditContext>('edit_tool', { args: ['context', jobId, String(clip)] }),
  // One wrapper, three intents at the call sites: persist(), and the
  // pre-flight saves before render and before suggest-visuals.
  saveClipEdits: (jobId: string, clip: number, edit: EditState) =>
    invoke<void>('save_clip_edits', { jobId, edits: { [String(clip)]: edit } }),
  runEditRender: (jobId: string, clip: number) =>
    invoke<void>('run_edit_render', { jobId, clip }),
  suggestVisuals: (jobId: string, clip: number, prefer: string) =>
    invoke<{ ok: boolean; edit?: EditState; error?: string }>('edit_tool', {
      args: ['suggest-visuals', jobId, String(clip), '--prefer', prefer]
    }),

  /* ---------- settings ---------- */
  settingsGet: () => invoke<SettingsPayload>('settings_tool', { args: ['get'] }),
  settingsSet: (settings: Record<string, unknown>) =>
    invoke<SettingsPayload>('settings_tool', { args: ['set', JSON.stringify(settings)] }),
  settingsReset: () => invoke<SettingsPayload>('settings_tool', { args: ['reset'] }),
  presetSave: (name: string, patch: CaptionPreset) =>
    invoke<SettingsPayload>('settings_tool', {
      args: ['preset-save', name, JSON.stringify(patch)]
    }),
  presetReset: (name: string) =>
    invoke<SettingsPayload>('settings_tool', { args: ['preset-reset', name] })
}
