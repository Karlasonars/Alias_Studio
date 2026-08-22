import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { api } from '../api'
import type { DescriptionResult, HookResult, TitlesResult } from '../types'

/**
 * The per-clip timeline editor. One horizontal timeline over a ±45s context
 * window: waveform, word blocks, event badges, free-drag bounds handles,
 * click-to-toggle dead-space cuts, and an overlay track with drag/resize/
 * delete + opt-in animation per item. RE-RENDER CLIP applies everything.
 */

interface Word { word: string; start: number; end: number; speaker?: number }
interface Cut { start: number; end: number; kept: boolean; reason: string }
interface OverlayItem {
  id: string; query: string; source: string; image_path: string
  start: number; end: number; x: number; y: number; scale: number
  animation: string; phrase: string
}
interface EditState {
  start: number; end: number
  caption_preset: string | null; camera_mode: string | null
  gameplay_amount: number | null
  title: string
  title_variants: { text: string; style: string; why: string; chars: number }[]
  description: string
  description_meta: Record<string, unknown>
  remove_dead_space: boolean; disabled_cuts: number[]
  overlays: OverlayItem[]
  // Per-clip overrides of the re-render-cost settings. Partial patches:
  // anything absent inherits the job's value.
  pacing: Record<string, number>
  caption_overrides: Record<string, string | number | boolean>
  lufs_target: number | null
  true_peak_db: number | null
}

/** The re-render-cost knobs, surfaced here so a clip can be tuned where the
 *  result is visible instead of in the global settings panel. Ranges and help
 *  text mirror settings_schema.py; kept short deliberately — this is the
 *  "while I'm looking at the clip" subset, not the whole panel. */
const PACING_FIELDS: { key: string; label: string; min: number; max: number; step: number; help: string }[] = [
  { key: 'min_cut_gap', label: 'shortest silence to cut', min: 0.1, max: 5, step: 0.05,
    help: 'Silences shorter than this are always kept. Lower = tighter edit.' },
  { key: 'breath_pad', label: 'breathing room', min: 0, max: 1, step: 0.05,
    help: "Kept on each side of a cut so it doesn't clip the start of words." },
  { key: 'event_protect_s', label: 'protect around reactions', min: 0, max: 6, step: 0.1,
    help: 'Pauses this close to laughter are comedic timing and never trimmed.' },
  { key: 'natural_pause_max', label: 'natural pause limit', min: 0, max: 4, step: 0.1,
    help: 'Post-sentence pauses up to this long read as normal cadence.' }
]

const CAPTION_QUICK: { key: string; label: string; type: 'number' | 'color' | 'bool'; min?: number; max?: number; step?: number; help: string }[] = [
  { key: 'size', label: 'font size', type: 'number', min: 20, max: 200, step: 2,
    help: 'Cap height in a 1080x1920 frame.' },
  { key: 'margin_v', label: 'distance from bottom', type: 'number', min: 0, max: 1400, step: 10,
    help: 'Keep clear of platform UI — and of the letterbox bar at high gameplay framing.' },
  { key: 'max_words', label: 'words per caption', type: 'number', min: 1, max: 12, step: 1,
    help: 'Fewer words = faster turnover, more urgent feel.' },
  { key: 'active', label: 'active word', type: 'color', help: 'The karaoke highlight colour.' },
  { key: 'primary', label: 'word colour', type: 'color', help: 'Base colour of inactive words.' },
  { key: 'uppercase', label: 'uppercase', type: 'bool', help: 'Force capitals.' }
]
interface EditContext {
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
}

const PRESETS = ['classic', 'beast', 'hormozi', 'minimal', 'karaoke-pop']
const CAMERAS = ['cut', 'pan', 'locked']
const ANIMS = ['none', 'pop', 'ping']

function fmt(t: number): string {
  const m = Math.floor(t / 60)
  const s = (t % 60).toFixed(1)
  return `${m}:${s.padStart(4, '0')}`
}

interface Props {
  jobId: string
  clipIndex: number
  onClose: () => void
  onRendered: () => void
}

export default function ClipEditor({ jobId, clipIndex, onClose, onRendered }: Props) {
  const [ctx, setCtx] = useState<EditContext | null>(null)
  const [edit, setEdit] = useState<EditState | null>(null)
  const [showTuning, setShowTuning] = useState(false)
  const [rendering, setRendering] = useState(false)
  const [renderMsg, setRenderMsg] = useState('')
  const [suggesting, setSuggesting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [titles, setTitles] = useState<TitlesResult | null>(null)
  const [hook, setHook] = useState<HookResult | null>(null)
  const [description, setDescription] = useState<DescriptionResult | null>(null)
  const [copied, setCopied] = useState(false)
  const [copyBusy, setCopyBusy] = useState<'titles' | 'description' | 'hook' | null>(null)
  const [selectedOverlay, setSelectedOverlay] = useState<string | null>(null)
  const railRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ kind: string; id?: string; edge?: 'l' | 'r' } | null>(null)
  const monitorDragRef = useRef<{ id: string; el: HTMLImageElement } | null>(null)

  // --- source-monitor player state ---------------------------------------
  const videoRef = useRef<HTMLVideoElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)        // the 9:16 output frame
  const playheadRef = useRef<HTMLDivElement>(null)     // moved via rAF, no re-render
  const [playing, setPlaying] = useState(false)
  const [timeLabel, setTimeLabel] = useState('')
  const editRef = useRef<EditState | null>(null)       // rAF reads latest edit
  editRef.current = edit
  const ctxRef = useRef<EditContext | null>(null)
  ctxRef.current = ctx
  const cutsRef = useRef<Cut[]>([])
  const seekPending = useRef<number | null>(null)

  const reload = useCallback(() => {
    invoke<EditContext>('edit_tool', { args: ['context', jobId, String(clipIndex)] })
      .then((c) => {
        setCtx(c)
        setEdit(c.edit)
      })
      .catch((e) => setError(String(e)))
  }, [jobId, clipIndex])

  useEffect(reload, [reload])

  useEffect(() => {
    let un: (() => void) | null = null
    listen<{ event: string; message?: string; ok?: boolean; error?: string }>(
      'pipeline-event',
      ({ payload }) => {
        if (payload.event === 'progress') setRenderMsg(payload.message ?? '')
        if (payload.event === 'result') {
          setRendering(false)
          if (payload.ok) {
            setRenderMsg('done ✓')
            onRendered()
          } else setError(String(payload.error))
        }
      }
    ).then((u) => (un = u))
    return () => un?.()
  }, [onRendered])

  const win = ctx?.window
  const span = win ? win.end - win.start : 1
  const toPx = useCallback(
    (t: number) => (win ? ((t - win.start) / span) * 100 : 0),
    [win, span]
  )
  const fromClientX = useCallback(
    (clientX: number): number => {
      const rail = railRef.current
      if (!rail || !win) return 0
      const rect = rail.getBoundingClientRect()
      const frac = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
      return win.start + frac * span
    },
    [win, span]
  )

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
        // source video inside the 9:16 stage so the crop rect fills it.
        const stage = stageRef.current
        const c = ctxRef.current
        if (stage && c && v.videoWidth) {
          const Ch = stage.clientHeight
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
          const s = Ch / chh
          v.style.width = `${v.videoWidth * s}px`
          v.style.maxWidth = 'none'
          v.style.transform = `translate(${-cx * s}px, ${-cy * s}px)`
          void cw
        }
        setTimeLabel(`${fmt(t)} / out ${fmt(e.end)}`)
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

  // waveform path
  const wavePath = useMemo(() => {
    if (!ctx || !ctx.rms.length) return ''
    const max = Math.max(...ctx.rms, 0.001)
    const pts = ctx.rms.map((v, i) => {
      const x = (i / (ctx.rms.length - 1)) * 100
      return `${x.toFixed(2)},${(30 - (v / max) * 28).toFixed(1)}`
    })
    return `M0,30 L${pts.join(' L')} L100,30 Z`
  }, [ctx])

  useEffect(() => {
    function onMove(e: MouseEvent) {
      const drag = dragRef.current
      if (!drag || !edit) return
      const t = fromClientX(e.clientX)
      if (drag.kind === 'bound-l') {
        setEdit({ ...edit, start: Math.min(t, edit.end - 3) })
        seekTo(t) // show the exact frame being cut to
      } else if (drag.kind === 'bound-r') {
        setEdit({ ...edit, end: Math.max(t, edit.start + 3) })
        seekTo(t)
      }
      else if (drag.kind === 'scrub') seekTo(t)
      else if (drag.kind === 'ov' && drag.id) {
        setEdit({
          ...edit,
          overlays: edit.overlays.map((o) => {
            if (o.id !== drag.id) return o
            const rel = t - edit.start
            if (drag.edge === 'l') return { ...o, start: Math.min(rel, o.end - 0.4) }
            if (drag.edge === 'r') return { ...o, end: Math.max(rel, o.start + 0.4) }
            const dur = o.end - o.start
            return { ...o, start: Math.max(0, rel - dur / 2), end: Math.max(dur, rel + dur / 2) }
          })
        })
      }
    }
    function onMonitorMove(e: MouseEvent) {
      const md = monitorDragRef.current
      const stage = stageRef.current
      if (!md || !stage || !editRef.current) return
      const rect = stage.getBoundingClientRect()
      const iw = md.el.clientWidth
      const ih = md.el.clientHeight
      const nx = Math.min(1, Math.max(0, (e.clientX - rect.left - iw / 2) / Math.max(1, rect.width - iw)))
      const ny = Math.min(1, Math.max(0, (e.clientY - rect.top - ih / 2) / Math.max(1, rect.height - ih)))
      const cur = editRef.current
      setEdit({
        ...cur,
        overlays: cur.overlays.map((o) => (o.id === md.id ? { ...o, x: nx, y: ny } : o))
      })
    }
    function onUp() {
      if (monitorDragRef.current && editRef.current) {
        void persist(editRef.current)
      }
      dragRef.current = null
      monitorDragRef.current = null
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mousemove', onMonitorMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mousemove', onMonitorMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [edit, fromClientX, seekTo])

  async function persist(next: EditState) {
    setEdit(next)
    await invoke('save_clip_edits', { jobId, edits: { [String(clipIndex)]: next } })
  }

  async function doRender() {
    if (!edit) return
    await invoke('save_clip_edits', { jobId, edits: { [String(clipIndex)]: edit } })
    setRendering(true)
    setRenderMsg('starting…')
    setError(null)
    await invoke('run_edit_render', { jobId, clip: clipIndex })
  }

  async function doSuggest(prefer: string) {
    if (!edit) return
    await invoke('save_clip_edits', { jobId, edits: { [String(clipIndex)]: edit } })
    setSuggesting(true)
    setError(null)
    try {
      const res = await invoke<{ ok: boolean; edit?: EditState; error?: string }>('edit_tool', {
        args: ['suggest-visuals', jobId, String(clipIndex), '--prefer', prefer]
      })
      if (res.ok && res.edit) setEdit(res.edit)
      else setError(res.error ?? 'no visuals found')
    } catch (e) {
      setError(String(e))
    } finally {
      setSuggesting(false)
    }
  }

  if (!ctx || !edit || !win) {
    return (
      <div className="editor-shell">
        <p className="mono editor-loading">{error ?? 'loading timeline…'}</p>
      </div>
    )
  }

  const activeCuts = ctx.auto_cuts
  // How many re-render settings this clip overrides, so the collapsed bar can
  // say "you changed things in here" without being opened.
  const tunedCount =
    Object.keys(edit.pacing ?? {}).length +
    Object.keys(edit.caption_overrides ?? {}).length +
    (edit.lufs_target !== null && edit.lufs_target !== undefined ? 1 : 0) +
    (edit.true_peak_db !== null && edit.true_peak_db !== undefined ? 1 : 0)

  return (
    <div className="editor-shell">
      <header className="editor-head">
        <button className="btn-ghost" onClick={onClose}>← clips</button>
        <span className="mono editor-title">
          CLIP {clipIndex} · {fmt(edit.start)}–{fmt(edit.end)} ·{' '}
          {(edit.end - edit.start).toFixed(1)}s source
        </span>
        <button className="btn-primary editor-render" onClick={doRender} disabled={rendering}>
          {rendering ? 'RENDERING…' : 'RE-RENDER CLIP'}
        </button>
      </header>
      {rendering && <p className="mono editor-msg">{renderMsg}</p>}
      {error && <p className="mono editor-err">{error}</p>}

      {/* vertical output monitor: the 9:16 frame, camera-trajectory-following */}
      <div className="monitor-src-wrap">
        <div className="monitor-src-stage" ref={stageRef} onClick={togglePlay}>
          <video
            ref={videoRef}
            className="monitor-src"
            src={api.fileUrl(ctx.media_path)}
            preload="auto"
            muted={false}
            onLoadedMetadata={() => seekTo(edit.start)}
          />
          {/* overlay preview — EXACT render math: left = x*(W-w), top = y*(H-h) */}
          {edit.overlays.map((o) => {
            const v = videoRef.current
            const t = v ? v.currentTime : -1
            if (t < edit.start + o.start || t > edit.start + o.end) return null
            const wPct = o.scale * 100
            return (
              <img
                key={o.id}
                src={api.fileUrl(o.image_path)}
                className={`monitor-ov monitor-ov-live ${selectedOverlay === o.id ? 'ov-on' : ''}`}
                onMouseDown={(ev) => {
                  ev.stopPropagation()
                  ev.preventDefault()
                  setSelectedOverlay(o.id)
                  monitorDragRef.current = { id: o.id, el: ev.currentTarget }
                }}
                onClick={(ev) => ev.stopPropagation()}
                style={{
                  width: `${wPct}%`,
                  left: `calc(${o.x} * (100% - ${wPct}%))`,
                  top: `calc(${o.y} * (100% - var(--ovh-${o.id}, 30%)))`
                }}
                onLoad={(e) => {
                  // publish this image's rendered height fraction so the
                  // top calc matches ffmpeg's (H-h)*y exactly
                  const img = e.currentTarget
                  const stage = stageRef.current
                  if (stage && stage.clientHeight) {
                    stage.style.setProperty(
                      `--ovh-${o.id}`,
                      `${(img.clientHeight / stage.clientHeight) * 100}%`
                    )
                  }
                }}
                alt=""
              />
            )
          })}
        </div>
        <div className="monitor-src-bar">
          <button className="play-btn" onClick={togglePlay}>
            {playing ? '❚❚' : '▶'}
          </button>
          <span className="mono play-time">{timeLabel}</span>
          <span className="mono play-hint">space = play/pause · drag handles to scrub · click timeline to seek</span>
        </div>
      </div>

      {/* style row */}
      <div className="editor-styles">
        <span className="opt-label">captions</span>
        {PRESETS.map((p) => (
          <button
            key={p}
            className={`opt ${(edit.caption_preset ?? ctx.run_caption_preset) === p ? 'opt-on' : ''}`}
            onClick={() => persist({ ...edit, caption_preset: p })}
          >
            {p}
          </button>
        ))}
        <span className="opt-label" style={{ marginLeft: 14 }}>camera</span>
        {CAMERAS.map((c) => (
          <button
            key={c}
            className={`opt ${(edit.camera_mode ?? 'cut') === c ? 'opt-on' : ''}`}
            onClick={() => persist({ ...edit, camera_mode: c })}
          >
            {c}
          </button>
        ))}
        <span className="opt-label" style={{ marginLeft: 14 }}>framing</span>
        <span className="slider-end">podcast</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={edit.gameplay_amount ?? 0}
          onChange={(e) => setEdit({ ...edit, gameplay_amount: Number(e.target.value) })}
          onMouseUp={(e) =>
            persist({ ...edit, gameplay_amount: Number((e.target as HTMLInputElement).value) })
          }
          onTouchEnd={(e) =>
            persist({ ...edit, gameplay_amount: Number((e.target as HTMLInputElement).value) })
          }
          className="framing-slider"
        />
        <span className="slider-end">gameplay</span>
        <button
          className={`opt ${edit.remove_dead_space ? 'opt-on' : ''}`}
          style={{ marginLeft: 14 }}
          onClick={() => persist({ ...edit, remove_dead_space: !edit.remove_dead_space })}
        >
          ✂ remove dead space
        </button>
      </div>

      {/* Its own bar rather than another pill in the row above: these are the
          knobs people actually hunt for, and a small toggle lost among the
          preset buttons is the same as not shipping them. */}
      <button
        className={`editor-tune-bar ${showTuning ? 'editor-tune-bar-on' : ''}`}
        onClick={() => setShowTuning((v) => !v)}
      >
        <span className="editor-tune-caret mono">{showTuning ? '▾' : '▸'}</span>
        <span className="editor-tune-title">Fine-tune this clip</span>
        <span className="editor-tune-sub mono">
          dead space · subtitle size, colours &amp; position · loudness
        </span>
        {tunedCount > 0 && <span className="settings-badge mono">{tunedCount}</span>}
        <span className="editor-tune-cost mono">re-render only</span>
      </button>

      {showTuning && (
        <div className="editor-tuning">
          <p className="editor-tuning-note mono">
            per-clip overrides · cost: re-render only · blank = inherit the job
          </p>

          <div className="editor-tuning-cols">
            <section>
              <h4 className="editor-tuning-h">Dead space</h4>
              {PACING_FIELDS.map((f) => {
                const active = edit.pacing?.[f.key]
                const shown = active ?? ctx.pacing?.[f.key] ?? 0
                return (
                  <div className="tune-row" key={f.key}>
                    <label className="tune-label" title={f.help}>
                      {f.label}
                      {active !== undefined && <span className="set-dot" />}
                    </label>
                    <input
                      type="range" min={f.min} max={f.max} step={f.step} value={shown}
                      onChange={(e) =>
                        setEdit({ ...edit, pacing: { ...edit.pacing, [f.key]: Number(e.target.value) } })
                      }
                      onMouseUp={(e) =>
                        persist({
                          ...edit,
                          pacing: { ...edit.pacing, [f.key]: Number((e.target as HTMLInputElement).value) }
                        })
                      }
                      className="framing-slider tune-slider"
                    />
                    <span className="tune-val mono">{Number(shown).toFixed(2)}s</span>
                    {active !== undefined && (
                      <button
                        className="btn-ghost tune-reset"
                        title="inherit the job's value"
                        onClick={() => {
                          const next = { ...edit.pacing }
                          delete next[f.key]
                          persist({ ...edit, pacing: next })
                        }}
                      >
                        ↺
                      </button>
                    )}
                  </div>
                )
              })}
              {!edit.remove_dead_space && (
                <p className="tune-hint">
                  Turn on “remove dead space” to apply these.
                </p>
              )}
            </section>

            <section>
              <h4 className="editor-tuning-h">Subtitles</h4>
              {CAPTION_QUICK.map((f) => {
                const active = edit.caption_overrides?.[f.key]
                const base = ctx.caption_style?.[f.key]
                const shown = active ?? base
                const set = (v: string | number | boolean) =>
                  persist({ ...edit, caption_overrides: { ...edit.caption_overrides, [f.key]: v } })
                return (
                  <div className="tune-row" key={f.key}>
                    <label className="tune-label" title={f.help}>
                      {f.label}
                      {active !== undefined && <span className="set-dot" />}
                    </label>
                    {f.type === 'number' && (
                      <>
                        <input
                          type="range" min={f.min} max={f.max} step={f.step}
                          value={Number(shown ?? 0)}
                          onChange={(e) =>
                            setEdit({
                              ...edit,
                              caption_overrides: {
                                ...edit.caption_overrides,
                                [f.key]: Number(e.target.value)
                              }
                            })
                          }
                          onMouseUp={(e) => set(Number((e.target as HTMLInputElement).value))}
                          className="framing-slider tune-slider"
                        />
                        <span className="tune-val mono">{Number(shown ?? 0)}</span>
                      </>
                    )}
                    {f.type === 'color' && (
                      <input
                        type="color"
                        value={String(shown ?? '#FFFFFF')}
                        onChange={(e) => set(e.target.value.toUpperCase())}
                        className="tune-color"
                      />
                    )}
                    {f.type === 'bool' && (
                      <button className={`opt ${shown ? 'opt-on' : ''}`} onClick={() => set(!shown)}>
                        {shown ? 'on' : 'off'}
                      </button>
                    )}
                    {active !== undefined && (
                      <button
                        className="btn-ghost tune-reset"
                        title="inherit the job's value"
                        onClick={() => {
                          const next = { ...edit.caption_overrides }
                          delete next[f.key]
                          persist({ ...edit, caption_overrides: next })
                        }}
                      >
                        ↺
                      </button>
                    )}
                  </div>
                )
              })}
            </section>

            <section>
              <h4 className="editor-tuning-h">Audio</h4>
              {([
                ['lufs_target', 'loudness', -30, -8, 0.5, 'LUFS'],
                ['true_peak_db', 'peak ceiling', -6, 0, 0.1, 'dB']
              ] as const).map(([key, label, min, max, step, unit]) => {
                const active = edit[key]
                const shown = active ?? ctx.audio?.[key] ?? 0
                return (
                  <div className="tune-row" key={key}>
                    <label className="tune-label">
                      {label}
                      {active !== null && active !== undefined && <span className="set-dot" />}
                    </label>
                    <input
                      type="range" min={min} max={max} step={step} value={shown}
                      onChange={(e) => setEdit({ ...edit, [key]: Number(e.target.value) })}
                      onMouseUp={(e) =>
                        persist({ ...edit, [key]: Number((e.target as HTMLInputElement).value) })
                      }
                      className="framing-slider tune-slider"
                    />
                    <span className="tune-val mono">
                      {Number(shown).toFixed(1)} {unit}
                    </span>
                    {active !== null && active !== undefined && (
                      <button
                        className="btn-ghost tune-reset"
                        onClick={() => persist({ ...edit, [key]: null })}
                        title="inherit the job's value"
                      >
                        ↺
                      </button>
                    )}
                  </div>
                )
              })}
            </section>
          </div>
        </div>
      )}

      {/* copy: titles + hook. Both are on-demand AI calls, so nothing here
          runs until asked — and neither touches the render. */}
      <div className="copy-block">
        <div className="copy-col">
          <div className="copy-head">
            <span className="opt-label">titles</span>
            <button
              className="btn-secondary copy-go"
              disabled={copyBusy !== null}
              onClick={async () => {
                setCopyBusy('titles')
                setError(null)
                try {
                  const res = await api.clipTitles(jobId, clipIndex)
                  if (res.ok) setTitles(res)
                  else setError(res.error ?? 'title generation failed')
                } catch (err) {
                  setError(String(err))
                } finally {
                  setCopyBusy(null)
                }
              }}
            >
              {copyBusy === 'titles' ? 'writing…' : titles ? 'regenerate' : 'generate'}
            </button>
          </div>

          {edit.title && (
            <p className="copy-chosen">
              <span className="mono copy-chosen-tag">chosen</span> {edit.title}
            </p>
          )}

          {titles?.titles.map((t, i) => (
            <button
              key={i}
              className={`copy-title ${edit.title === t.text ? 'copy-title-on' : ''}`}
              onClick={() => persist({ ...edit, title: t.text })}
              title={t.why}
            >
              <span className="copy-title-text">{t.text}</span>
              <span className="copy-title-meta mono">
                {t.style} · {t.chars}
              </span>
            </button>
          ))}
          {titles && titles.titles.length === 0 && (
            <p className="copy-empty">
              every variant was rejected by your title rules — loosen the length
              limits or allow questions/numbers in Settings
            </p>
          )}
          {titles && titles.rejected.length > 0 && (
            <p className="copy-empty mono">
              {titles.rejected.length} rejected ({titles.rejected[0].rejected_because})
            </p>
          )}
        </div>

        <div className="copy-col">
          <div className="copy-head">
            <span className="opt-label">description</span>
            <button
              className="btn-secondary copy-go"
              disabled={copyBusy !== null}
              onClick={async () => {
                setCopyBusy('description')
                setError(null)
                try {
                  const res = await api.clipDescription(jobId, clipIndex)
                  if (res.ok) {
                    setDescription(res)
                    // `full` is what gets pasted, so that's what we keep on
                    // the clip — the parts stay in `description` for display.
                    persist({ ...edit, description: res.full })
                  } else setError(res.error ?? 'description generation failed')
                } catch (err) {
                  setError(String(err))
                } finally {
                  setCopyBusy(null)
                }
              }}
            >
              {copyBusy === 'description'
                ? 'writing…'
                : edit.description
                  ? 'regenerate'
                  : 'generate'}
            </button>
          </div>

          {edit.description ? (
            <>
              <textarea
                className="copy-desc mono"
                value={edit.description}
                spellCheck={false}
                onChange={(e) => setEdit({ ...edit, description: e.target.value })}
                onBlur={() => persist(edit)}
              />
              <div className="copy-desc-foot">
                <button
                  className="btn-secondary copy-copy"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(edit.description)
                      setCopied(true)
                      window.setTimeout(() => setCopied(false), 1600)
                    } catch {
                      setError('could not reach the clipboard')
                    }
                  }}
                >
                  {copied ? 'COPIED ✓' : '⧉ COPY'}
                </button>
                <span className="copy-desc-meta mono">
                  {edit.description.length} chars
                  {description?.hashtags?.length
                    ? ` · ${description.hashtags.length} hashtags`
                    : ''}
                </span>
              </div>
              {description?.warnings?.length ? (
                <p className="copy-empty mono">{description.warnings.join(' · ')}</p>
              ) : null}
            </>
          ) : (
            <p className="copy-empty">
              the caption pasted under the video — longer than the title, and
              carrying the context and searchable words it had no room for
            </p>
          )}
        </div>

        <div className="copy-col">
          <div className="copy-head">
            <span className="opt-label">hook</span>
            <button
              className="btn-secondary copy-go"
              disabled={copyBusy !== null}
              onClick={async () => {
                setCopyBusy('hook')
                setError(null)
                try {
                  const res = await api.clipHook(jobId, clipIndex)
                  if (res.ok) setHook(res)
                  else setError(res.error ?? 'hook analysis failed')
                } catch (err) {
                  setError(String(err))
                } finally {
                  setCopyBusy(null)
                }
              }}
            >
              {copyBusy === 'hook' ? 'analysing…' : hook ? 're-analyse' : 'analyse opening'}
            </button>
          </div>

          {hook?.note && <p className="copy-empty">{hook.note}</p>}
          {hook && !hook.note && (
            <p className="copy-verdict">
              {hook.improves ? (
                <>a stronger opening is available</>
              ) : (
                <>your current opening is the strongest one found</>
              )}
              {hook.current_strength !== null && (
                <span className="mono"> · now {hook.current_strength}/10</span>
              )}
            </p>
          )}

          {hook?.candidates.map((c, i) => {
            const isCurrent = Math.abs(c.start - hook.current_start) < 0.25
            return (
              <div key={i} className={`copy-hook ${isCurrent ? 'copy-hook-now' : ''}`}>
                <div className="copy-hook-top">
                  <span className="mono copy-hook-score">{c.strength}</span>
                  <span className="copy-hook-type mono">{c.hook_type.replace(/_/g, ' ')}</span>
                  {isCurrent ? (
                    <span className="copy-hook-now-tag mono">current</span>
                  ) : (
                    <button
                      className="opt copy-hook-use"
                      onClick={() => persist({ ...edit, start: c.start })}
                      title={`move the clip start to ${c.start.toFixed(2)}s`}
                    >
                      use
                    </button>
                  )}
                </div>
                <p className="copy-hook-why">{c.why}</p>
                {c.risk && c.risk.toLowerCase() !== 'none' && (
                  <p className="copy-hook-risk">risk: {c.risk}</p>
                )}
              </div>
            )
          })}

          {hook?.text_hook && (
            <p className="copy-texthook">
              <span className="mono copy-chosen-tag">on-screen</span> “{hook.text_hook}”
            </p>
          )}
        </div>
      </div>

      {/* timeline */}
      <div
        className="timeline"
        ref={railRef}
        onMouseDown={(e) => {
          seekTo(fromClientX(e.clientX))
          dragRef.current = { kind: 'scrub' }
        }}
      >
        <div className="tl-playhead" ref={playheadRef} />
        {/* waveform */}
        <svg className="tl-wave" viewBox="0 0 100 30" preserveAspectRatio="none">
          <path d={wavePath} fill="rgba(255,178,36,0.25)" />
        </svg>

        {/* out-of-bounds shade */}
        <div className="tl-shade" style={{ left: 0, width: `${toPx(edit.start)}%` }} />
        <div className="tl-shade" style={{ left: `${toPx(edit.end)}%`, right: 0 }} />

        {/* dead-space cuts */}
        {edit.remove_dead_space &&
          activeCuts.map((c, i) => {
            const disabled = edit.disabled_cuts.includes(i)
            const active = !c.kept && !disabled
            return (
              <div
                key={i}
                className={`tl-cut ${active ? 'tl-cut-on' : 'tl-cut-off'}`}
                style={{ left: `${toPx(c.start)}%`, width: `${Math.max(0.4, toPx(c.end) - toPx(c.start))}%` }}
                title={`${c.reason} — click to ${active ? 'keep' : 'cut'}`}
                onClick={() => {
                  if (c.kept) return
                  const next = disabled
                    ? edit.disabled_cuts.filter((d) => d !== i)
                    : [...edit.disabled_cuts, i]
                  persist({ ...edit, disabled_cuts: next })
                }}
              />
            )
          })}

        {/* word blocks */}
        <div className="tl-words">
          {ctx.words.map((w, i) => (
            <span
              key={i}
              className={`tl-word ${w.start >= edit.start && w.start < edit.end ? '' : 'tl-word-out'}`}
              style={{ left: `${toPx(w.start)}%`, width: `${Math.max(0.3, toPx(w.end) - toPx(w.start))}%` }}
              title={`${w.word} @ ${fmt(w.start)}`}
            />
          ))}
        </div>

        {/* event badges */}
        {ctx.events.map((e, i) => (
          <span
            key={i}
            className="tl-event"
            style={{ left: `${toPx(e.start)}%` }}
            title={`${e.type} ${fmt(e.start)}`}
          >
            {e.type === 'laugh' ? '😂' : e.type === 'gasp' ? '😮' : '◆'}
          </span>
        ))}

        {/* bounds handles */}
        <div
          className="tl-handle"
          style={{ left: `${toPx(edit.start)}%` }}
          onMouseDown={(e) => {
            e.stopPropagation()
            dragRef.current = { kind: 'bound-l' }
          }}
        />
        <div
          className="tl-handle tl-handle-r"
          style={{ left: `${toPx(edit.end)}%` }}
          onMouseDown={(e) => {
            e.stopPropagation()
            dragRef.current = { kind: 'bound-r' }
          }}
        />
      </div>

      {/* overlay track */}
      <div className="ov-track">
        <span className="opt-label">visuals</span>
        <div className="ov-rail">
          {edit.overlays.map((o) => {
            const absStart = edit.start + o.start
            const absEnd = edit.start + o.end
            return (
              <div
                key={o.id}
                className={`ov-item ${selectedOverlay === o.id ? 'ov-on' : ''}`}
                style={{ left: `${toPx(absStart)}%`, width: `${Math.max(1, toPx(absEnd) - toPx(absStart))}%` }}
                onMouseDown={() => {
                  setSelectedOverlay(o.id)
                  dragRef.current = { kind: 'ov', id: o.id }
                }}
                title={`${o.query} (${o.source})`}
              >
                <span
                  className="ov-edge"
                  onMouseDown={(e) => {
                    e.stopPropagation()
                    dragRef.current = { kind: 'ov', id: o.id, edge: 'l' }
                  }}
                />
                <span className="ov-label">{o.query.slice(0, 18)}</span>
                <span
                  className="ov-edge ov-edge-r"
                  onMouseDown={(e) => {
                    e.stopPropagation()
                    dragRef.current = { kind: 'ov', id: o.id, edge: 'r' }
                  }}
                />
              </div>
            )
          })}
        </div>
        <div className="ov-actions">
          <button className="btn-secondary" onClick={() => doSuggest('pexels')} disabled={suggesting}>
            {suggesting ? 'planning…' : '✚ suggest visuals (stock)'}
          </button>
          <button className="btn-secondary" onClick={() => doSuggest('gemini')} disabled={suggesting}>
            ✚ suggest (AI-generated)
          </button>
        </div>
      </div>

      {/* all visuals, always listed */}
      {edit.overlays.length > 0 && (
        <div className="ov-cards">
          {edit.overlays.map((o) => (
            <div
              key={o.id}
              className={`ov-card ${selectedOverlay === o.id ? 'ov-on' : ''}`}
              onClick={() => setSelectedOverlay(o.id)}
            >
              <img src={api.fileUrl(o.image_path)} className="ov-card-thumb" alt={o.query} />
              <div className="ov-card-body">
                <span className="mono ov-card-title">
                  {o.query.slice(0, 30)} · {fmt(edit.start + o.start)}–{fmt(edit.start + o.end)}
                </span>
                <div className="ov-card-row">
                  {ANIMS.map((a) => (
                    <button
                      key={a}
                      className={`opt ${o.animation === a ? 'opt-on' : ''}`}
                      onClick={(e) => {
                        e.stopPropagation()
                        persist({
                          ...edit,
                          overlays: edit.overlays.map((x) => (x.id === o.id ? { ...x, animation: a } : x))
                        })
                      }}
                    >
                      {a}
                    </button>
                  ))}
                  <button
                    className="opt"
                    onClick={(e) => {
                      e.stopPropagation()
                      persist({
                        ...edit,
                        overlays: edit.overlays.map((x) =>
                          x.id === o.id ? { ...x, scale: Math.max(0.15, x.scale - 0.06) } : x
                        )
                      })
                    }}
                  >
                    −
                  </button>
                  <span className="mono">{Math.round(o.scale * 100)}%</span>
                  <button
                    className="opt"
                    onClick={(e) => {
                      e.stopPropagation()
                      persist({
                        ...edit,
                        overlays: edit.overlays.map((x) =>
                          x.id === o.id ? { ...x, scale: Math.min(0.85, x.scale + 0.06) } : x
                        )
                      })
                    }}
                  >
                    +
                  </button>
                  <button
                    className="opt ov-delete"
                    onClick={(e) => {
                      e.stopPropagation()
                      setSelectedOverlay(null)
                      persist({ ...edit, overlays: edit.overlays.filter((x) => x.id !== o.id) })
                    }}
                  >
                    ✕
                  </button>
                </div>
                <span className="ov-card-hint">drag it on the video to reposition</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
