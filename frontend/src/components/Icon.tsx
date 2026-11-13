// Simple line icons drawn with SVG, so we don't need an icon library.
// Every icon is decorative: buttons always show a text label too.

const PATHS = {
  camera: 'M3 8h3l2-3h8l2 3h3v11H3z M12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  gallery: 'M3 5h18v14H3z M3 16l5-5 4 4 3-3 6 6 M15.5 9.5a1.5 1.5 0 1 0 0-.01',
  history: 'M3 12a9 9 0 1 0 3-6.7 M3 4v5h5 M12 7v5l3 3',
  mic: 'M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z M5 11a7 7 0 0 0 14 0 M12 18v3',
  stop: 'M7 7h10v10H7z',
  speaker: 'M4 9h4l5-4v14l-5-4H4z M16.5 8.5a5 5 0 0 1 0 7 M19 6a8.5 8.5 0 0 1 0 12',
  home: 'M3 11l9-8 9 8 M5 9.5V21h5v-6h4v6h5V9.5',
  back: 'M15 5l-7 7 7 7',
  alert: 'M12 3l10 18H2z M12 10v5 M12 18v.01',
  bolt: 'M13 2L4 14h7l-1 8 9-12h-7z',
  bank: 'M3 10l9-6 9 6 M5 10v8 M9.5 10v8 M14.5 10v8 M19 10v8 M3 21h18',
  notice: 'M6 2h9l5 5v15H6z M14 2v6h6 M9 13h8 M9 17h8',
  retry: 'M4 4v6h6 M20 20v-6h-6 M5.5 15a7.5 7.5 0 0 0 13 2 M18.5 9a7.5 7.5 0 0 0-13-2',
  chevron: 'M9 5l7 7-7 7',
} as const

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 28 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
