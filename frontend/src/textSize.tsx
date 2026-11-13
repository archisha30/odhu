// "Large text" setting, shared by every screen through a React context.
// When it's on, the <html> element gets the class "big-text", and the CSS makes
// the base font bigger. Every size in index.css is in rem, so everything grows together.

import { useEffect, useState, type ReactNode } from 'react'
import { TextSizeContext } from './textSizeContext'

const STORAGE_KEY = 'odhu-big-text'

function loadBig(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false // storage blocked (e.g. private mode): just use normal size
  }
}

export function TextSizeProvider({ children }: { children: ReactNode }) {
  const [big, setBigState] = useState(loadBig)

  useEffect(() => {
    document.documentElement.classList.toggle('big-text', big)
  }, [big])

  function setBig(next: boolean) {
    setBigState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next ? '1' : '0')
    } catch {
      // ignore: the setting just won't be remembered
    }
  }

  return <TextSizeContext.Provider value={{ big, setBig }}>{children}</TextSizeContext.Provider>
}
