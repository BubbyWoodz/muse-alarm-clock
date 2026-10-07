import type { ReactElement, SVGProps } from 'react'

// ---------------------------------------------------------------------------
// Inline SVG icon set. All icons use `currentColor` so they adapt to the
// theme automatically (see styles.css CSS variables). No emojis anywhere.
// ---------------------------------------------------------------------------

type P = SVGProps<SVGSVGElement>

function base(props: P) {
  return {
    width: 18,
    height: 18,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
    ...props,
  }
}

export const IconClock = (p: P) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
)

export const IconButton = (p: P) => (
  <svg {...base(p)}>
    <rect x="7" y="7" width="10" height="10" rx="5" />
    <circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none" />
  </svg>
)

export const IconBell = (p: P) => (
  <svg {...base(p)}>
    <path d="M18 9a6 6 0 1 0-12 0c0 5-2 6-2 6h16s-2-1-2-6" />
    <path d="M10 20a2 2 0 0 0 4 0" />
  </svg>
)

export const IconPage = (p: P) => (
  <svg {...base(p)}>
    <rect x="5" y="3" width="14" height="18" rx="2" />
    <path d="M9 8h6M9 12h6M9 16h4" />
  </svg>
)

export const IconAudio = (p: P) => (
  <svg {...base(p)}>
    <path d="M9 18V6l10-2v12" />
    <circle cx="6.5" cy="18" r="2.5" />
    <circle cx="16.5" cy="16" r="2.5" />
  </svg>
)

export const IconWait = (p: P) => (
  <svg {...base(p)}>
    <path d="M6 3h12l-2 4h-8L6 3z" />
    <path d="M8 7c0 5-1 7-3 9a7 7 0 0 0 14 0c-2-2-3-4-3-9" />
  </svg>
)

export const IconPlus = (p: P) => (
  <svg {...base(p)}>
    <path d="M12 5v14M5 12h14" />
  </svg>
)

export const IconTrash = (p: P) => (
  <svg {...base(p)}>
    <path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m3 0-1 13a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1L6 7" />
  </svg>
)

export const IconPencil = (p: P) => (
  <svg {...base(p)}>
    <path d="M17 3a2.8 2.8 0 1 1 4 4L8 20l-5 1 1-5L17 3z" />
  </svg>
)

export const IconBack = (p: P) => (
  <svg {...base(p)}>
    <path d="M19 12H5m7-7-7 7 7 7" />
  </svg>
)

export const IconPlay = (p: P) => (
  <svg {...base(p)}>
    <path d="M7 4.5v15l13-7.5-13-7.5z" fill="currentColor" stroke="none" />
  </svg>
)

export const IconSave = (p: P) => (
  <svg {...base(p)}>
    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
    <path d="M17 21v-8H7v8M7 3v5h8" />
  </svg>
)

export const IconSun = (p: P) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4m11.4-11.4 1.4-1.4" />
  </svg>
)

export const IconMoon = (p: P) => (
  <svg {...base(p)}>
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
  </svg>
)

export const IconX = (p: P) => (
  <svg {...base(p)}>
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
)

export const IconCheck = (p: P) => (
  <svg {...base(p)}>
    <path d="M20 6 9 17l-5-5" />
  </svg>
)

export const IconGrip = (p: P) => (
  <svg {...base(p)}>
    <circle cx="9" cy="6" r="1" fill="currentColor" stroke="none" />
    <circle cx="15" cy="6" r="1" fill="currentColor" stroke="none" />
    <circle cx="9" cy="12" r="1" fill="currentColor" stroke="none" />
    <circle cx="15" cy="12" r="1" fill="currentColor" stroke="none" />
    <circle cx="9" cy="18" r="1" fill="currentColor" stroke="none" />
    <circle cx="15" cy="18" r="1" fill="currentColor" stroke="none" />
  </svg>
)

export const IconZap = (p: P) => (
  <svg {...base(p)}>
    <path d="M13 2 3 14h8l-1 8 10-12h-8l1-8z" />
  </svg>
)

export const IconPerson = (p: P) => (
  <svg {...base(p)}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5" />
  </svg>
)

export const IconSpark = (p: P) => (
  <svg {...base(p)}>
    <path d="M12 2v6M12 16v6M2 12h6M16 12h6" />
    <path d="M12 8l1.2 2.8L16 12l-2.8 1.2L12 16l-1.2-2.8L8 12l2.8-1.2L12 8z" fill="currentColor" stroke="none" />
  </svg>
)

export const BLOCK_ICONS: Record<string, (p: P) => ReactElement> = {
  time_trigger: IconClock,
  button_trigger: IconButton,
  alarm: IconBell,
  page: IconPage,
  audio: IconAudio,
  wait: IconWait,
}
