import { useCallback, useEffect, useRef, useState } from 'react'
import { openUrl } from '@tauri-apps/plugin-opener'
import { api } from '../api'
import { hardwareLabel, sixtyMinEstimate } from '../hw'
import type { HardwareProfile } from '../types'
import SetupModels from './SetupModels'

/**
 * Three beats: what this is → pick the brain (Gemini key or local Ollama) →
 * go. The optional Instagram feedback module gets its own guided flow later
 * (Settings → Connect Instagram), so first-run stays under a minute.
 *
 * The Continue gate is deliberate (PRD §4.2, D-15): one of the two brains
 * is a contract, not friction to remove. E1-F02's job is that the gate
 * LEADS THROUGH — both doors prove they work before opening (a verified
 * key, a chat-capable Ollama), and a closed door says what to do next.
 */

interface Props {
  onDone: () => void
}

type KeyState = 'idle' | 'checking' | 'verified' | 'unverified' | 'rejected'

const PULL_CMD = 'ollama pull llama3.1:8b'

export default function Onboarding({ onDone }: Props) {
  const [step, setStep] = useState(0)
  const [key, setKey] = useState('')
  const [keyState, setKeyState] = useState<KeyState>('idle')
  const [keyReason, setKeyReason] = useState<string | null>(null)
  const [keyError, setKeyError] = useState<string | null>(null)
  const [ollama, setOllama] = useState<{ running: boolean; models: string[] } | null>(null)
  const [copied, setCopied] = useState(false)
  // undefined = still asking; null = probe failed (line is omitted, §5.9)
  const [hw, setHw] = useState<HardwareProfile | null | undefined>(undefined)
  const checkingRef = useRef(false)

  // The profile is a file the shell just reads. Only when no file exists
  // yet (a fresh machine) does onboarding trigger the ONE deliberate
  // probe - never on a timer, never per view (T-08's poll lesson; the
  // probe is a uv one-shot with nvidia-smi's 20 s worst case inside).
  useEffect(() => {
    let disposed = false
    api
      .hardwareProfile()
      .then((p) => {
        if (disposed) return undefined
        if (p) {
          setHw(p)
          return undefined
        }
        return api.probeHardware().then((fresh) => {
          if (!disposed) setHw(fresh)
        })
      })
      .catch(() => {
        if (!disposed) setHw(null)
      })
    return () => {
      disposed = true
    }
  }, [])

  // Re-check on demand and on window focus — never on a timer (T-08's 2 s
  // poll stacked subprocesses faster than they answered; a focus event
  // fires exactly when the user comes back from installing Ollama in
  // another window, which is better timing than any interval). Cost when
  // the answer is "no": one curl with a 3 s cap per focus or press; the
  // in-flight guard keeps a focus flood from stacking curls.
  const refreshOllama = useCallback(() => {
    if (checkingRef.current) return
    checkingRef.current = true
    api
      .checkOllama()
      .then(setOllama)
      .catch(() => setOllama({ running: false, models: [] }))
      .finally(() => {
        checkingRef.current = false
      })
  }, [])

  useEffect(() => {
    refreshOllama()
    window.addEventListener('focus', refreshOllama)
    return () => window.removeEventListener('focus', refreshOllama)
  }, [refreshOllama])

  // Embedding-only Ollama must not read as ready: scoring needs a chat
  // model, and OllamaClient fails on an empty list — after the expensive
  // stages already ran.
  const chatModels = (ollama?.models ?? []).filter((m) => !m.includes('embed'))
  const ollamaReady = !!ollama?.running && chatModels.length > 0
  const keySaved = keyState === 'verified' || keyState === 'unverified'

  async function saveKey() {
    if (!key.trim() || keyState === 'checking') return
    setKeyState('checking')
    setKeyError(null)
    try {
      const res = await api.saveGeminiKey(key)
      setKeyState(res.status)
      setKeyReason(res.reason ?? null)
    } catch (err) {
      // the write itself failed — nothing on disk, so the gate must not open
      setKeyState('idle')
      setKeyError(String(err))
    }
  }

  function copyPull() {
    navigator.clipboard
      .writeText(PULL_CMD)
      .then(() => setCopied(true))
      .catch(() => {})
  }

  return (
    <div className="onboarding">
      <div className="grain" />
      {step === 0 && (
        <section className="ob-step" key="s0">
          <p className="ob-kicker">Alias Studio</p>
          <h1 className="ob-title">
            THE CLIPPER
            <br />
            THAT SHOWS
            <br />
            ITS WORK<span className="amber">.</span>
          </h1>
          <p className="ob-body">
            Long video in, vertical clips out. Speech, laughter, speakers, and camera
            moves are all computed <em>on this machine</em>, and your video is never
            uploaded. Scoring sends short transcript excerpts and a few still frames
            to the model you pick — or nothing at all in Ollama mode. Every network
            call the app can make is named in Settings → Privacy, and every score
            comes with the full audit trail of how it was made.
          </p>
          <button className="btn-primary" onClick={() => setStep(1)}>
            Set it up
          </button>
        </section>
      )}
      {step === 1 && (
        <section className="ob-step" key="s1">
          <p className="ob-kicker">01 / the scoring brain</p>
          <h2 className="ob-h2">Pick how moments get judged</h2>
          <p className="ob-fine">
            Without a model that judges content, a score would be a number pretending
            to be a judgment — so one of these two is required. Both are free.
          </p>
          <div className="ob-cards">
            <div className={`ob-card ${keySaved ? 'done' : ''}`}>
              <h3>Gemini key <span className="chip chip-amber">recommended</span></h3>
              <p>
                Bring your own key: sign in at aistudio.google.com, press{' '}
                <em>Get API key</em>, paste it here. Google's free tier works —
                rate-limited (the run paces itself), and Google may use free-tier
                prompts to improve its products. The paid tier costs roughly{' '}
                <span className="mono">$1.20</span> per hour of source video.
                Best humor and shock judgment.
              </p>
              <button
                className="btn-ghost"
                onClick={() => openUrl('https://aistudio.google.com/apikey').catch(() => {})}
              >
                ↗ get a key (aistudio.google.com)
              </button>
              <div className="ob-key-row">
                <input
                  type="password"
                  placeholder="AIza…"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && saveKey()}
                />
                <button
                  className="btn-secondary"
                  onClick={saveKey}
                  disabled={!key.trim() || keyState === 'checking'}
                >
                  {keyState === 'checking'
                    ? 'Checking…'
                    : keyState === 'verified'
                      ? 'Verified ✓'
                      : keyState === 'unverified'
                        ? 'Saved'
                        : 'Save & verify'}
                </button>
              </div>
              {/* A refusal is not one thing (the gate closes for all of
                  them, but the next step differs): SERVICE_DISABLED means
                  the key is fine and the API just is not enabled on its
                  project; other non-invalid reasons usually mean console
                  restrictions. Calling those "a typo" is the dead end one
                  layer down. */}
              {keyState === 'rejected' && (
                <p className="ob-fine">
                  <span className="led led-err" />{' '}
                  {keyReason === 'SERVICE_DISABLED'
                    ? 'The key itself is fine, but its Google Cloud project has the Generative Language API disabled. Enable it in the Google console — or make a key at aistudio.google.com, which enables it for you. Nothing was saved.'
                    : keyReason && keyReason !== 'API_KEY_INVALID'
                      ? `Google refused the key (${keyReason}). The key itself may be fine — check its restrictions in the Google console. Nothing was saved.`
                      : 'Google rejected that key — a typo, or it was revoked. Nothing was saved; fix it and try again.'}
                </p>
              )}
              {keyState === 'unverified' && (
                <p className="ob-fine">
                  <span className="led led-half" /> Saved, but Google could not be
                  reached to verify it (offline?). It will be checked on first use.
                </p>
              )}
              {keyError && (
                <p className="ob-fine">
                  <span className="led led-err" /> Could not save the key: {keyError}
                </p>
              )}
            </div>
            <div className={`ob-card ${ollamaReady ? '' : 'dim'}`}>
              <h3>
                Ollama{' '}
                <span
                  className={`led ${ollamaReady ? 'led-on' : ollama?.running ? 'led-half' : 'led-off'}`}
                />
              </h3>
              {ollama === null ? (
                <p>Checking…</p>
              ) : ollamaReady ? (
                <p>
                  Running locally ({chatModels.slice(0, 2).join(', ')}). Zero cost,
                  fully offline — scores are labeled "local estimate" because small
                  models judge humor less reliably.
                </p>
              ) : ollama.running ? (
                <>
                  <p>
                    Running — but it has no chat model yet
                    {ollama.models.length > 0 ? ' (only embedding models are installed)' : ''}
                    , so it cannot judge anything. Pull the recommended one
                    (~<span className="mono">4.9 GB</span>) in a terminal, then check
                    again:
                  </p>
                  <p className="mono">
                    {PULL_CMD}{' '}
                    <button className="btn-ghost" onClick={copyPull}>
                      {copied ? 'copied ✓' : 'copy'}
                    </button>
                  </p>
                </>
              ) : (
                <>
                  <p>
                    Not installed (or not running). Free, no limits, fully offline —
                    three steps: install Ollama, run{' '}
                    <span className="mono">{PULL_CMD}</span> (~
                    <span className="mono">4.9 GB</span>) in a terminal, come back
                    here.
                  </p>
                  <button
                    className="btn-ghost"
                    onClick={() => openUrl('https://ollama.com/download').catch(() => {})}
                  >
                    ⇩ get Ollama (ollama.com)
                  </button>
                </>
              )}
              {ollama !== null && !ollamaReady && (
                <button className="btn-ghost" onClick={refreshOllama}>
                  ↻ check again
                </button>
              )}
            </div>
          </div>
          <p className="ob-fine">
            You can switch per-run. Everything else — transcription, laughter
            detection, speaker tracking, rendering — is local either way.
          </p>
          {/* The gate. Deliberate (PRD §4.2, D-15) — do not remove, do not
              add a skip. Both sides now mean "proven to work": a rejected
              key never sets keySaved, and Ollama without a chat model is
              not ready (it would fail at scoring, after the expensive
              stages already ran — the exact late failure the key check
              exists to prevent). */}
          <button
            className="btn-primary"
            onClick={() => setStep(2)}
            disabled={!keySaved && !ollamaReady}
          >
            Continue
          </button>
        </section>
      )}
      {step === 2 && (
        <section className="ob-step" key="s2">
          <p className="ob-kicker">02 / one honest warning</p>
          <h2 className="ob-h2">First run downloads the models</h2>
          <p className="ob-body">
            The open speech and audio models land once in{' '}
            <span className="mono">~/.publikclip</span> — real sizes below, shown{' '}
            <em>before</em> anything downloads. Grab them now, or skip: they
            fetch during your first job instead. Either way every download resumes
            where it stopped, every stage checkpoints, and the progress bar never
            lies to you.
          </p>
          <SetupModels />
          {/* The honest hardware sentence (E1-F03): the GPU or its absence,
              the forced device when PUBLIKCLIP_DEVICE is set, and an
              estimate ONLY once one has been measured — never invented. */}
          {hw !== null && (
            <p className="ob-fine mono">
              {hw === undefined
                ? 'checking hardware…'
                : `${hardwareLabel(hw)} — ${
                    sixtyMinEstimate(hw) != null
                      ? `a 60 min video ≈ ${sixtyMinEstimate(hw)} min`
                      : /* not "first run" — a changed configuration also
                           voids the estimate (F7) */
                        'no estimate for this setup yet; measured from your first full run'
                  }`}
            </p>
          )}
          <button className="btn-primary" onClick={onDone}>
            Open the studio
          </button>
        </section>
      )}
    </div>
  )
}
