import { useState } from 'react'
import type { EditContext, EditState } from '../../types'
import { CAMERAS, CAPTION_QUICK, PACING_FIELDS, PRESETS } from './shared'

interface Props {
  ctx: EditContext
  edit: EditState
  setEdit: (next: EditState) => void
  persist: (next: EditState) => Promise<void>
}

/** The persist-writing control surface: the always-visible style row and the
 *  collapsible fine-tune drawer. Sliders follow the drag rule for form
 *  controls — setEdit continuously in onChange, persist once in onMouseUp. */
export default function Controls({ ctx, edit, setEdit, persist }: Props) {
  const [showTuning, setShowTuning] = useState(false)

  // How many re-render settings this clip overrides, so the collapsed bar can
  // say "you changed things in here" without being opened.
  const tunedCount =
    Object.keys(edit.pacing ?? {}).length +
    Object.keys(edit.caption_overrides ?? {}).length +
    (edit.lufs_target !== null && edit.lufs_target !== undefined ? 1 : 0) +
    (edit.true_peak_db !== null && edit.true_peak_db !== undefined ? 1 : 0) +
    (edit.letterbox_fill ? 1 : 0)

  return (
    <>
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
              <h4 className="editor-tuning-h">Framing</h4>
              <div className="tune-row">
                <label
                  className="tune-label"
                  title="What fills the bars when the framing dial is wide enough that the crop stops filling the frame. Blurred repeats this frame zoomed and blurred behind the image; it roughly doubles render time."
                >
                  letterbox bars
                  {edit.letterbox_fill && <span className="set-dot" />}
                </label>
                <div className="set-opts">
                  {(['black', 'blur'] as const).map((v) => (
                    <button
                      key={v}
                      className={`opt ${(edit.letterbox_fill ?? ctx.letterbox_fill ?? 'black') === v ? 'opt-on' : ''}`}
                      onClick={() => persist({ ...edit, letterbox_fill: v })}
                    >
                      {v === 'black' ? 'black' : 'blurred'}
                    </button>
                  ))}
                </div>
                {edit.letterbox_fill && (
                  <button
                    className="btn-ghost tune-reset"
                    title="inherit the job's value"
                    onClick={() => persist({ ...edit, letterbox_fill: null })}
                  >
                    ↺
                  </button>
                )}
              </div>
              <p className="tune-hint">
                Only visible once framing is wide enough to letterbox.
              </p>
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
    </>
  )
}
