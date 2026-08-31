import { describe, expect, it } from 'vitest'
import { monitorLayout } from './shared'

/** Test-day finding 2: a gameplay-framed clip previewed as a podcast crop
 *  because the monitor always filled the stage height and threw the crop
 *  width away. These pin both halves of monitorLayout: the podcast path must
 *  stay pixel-identical to the old math (the §5.6 zero-regression idea
 *  applied to the preview), and a wide crop must letterbox exactly the way
 *  renderer.letterbox_geometry does. */

// A 52vh stage at 9:16 — realistic numbers, not round ones.
const STAGE_W = 324
const STAGE_H = 576

describe('monitorLayout', () => {
  it('a 9:16 crop fills the stage exactly as the pre-fix math did', () => {
    // tight podcast crop of a 1920x1080 source: 607.5x1080 at x=656
    const crop = { x: 656, y: 0, w: 607.5, h: 1080 }
    const L = monitorLayout(crop, 1920, 1080, STAGE_W, STAGE_H)
    const s = STAGE_H / crop.h // the old scale rule
    expect(L.letterboxed).toBe(false)
    expect(L.widthPx).toBeCloseTo(1920 * s, 6)
    expect(L.tx).toBeCloseTo(-crop.x * s, 6)
    expect(L.ty).toBeCloseTo(-crop.y * s, 6)
  })

  it('a full-frame gameplay crop is scaled to the stage width and letterboxed', () => {
    const crop = { x: 0, y: 0, w: 1920, h: 1080 }
    const L = monitorLayout(crop, 1920, 1080, STAGE_W, STAGE_H)
    const s = STAGE_W / crop.w
    const bandH = crop.h * s
    expect(L.letterboxed).toBe(true)
    expect(L.widthPx).toBeCloseTo(STAGE_W, 6) // crop spans the full stage width
    // band vertically centred: same bar above and below, renderer-style
    expect(L.ty).toBeCloseTo((STAGE_H - bandH) / 2, 6)
    // the band proportion must match letterbox_geometry's:
    // scaled_h/OUT_H = (1080 * 1080/1920) / 1920
    expect(bandH / STAGE_H).toBeCloseTo((1080 * (1080 / 1920)) / 1920, 6)
  })

  it('letterboxing clips the source rows above and below the crop', () => {
    // mid-frame wide crop: rows outside it would bleed into the bars
    const crop = { x: 100, y: 200, w: 1600, h: 900 }
    const L = monitorLayout(crop, 1920, 1080, STAGE_W, STAGE_H)
    const s = STAGE_W / crop.w
    expect(L.letterboxed).toBe(true)
    expect(L.clipTopPx).toBeCloseTo(200 * s, 6)
    expect(L.clipBottomPx).toBeCloseTo((1080 - 200 - 900) * s, 6)
    // crop's top edge lands at the top of the centred band
    expect(L.ty + crop.y * s).toBeCloseTo((STAGE_H - crop.h * s) / 2, 6)
  })
})
