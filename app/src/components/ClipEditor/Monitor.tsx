import type { RefObject } from 'react'
import { api } from '../../api'
import type { EditContext, EditState } from '../../types'

interface Props {
  ctx: EditContext
  edit: EditState
  playing: boolean
  timeLabelRef: RefObject<HTMLSpanElement | null>
  videoRef: RefObject<HTMLVideoElement | null>
  stageRef: RefObject<HTMLDivElement | null>
  monitorDragRef: RefObject<{ id: string; el: HTMLImageElement } | null>
  selectedOverlay: string | null
  setSelectedOverlay: (id: string | null) => void
  togglePlay: () => void
  seekTo: (t: number) => void
}

/** The vertical output monitor: the 9:16 frame, camera-trajectory-following.
 *  The video element is positioned imperatively by usePlayer's rAF loop;
 *  this component owns none of the player state. */
export default function Monitor({
  ctx, edit, playing, timeLabelRef, videoRef, stageRef, monitorDragRef,
  selectedOverlay, setSelectedOverlay, togglePlay, seekTo
}: Props) {
  return (
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
        {/* React no longer owns this node's content: usePlayer's rAF loop
            writes it every frame, exactly like the playhead. Rendering a
            value here would fight the loop — do not move it back into JSX. */}
        <span className="mono play-time" ref={timeLabelRef} />
        <span className="mono play-hint">space = play/pause · drag handles to scrub · click timeline to seek</span>
      </div>
    </div>
  )
}
