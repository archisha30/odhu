// Home: one big "Scan" button, a gallery button, the language choice and History.

import type { ErrorKind, Language } from '../api'
import { Icon } from '../components/Icon'
import { PhotoButton } from '../components/PhotoButton'
import { TopBar } from '../components/TopBar'
import type { Strings } from '../i18n'

interface Props {
  t: Strings
  language: Language
  onLanguage: (language: Language) => void
  onPhoto: (file: File) => void
  error: ErrorKind | null
}

export function Home({ t, language, onLanguage, onPhoto, error }: Props) {
  return (
    <div className="screen">
      <TopBar t={t} showHome={false} />
      <main className="content home">
        <section className="hero fade-up">
          <div className="hero-art" aria-hidden="true">
            <span className="hero-paper" />
            <span className="hero-wave" />
          </div>
          <p className="tagline">{t.tagline}</p>
        </section>

        {error && (
          <div className="banner banner-error fade-up" role="alert">
            <Icon name="alert" />
            <span>{t.errors[error]}</span>
          </div>
        )}

        <div className="stack fade-up delay-1">
          <PhotoButton label={t.scan} icon="camera" camera variant="primary" big onPhoto={onPhoto} />
          <PhotoButton label={t.gallery} icon="gallery" camera={false} variant="secondary" onPhoto={onPhoto} />
        </div>

        <fieldset className="lang fade-up delay-2">
          <legend>{t.language}</legend>
          <div className="lang-options">
            <LanguageOption value="kn-IN" label="ಕನ್ನಡ" current={language} onChange={onLanguage} />
            <LanguageOption value="hi-IN" label="हिंदी" current={language} onChange={onLanguage} />
            <LanguageOption value="en-IN" label="English" current={language} onChange={onLanguage} />
          </div>
        </fieldset>

        <a className="btn btn-ghost fade-up delay-3" href="#/history">
          <Icon name="history" />
          <span>{t.history}</span>
          <span className="push-right">
            <Icon name="chevron" size={24} />
          </span>
        </a>
      </main>
    </div>
  )
}

function LanguageOption(props: {
  value: Language
  label: string
  current: Language
  onChange: (language: Language) => void
}) {
  const selected = props.value === props.current
  return (
    <label className={`lang-option ${selected ? 'lang-selected' : ''}`}>
      <input
        type="radio"
        name="language"
        value={props.value}
        checked={selected}
        onChange={() => props.onChange(props.value)}
      />
      <span>{props.label}</span>
    </label>
  )
}
