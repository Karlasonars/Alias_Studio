import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import type {
  CaptionPreset,
  DescriptionResult,
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
