import { useState } from 'react'
import { api } from '../../api'
import type { DescriptionResult, EditState, HookResult, TitlesResult } from '../../types'

interface Props {
  jobId: string
  clipIndex: number
  edit: EditState
  setEdit: (next: EditState) => void
  persist: (next: EditState) => Promise<void>
  setError: (e: string | null) => void
}

/** Titles, description and hook. Both are on-demand AI calls, so nothing
 *  here runs until asked — and neither touches the render. This panel owns
 *  its five result/busy states outright: nothing outside it reads them,
 *  which is also why loading a batch of titles no longer re-renders the
 *  timeline. */
export default function CopyPanel({ jobId, clipIndex, edit, setEdit, persist, setError }: Props) {
  const [titles, setTitles] = useState<TitlesResult | null>(null)
  const [hook, setHook] = useState<HookResult | null>(null)
  const [description, setDescription] = useState<DescriptionResult | null>(null)
  const [copied, setCopied] = useState(false)
  const [copyBusy, setCopyBusy] = useState<'titles' | 'description' | 'hook' | null>(null)

  return (
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
  )
}
