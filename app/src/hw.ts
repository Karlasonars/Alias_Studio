import type { HardwareProfile } from './types'

/* One place turns the measured ratio into the number both screens show —
 * onboarding and studio must never disagree about the same estimate. */

/** PUBLIKCLIP_DEVICE is live in the shell's environment but the measured
 *  summary was probed without it: everything measured belongs to the other
 *  configuration. The profile file only learns about forcing at the next
 *  job-end probe, which is exactly how a forced-CPU session kept showing
 *  the GPU's numbers (test-day F3). */
function envForcingUnmeasured(p: HardwareProfile): boolean {
  return p.env_forced != null && p.env_forced !== p.summary?.forced
}

/** Minutes for a 60-minute source, or null when no honest estimate exists
 *  under the current configuration — no invented numbers (§5.9). A live
 *  env forcing the summary was not measured under voids the estimate:
 *  T-10's rule — a speed measured on the GPU is never promised on the
 *  CPU path. */
export function sixtyMinEstimate(p: HardwareProfile | null): number | null {
  if (!p || p.estimate_ratio == null || envForcingUnmeasured(p)) return null
  return Math.max(1, Math.round(60 * p.estimate_ratio))
}

/** "RTX 4070 · 12 GB", or "No GPU — CPU only" — with the forced device
 *  named when PUBLIKCLIP_DEVICE is set, so forcing is never invisible. */
export function hardwareLabel(p: HardwareProfile | null): string | null {
  if (!p) return null
  if (envForcingUnmeasured(p)) {
    // Withhold the measured hardware line entirely: it is the thing that
    // misled — a GPU name on screen while every model runs on the CPU.
    return `forced ${p.env_forced!.toUpperCase()} (PUBLIKCLIP_DEVICE) — measured profile does not apply`
  }
  if (!p.summary) return null
  const s = p.summary
  const base = s.gpu
    ? `${s.gpu}${s.vram_gb ? ` · ${s.vram_gb} GB` : ''}`
    : 'No GPU — CPU only'
  return s.forced ? `${base} · forced ${s.forced.toUpperCase()} (PUBLIKCLIP_DEVICE)` : base
}
