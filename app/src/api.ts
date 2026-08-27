import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import type {
  CaptionPreset,
  DescriptionResult,
  EditContext,
  EditState,
  HookResult,
  JobResults,
  JobSummary,
  LoopOverview,
  SettingsPayload,
  SetupState,
  SyncSummary,
  TitlesResult
} from './types'

export const api = {
  runJob: (source: string, llm: string, captions: string, gameplayAmount: number) =>
    invoke<void>('run_job', { source, llm, captions, gameplayAmount }),
  resumeJob: (
    jobId: string,
    llm?: string,
    captions?: string,
    camera?: string,
    gameplayAmount?: number
  ) => invoke<void>('resume_job', { jobId, llm, captions, camera, gameplayAmount }),
  cancelJob: () => invoke<void>('cancel_job'),
  jobResults: (jobId: string) => invoke<JobResults>('job_results', { jobId }),
  listJobs: () => invoke<JobSummary[]>('list_job_dirs'),
  saveGeminiKey: (key: string) => invoke<boolean>('save_gemini_key', { key }),
  setupState: () => invoke<SetupState>('get_setup_state'),
  markOnboarded: () => invoke<void>('mark_onboarded'),
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
