// The app shell: picks which screen to show and holds the shared state.
//
// Screens are chosen by the URL hash, so the phone's Back button works:
//   #/            Home
//   #/history     History
//   #/doc/<id>    Result for one document

import { useEffect, useState } from 'react'
import { ApiError, getDocument, scanDocument, type ErrorKind, type Language, type ScannedDocument } from './api'
import { STRINGS } from './i18n'
import { shrinkPhoto } from './photo'
import { History } from './screens/History'
import { Home } from './screens/Home'
import { Loading } from './screens/Loading'
import { Result } from './screens/Result'

type Route = { name: 'home' } | { name: 'history' } | { name: 'doc'; id: string }

function parseRoute(hash: string): Route {
  const docMatch = hash.match(/^#\/doc\/([0-9a-f]+)$/)
  if (docMatch) return { name: 'doc', id: docMatch[1] }
  if (hash === '#/history') return { name: 'history' }
  return { name: 'home' }
}

// The chosen language is remembered on this phone. Storage can fail (private
// mode), so every access is wrapped in try/catch and English is the default.
function loadLanguage(): Language {
  try {
    const saved = localStorage.getItem('odhu-language')
    if (saved === 'kn-IN' || saved === 'hi-IN' || saved === 'en-IN') return saved
  } catch {
    // ignore
  }
  return 'en-IN'
}

function saveLanguage(language: Language) {
  try {
    localStorage.setItem('odhu-language', language)
  } catch {
    // ignore
  }
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash))
  const [language, setLanguage] = useState<Language>(loadLanguage)
  const [docs, setDocs] = useState<Record<string, ScannedDocument>>({}) // documents we've already loaded
  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState<ErrorKind | null>(null)
  const [autoplayId, setAutoplayId] = useState<string | null>(null) // play the explanation once, right after scanning
  const [loadError, setLoadError] = useState<ErrorKind | null>(null)

  const t = STRINGS[language]

  useEffect(() => {
    const onHashChange = () => {
      setRoute(parseRoute(window.location.hash))
      setLoadError(null) // a new screen starts without the old screen's error
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    document.documentElement.lang = language.slice(0, 2)
  }, [language])

  // Opening #/doc/<id> directly (from History, or after a page refresh): fetch it.
  const openId = route.name === 'doc' ? route.id : null
  useEffect(() => {
    if (!openId || docs[openId]) return
    getDocument(openId)
      .then((doc) => setDocs((all) => ({ ...all, [doc.id]: doc })))
      .catch((e) => setLoadError(e instanceof ApiError ? e.kind : 'generic'))
  }, [openId, docs])

  function changeLanguage(next: Language) {
    setLanguage(next)
    saveLanguage(next)
  }

  function rememberDoc(doc: ScannedDocument) {
    setDocs((all) => ({ ...all, [doc.id]: doc }))
  }

  async function handlePhoto(file: File) {
    setScanError(null)
    setScanning(true)
    try {
      const photo = await shrinkPhoto(file)
      const doc = await scanDocument(photo, language)
      rememberDoc(doc)
      setAutoplayId(doc.id)
      window.location.hash = `#/doc/${doc.id}`
    } catch (error) {
      setScanError(error instanceof ApiError ? error.kind : 'generic')
      window.location.hash = '#/'
    } finally {
      setScanning(false)
    }
  }

  if (scanning) return <Loading t={t} />

  if (route.name === 'history') {
    return <History t={t} onLoaded={(list) => list.forEach(rememberDoc)} />
  }

  if (route.name === 'doc') {
    const doc = docs[route.id]
    if (doc) {
      return (
        <Result
          key={doc.id}
          t={t}
          language={language}
          doc={doc}
          autoplay={autoplayId === doc.id}
          onAutoplayed={() => setAutoplayId(null)}
          onPhoto={handlePhoto}
          onDocChange={rememberDoc}
        />
      )
    }
    if (!loadError) return <Loading t={t} showSteps={false} />
    // Couldn't load it: fall through to Home with the error shown.
  }

  return (
    <Home
      t={t}
      language={language}
      onLanguage={changeLanguage}
      onPhoto={handlePhoto}
      error={scanError ?? (route.name === 'doc' ? loadError : null)}
    />
  )
}
