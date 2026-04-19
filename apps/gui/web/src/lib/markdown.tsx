// Minimal markdown renderer — ported from JARVIS GUI.html line 337-429.
// Same heuristic as apps/cli/display.py:43-56 so CLI/GUI render parity.

import { useMemo } from 'react'

import { JARVIS_FONTS, type Theme } from './tokens'

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function renderInline(text: string, theme: Theme): string {
  let s = escapeHtml(text)
  s = s.replace(
    /`([^`]+)`/g,
    (_m, c) =>
      `<code style="font-family:${JARVIS_FONTS.mono};background:${theme.surface2};color:${theme.assistant};padding:1px 6px;border-radius:4px;font-size:0.92em">${c}</code>`,
  )
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>')
  s = s.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    `<a href="$2" style="color:${theme.assistant};text-decoration:underline;text-underline-offset:2px">$1</a>`,
  )
  return s
}

export function Markdown({ text, theme }: { text: string; theme: Theme }) {
  const html = useMemo(() => {
    const lines = (text || '').split('\n')
    const out: string[] = []
    let i = 0
    while (i < lines.length) {
      const line = lines[i]
      if (/^```/.test(line)) {
        const buf: string[] = []
        i++
        while (i < lines.length && !/^```/.test(lines[i])) {
          buf.push(escapeHtml(lines[i]))
          i++
        }
        i++
        out.push(
          `<pre style="margin:12px 0;padding:12px 14px;background:${theme.surface2};border:1px solid ${theme.border};border-radius:8px;overflow-x:auto"><code style="font-family:${JARVIS_FONTS.mono};font-size:13px;line-height:1.55;color:${theme.textPrimary}">${buf.join('\n')}</code></pre>`,
        )
        continue
      }
      const h = line.match(/^(#{1,6})\s+(.+)$/)
      if (h) {
        const lvl = h[1].length
        const size = [22, 19, 17, 16, 15, 14][lvl - 1]
        out.push(
          `<div style="font-size:${size}px;font-weight:700;margin:14px 0 6px;color:${theme.textPrimary}">${renderInline(h[2], theme)}</div>`,
        )
        i++
        continue
      }
      if (/^- /.test(line)) {
        const items: string[] = []
        while (i < lines.length && /^- /.test(lines[i])) {
          items.push(`<li style="margin:2px 0">${renderInline(lines[i].slice(2), theme)}</li>`)
          i++
        }
        out.push(`<ul style="margin:6px 0 10px;padding-left:22px">${items.join('')}</ul>`)
        continue
      }
      if (/^\d+\.\s/.test(line)) {
        const items: string[] = []
        while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
          items.push(
            `<li style="margin:2px 0">${renderInline(lines[i].replace(/^\d+\.\s/, ''), theme)}</li>`,
          )
          i++
        }
        out.push(`<ol style="margin:6px 0 10px;padding-left:24px">${items.join('')}</ol>`)
        continue
      }
      if (!line.trim()) {
        out.push('<div style="height:8px"></div>')
        i++
        continue
      }
      const para = [line]
      i++
      while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|```|- |\d+\.\s)/.test(lines[i])) {
        para.push(lines[i])
        i++
      }
      out.push(`<p style="margin:6px 0;line-height:1.65">${renderInline(para.join(' '), theme)}</p>`)
    }
    return out.join('')
  }, [text, theme])

  return <div dangerouslySetInnerHTML={{ __html: html }} />
}
