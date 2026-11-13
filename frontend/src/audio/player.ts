// One shared <audio> element for the whole app.
//
// Why only one? Phone browsers (especially iPhone Safari) only allow sound that
// starts from a tap. A scan takes ~10 seconds, so by the time the explanation is
// ready, the tap is long gone. The trick: during the tap we "unlock" this element
// by playing a tiny silent clip. After that, the same element may play later.

const audio = new Audio()
audio.preload = 'auto'

// 0.1 s of silence as a WAV data URL, used only to unlock the element.
const SILENCE =
  'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA='

let currentUrl: string | null = null
const listeners = new Set<(url: string | null) => void>()

function setCurrent(url: string | null) {
  currentUrl = url
  listeners.forEach((listener) => listener(url))
}

audio.addEventListener('ended', () => setCurrent(null))
audio.addEventListener('pause', () => setCurrent(null))

/** Call this inside a tap handler, before any slow work. */
export function unlockAudio(): void {
  if (currentUrl) return // already playing something real
  audio.src = SILENCE
  audio.play().catch(() => {
    // Unlocking failed; play() later may need another tap. That's handled by the UI.
  })
}

/** Play a URL. Resolves to false if the browser blocked it (the UI then shows a big Listen button). */
export async function playAudio(url: string): Promise<boolean> {
  audio.pause()
  audio.src = url
  try {
    await audio.play()
    setCurrent(url)
    return true
  } catch {
    setCurrent(null)
    return false
  }
}

export function stopAudio(): void {
  audio.pause()
}

/** Get told whenever the playing URL changes (null = nothing playing). Returns an unsubscribe function. */
export function onPlayingChange(listener: (url: string | null) => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function playingUrl(): string | null {
  return currentUrl
}
