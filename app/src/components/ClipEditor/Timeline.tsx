import { useMemo } from 'react'
import type { RefObject } from 'react'
import type { EditContext, EditState } from '../../types'
import { fmt } from './shared'

interface Props {
  ctx: EditContext
  edit: EditState
  toPx: (t: number) => number
  fromClientX: (clientX: number) => number
  seekTo: (t: number) => void
  persist: (next: EditState) => Promise<void>
  railRef: RefObject<HTMLDivElement | null>
  playheadRef: RefObject<HTMLDivElement | null>
  dragRef: RefObject<{ kind: string; id?: string; edge?: 'l' | 'r' } | null>
}

/** The timeline rail: waveform, shades, dead-space cuts, word blocks, event
 *  badges, bounds handles and the playhead. Drags only *arm* dragRef here —
 *  the movement itself is handled by the shell's single window-level drag
 *  effect, and the playhead node is written by usePlayer's rAF loop. */
export default function Timeline({
  ctx, edit, toPx, fromClientX, seekTo, persist, railRef, playheadRef, dragRef
}: Props) {
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

  const activeCuts = ctx.auto_cuts

  return (
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
  )
}
