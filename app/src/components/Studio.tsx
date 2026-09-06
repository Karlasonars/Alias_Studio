import { useEffect, useRef, useState } from 'react'
import { openUrl } from '@tauri-apps/plugin-opener'
import { api } from '../api'
import { hardwareLabel, sixtyMinEstimate } from '../hw'
import type {
  ErrorInfo, HardwareProfile, JobSummary, LogLine, ResumeInfo, StoryLimits, StoryRun
} from '../types'
import ErrorPanel from './ErrorPanel'
import KeyModal from './KeyModal'
import ResumePicker from './ResumePicker'

/** The stage rows per chain (E20, D-19). Mirrors chains.py — python is the
 *  truth and pins cli._stages() to it; this copy only decides the order and
 *  the label of the rows the deck draws. A `progress` event for a stage not
 *  listed here still lands in `stages`, it just has no row. */
export const CHAIN_ORDER: Record<string, string[]> = {
  clips: ['ingest', 'asr', 'diarize', 'events', 'candidates', 'score', 'camera', 'render'],
  stories: ['ingest', 'narrate', 'asr', 'render']
}

export const STAGE_LABELS: Record<string, string> = {
  ingest: 'INGEST',
  narrate: 'NARRATE',
  asr: 'TRANSCRIBE',
  diarize: 'SPEAKERS',
  events: 'LISTEN',
  candidates: 'SCAN',
  score: 'JUDGE',
  camera: 'DIRECT',
  render: 'RENDER'
}

const CAPTION_PRESETS = ['classic', 'beast', 'hormozi', 'minimal', 'karaoke-pop']
// E20-F04: one word at a time is a preset, not a mechanism — it leads the
// list on the stories deck and is the story default.
const STORY_CAPTION_PRESETS = ['story', ...CAPTION_PRESETS]
// Kokoro's speed multiplier, as four pills: 1.0 is the voice's own pace,
// 1.1–1.2 the brisk delivery the format usually has.
const STORY_SPEEDS = [0.9, 1.0, 1.1, 1.2]

export function countWords(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0
}

/** The deck's estimate, with python's numbers (api.storyLimits). */
export function narrationSeconds(words: number, wordsPerMinute: number, speed: number): number {
  return (words / wordsPerMinute) * 60 / Math.max(0.1, speed)
}

function fmtDuration(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  return m > 0 ? `${m} min ${String(s).padStart(2, '0')} s` : `${s} s`
}
// E18-F01: the top-N choices. Eight is where the list still fits the bar
// gameplay framing leaves at the top (captions/ranking.py:band_for).
const RANKING_COUNTS = [3, 4, 5, 6, 7, 8]

interface Props {
  jobs: JobSummary[]
  running: boolean
  stages: Record<string, { fraction: number; message: string }>
  error: ErrorInfo | null
  /** the job the error belongs to — lets the panel offer T-15's bundle */
  errorJobId: string | null
  cancelled: boolean
  /** E1-F07 warn-level disk notice: the job is running, just tight on space */
  diskNotice: string | null
  log: LogLine[]
  enqueueing: boolean
  queued: number
  hardware: HardwareProfile | null
  /** E20: which chain the running (or last started) job runs — from the job
   *  event, so the deck draws that chain's rows. 'clips' until a job starts. */
  chain: string
  onCancel: () => void
  onRun: (
    source: string,
    llm: string,
    captions: string,
    gameplayAmount: number,
    letterboxFill: string,
    ranking: boolean,
    rankingCount: number,
    rankingOrder: string,
    watermarkImage: string,
    watermarkText: string,
    story: StoryRun | null
  ) => void
  onOpenLoop: () => void
  onOpenQueue: () => void
  onOpenSettings: () => void
  onOpenJob: (id: string) => void
  onResume: (id: string, fromStage?: string) => void
}

export default function Studio({ jobs, running, stages, error, errorJobId, cancelled, diskNotice, log, enqueueing, queued, hardware, chain, onCancel, onRun, onOpenLoop, onOpenQueue, onOpenSettings, onOpenJob, onResume }: Props) {
  const [source, setSource] = useState('')
  // E20 (D-19): the chain, chosen above CUT IT. Stories is its own panel:
  // a background of the user's, a text, a voice and a speed. The clips
  // controls that change nothing for a story (brain, framing, ranking)
  // are not shown there — a control with nothing behind it lies (§5.2).
  const [mode, setMode] = useState<'clips' | 'stories'>('clips')
  const [storyText, setStoryText] = useState('')
  const [storyFileName, setStoryFileName] = useState('')
  const [background, setBackground] = useState('')
  const [voice, setVoice] = useState('')
  const [speed, setSpeed] = useState(1.0)
  const [storyCaptions, setStoryCaptions] = useState('story')
  // python's numbers (narrate/limits.py) — the deck never carries a copy
  const [limits, setLimits] = useState<StoryLimits | null>(null)
  const [storyNotice, setStoryNotice] = useState<string | null>(null)
  const [storyBusy, setStoryBusy] = useState(false)
  const [llm, setLlm] = useState('gemini')
  const [captions, setCaptions] = useState('classic')
  const [gameplayAmount, setGameplayAmount] = useState(0)
  const [letterboxFill, setLetterboxFill] = useState('black')
  // E18-F01, D-18: the ranking videos. Off = the clips alone, as always;
  // on = the clips AND up to two ranking videos, moments 1..N and N+1..2N
  // (E18-F06). Never instead of the clips — D-17 said so and was reversed.
  const [ranking, setRanking] = useState(false)
  const [rankingCount, setRankingCount] = useState(5)
  // E18-F07: the order the moments play in. Countdown is the default; a
  // random order is shuffled once per job by python and kept on the
  // checkpoint, so the deck sends the word and never a seed.
  const [rankingOrder, setRankingOrder] = useState<'countdown' | 'random'>('countdown')
  // E19-F02: the channel mark, decided before the cut like the rest of the
  // deck and sent explicitly — '' is "none", so a job never inherits a
  // mark the deck did not show (the Settings default seeds only jobs made
  // without the deck, exactly like the fill and the ranking toggle). The
  // PNG is copied into the app's own folder on selection, and the job
  // stores THAT path: a logo moved later breaks nothing.
  const [wmKind, setWmKind] = useState<'none' | 'image' | 'text'>('none')
  const [wmImage, setWmImage] = useState('')
  const [wmImageName, setWmImageName] = useState('')
  const [wmText, setWmText] = useState('')
  const [wmBusy, setWmBusy] = useState(false)
  const [wmError, setWmError] = useState<string | null>(null)
  const [showKey, setShowKey] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  // T-14: the resume picker for one rail job. info=null while the one-shot
  // answers; an unreadable answer degrades to an empty stage list, so the
  // picker still offers plain resume — the check must never block it (§5.9).
  const [resumePick, setResumePick] = useState<{
    id: string
    title: string
    info: ResumeInfo | null
  } | null>(null)
  const consoleRef = useRef<HTMLDivElement>(null)
  const showConsole = running || log.length > 0

  useEffect(() => {
    const el = consoleRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [log])

  // The stories panel's numbers and defaults, fetched once, the first time
  // it opens: the limits from the module that applies them, and the saved
  // voice, speed and last-used background (E20 Q2) from the settings the
  // panel edits. Clips users never pay these two one-shots.
  useEffect(() => {
    if (mode !== 'stories' || limits !== null) return
    api
      .storyLimits()
      .then((l) => {
        setLimits(l)
        setVoice((v) => v || l.default_voice)
      })
      .catch((err) => setStoryNotice(`could not read the story limits: ${String(err)}`))
    api
      .settingsGet()
      .then((p) => {
        const story = (p.defaults?.story ?? {}) as { voice?: string; speed?: number; background?: string }
        if (story.voice) setVoice(story.voice)
        if (typeof story.speed === 'number') setSpeed(story.speed)
        if (story.background) setBackground((b) => b || story.background!)
      })
      .catch(() => {})
  }, [mode, limits])

  const words = countWords(storyText)
  const estimate = limits ? narrationSeconds(words, limits.words_per_minute, speed) : null
  const storyRefusal =
    limits && words > limits.max_words
      ? `The story is ${words} words; the limit is ${limits.max_words}. Cut it down by ${words - limits.max_words} words, or split it into two stories.`
      : null
  const storyWarning =
    limits && !storyRefusal && words > limits.warn_words
      ? `${words} words is a long story — about ${fmtDuration(estimate ?? 0)} of narration. Stories under ${limits.warn_words} words tend to hold better.`
      : null
  const storyReady = mode === 'stories' && background.trim() !== '' && words > 0 && !storyRefusal

  const pickBackground = async () => {
    setStoryNotice(null)
    let picked: string | null = null
    try {
      picked = await api.pickBackgroundVideo()
    } catch (err) {
      setStoryNotice(String(err))
      return
    }
    if (!picked) return
    setBackground(picked)
    // remembered as a real setting (E20 Q2); a refusal is a notice, not a block
    api.rememberBackground(picked).catch((err) => setStoryNotice(String(err)))
  }

  const loadStoryFile = async () => {
    setStoryNotice(null)
    let picked: string | null = null
    try {
      picked = await api.pickStoryFile()
    } catch (err) {
      setStoryNotice(String(err))
      return
    }
    if (!picked) return
    setStoryBusy(true)
    try {
      const res = await api.storyRead(picked)
      if (res.ok && typeof res.text === 'string') {
        setStoryText(res.text)
        setStoryFileName(res.name ?? '')
      } else {
        setStoryNotice(res.error ?? 'could not read the file')
      }
    } catch (err) {
      setStoryNotice(String(err))
    } finally {
      setStoryBusy(false)
    }
  }

  // The button disables itself on click; the run ending (cancelled event,
  // result, or crash) is what re-arms it.
  useEffect(() => {
    if (!running) setCancelling(false)
  }, [running])

  const openResumePicker = (job: JobSummary) => {
    setResumePick({ id: job.id, title: job.title ?? job.id, info: null })
    api
      .resumeInfo(job.id)
      .then((info) => setResumePick((p) => (p && p.id === job.id ? { ...p, info } : p)))
      .catch(() =>
        setResumePick((p) =>
          p && p.id === job.id
            ? { ...p, info: { stages: [], default_stage: null, duration_sec: null } }
            : p
        )
      )
  }

  // The picker, then the copy. A cancelled dialog changes nothing; a
  // refused file (not a PNG) says why here, under the control, and sends
  // no image — never the picked path in place of a stored one.
  const pickWatermarkImage = async () => {
    setWmError(null)
    let picked: string | null = null
    try {
      picked = await api.pickWatermarkImage()
    } catch (err) {
      setWmError(String(err))
      return
    }
    if (!picked) {
      if (wmImage) setWmKind('image')
      return
    }
    setWmBusy(true)
    try {
      const res = await api.watermarkImport(picked)
      if (res.ok && res.path) {
        setWmImage(res.path)
        setWmImageName(res.name ?? res.path)
        setWmKind('image')
      } else {
        setWmError(res.error ?? 'could not import the image')
      }
    } catch (err) {
      setWmError(String(err))
    } finally {
      setWmBusy(false)
    }
  }

  // Enqueue and clear the field: with the input live while a job runs, a
  // stuck value plus a second Enter would silently queue a duplicate.
  const submit = () => {
    if (mode === 'stories') {
      if (!storyReady) return
      onRun(
        background.trim(), llm, storyCaptions, 0, 'black', false, rankingCount, rankingOrder,
        wmKind === 'image' ? wmImage : '',
        wmKind === 'text' ? wmText.trim() : '',
        { text: storyText, voice, speed }
      )
      // the background stays (the next story usually reuses it); the text
      // goes, exactly as the URL field clears after a cut
      setStoryText('')
      setStoryFileName('')
      return
    }
    if (!source.trim()) return
    onRun(
      source.trim(), llm, captions, gameplayAmount, letterboxFill, ranking, rankingCount, rankingOrder,
      wmKind === 'image' ? wmImage : '',
      wmKind === 'text' ? wmText.trim() : '',
      null
    )
    setSource('')
  }

  return (
    <div className="studio">
      <div className="grain" />
      {showKey && <KeyModal onClose={() => setShowKey(false)} />}
      {resumePick && (
        <ResumePicker
          title={resumePick.title}
          info={resumePick.info}
          onGo={(fromStage) => {
            const id = resumePick.id
            setResumePick(null)
            onResume(id, fromStage ?? undefined)
          }}
          onClose={() => setResumePick(null)}
        />
      )}
      <aside className="rail">
        <header className="rail-brand">
          <span className="rail-logo">Alias Studio</span>
          <span className="rail-sub">the clipper that shows its work</span>
        </header>
        <div className="rail-jobs">
          <p className="rail-label">SESSIONS</p>
          {jobs.length === 0 && <p className="rail-empty">nothing yet</p>}
          {jobs.map((job) => (
            <button
              key={job.id}
              className={`rail-job ${job.rendered ? '' : 'partial'}`}
              onClick={() => (job.rendered ? onOpenJob(job.id) : openResumePicker(job))}
              disabled={running}
              title={
                job.rendered
                  ? 'open results'
                  : job.cancelled
                    ? 'cancelled — resume from checkpoint'
                    : 'resume from checkpoint'
              }
            >
              <span className={`led ${job.rendered ? 'led-on' : 'led-half'}`} />
              <span className="rail-job-title">{job.title ?? job.id}</span>
              <span className="rail-job-hint">
                {job.rendered ? 'open' : job.cancelled ? 'cancelled' : 'resume'}
              </span>
            </button>
          ))}
        </div>
        {/* E13-F01: the machine and its measured expectation, refreshed by
            App after every run. No profile file yet → no block — never an
            invented number. */}
        {hardware && (
          <div className="rail-hw mono">
            <p>{hardwareLabel(hardware)}</p>
            <p>
              {sixtyMinEstimate(hardware) != null
                ? `60 min video ≈ ${sixtyMinEstimate(hardware)} min`
                : /* not "first run" — a changed configuration also voids the
                     estimate, and calling that a first run lied (F7) */
                  'no estimate for this setup yet — measured from the first full run'}
            </p>
          </div>
        )}
        <footer className="rail-foot">
          <button className="btn-ghost" onClick={() => setShowKey(true)}>
            ◈ gemini key
          </button>
          <button className="btn-ghost" onClick={onOpenLoop}>
            ⟳ instagram loop
          </button>
          {/* ▤ U+25A4: same Unicode block as ◈ (Geometric Shapes), so it
              rides the same font fallback — ⧉ U+29C9 sits in a block the
              Windows fallback never routes anywhere and drew a box. */}
          <button className="btn-ghost" onClick={onOpenQueue}>
            ▤ queue
          </button>
          <button className="btn-ghost" onClick={onOpenSettings}>
            ⚙ settings
          </button>
        </footer>
      </aside>

      <main className="stage-area">
        <div className="stage-main">
          <section className="input-block">
            {/* E20 (D-19): two chains, one deck. The choice sits above
                CUT IT because everything under it depends on it. */}
            <div className="mode-switch" role="tablist" aria-label="mode">
              <button
                role="tab"
                aria-selected={mode === 'clips'}
                className={`opt mode-tab ${mode === 'clips' ? 'opt-on' : ''}`}
                onClick={() => setMode('clips')}
              >
                Clips
              </button>
              <button
                role="tab"
                aria-selected={mode === 'stories'}
                className={`opt mode-tab ${mode === 'stories' ? 'opt-on' : ''}`}
                onClick={() => setMode('stories')}
              >
                Stories
              </button>
            </div>
            <h1 className="input-heading">
              {mode === 'stories' ? (
                <>TELL IT<span className="amber"> A STORY.</span></>
              ) : (
                <>FEED IT<span className="amber"> AN HOUR.</span></>
              )}
            </h1>
            {/* Attribution, not decoration: this build is a modified
                publikclip, and publikclip is AGPL-3.0 — saying where it
                came from is both honest and part of the licence. */}
            <p className="brand-credit">
              Alias Studio is based on{' '}
              <button
                className="brand-credit-link"
                onClick={() =>
                  openUrl('https://github.com/Blueturboguy07/publikclip').catch(() => {})
                }
                title="github.com/Blueturboguy07/publikclip"
              >
                publikclip
              </button>
              , an open-source (AGPL-3.0) project on GitHub.
            </p>
            {mode === 'clips' && (
              <div className="input-row">
                <input
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && submit()}
                  placeholder="YouTube URL or a path to a video file"
                />
                <button className="btn-primary" onClick={submit} disabled={!source.trim()}>
                  {running ? 'QUEUE IT' : 'CUT IT'}
                </button>
              </div>
            )}
            {mode === 'stories' && (
              <div className="story-panel">
                {/* F03: the background is the user's own file; the tool never
                    generates one. Remembered on pick (Q2). */}
                <div className="input-row">
                  <input
                    value={background}
                    onChange={(e) => setBackground(e.target.value)}
                    placeholder="path to a background video (looped or trimmed to the narration, its sound muted)"
                    aria-label="background video"
                  />
                  <button className="btn-secondary" onClick={pickBackground}>
                    browse…
                  </button>
                </div>
                {/* F01: pasted text or a .txt — copied into the job, never
                    fetched from anywhere. First line = the title (the card). */}
                <textarea
                  className="story-text mono"
                  value={storyText}
                  onChange={(e) => setStoryText(e.target.value)}
                  placeholder={'The title on the first line\n\nThen the story. Paste it, or load a .txt.'}
                  aria-label="story text"
                  rows={9}
                />
                <div className="story-meta mono">
                  <span>
                    {words} {words === 1 ? 'word' : 'words'}
                    {limits && words > 0 && estimate !== null
                      ? ` · about ${fmtDuration(estimate)} of narration`
                      : ''}
                    {storyFileName ? ` · from ${storyFileName}` : ''}
                  </span>
                  <button className="btn-ghost" onClick={loadStoryFile} disabled={storyBusy}>
                    {storyBusy ? 'reading…' : 'load .txt…'}
                  </button>
                </div>
                {storyRefusal && <p className="opt-hint story-refusal">{storyRefusal}</p>}
                {storyWarning && <p className="opt-hint">{storyWarning}</p>}
                {storyNotice && <p className="opt-hint">{storyNotice}</p>}
                <div className="input-row">
                  <button className="btn-primary" onClick={submit} disabled={!storyReady}>
                    {running ? 'QUEUE IT' : 'CUT IT'}
                  </button>
                </div>
              </div>
            )}
            {/* The press must answer on THIS screen: the queue once grew to
                six invisible jobs because the only evidence lived in views
                the user was not on. */}
            {(enqueueing || queued > 0) && (
              <p className="queue-ack mono">
                <span className={`led ${enqueueing ? 'led-on' : 'led-half'}`} />
                {enqueueing
                  ? 'adding to queue…'
                  : `${queued} waiting in the queue`}
                {!enqueueing && (
                  <button className="btn-ghost" onClick={onOpenQueue}>
                    view queue
                  </button>
                )}
              </p>
            )}
            <div className="run-options">
              {mode === 'stories' && (
                <>
                  {/* F02: a generic synthetic voice from local weights; the
                      list is python's (settings story-limits). */}
                  <div className="opt-group">
                    <span className="opt-label">voice</span>
                    {(limits?.voices ?? []).map((v) => (
                      <button
                        key={v.id}
                        className={`opt ${voice === v.id ? 'opt-on' : ''}`}
                        onClick={() => setVoice(v.id)}
                        title={v.label}
                      >
                        {v.label.split(' ·')[0]}
                      </button>
                    ))}
                    {limits === null && <span className="opt-hint">loading voices…</span>}
                  </div>
                  <div className="opt-group">
                    <span className="opt-label">speed</span>
                    {STORY_SPEEDS.map((s) => (
                      <button
                        key={s}
                        className={`opt ${Math.abs(speed - s) < 0.001 ? 'opt-on' : ''}`}
                        onClick={() => setSpeed(s)}
                      >
                        {s.toFixed(1)}×
                      </button>
                    ))}
                  </div>
                  <div className="opt-group">
                    <span className="opt-label">captions</span>
                    {STORY_CAPTION_PRESETS.map((preset) => (
                      <button
                        key={preset}
                        className={`opt ${storyCaptions === preset ? 'opt-on' : ''}`}
                        onClick={() => setStoryCaptions(preset)}
                      >
                        {preset}
                      </button>
                    ))}
                  </div>
                </>
              )}
              {mode === 'clips' && (
              <div className="opt-group">
                <span className="opt-label">brain</span>
                {['gemini', 'ollama'].map((mode) => (
                  <button
                    key={mode}
                    className={`opt ${llm === mode ? 'opt-on' : ''}`}
                    onClick={() => setLlm(mode)}
                  >
                    {mode}
                  </button>
                ))}
              </div>
              )}
              {mode === 'clips' && (
              <div className="opt-group">
                <span className="opt-label">captions</span>
                {CAPTION_PRESETS.map((preset) => (
                  <button
                    key={preset}
                    className={`opt ${captions === preset ? 'opt-on' : ''}`}
                    onClick={() => setCaptions(preset)}
                  >
                    {preset}
                  </button>
                ))}
              </div>
              )}
              {mode === 'clips' && (
              <div className="opt-group">
                <span className="opt-label">framing</span>
                <button
                  className={`opt ${gameplayAmount === 0 ? 'opt-on' : ''}`}
                  onClick={() => setGameplayAmount(0)}
                >
                  podcast
                </button>
                <button
                  className={`opt ${gameplayAmount === 1 ? 'opt-on' : ''}`}
                  onClick={() => setGameplayAmount(1)}
                >
                  gameplay
                </button>
              </div>
              )}
              {/* E6-F09: the job-level letterbox fill, decided BEFORE the cut
                  instead of re-rendered into N clips afterwards. Only shown
                  at gameplay framing — a podcast crop is exactly 9:16, bars
                  never exist, and a control that does nothing is a lie
                  (§5.2). Per-clip editor choices still win over this. */}
              {mode === 'clips' && gameplayAmount > 0 && (
                <div className="opt-group">
                  <span className="opt-label">edges</span>
                  {(['black', 'blur'] as const).map((fill) => (
                    <button
                      key={fill}
                      className={`opt ${letterboxFill === fill ? 'opt-on' : ''}`}
                      onClick={() => setLetterboxFill(fill)}
                    >
                      {fill === 'black' ? 'black' : 'blurred'}
                    </button>
                  ))}
                </div>
              )}
              {/* E18-F01, D-18: the ranking videos, decided before the cut
                  like the rest of the deck — beside the clips, never
                  instead of them. The count only exists while ranking is
                  on — shown always, it would be a control that changes
                  nothing (§5.2). */}
              {mode === 'clips' && (
              <div className="opt-group">
                <span className="opt-label">ranking videos</span>
                <button className={`opt ${!ranking ? 'opt-on' : ''}`} onClick={() => setRanking(false)}>
                  off
                </button>
                <button className={`opt ${ranking ? 'opt-on' : ''}`} onClick={() => setRanking(true)}>
                  on
                </button>
              </div>
              )}
              {mode === 'clips' && ranking && (
                <div className="opt-group">
                  <span className="opt-label">moments</span>
                  {RANKING_COUNTS.map((n) => (
                    <button
                      key={n}
                      className={`opt ${rankingCount === n ? 'opt-on' : ''}`}
                      onClick={() => setRankingCount(n)}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              )}
              {/* E18-F07: the play order, only while ranking is on for the
                  same reason as the count. The shuffle itself is python's
                  and is kept per job — there is no reshuffle here, on
                  purpose: if the owner turns out to reshuffle constantly,
                  that is the next requirement. */}
              {mode === 'clips' && ranking && (
                <div className="opt-group">
                  <span className="opt-label">play order</span>
                  <button
                    className={`opt ${rankingOrder === 'countdown' ? 'opt-on' : ''}`}
                    onClick={() => setRankingOrder('countdown')}
                    title={`rank ${rankingCount} first, rank 1 last`}
                  >
                    countdown
                  </button>
                  <button
                    className={`opt ${rankingOrder === 'random' ? 'opt-on' : ''}`}
                    onClick={() => setRankingOrder('random')}
                    title="shuffled once per job and kept; re-rendering plays the same order"
                  >
                    random
                  </button>
                </div>
              )}
              {/* E18-F06: what "on" makes, said where it is chosen — the
                  second video exists only when the job has 2N finalists. */}
              {mode === 'clips' && ranking && (
                <p className="opt-hint">
                  two ranking videos beside the clips — moments 1 to {rankingCount} and the next{' '}
                  {rankingCount}; one, if the job renders fewer than {rankingCount * 2} clips
                  {rankingOrder === 'random' && (
                    <>; shuffled once for this job and kept, so a re-render plays the same order</>
                  )}
                </p>
              )}
              {/* E19-F02: a picture or a word on every output file, clips
                  and ranking videos alike. The image button carries the
                  stored file's name once one is imported. */}
              <div className="opt-group">
                <span className="opt-label">watermark</span>
                <button
                  className={`opt ${wmKind === 'none' ? 'opt-on' : ''}`}
                  onClick={() => setWmKind('none')}
                >
                  none
                </button>
                <button
                  className={`opt ${wmKind === 'image' ? 'opt-on' : ''}`}
                  onClick={pickWatermarkImage}
                  disabled={wmBusy}
                  title="a PNG, bottom centre of every clip and ranking video"
                >
                  {wmBusy ? 'copying…' : wmImageName || 'image…'}
                </button>
                <button
                  className={`opt ${wmKind === 'text' ? 'opt-on' : ''}`}
                  onClick={() => setWmKind('text')}
                >
                  word
                </button>
              </div>
              {wmKind === 'text' && (
                <div className="opt-group">
                  <span className="opt-label">text</span>
                  <input
                    className="opt-input mono"
                    value={wmText}
                    onChange={(e) => setWmText(e.target.value)}
                    placeholder="@yourchannel"
                    aria-label="watermark word"
                  />
                </div>
              )}
              {wmError && <p className="opt-hint">{wmError}</p>}
              {wmKind !== 'none' && (
                <p className="opt-hint">
                  bottom centre of every clip and ranking video — inside the bar at gameplay
                  framing, over the picture at reduced opacity otherwise; never over the captions
                </p>
              )}
            </div>
            {/* At podcast framing the crop fills the canvas and there is no
                bar for the list to sit in, so it is drawn over the top of
                the picture (owner's decision, E18-F03). Say so here, where
                the framing is chosen, not after the render. */}
            {mode === 'clips' && ranking && gameplayAmount === 0 && (
              <p className="opt-hint">
                at podcast framing the list sits over the top of the picture — gameplay framing gives it its own band
              </p>
            )}
          </section>

          {(running || Object.keys(stages).length > 0) && (
            <section className="deck">
              {(CHAIN_ORDER[chain] ?? CHAIN_ORDER.clips).filter((s) => stages[s] || running).map((name, i) => {
                const st = stages[name]
                const state = !st ? 'idle' : st.fraction >= 1 ? 'done' : 'live'
                return (
                  <div className={`deck-row ${state}`} key={name} style={{ animationDelay: `${i * 40}ms` }}>
                    <span className="deck-name mono">{STAGE_LABELS[name] ?? name.toUpperCase()}</span>
                    <div className="deck-bar">
                      <div
                        className={`deck-fill ${st && st.fraction < 0 ? 'indeterminate' : ''}`}
                        style={st && st.fraction >= 0 ? { width: `${Math.min(100, st.fraction * 100)}%` } : undefined}
                      />
                    </div>
                    <span className="deck-msg">{st?.message ?? ''}</span>
                  </div>
                )
              })}
              {running && (
                <div className="deck-cancel">
                  <button
                    className="btn-ghost"
                    onClick={() => {
                      setCancelling(true)
                      onCancel()
                    }}
                    disabled={cancelling}
                  >
                    {cancelling ? 'CANCELLING…' : '■ CANCEL'}
                  </button>
                </div>
              )}
            </section>
          )}

          {/* Warn-severity, so the amber half-led, not the error one: the
              job is still running and Cancel stays available above. */}
          {diskNotice && (
            <section className="error-block">
              <span className="led led-half" />
              {diskNotice}
            </section>
          )}

          {cancelled && !running && (
            <section className="error-block">
              <span className="led led-half" />
              Cancelled — the job kept its checkpoints. Resume it from the rail anytime.
            </section>
          )}

          {error && <ErrorPanel error={error} jobId={errorJobId} />}
        </div>

        {showConsole && (
          <aside className="console">
            <div className="console-head">
              <span className="led led-on" />
              <span className="console-title mono">LIVE FEED</span>
            </div>
            <div className="console-body mono" ref={consoleRef}>
              {log.length === 0 && <p className="console-empty">waiting for the pipeline to say something…</p>}
              {log.map((line) => (
                <p key={line.id} className="console-line">
                  <span className="console-time">{line.time}</span> {line.text}
                </p>
              ))}
            </div>
          </aside>
        )}
      </main>
    </div>
  )
}
