import { useEffect, useState } from 'react'
import type { ResumeInfo } from '../types'
import { STAGE_LABELS } from './Studio'

/* T-14 (E14-F02): choosing where a resume restarts. The first option is
 * plain resume — exactly what clicking the rail always did — so a user who
 * does not choose changes nothing. A failed job arrives with its failed
 * stage preselected (T-13's error.json); a finished job preselects
 * nothing, because it must not pretend a failure happened. The cost line
 * under a chosen stage is measured data (T-10's medians × this job's
 * duration) and simply absent when this machine has no measurement —
 * never an invented number (§5.9). */

interface Props {
  title: string
  /** null while the one-shot is still answering */
  info: ResumeInfo | null
  onGo: (fromStage: string | null) => void
  onClose: () => void
}

function minutes(sec: number): string {
  if (sec < 60) return 'under a minute'
  return `about ${Math.round(sec / 60)} min`
}

export default function ResumePicker({ title, info, onGo, onClose }: Props) {
  const [choice, setChoice] = useState<string | null>(null)
  const [seeded, setSeeded] = useState(false)

  useEffect(() => {
    if (info && !seeded) {
      setChoice(info.default_stage)
      setSeeded(true)
    }
  }, [info, seeded])

  const chosen = info?.stages.find((s) => s.name === choice) ?? null

  return (
    <div className="modal-scrim" onClick={onClose}>
      <div className="modal resume-picker" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <p className="audit-kicker">RESUME · {title}</p>
          <button className="btn-ghost" onClick={onClose}>
            close ✕
          </button>
        </header>
        <button
          className={`resume-option ${choice === null ? 'opt-on' : ''}`}
          onClick={() => setChoice(null)}
        >
          continue from where it stopped
        </button>
        {info === null && <p className="resume-loading mono">reading this job…</p>}
        {info !== null && info.stages.length > 0 && (
          <>
            <p className="rail-label">OR REDO A STEP AND EVERYTHING AFTER IT</p>
            <div className="resume-stages">
              {info.stages.map((stage) => (
                <button
                  key={stage.name}
                  className={`resume-option ${choice === stage.name ? 'opt-on' : ''}`}
                  onClick={() => setChoice(stage.name)}
                >
                  <span>{STAGE_LABELS[stage.name] ?? stage.name.toUpperCase()}</span>
                  <span className={`resume-status resume-status-${stage.status}`}>
                    {stage.status}
                  </span>
                </button>
              ))}
            </div>
            {/* measured, or silent — a picker that guesses at hours is a trap */}
            {chosen && chosen.estimate_sec != null && (
              <p className="resume-cost mono">
                re-running from {STAGE_LABELS[chosen.name] ?? chosen.name} takes{' '}
                {minutes(chosen.estimate_sec)} on this machine
              </p>
            )}
          </>
        )}
        <footer className="resume-foot">
          <button className="btn-primary" onClick={() => onGo(choice)}>
            RESUME
          </button>
        </footer>
      </div>
    </div>
  )
}
