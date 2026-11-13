// A big button that opens the phone camera (or the photo gallery) and hands
// back the chosen photo. The real <input type="file"> is hidden, because file
// inputs are small and hard to style; the button clicks it for us.

import { useRef } from 'react'
import { unlockAudio } from '../audio/player'
import { Icon, type IconName } from './Icon'

interface Props {
  label: string
  icon: IconName
  camera: boolean // true = open the camera directly, false = choose from gallery
  variant: 'primary' | 'secondary'
  onPhoto: (file: File) => void
  big?: boolean
}

export function PhotoButton({ label, icon, camera, variant, onPhoto, big = false }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)

  function open() {
    unlockAudio() // this tap lets the explanation play out loud later (see audio/player.ts)
    inputRef.current?.click()
  }

  return (
    <>
      <button type="button" className={`btn btn-${variant} ${big ? 'btn-hero' : ''}`} onClick={open}>
        <Icon name={icon} size={big ? 48 : 30} />
        <span>{label}</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture={camera ? 'environment' : undefined}
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = '' // so choosing the same photo again still triggers onChange
          if (file) onPhoto(file)
        }}
      />
    </>
  )
}
