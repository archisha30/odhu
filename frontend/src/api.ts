// All calls to our FastAPI backend live here. The Vite dev server forwards
// /api/* to http://localhost:8000 (see vite.config.ts).

export type Language = 'kn-IN' | 'hi-IN' | 'en-IN'
export type DocumentType = 'electricity_bill' | 'bank_letter' | 'official_notice' | 'other' | 'unreadable'

export interface ExtractedDocument {
  legibility: 'clear' | 'partly_readable' | 'unreadable'
  document_type: DocumentType
  sender: string | null
  amount_due: number | null
  due_date: string | null // "YYYY-MM-DD"
  account_holder_name: string | null
  key_points: string[]
  confidence: number
}

export interface Question {
  id: string
  created_at: string
  transcript: string // what the app heard
  language: Language | null // the language the person spoke; the answer is in it too
  answer: string
  audio_url: string | null
}

export interface ScannedDocument {
  id: string
  created_at: string
  language: Language
  status: 'ok' | 'unclear' | 'unsupported'
  document: ExtractedDocument | null
  explanation: string
  audio_url: string | null
  questions: Question[]
  explanations: Explanation[] // the explanation in other languages, made when asked for
}

export interface Explanation {
  language: Language
  explanation: string
  audio_url: string | null
}

// The kinds of error the screens show different messages for.
export type ErrorKind = 'network' | 'busy' | 'generic'

export class ApiError extends Error {
  kind: ErrorKind
  constructor(kind: ErrorKind, message: string) {
    super(message)
    this.kind = kind
  }
}

// fetch() + turn every failure into an ApiError with a simple "kind".
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, options)
  } catch {
    throw new ApiError('network', 'Could not reach the server')
  }
  if (!response.ok) {
    let detail = response.statusText
    try {
      detail = (await response.json()).detail ?? detail
    } catch {
      // the body wasn't JSON; keep the status text
    }
    const kind: ErrorKind = response.status >= 500 ? 'busy' : 'generic'
    throw new ApiError(kind, String(detail))
  }
  return response.json() as Promise<T>
}

export function scanDocument(photo: Blob, language: Language): Promise<ScannedDocument> {
  const form = new FormData()
  form.append('image', photo, photo.type === 'image/png' ? 'photo.png' : 'photo.jpg')
  form.append('language', language)
  return request('/api/documents', { method: 'POST', body: form })
}

// `language` is the language the person is listening in: a hint for the speech
// recogniser. If they speak another language, the answer comes back in that one.
export function askQuestion(documentId: string, wav: Blob, language: Language): Promise<Question> {
  const form = new FormData()
  form.append('audio', wav, 'question.wav')
  form.append('language', language)
  return request(`/api/documents/${documentId}/ask`, { method: 'POST', body: form })
}

// The document's explanation in another language (made once on the server, then saved).
export function getExplanation(documentId: string, language: Language): Promise<Explanation> {
  return request(`/api/documents/${documentId}/explanations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ language }),
  })
}

export function getDocument(documentId: string): Promise<ScannedDocument> {
  return request(`/api/documents/${documentId}`)
}

export function listDocuments(): Promise<ScannedDocument[]> {
  return request('/api/documents')
}
