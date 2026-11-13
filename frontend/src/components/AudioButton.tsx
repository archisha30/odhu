// A big "Listen / Listen again" button. While its audio is playing, it turns
// into a "Stop" button with little animated sound bars.

import { useEffect, useState } from 'react'
import { onPlayingChange, playAudio, playingUrl, stopAudio } from '../audio/player'
import type { Strings } from '../i18n'
import { Icon } from './Icon'

interface Props {
  url: string
  t: Strings
  /** Pulse to draw attention, e.g. when the browser blocked auto-play. */
  highlight?: boolean
  small?: boolean
}

export function AudioButton({ url, t, highlight = false, small = false }: Props) {
  const [playing, setPlaying] = useState(playingUrl() === url)

  useEffect(() => onPlayingChange((current) => setPlaying(current === url)), [url])

  function toggle() {
    if (playing) stopAudio()
    else void playAudio(url)
  }

  return (
    <button
      type="button"
      className={`btn ${small ? 'btn-small' : ''} ${playing ? 'btn-playing' : 'btn-listen'} ${highlight && !playing ? 'pulse' : ''}`}
      onClick={toggle}
    >
      {playing ? <SoundBars /> : <Icon name="speaker" />}
      <span>{playing ? t.stop : highlight ? t.listen : t.listenAgain}</span>
    </button>
  )
}

function SoundBars() {
  return (
    <span className="sound-bars" aria-hidden="true">
      <i />
      <i />
      <i />
      <i />
    </span>
  )
}
