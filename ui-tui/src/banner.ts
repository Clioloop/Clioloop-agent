import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import type { ThemeColors } from './theme.js'

const RICH_RE = /\[(?:bold\s+)?(?:dim\s+)?(#(?:[0-9a-fA-F]{3,8}))\]([\s\S]*?)(\[\/\])/g

export function parseRichMarkup(markup: string): Line[] {
  const lines: Line[] = []

  for (const raw of markup.split('\n')) {
    const trimmed = raw.trimEnd()

    if (!trimmed) {
      lines.push(['', ' '])

      continue
    }

    const matches = [...trimmed.matchAll(RICH_RE)]

    if (!matches.length) {
      lines.push(['', trimmed])

      continue
    }

    let cursor = 0

    for (const m of matches) {
      const before = trimmed.slice(cursor, m.index)

      if (before) {
        lines.push(['', before])
      }

      lines.push([m[1]!, m[2]!])
      cursor = m.index! + m[0].length
    }

    if (cursor < trimmed.length) {
      lines.push(['', trimmed.slice(cursor)])
    }
  }

  return lines
}

const LOGO_ART = [
  ' ██████╗██╗     ██╗ ██████╗ ██╗      ██████╗  ██████╗ ██████╗      █████╗  ██████╗ ███████╗███╗   ██╗████████╗',
  '██╔════╝██║     ██║██╔═══██╗██║     ██╔═══██╗██╔═══██╗██╔══██╗    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝',
  '██║     ██║     ██║██║   ██║██║     ██║   ██║██║   ██║██████╔╝    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ',
  '██║     ██║     ██║██║   ██║██║     ██║   ██║██║   ██║██╔═══╝     ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ',
  '╚██████╗███████╗██║╚██████╔╝███████╗╚██████╔╝╚██████╔╝██║         ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ',
  ' ╚═════╝╚══════╝╚═╝ ╚═════╝ ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝         ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ',
]

const INFINITY_ART = [
  '      ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄',
  '    ▄█▀▀▀▀▀█▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▀▀▀▀▀█▄',
  '  ▄█▀   ▄▄▄▄   ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀   ▄▄▄▄   ▀█▄',
  '  █   ▄█▀   ▀█▄  ▄▄▄▄▄▄▄▄▄▄▄▄  ▄█▀   ▀█▄   █',
  '  █  ▄█  ∞  ██  █▀▀▀▀▀▀█▀▀▀▀▀█  ██  ∞  █▄  █',
  '  █  ▀█     █▀  █  ▄▄▄▄█  ▄▄▄▄  ▀█     █▀  █',
  '  ▀█▄  ▀▀▀▀▀  ▄█  █▀▀▀▀▀  ▀▀▀▀█  ▄▀▀▀▀▀  ▄█▀',
  '    ▀█▄▄▄▄▄▄█▀   ▀▀▀▀▀▀▀▀▀▀▀▀▀▀  ▀█▄▄▄▄▄▄█▀',
  '      ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀',
  '                 ∞  Clioloop  ∞',
  '            ── Omni Loop Labs ──'
]

const LOGO_GRADIENT = [0, 0, 1, 1, 2, 2] as const
const INFINITY_GRADIENT = [0, 0, 1, 1, 2, 2, 1, 1, 0, 0, 1] as const
const TERMINAL_GRADIENT = [0, 0, 1, 1, 2, 2, 3, 2, 1, 1, 0, 0] as const

let terminalArtCache: string[] | null | undefined

const candidateAssetPaths = () => {
  const here = dirname(fileURLToPath(import.meta.url))
  const cwd = process.cwd()

  return [
    resolve(cwd, 'assets/terminal-art.txt'),
    resolve(cwd, '../assets/terminal-art.txt'),
    resolve(here, '../../assets/terminal-art.txt'),
    resolve(here, '../../../assets/terminal-art.txt'),
    resolve(here, '../../../../assets/terminal-art.txt')
  ]
}

const loadTerminalArt = (): string[] | null => {
  if (terminalArtCache !== undefined) {
    return terminalArtCache
  }

  for (const path of candidateAssetPaths()) {
    try {
      if (existsSync(path)) {
        terminalArtCache = readFileSync(path, 'utf8')
          .split('\n')
          .map(line => line.trimEnd())
          .filter(Boolean)

        return terminalArtCache
      }
    } catch {
      // Keep startup resilient; bundled fallback art remains available.
    }
  }

  terminalArtCache = null

  return terminalArtCache
}

const colorize = (art: string[], gradient: readonly number[], c: ThemeColors): Line[] => {
  const p = [c.primary, c.accent, c.border, c.muted]

  return art.map((text, i) => [p[gradient[i]!] ?? c.muted, text])
}

const cropLine = (line: string, width: number) => {
  if (line.length <= width) {
    return line
  }

  const start = Math.max(0, Math.floor((line.length - width) / 2))

  return line.slice(start, start + width)
}

export const terminalArt = (c: ThemeColors, maxWidth: number, maxHeight = 12): Line[] | null => {
  const art = loadTerminalArt()

  if (!art?.length || maxWidth < 70) {
    return null
  }

  const height = Math.min(maxHeight, art.length)
  const start = Math.max(0, Math.floor((art.length - height) / 3))
  const width = Math.max(1, maxWidth)
  const cropped = art.slice(start, start + height).map(line => cropLine(line, width))

  return colorize(cropped, TERMINAL_GRADIENT, c)
}

// Compact variant for the session panel hero block — lower min-width so it
// fits in the narrower left column.
export const terminalArtHero = (c: ThemeColors, maxWidth: number, maxHeight = 16): Line[] | null => {
  const art = loadTerminalArt()

  if (!art?.length || maxWidth < 42) {
    return null
  }

  const height = Math.min(maxHeight, art.length)
  const start = 0
  const width = Math.max(1, maxWidth)
  const cropped = art.slice(start, start + height).map(line => cropLine(line, width))

  return colorize(cropped, TERMINAL_GRADIENT, c)
}

export const LOGO_WIDTH = Math.max(...LOGO_ART.map(line => line.length))
export const INFINITY_WIDTH = Math.max(...INFINITY_ART.map(line => line.length))

export const logo = (c: ThemeColors, customLogo?: string): Line[] =>
  customLogo ? parseRichMarkup(customLogo) : colorize(LOGO_ART, LOGO_GRADIENT, c)

export const infinity = (c: ThemeColors, customHero?: string): Line[] =>
  customHero ? parseRichMarkup(customHero) : colorize(INFINITY_ART, INFINITY_GRADIENT, c)

// Back-compat alias for callers that still import the old name.
export const caduceus = infinity

export const artWidth = (lines: Line[]) => lines.reduce((m, [, t]) => Math.max(m, t.length), 0)

type Line = [string, string]
