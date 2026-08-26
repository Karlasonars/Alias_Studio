import type { RefObject } from 'react'
import { api } from '../../api'
import type { EditState } from '../../types'
import { ANIMS, fmt } from './shared'

interface Props {
  edit: EditState
  toPx: (t: number) => number
  selectedOverlay: string | null
  setSelectedOverlay: (id: string | null) => void
  dragRef: RefObject<{ kind: string; id?: string; edge?: 'l' | 'r' } | null>
  persist: (next: EditState) => Promise<void>
  doSuggest: (prefer: string) => Promise<void>
  suggesting: boolean
}

/** The overlay track and the per-overlay cards. Selection lives in the shell
 *  because the monitor highlights the same overlay; track drags only arm
 *  dragRef — the shell's window-level drag effect does the moving. */
export default function OverlayPanel({
  edit, toPx, selectedOverlay, setSelectedOverlay, dragRef, persist, doSuggest, suggesting
}: Props) {
  return (
    <>
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
    </>
  )
}
