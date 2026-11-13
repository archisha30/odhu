// A React hook for "tap to start, tap to stop" voice recording.
// Recording stops by itself after MAX_SECONDS. The result is a WAV Blob.

import { useEffect, useRef, useState } from 'react'
import { stopAudio } from './player'
import { recordingToWav } from './wav'

export const MAX_SECONDS = 30
const MIN_SECONDS = 1 // shorter than this is almost certainly an accidental tap

export type RecorderState = 'idle' | 'recording' | 'processing'
export type RecorderProblem = 'denied' | 'unsupported' | 'too-short' | 'failed' | null

export function useRecorder(onFinished: (wav: Blob) => void) {
  const [state, setState] = useState<RecorderState>('idle')
  const [seconds, setSeconds] = useState(0)
  const [problem, setProblem] = useState<RecorderProblem>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const timerRef = useRef<number | undefined>(undefined)
  const onFinishedRef = useRef(onFinished)
  onFinishedRef.current = onFinished

  // If the screen closes mid-recording, release the microphone.
  useEffect(() => () => cleanup(), [])

  function cleanup() {
    window.clearInterval(timerRef.current)
    const recorder = recorderRef.current
    if (recorder) {
      recorder.onstop = null // the screen is closing: don't send this recording
      recorder.stream.getTracks().forEach((track) => track.stop())
      if (recorder.state !== 'inactive') recorder.stop()
    }
  }

  async function start() {
    setProblem(null)
    // Browsers only allow the microphone on https:// (or localhost) pages.
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setProblem('unsupported')
      return
    }
    stopAudio() // don't record the app's own voice
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      })
    } catch {
      setProblem('denied')
      return
    }

    const chunks: Blob[] = []
    const recorder = new MediaRecorder(stream)
    recorderRef.current = recorder
    const startedAt = Date.now()

    recorder.ondataavailable = (event) => chunks.push(event.data)
    recorder.onstop = async () => {
      window.clearInterval(timerRef.current)
      setSeconds(0) // empty the countdown ring
      stream.getTracks().forEach((track) => track.stop())
      recorderRef.current = null
      const duration = (Date.now() - startedAt) / 1000
      if (duration < MIN_SECONDS) {
        setProblem('too-short')
        setState('idle')
        return
      }
      setState('processing')
      try {
        const wav = await recordingToWav(new Blob(chunks, { type: recorder.mimeType }))
        onFinishedRef.current(wav)
      } catch {
        setProblem('failed')
      }
      setState('idle')
    }

    recorder.start()
    setSeconds(0)
    setState('recording')
    // Update the countdown, and stop automatically at the limit.
    timerRef.current = window.setInterval(() => {
      const elapsed = (Date.now() - startedAt) / 1000
      setSeconds(elapsed)
      if (elapsed >= MAX_SECONDS) stop()
    }, 100)
  }

  function stop() {
    const recorder = recorderRef.current
    if (recorder && recorder.state === 'recording') recorder.stop()
  }

  return { state, seconds, problem, start, stop }
}
