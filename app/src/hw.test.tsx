import { describe, expect, it } from 'vitest'
import { hardwareLabel, sixtyMinEstimate } from './hw'
import type { HardwareProfile } from './types'

/** Test-day F3: the owner forced CPU and the screen kept reading
 *  "NVIDIA GeForce RTX 3050 Ti · 4.3 GB" with a GPU-measured estimate,
 *  because the profile file only learns about forcing at the next job-end
 *  probe. env_forced is the shell's live environment; when the measured
 *  summary was probed WITHOUT that forcing, the GPU line and its estimate
 *  must be withheld — T-10's rule. */

const gpuProfile = (extra: Partial<HardwareProfile> = {}): HardwareProfile => ({
  summary: {
    torch_device: 'cuda',
    gpu: 'NVIDIA GeForce RTX 3050 Ti Laptop GPU',
    vram_gb: 4.3,
    whisper_device: 'cuda',
    whisper_compute: 'float16',
    onnx_providers: ['CPUExecutionProvider'],
    cpu_threads: 6,
    forced: null
  },
  key: 'k',
  estimate_ratio: 0.15,
  estimate_jobs: 3,
  ...extra
})

describe('hardwareLabel / sixtyMinEstimate with a live PUBLIKCLIP_DEVICE', () => {
  it('an unforced profile behaves as before', () => {
    expect(hardwareLabel(gpuProfile())).toMatch(/RTX 3050 Ti.*4\.3 GB/)
    expect(sixtyMinEstimate(gpuProfile())).toBe(9)
  })

  it('forcing the summary was not measured under withholds the GPU line and the estimate', () => {
    const p = gpuProfile({ env_forced: 'cpu' })
    expect(hardwareLabel(p)).toBe(
      'forced CPU (PUBLIKCLIP_DEVICE) — measured profile does not apply'
    )
    expect(sixtyMinEstimate(p)).toBeNull()
  })

  it('forcing already reflected in the summary shows the normal forced label and its estimate', () => {
    const p = gpuProfile({ env_forced: 'cpu' })
    p.summary!.forced = 'cpu'
    expect(hardwareLabel(p)).toMatch(/forced CPU \(PUBLIKCLIP_DEVICE\)$/)
    expect(sixtyMinEstimate(p)).toBe(9)
  })

  it('a forced device with no profile file yet is still visible', () => {
    const p: HardwareProfile = { env_forced: 'cpu' }
    expect(hardwareLabel(p)).toBe(
      'forced CPU (PUBLIKCLIP_DEVICE) — measured profile does not apply'
    )
    expect(sixtyMinEstimate(p)).toBeNull()
  })
})
