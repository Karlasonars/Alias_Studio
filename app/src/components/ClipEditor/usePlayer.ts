import { useCallback, useEffect, useRef, useState } from 'react'
import type { Cut, EditContext, EditState } from '../../types'
import { fmt, monitorLayout } from './shared'

/** Player machinery: the source video, the throttled seek queue, and the rAF
 *  loop driving the playhead, the crop-following monitor and the jump-cut
 *  preview. The loop reads editRef/ctxRef — not edit/ctx — so its dependency
 *  array can stay [win, span]: it must NOT restart on every edit change
 *  (every drag frame, every keystroke). ctx is also taken as a value, used
 *  only by the two effects whose dependency arrays need it. */
export function usePlayer(
  ctx: EditContext | null,
  ctxRef: { current: EditContext | null },
  editRef: { current: EditState | null },
  win: { start: number; end: number } | undefined,
  span: number
) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)        // the 9:16 output frame
  const playheadRef = useRef<HTMLDivElement>(null)     // moved via rAF, no re-render
  const [playing, setPlaying] = useState(false)
  // Written every frame like the playhead, not held as state: as state it
  // re-rendered the whole editor ~10x/s during playback, and after the split
  // that cascade would hit every child instead of one component.
  const timeLabelRef = useRef<HTMLSpanElement>(null)
  const cutsRef = useRef<Cut[]>([])
  const seekPending = useRef<number | null>(null)

  // ---- player mechanics ---------------------------------------------------
  // Throttled latest-wins seek: while the decoder is mid-seek, remember only
  // the newest target — continuous handle-drags stay smooth on a big file.
  const seekTo = useCallback((t: number) => {
    const v = videoRef.current
    if (!v) return
    if (v.seeking) {
      seekPending.current = t
    } else {
      v.currentTime = t
    }
  }, [])

  useEffect(() => {
    const v = videoRef.current
    if (!v) return
    const onSeeked = () => {
      if (seekPending.current !== null) {
        const t = seekPending.current
        seekPending.current = null
        v.currentTime = t
      }
    }
    v.addEventListener('seeked', onSeeked)
    return () => v.removeEventListener('seeked', onSeeked)
  }, [ctx?.media_path])

  // rAF loop: playhead position, time label, edit-preview jump-cuts,
  // stop at the out point. timeupdate fires ~4Hz — useless for an editor.
  useEffect(() => {
    let raf = 0
    const tick = () => {
      const v = videoRef.current
      const e = editRef.current
      if (v && e && win) {
        const t = v.currentTime
        if (playheadRef.current) {
          const frac = Math.min(1, Math.max(0, (t - win.start) / span))
          playheadRef.current.style.left = `${frac * 100}%`
        }
        // Vertical monitor: follow the camera trajectory — position the
        // source video inside the 9:16 stage the way the renderer frames it:
        // a 9:16-or-narrower crop fills the stage, a wider (gameplay) crop is
        // letterboxed. monitorLayout mirrors letterbox_geometry (§5.8).
        const stage = stageRef.current
        const c = ctxRef.current
        if (stage && c && v.videoWidth) {
          const traj = c.trajectory
          let crop: number[]
          if (traj && traj.frames.length) {
            const idx = Math.max(
              0,
              Math.min(traj.frames.length - 1, Math.round((t - e.start) * traj.fps))
            )
            crop = traj.frames[idx]
          } else {
            const h = v.videoHeight
            const w = (h * 9) / 16
            crop = [(v.videoWidth - w) / 2, 0, w, h]
          }
          const [cx, cy, cw, chh] = crop
          const L = monitorLayout(
            { x: cx, y: cy, w: cw, h: chh },
            v.videoWidth, v.videoHeight,
            stage.clientWidth, stage.clientHeight
          )
          v.style.width = `${L.widthPx}px`
          v.style.maxWidth = 'none'
          v.style.transform = `translate(${L.tx}px, ${L.ty}px)`
          // Bars only exist when letterboxed; an empty clip-path elsewhere
          // keeps the podcast path pixel-identical to the pre-fix math.
          v.style.clipPath = L.letterboxed
            ? `inset(${L.clipTopPx}px 0 ${L.clipBottomPx}px 0)`
            : ''
        }
        if (timeLabelRef.current) {
          timeLabelRef.current.textContent = `${fmt(t)} / out ${fmt(e.end)}`
        }
        if (!v.paused) {
          // skip active dead-space cuts during preview playback
          if (e.remove_dead_space) {
            for (let i = 0; i < cutsRef.current.length; i++) {
              const c = cutsRef.current[i]
              if (!c.kept && !e.disabled_cuts.includes(i) && t >= c.start && t < c.end - 0.05) {
                v.currentTime = c.end
                break
              }
            }
          }
          if (t >= e.end) {
            v.pause()
            setPlaying(false)
            v.currentTime = e.start
          }
        }
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [win, span])

  useEffect(() => {
    cutsRef.current = ctx?.auto_cuts ?? []
  }, [ctx])

  const togglePlay = useCallback(() => {
    const v = videoRef.current
    const e = editRef.current
    if (!v || !e) return
    if (v.paused) {
      if (v.currentTime < e.start - 0.01 || v.currentTime >= e.end - 0.05) v.currentTime = e.start
      void v.play()
      setPlaying(true)
    } else {
      v.pause()
      setPlaying(false)
    }
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !(e.target instanceof HTMLInputElement)) {
        e.preventDefault()
        togglePlay()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [togglePlay])

  return { videoRef, stageRef, playheadRef, timeLabelRef, playing, seekTo, togglePlay }
}
