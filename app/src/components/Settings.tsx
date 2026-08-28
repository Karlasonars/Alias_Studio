import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import About from './About'
import PrivacyNotice from './PrivacyNotice'
import type {
  CaptionPreset,
  SettingsField,
  SettingsGroup,
  SettingsPayload
} from '../types'

/**
 * The control panel. Every control here is generated from the schema the
 * pipeline emits (settings_schema.py) rather than hand-listed, so a knob
 * cannot drift out of sync with what the pipeline actually reads — and a
 * control can never exist for a setting that does nothing.
 *
 * Editing here changes the GLOBAL defaults, i.e. what the next job starts
 * from. Jobs already on disk keep their own snapshot; that is deliberate,
 * and the panel says so, because silently rescoring finished work would be
 * worse than making the user press Restyle.
 */

interface Props {
  onBack: () => void
}

const COST_LABEL: Record<string, string> = {
  cheap: 're-render',
  moderate: 're-direct + re-render',
  high: 'full rescore'
}

/* Read/write a dotted path ("clips.min_len") on the settings tree. */
function readPath(tree: Record<string, unknown>, path: string): unknown {
  return path.split('.').reduce<unknown>((node, part) => {
    if (node && typeof node === 'object') return (node as Record<string, unknown>)[part]
    return undefined
  }, tree)
}

function writePath(
  tree: Record<string, unknown>,
  path: string,
  value: unknown
): Record<string, unknown> {
  const parts = path.split('.')
  const next = { ...tree }
  let node: Record<string, unknown> = next
  for (const part of parts.slice(0, -1)) {
    node[part] = { ...(node[part] as Record<string, unknown>) }
    node = node[part] as Record<string, unknown>
  }
  node[parts[parts.length - 1]] = value
  return next
}

/** The caption preview approximates the burned-in ASS output: real colours,
 *  size ratio, uppercase, outline and words-per-caption. Fonts fall back to
 *  the app's own faces, so treat it as a layout guide rather than a pixel
 *  match — the label says as much. */
function CaptionPreview({ preset }: { preset: CaptionPreset }) {
  const size = Number(preset.size ?? 72)
  const outline = Number(preset.outline ?? 4)
  const maxWords = Math.max(1, Number(preset.max_words ?? 4))
  const words = ['this', 'is', 'how', 'your', 'captions', 'will', 'look']
  const shown = words.slice(0, maxWords)
  const activeIdx = Math.min(1, shown.length - 1)

  // 1080x1920 source canvas → preview box. margin_v is distance from bottom.
  const scale = 250 / 1080
  const marginV = Number(preset.margin_v ?? 560)
  const outlineColor = String(preset.outline_color ?? '#000000')
  const stroke = outline * scale
  const shadowPx = Number(preset.shadow ?? 0) * scale

  return (
    <div className="cap-preview">
      <div className="cap-preview-stage">
        <div className="cap-preview-grid" />
        <div
          className="cap-preview-line"
          style={{
            bottom: `${marginV * scale}px`,
            fontSize: `${size * scale}px`,
            fontFamily:
              String(preset.font) === 'Anton' || String(preset.font) === 'Archivo Black'
                ? "'Archivo Black', sans-serif"
                : "'Public Sans', sans-serif",
            fontWeight: preset.bold ? 800 : 400,
            textTransform: preset.uppercase ? 'uppercase' : 'none',
            WebkitTextStroke: stroke > 0 ? `${stroke}px ${outlineColor}` : undefined,
            filter: shadowPx > 0 ? `drop-shadow(0 ${shadowPx}px ${shadowPx}px #000)` : undefined
          }}
        >
          {shown.map((w, i) => (
            <span
              key={i}
              style={{
                color: String(
                  i === activeIdx ? preset.active : i === 0 ? preset.emphasis : preset.primary
                )
              }}
            >
              {w}{' '}
            </span>
          ))}
        </div>
      </div>
      <p className="cap-preview-note mono">
        approximate — real render uses the bundled {String(preset.font)} face
      </p>
    </div>
  )
}

export default function Settings({ onBack }: Props) {
  const [payload, setPayload] = useState<SettingsPayload | null>(null)
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null)
  const [presets, setPresets] = useState<Record<string, CaptionPreset>>({})
  const [activeGroup, setActiveGroup] = useState('clips')
  const [activePreset, setActivePreset] = useState('classic')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const saveTimer = useRef<number | null>(null)

  const load = useCallback(async () => {
    try {
      const p = await api.settingsGet()
      setPayload(p)
      setDraft(p.defaults)
      setPresets(p.presets)
      setActivePreset(String(p.defaults.caption_preset ?? 'classic'))
      setError(null)
    } catch (err) {
      setError(String(err))
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // Debounced autosave: dragging a slider must not fire a write per pixel.
  const scheduleSave = useCallback((next: Record<string, unknown>) => {
    if (saveTimer.current) window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(async () => {
      setBusy(true)
      try {
        const p = await api.settingsSet(next)
        setPayload(p)
        setPresets(p.presets)
        setSavedAt(Date.now())
        setError(null)
      } catch (err) {
        setError(String(err))
      } finally {
        setBusy(false)
      }
    }, 400)
  }, [])

  useEffect(() => {
    return () => {
      if (saveTimer.current) window.clearTimeout(saveTimer.current)
    }
  }, [])

  const setField = useCallback(
    (path: string, value: unknown) => {
      setDraft((prev) => {
        if (!prev) return prev
        const next = writePath(prev, path, value)
        scheduleSave(next)
        return next
      })
    },
    [scheduleSave]
  )

  const savePreset = useCallback(
    async (name: string, patch: CaptionPreset) => {
      setPresets((prev) => ({ ...prev, [name]: patch })) // optimistic, keeps the slider smooth
      if (saveTimer.current) window.clearTimeout(saveTimer.current)
      saveTimer.current = window.setTimeout(async () => {
        setBusy(true)
        try {
          const p = await api.presetSave(name, patch)
          setPayload(p)
          setPresets(p.presets)
          setSavedAt(Date.now())
          setError(null)
        } catch (err) {
          setError(String(err))
        } finally {
          setBusy(false)
        }
      }, 400)
    },
    []
  )

  const groups = payload?.schema.groups ?? []
  const group = useMemo(
    () => groups.find((g) => g.key === activeGroup) ?? groups[0],
    [groups, activeGroup]
  )

  const changedKeys = useMemo(() => {
    if (!payload || !draft) return new Set<string>()
    const changed = new Set<string>()
    for (const g of payload.schema.groups) {
      for (const f of g.fields) {
        if (readPath(draft, f.key) !== readPath(payload.factory, f.key)) changed.add(f.key)
      }
    }
    return changed
  }, [payload, draft])

  if (error && !payload) {
    return (
      <div className="settings">
        <div className="grain" />
        <header className="review-head">
          <button className="btn-ghost" onClick={onBack}>← studio</button>
          <h1 className="review-title">Settings</h1>
        </header>
        <section className="error-block">
          <span className="led led-err" />
          {error}
        </section>
      </div>
    )
  }

  if (!payload || !draft || !group) {
    return (
      <div className="settings">
        <div className="grain" />
        <p className="settings-loading mono">loading settings…</p>
      </div>
    )
  }

  const renderControl = (field: SettingsField) => {
    const value = readPath(draft, field.key)
    const isChanged = changedKeys.has(field.key)
    const options =
      field.options ??
      (field.options_from === 'presets'
        ? payload.preset_names.map((n) => ({ value: n, label: n }))
        : field.options_from === 'fonts'
          ? payload.schema.fonts.map((n) => ({ value: n, label: n }))
          : [])

    return (
      <div className={`set-row ${isChanged ? 'set-changed' : ''}`} key={field.key}>
        <div className="set-label-col">
          <label className="set-label">
            {field.label}
            {isChanged && <span className="set-dot" title="changed from default" />}
          </label>
          <p className="set-help">{field.help}</p>
        </div>
        <div className="set-control">
          {field.type === 'number' && (
            <div className="set-number">
              <input
                type="range"
                min={field.min}
                max={field.max}
                step={field.step}
                value={Number(value ?? 0)}
                onChange={(e) => setField(field.key, Number(e.target.value))}
                className="framing-slider set-slider"
              />
              <input
                type="number"
                min={field.min}
                max={field.max}
                step={field.step}
                value={Number(value ?? 0)}
                onChange={(e) => setField(field.key, Number(e.target.value))}
                className="set-num-input mono"
              />
              {field.unit && <span className="set-unit mono">{field.unit}</span>}
            </div>
          )}
          {field.type === 'bool' && (
            <button
              className={`opt ${value ? 'opt-on' : ''}`}
              onClick={() => setField(field.key, !value)}
            >
              {value ? 'on' : 'off'}
            </button>
          )}
          {field.type === 'select' && (
            <div className="set-opts">
              {options.map((o) => (
                <button
                  key={o.value}
                  className={`opt ${value === o.value ? 'opt-on' : ''}`}
                  onClick={() => setField(field.key, o.value)}
                >
                  {o.label}
                </button>
              ))}
            </div>
          )}
          {field.type === 'multiselect' && (
            <div className="set-opts">
              {options.map((o) => {
                const list = Array.isArray(value) ? (value as string[]) : []
                const on = list.includes(o.value)
                return (
                  <button
                    key={o.value}
                    className={`opt ${on ? 'opt-on' : ''}`}
                    onClick={() => {
                      const next = on
                        ? list.filter((v) => v !== o.value)
                        : [...list, o.value]
                      // Never let the user empty the set — an engine with no
                      // choices left would silently fall back to defaults.
                      if (next.length === 0) return
                      setField(field.key, next)
                    }}
                    title={on && list.length === 1 ? 'at least one must stay selected' : undefined}
                  >
                    {o.label}
                  </button>
                )
              })}
            </div>
          )}
          {field.type === 'text' && (
            <input
              type="text"
              value={String(value ?? '')}
              onChange={(e) => setField(field.key, e.target.value)}
              placeholder="none"
              className="set-text-input"
            />
          )}
          {isChanged && (
            <button
              className="btn-ghost set-reset"
              title="reset to default"
              onClick={() => setField(field.key, readPath(payload.factory, field.key))}
            >
              ↺
            </button>
          )}
        </div>
      </div>
    )
  }

  const renderMatrix = (g: SettingsGroup) => {
    const m = g.matrix
    if (!m) return null
    const table = (readPath(draft, m.key) ?? {}) as Record<string, Record<string, number>>
    return (
      <div className="set-matrix">
        <div className="set-label-col">
          <label className="set-label">{m.label}</label>
          <p className="set-help">{m.help}</p>
        </div>
        <table className="set-matrix-table">
          <thead>
            <tr>
              <th />
              {m.columns.map((c) => (
                <th key={c} title={m.column_help[c]} className="mono">
                  {c.replace('_', ' ')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.keys(table).map((platform) => (
              <tr key={platform}>
                <td className="set-matrix-row mono">{platform}</td>
                {m.columns.map((c) => (
                  <td key={c}>
                    <input
                      type="number"
                      min={m.min}
                      max={m.max}
                      step={m.step}
                      value={table[platform]?.[c] ?? 0}
                      onChange={(e) =>
                        setField(m.key, {
                          ...table,
                          [platform]: { ...table[platform], [c]: Number(e.target.value) }
                        })
                      }
                      className="set-num-input mono"
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const preset = presets[activePreset] ?? {}

  return (
    <div className="settings">
      <div className="grain" />
      <header className="settings-head">
        <button className="btn-ghost" onClick={onBack}>← studio</button>
        <div>
          <h1 className="review-title">Settings</h1>
          <p className="review-sub mono">
            applies to new jobs · existing jobs keep their own snapshot
            {busy ? ' · saving…' : savedAt ? ' · saved' : ''}
          </p>
        </div>
        <button
          className="btn-secondary settings-reset-all"
          onClick={async () => {
            setBusy(true)
            try {
              const p = await api.settingsReset()
              setPayload(p)
              setDraft(p.defaults)
              setPresets(p.presets)
              setSavedAt(Date.now())
            } finally {
              setBusy(false)
            }
          }}
        >
          RESET ALL
        </button>
      </header>

      {error && (
        <section className="error-block">
          <span className="led led-err" />
          {error}
        </section>
      )}

      <div className="settings-body">
        <nav className="settings-nav">
          {groups.map((g) => {
            const n = g.fields.filter((f) => changedKeys.has(f.key)).length
            return (
              <button
                key={g.key}
                className={`settings-tab ${g.key === activeGroup ? 'settings-tab-on' : ''}`}
                onClick={() => setActiveGroup(g.key)}
              >
                <span>{g.label}</span>
                {n > 0 && <span className="settings-badge mono">{n}</span>}
              </button>
            )
          })}
          <button
            className={`settings-tab ${activeGroup === '__captions' ? 'settings-tab-on' : ''}`}
            onClick={() => setActiveGroup('__captions')}
          >
            <span>Subtitle styles</span>
            {payload.edited_presets.length > 0 && (
              <span className="settings-badge mono">{payload.edited_presets.length}</span>
            )}
          </button>
          <button
            className={`settings-tab ${activeGroup === '__privacy' ? 'settings-tab-on' : ''}`}
            onClick={() => setActiveGroup('__privacy')}
          >
            <span>Privacy</span>
          </button>
          <button
            className={`settings-tab ${activeGroup === '__about' ? 'settings-tab-on' : ''}`}
            onClick={() => setActiveGroup('__about')}
          >
            <span>About</span>
          </button>
        </nav>

        <main className="settings-main">
          {activeGroup === '__about' ? (
            <About />
          ) : activeGroup === '__privacy' ? (
            <PrivacyNotice />
          ) : activeGroup === '__captions' ? (
            <>
              <div className="settings-group-head">
                <h2 className="settings-group-title">Subtitle styles</h2>
                <p className="settings-group-help">
                  Edit any style — including the built-ins. Changes apply everywhere that
                  style is used, on the next render.
                </p>
                <span className={`settings-cost cost-cheap mono`}>
                  cost: {COST_LABEL.cheap}
                </span>
              </div>

              <div className="set-opts settings-preset-picker">
                {payload.preset_names.map((n) => (
                  <button
                    key={n}
                    className={`opt ${n === activePreset ? 'opt-on' : ''}`}
                    onClick={() => setActivePreset(n)}
                  >
                    {n}
                    {payload.edited_presets.includes(n) ? ' •' : ''}
                  </button>
                ))}
              </div>

              <div className="settings-caption-layout">
                <div className="settings-caption-fields">
                  {payload.schema.caption_fields.map((field) => {
                    const value = preset[field.key]
                    return (
                      <div className="set-row" key={field.key}>
                        <div className="set-label-col">
                          <label className="set-label">{field.label}</label>
                          <p className="set-help">{field.help}</p>
                        </div>
                        <div className="set-control">
                          {field.type === 'number' && (
                            <div className="set-number">
                              <input
                                type="range"
                                min={field.min}
                                max={field.max}
                                step={field.step}
                                value={Number(value ?? 0)}
                                onChange={(e) =>
                                  savePreset(activePreset, {
                                    ...preset,
                                    [field.key]: Number(e.target.value)
                                  })
                                }
                                className="framing-slider set-slider"
                              />
                              <input
                                type="number"
                                min={field.min}
                                max={field.max}
                                step={field.step}
                                value={Number(value ?? 0)}
                                onChange={(e) =>
                                  savePreset(activePreset, {
                                    ...preset,
                                    [field.key]: Number(e.target.value)
                                  })
                                }
                                className="set-num-input mono"
                              />
                              {field.unit && <span className="set-unit mono">{field.unit}</span>}
                            </div>
                          )}
                          {field.type === 'bool' && (
                            <button
                              className={`opt ${value ? 'opt-on' : ''}`}
                              onClick={() =>
                                savePreset(activePreset, { ...preset, [field.key]: !value })
                              }
                            >
                              {value ? 'on' : 'off'}
                            </button>
                          )}
                          {field.type === 'color' && (
                            <div className="set-color">
                              <input
                                type="color"
                                value={String(value ?? '#FFFFFF')}
                                onChange={(e) =>
                                  savePreset(activePreset, {
                                    ...preset,
                                    [field.key]: e.target.value.toUpperCase()
                                  })
                                }
                              />
                              <span className="mono set-color-hex">{String(value ?? '')}</span>
                            </div>
                          )}
                          {field.type === 'select' && (
                            <div className="set-opts">
                              {(field.options_from === 'fonts'
                                ? payload.schema.fonts
                                : []
                              ).map((f) => (
                                <button
                                  key={f}
                                  className={`opt ${value === f ? 'opt-on' : ''}`}
                                  onClick={() =>
                                    savePreset(activePreset, { ...preset, [field.key]: f })
                                  }
                                >
                                  {f}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>

                <aside className="settings-preview-col">
                  <CaptionPreview preset={preset} />
                  {payload.edited_presets.includes(activePreset) && (
                    <button
                      className="btn-secondary"
                      onClick={async () => {
                        setBusy(true)
                        try {
                          const p = await api.presetReset(activePreset)
                          setPayload(p)
                          setPresets(p.presets)
                          setSavedAt(Date.now())
                        } finally {
                          setBusy(false)
                        }
                      }}
                    >
                      ↺ RESET “{activePreset}”
                    </button>
                  )}
                </aside>
              </div>
            </>
          ) : (
            <>
              <div className="settings-group-head">
                <h2 className="settings-group-title">{group.label}</h2>
                <p className="settings-group-help">{group.help}</p>
                <span className={`settings-cost cost-${group.cost} mono`}>
                  cost: {COST_LABEL[group.cost]} — {group.cost_note}
                </span>
              </div>
              {group.fields.map(renderControl)}
              {renderMatrix(group)}
            </>
          )}
        </main>
      </div>
    </div>
  )
}
