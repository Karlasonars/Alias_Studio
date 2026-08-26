import { useCallback, useEffect, useRef, useState } from 'react'
import { listen } from '@tauri-apps/api/event'
import { api } from '../../api'
import Controls from './Controls'
import CopyPanel from './CopyPanel'
import Monitor from './Monitor'
import OverlayPanel from './OverlayPanel'
import Timeline from './Timeline'
import { fmt } from './shared'
import { useClipEdit } from './useClipEdit'
import { usePlayer } from './usePlayer'

/**
 * The per-clip timeline editor. One horizontal timeline over a ±45s context
 * window: waveform, word blocks, event badges, free-drag bounds handles,
 * click-to-toggle dead-space cuts, and an overlay track with drag/resize/
 * delete + opt-in animation per item. RE-RENDER CLIP applies everything.
 *
 * Split by state ownership (T-03): useClipEdit owns the document, usePlayer
 * owns the video machinery, CopyPanel owns its result states, and this shell
 * owns everything that crosses those lines — the drag machinery (one window-
 * level effect serving both drag kinds), the render lifecycle, and selection.
 */

interface Props {
  jobId: string
  clipIndex: number
  onClose: () => void
  onRendered: () => void
}

export default function ClipEditor({ jobId, clipIndex, onClose, onRendered }: Props) {
  const { ctx, edit, setEdit, error, setError, editRef, ctxRef, persist } =
    useClipEdit(jobId, clipIndex)
  const [rendering, setRendering] = useState(false)
  const [renderMsg, setRenderMsg] = useState('')
  const [suggesting, setSuggesting] = useState(false)
  const [selectedOverlay, setSelectedOverlay] = useState<string | null>(null)
  const railRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{ kind: string; id?: string; edge?: 'l' | 'r' } | null>(null)
  const monitorDragRef = useRef<{ id: string; el: HTMLImageElement } | null>(null)

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

  const { videoRef, stageRef, playheadRef, playing, timeLabel, seekTo, togglePlay } =
    usePlayer(ctx, ctxRef, editRef, win, span)

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

  async function doRender() {
    if (!edit) return
    await api.saveClipEdits(jobId, clipIndex, edit)
    setRendering(true)
    setRenderMsg('starting…')
    setError(null)
    await api.runEditRender(jobId, clipIndex)
  }

  async function doSuggest(prefer: string) {
    if (!edit) return
    await api.saveClipEdits(jobId, clipIndex, edit)
    setSuggesting(true)
    setError(null)
    try {
      const res = await api.suggestVisuals(jobId, clipIndex, prefer)
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

      <Monitor
        ctx={ctx}
        edit={edit}
        playing={playing}
        timeLabel={timeLabel}
        videoRef={videoRef}
        stageRef={stageRef}
        monitorDragRef={monitorDragRef}
        selectedOverlay={selectedOverlay}
        setSelectedOverlay={setSelectedOverlay}
        togglePlay={togglePlay}
        seekTo={seekTo}
      />

      <Controls ctx={ctx} edit={edit} setEdit={setEdit} persist={persist} />

      <CopyPanel
        jobId={jobId}
        clipIndex={clipIndex}
        edit={edit}
        setEdit={setEdit}
        persist={persist}
        setError={setError}
      />

      <Timeline
        ctx={ctx}
        edit={edit}
        toPx={toPx}
        fromClientX={fromClientX}
        seekTo={seekTo}
        persist={persist}
        railRef={railRef}
        playheadRef={playheadRef}
        dragRef={dragRef}
      />

      <OverlayPanel
        edit={edit}
        toPx={toPx}
        selectedOverlay={selectedOverlay}
        setSelectedOverlay={setSelectedOverlay}
        dragRef={dragRef}
        persist={persist}
        doSuggest={doSuggest}
        suggesting={suggesting}
      />
    </div>
  )
}
