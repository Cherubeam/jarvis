// Inline SVG icons — ported from JARVIS GUI.html line 458-495.

const PATHS: Record<string, string> = {
  send: 'M3 11L21 3l-8 18-2-8-8-2z',
  chevron: 'M6 9l6 6 6-6',
  right: 'M9 6l6 6-6 6',
  tool: 'M14.7 6.3a1 1 0 010 1.4l-6 6a1 1 0 01-1.4 0l-3-3a1 1 0 111.4-1.4L8 11.6l5.3-5.3a1 1 0 011.4 0z M20 4h-4v4 M20 4l-6 6',
  search: 'M10 4a6 6 0 104.47 10.03L19 18.5l1.5-1.5-4.47-4.53A6 6 0 0010 4zm0 2a4 4 0 110 8 4 4 0 010-8z',
  close: 'M5 5l14 14 M19 5L5 19',
  check: 'M5 12l5 5L20 7',
  sparkle: 'M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2z',
  folder: 'M3 6a2 2 0 012-2h3l2 2h9a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V6z',
  note: 'M5 3h10l4 4v14H5z M15 3v4h4',
  dot: 'M12 12m-3 0a3 3 0 106 0 3 3 0 10-6 0',
  terminal: 'M4 5h16v14H4z M7 9l3 3-3 3 M13 15h4',
  sun: 'M12 5V3 M12 21v-2 M5 12H3 M21 12h-2 M6.3 6.3L4.9 4.9 M19.1 19.1l-1.4-1.4 M17.7 6.3l1.4-1.4 M4.9 19.1l1.4-1.4 M12 8a4 4 0 100 8 4 4 0 000-8z',
  moon: 'M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z',
  slash: 'M10 19L14 5',
  history: 'M3 12a9 9 0 109-9 M3 5v5h5 M12 7v6l4 2',
}

export function Icon({
  name,
  size = 14,
  color = 'currentColor',
}: {
  name: keyof typeof PATHS | string
  size?: number
  color?: string
}) {
  const d = PATHS[name as string]
  if (!d) return null
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={d} />
    </svg>
  )
}
