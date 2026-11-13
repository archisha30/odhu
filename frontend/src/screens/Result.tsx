// Result: what the document says, read out loud, plus voice questions.

import { useEffect, useRef, useState } from 'react'
import {
  ApiError,
  askQuestion,
  getExplanation,
  type ErrorKind,
  type Explanation,
  type Language,
  type ScannedDocument,
} from '../api'
import { playAudio, unlockAudio } from '../audio/player'
import { AudioButton } from '../components/AudioButton'
import { Icon, type IconName } from '../components/Icon'
import { MicButton } from '../components/MicButton'
import { PhotoButton } from '../components/PhotoButton'
import { TopBar } from '../components/TopBar'
import { daysUntil, formatDayMonth, formatRupees, type Strings } from '../i18n'

const TYPE_ICONS: Record<string, IconName> = {
  electricity_bill: 'bolt',
  bank_letter: 'bank',
  official_notice: 'notice',
  other: 'notice',
  unreadable: 'alert',
}

const LANGUAGE_LABELS: [Language, string][] = [
  ['kn-IN', 'ಕನ್ನಡ'],
  ['hi-IN', 'हिंदी'],
  ['en-IN', 'English'],
]

interface Props {
  t: Strings
  language: Language // the language chosen on Home: the document opens in this one
  doc: ScannedDocument
  autoplay: boolean // true right after scanning; false when opened from History
  onAutoplayed: () => void // called once auto-play was tried, so it doesn't repeat
  onPhoto: (file: File) => void
  onDocChange: (doc: ScannedDocument) => void
}

export function Result({ t, language, doc, autoplay, onAutoplayed, onPhoto, onDocChange }: Props) {
  // The language the explanation is shown and spoken in. Starts as the Home-screen language.
  const [hearLang, setHearLang] = useState<Language>(language)
  const [preparing, setPreparing] = useState(false) // making the explanation in a new language
  const [explainError, setExplainError] = useState<ErrorKind | null>(null)
  // If the browser blocks auto-play, we make the Listen button pulse instead.
  const [needsTap, setNeedsTap] = useState(false)
  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState<ErrorKind | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  // Every language we already have the explanation in.
  const versions: Partial<Record<Language, Explanation>> = {
    [doc.language]: { language: doc.language, explanation: doc.explanation, audio_url: doc.audio_url },
  }
  doc.explanations.forEach((e) => (versions[e.language] = e))
  const current = versions[hearLang]

  // Switch the explanation to another language; make it on the server if needed.
  async function chooseLanguage(next: Language, play: boolean) {
    setHearLang(next)
    setExplainError(null)
    const ready = versions[next]
    if (ready) {
      if (play && ready.audio_url) void playAudio(ready.audio_url)
      return
    }
    setPreparing(true)
    try {
      const made = await getExplanation(doc.id, next)
      onDocChange({ ...doc, explanations: [...doc.explanations, made] })
      if (play && made.audio_url) void playAudio(made.audio_url)
    } catch (error) {
      setExplainError(error instanceof ApiError ? error.kind : 'generic')
    } finally {
      setPreparing(false)
    }
  }

  useEffect(() => {
    if (autoplay && current?.audio_url) {
      playAudio(current.audio_url).then((played) => setNeedsTap(!played))
      onAutoplayed()
    }
    // An older document in another language: make it in the Home-screen language (no auto-play).
    if (!current) void chooseLanguage(hearLang, false)
    // Only when a new document opens, not on every re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc.id])

  async function handleRecorded(wav: Blob) {
    setAsking(true)
    setAskError(null)
    unlockAudio()
    // Scroll so the "thinking…" bubble is visible.
    requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }))
    try {
      // The answer comes back in whatever language the person spoke.
      const question = await askQuestion(doc.id, wav, hearLang)
      onDocChange({ ...doc, questions: [...doc.questions, question] })
      if (question.audio_url) void playAudio(question.audio_url)
    } catch (error) {
      setAskError(error instanceof ApiError ? error.kind : 'generic')
    } finally {
      setAsking(false)
      requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }))
    }
  }

  const hearIn = (
    <HearIn
      t={t}
      value={hearLang}
      disabled={preparing}
      onChange={(next) => {
        unlockAudio() // this tap allows the new explanation to play once it's ready
        void chooseLanguage(next, true)
      }}
    />
  )
  // The explanation text, a "getting it ready" note, or an error.
  const speech = preparing ? (
    <p className="speech-text speech-preparing" aria-live="polite">
      <span className="dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      {t.preparing}
    </p>
  ) : explainError ? (
    <div className="banner banner-error" role="alert">
      <Icon name="alert" />
      <span>{t.errors[explainError]}</span>
    </div>
  ) : current ? (
    <p className="speech-text fade-up delay-1" lang={hearLang}>
      {current.explanation}
    </p>
  ) : null
  const listen = !preparing && current?.audio_url ? <AudioButton url={current.audio_url} t={t} highlight={needsTap} /> : null

  if (doc.status !== 'ok' || !doc.document) {
    return <Problem t={t} doc={doc} hearIn={hearIn} speech={speech} listen={listen} onPhoto={onPhoto} />
  }

  const facts = doc.document
  return (
    <div className="screen">
      <TopBar t={t} showHome />
      <main className="content result">
        <section className="doc-card fade-up">
          <div className="doc-type">
            <span className="doc-icon">
              <Icon name={TYPE_ICONS[facts.document_type] ?? 'notice'} size={32} />
            </span>
            <div>
              <h1>{t.types[facts.document_type]}</h1>
              {facts.sender && <p className="doc-sender">{facts.sender}</p>}
            </div>
          </div>

          {/* The amount and date come first, so they're visible without scrolling. */}
          {(facts.amount_due !== null || facts.due_date) && (
            <div className="facts">
              {facts.amount_due !== null && (
                <div className="fact fact-amount">
                  <span className="fact-label">{t.amountDue}</span>
                  <span className="fact-value">{formatRupees(facts.amount_due)}</span>
                </div>
              )}
              {facts.due_date && <DueDate t={t} isoDate={facts.due_date} />}
            </div>
          )}

          {listen}
          {hearIn}
        </section>

        {(facts.legibility === 'partly_readable' || facts.confidence < 0.8) && (
          <div className="banner banner-warn fade-up delay-1" role="note">
            <Icon name="alert" />
            <span>{t.checkPaper}</span>
          </div>
        )}

        {speech}

        {doc.questions.length > 0 && (
          <section className="chat" aria-label={t.ask}>
            {doc.questions.map((question) => (
              <div key={question.id} className="qa fade-up">
                <div className="bubble bubble-user" lang={question.language ?? undefined}>
                  <span className="bubble-label">{t.youAsked}</span>
                  {question.transcript || '…'}
                </div>
                <div className="bubble bubble-app" lang={question.language ?? doc.language}>
                  <p>{question.answer}</p>
                  {question.audio_url && <AudioButton url={question.audio_url} t={t} small />}
                </div>
              </div>
            ))}
          </section>
        )}

        {asking && (
          <div className="bubble bubble-app bubble-thinking fade-up" aria-live="polite">
            <span className="dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            {t.thinking}
          </div>
        )}
        {askError && (
          <div className="banner banner-error" role="alert">
            <Icon name="alert" />
            <span>{t.errors[askError]}</span>
          </div>
        )}
        <div ref={endRef} className="scroll-anchor" />
      </main>

      <footer className="dock">
        <MicButton t={t} busy={asking} onRecorded={handleRecorded} />
      </footer>
    </div>
  )
}

// "Hear it in: ಕನ್ನಡ | हिंदी | English"
function HearIn({ t, value, disabled, onChange }: { t: Strings; value: Language; disabled: boolean; onChange: (language: Language) => void }) {
  return (
    <div className="hear-in">
      <span className="hear-in-label">{t.hearIn}</span>
      <div className="lang-options hear-in-options" role="group" aria-label={t.hearIn}>
        {LANGUAGE_LABELS.map(([code, label]) => (
          <button
            key={code}
            type="button"
            className={`lang-option ${code === value ? 'lang-selected' : ''}`}
            aria-pressed={code === value}
            disabled={disabled}
            onClick={() => onChange(code)} // tapping the current language replays it (or retries after an error)
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}

function DueDate({ t, isoDate }: { t: Strings; isoDate: string }) {
  const days = daysUntil(isoDate)
  const badge = days < 0 ? t.overdue : days === 0 ? t.dueToday : t.daysLeft(days)
  const urgent = days <= 3
  return (
    <div className={`fact fact-date ${urgent ? 'fact-urgent' : ''}`}>
      <span className="fact-label">{t.dueDate}</span>
      <span className="fact-value">
        {formatDayMonth(isoDate, t)} <small className="fact-year">{isoDate.slice(0, 4)}</small>
      </span>
      <span className="badge">{badge}</span>
    </div>
  )
}

// The photo was unclear, or the document isn't one we support.
function Problem(props: {
  t: Strings
  doc: ScannedDocument
  hearIn: React.ReactNode
  speech: React.ReactNode
  listen: React.ReactNode
  onPhoto: (file: File) => void
}) {
  const { t, doc } = props
  return (
    <div className="screen">
      <TopBar t={t} showHome />
      <main className="content">
        <section className="problem fade-up">
          <span className="problem-icon">
            <Icon name="alert" size={48} />
          </span>
          <h1>{doc.status === 'unclear' ? t.unclearTitle : t.unsupportedTitle}</h1>
          {props.hearIn}
          {props.speech}
          {props.listen}
        </section>
        <div className="stack fade-up delay-1">
          <PhotoButton
            label={doc.status === 'unclear' ? t.retakePhoto : t.newScan}
            icon="camera"
            camera
            variant="primary"
            big
            onPhoto={props.onPhoto}
          />
        </div>
      </main>
    </div>
  )
}
