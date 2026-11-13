// Shown while a photo is being read (usually 5-10 seconds, sometimes ~25).
// An animated "scanning" picture plus three steps, so the wait feels shorter.
// The steps move on a timer: the server doesn't report progress, so they are
// a friendly guide to what's happening rather than an exact measurement.

import { useEffect, useState } from 'react'
import type { Strings } from '../i18n'

const STEP_TIMES = [0, 2500, 8000] // ms after which each step becomes the active one

export function Loading({ t, showSteps = true }: { t: Strings; showSteps?: boolean }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const started = Date.now()
    const timer = window.setInterval(() => setElapsed(Date.now() - started), 250)
    return () => window.clearInterval(timer)
  }, [])

  const steps = [t.stepSending, t.stepReading, t.stepSpeaking]
  const active = STEP_TIMES.filter((time) => elapsed >= time).length - 1

  return (
    <div className="screen loading-screen" role="status" aria-live="polite">
      <div className="scanner" aria-hidden="true">
        <div className="scanner-paper">
          <i />
          <i />
          <i />
          <i />
          <i />
        </div>
        <div className="scanner-line" />
      </div>
      <p className="loading-title">{t.pleaseWait}</p>
      {showSteps && (
        <ol className="steps">
          {steps.map((label, index) => (
            <li key={label} className={index < active ? 'step-done' : index === active ? 'step-active' : ''}>
              <span className="step-dot" />
              {label}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
