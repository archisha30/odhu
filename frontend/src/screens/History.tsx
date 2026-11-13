// History: every document scanned before, newest first. Tap one to open it.

import { useEffect, useState } from 'react'
import { ApiError, listDocuments, type ErrorKind, type ScannedDocument } from '../api'
import { Icon, type IconName } from '../components/Icon'
import { TopBar } from '../components/TopBar'
import { formatDate, formatRupees, type Strings } from '../i18n'

const TYPE_ICONS: Record<string, IconName> = {
  electricity_bill: 'bolt',
  bank_letter: 'bank',
  official_notice: 'notice',
}

export function History({ t, onLoaded }: { t: Strings; onLoaded: (docs: ScannedDocument[]) => void }) {
  const [docs, setDocs] = useState<ScannedDocument[] | null>(null)
  const [error, setError] = useState<ErrorKind | null>(null)

  function load() {
    setError(null)
    listDocuments()
      .then((list) => {
        setDocs(list)
        onLoaded(list) // so opening one doesn't need another request
      })
      .catch((e) => setError(e instanceof ApiError ? e.kind : 'generic'))
  }

  // Load once when the screen opens.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, [])

  return (
    <div className="screen">
      <TopBar t={t} showHome />
      <main className="content history-screen">
        <h1 className="page-title">{t.history}</h1>

        {error && (
          <div className="banner banner-error" role="alert">
            <Icon name="alert" />
            <span>{t.errors[error]}</span>
            <button type="button" className="btn btn-small btn-secondary" onClick={load}>
              <Icon name="retry" size={22} />
              <span>{t.tryAgain}</span>
            </button>
          </div>
        )}

        {!docs && !error && (
          <div className="history-list" aria-hidden="true">
            <div className="skeleton" />
            <div className="skeleton" />
            <div className="skeleton" />
          </div>
        )}

        {docs && docs.length === 0 && <p className="empty">{t.historyEmpty}</p>}

        {docs && docs.length > 0 && (
          <ul className="history-list">
            {docs.map((doc, index) => (
              <li key={doc.id} className="fade-up" style={{ animationDelay: `${Math.min(index, 8) * 50}ms` }}>
                <HistoryCard t={t} doc={doc} />
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  )
}

function HistoryCard({ t, doc }: { t: Strings; doc: ScannedDocument }) {
  const facts = doc.document
  const ok = doc.status === 'ok' && facts
  const icon: IconName = ok ? TYPE_ICONS[facts.document_type] ?? 'notice' : 'alert'
  const title = ok ? t.types[facts.document_type] : doc.status === 'unclear' ? t.unclearTitle : t.unsupportedTitle

  return (
    <a className={`history-card ${ok ? '' : 'history-card-muted'}`} href={`#/doc/${doc.id}`}>
      <span className="doc-icon">
        <Icon name={icon} size={28} />
      </span>
      <span className="history-main">
        <span className="history-title">{title}</span>
        {ok && facts.sender && <span className="history-sender">{facts.sender}</span>}
        {ok && (facts.amount_due !== null || facts.due_date) && (
          <span className="history-facts">
            {facts.amount_due !== null && <b>{formatRupees(facts.amount_due)}</b>}
            {facts.due_date && <span>{formatDate(facts.due_date, t)}</span>}
          </span>
        )}
      </span>
      <Icon name="chevron" size={24} />
    </a>
  )
}
