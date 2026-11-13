// The "Ask a question" button. Tap once to start recording, tap again to stop.
// It's a wide pill: easy to hit, and short enough to leave room for the document.
// While recording it turns red and fills up to show how much of the 30 seconds is used.

import { MAX_SECONDS, useRecorder } from '../audio/useRecorder'
import type { Strings } from '../i18n'
import { Icon } from './Icon'

interface Props {
  t: Strings
  busy: boolean // waiting for an answer: don't allow a new recording yet
  onRecorded: (wav: Blob) => void
}

export function MicButton({ t, busy, onRecorded }: Props) {
  const { state, seconds, problem, start, stop } = useRecorder(onRecorded)
  const recording = state === 'recording'
  const disabled = busy || state === 'processing'
  const left = Math.max(0, Math.ceil(MAX_SECONDS - seconds))
  const progress = Math.min(1, seconds / MAX_SECONDS) // 0..1, drives the fill

  const hint = recording ? t.recording : problem === 'denied' ? t.micDenied : problem === 'unsupported' ? t.micUnsupported : problem === 'too-short' ? t.tooShort : problem === 'failed' ? t.errors.generic : t.askHint

  return (
    <div className="mic-area">
      <button
        type="button"
        className={`mic ${recording ? 'mic-recording' : ''}`}
        style={{ '--progress': progress } as React.CSSProperties}
        onClick={recording ? stop : start}
        disabled={disabled}
        aria-label={recording ? t.done : t.ask}
      >
        <Icon name={recording ? 'stop' : 'mic'} size={32} />
        <span className="mic-label">{recording ? t.done : t.ask}</span>
        {recording && <span className="mic-timer">0:{String(left).padStart(2, '0')}</span>}
      </button>
      <p className={`mic-hint ${problem && !recording ? 'mic-hint-problem' : ''}`} aria-live="polite">
        {hint}
      </p>
    </div>
  )
}
