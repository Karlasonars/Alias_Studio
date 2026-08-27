import type { HardwareProfile } from './types'

/* One place turns the measured ratio into the number both screens show —
 * onboarding and studio must never disagree about the same estimate. */

/** Minutes for a 60-minute source, or null when no honest estimate exists
 *  under the current configuration — no invented numbers (§5.9). */
export function sixtyMinEstimate(p: HardwareProfile | null): number | null {
  if (!p || p.estimate_ratio == null) return null
  return Math.max(1, Math.round(60 * p.estimate_ratio))
}

/** "RTX 4070 · 12 GB", or "No GPU — CPU only" — with the forced device
 *  named when PUBLIKCLIP_DEVICE is set, so forcing is never invisible. */
export function hardwareLabel(p: HardwareProfile | null): string | null {
  if (!p || !p.summary) return null
  const s = p.summary
  const base = s.gpu
    ? `${s.gpu}${s.vram_gb ? ` · ${s.vram_gb} GB` : ''}`
    : 'No GPU — CPU only'
  return s.forced ? `${base} · forced ${s.forced.toUpperCase()} (PUBLIKCLIP_DEVICE)` : base
}
