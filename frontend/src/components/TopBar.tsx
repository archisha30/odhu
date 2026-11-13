// The coloured bar at the top of every screen: app name, a quick "A+" button for
// large text, plus a Home button on every screen except Home itself.

import type { Strings } from '../i18n'
import { useTextSize } from '../textSizeContext'
import { Icon } from './Icon'

export function TopBar({ t, showHome }: { t: Strings; showHome: boolean }) {
  const { big, setBig } = useTextSize()
  const textToggle = (labelled: boolean) => (
    <button
      type="button"
      className={`text-toggle ${big ? 'text-toggle-on' : ''} ${labelled ? 'text-toggle-labelled' : ''}`}
      onClick={() => setBig(!big)}
      aria-pressed={big}
      aria-label={`${t.textSize}: ${big ? t.largeText : t.normalText}`}
    >
      <span aria-hidden="true">
        A<span className="text-toggle-plus">+</span>
      </span>
      {labelled && <b aria-hidden="true">{t.textSize}</b>}
    </button>
  )

  return (
    <header className="topbar">
      {/* Left: Home button, or (on Home itself) the labelled text-size button. */}
      {showHome ? (
        <a className="topbar-home" href="#/">
          <Icon name="back" size={26} />
          <span>{t.home}</span>
        </a>
      ) : (
        textToggle(true)
      )}
      <div className="topbar-right">
        {showHome && textToggle(false)}
        <a className="brand" href="#/" aria-label="Odhu">
          <span className="brand-mark">ಓ</span>
          <span className="brand-name">Odhu</span>
        </a>
      </div>
    </header>
  )
}
