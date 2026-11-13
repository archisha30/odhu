// The shared "large text" setting. The provider that fills it in is in textSize.tsx.

import { createContext, useContext } from 'react'

export interface TextSize {
  big: boolean
  setBig: (big: boolean) => void
}

export const TextSizeContext = createContext<TextSize>({ big: false, setBig: () => {} })

export function useTextSize(): TextSize {
  return useContext(TextSizeContext)
}
