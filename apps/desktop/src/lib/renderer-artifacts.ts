/** Pure renderer artifact policy: detection, bounded versioning, and sandbox
 * attributes. Keeping these decisions together prevents a card detector and a
 * preview iframe from quietly disagreeing about what is executable content. */

export type RendererArtifactKind = 'code' | 'html' | 'svg'

export interface RendererArtifactDetection {
  kind: RendererArtifactKind
  language: string
  title: string
}

export interface RendererArtifactVersion {
  content: string
  createdAt: number
  hash: string
}

export interface VersionedRendererArtifact extends RendererArtifactDetection {
  id: string
  versions: RendererArtifactVersion[]
}

const HTML_DOCUMENT = /<!doctype\s+html|<html[\s>]|<head[\s>]|<body[\s>]/i
const HTML_TAG = /<[a-z][a-z0-9-]*(?:\s[^>]*)?>/i
const SVG_ROOT = /<svg[\s>]/i
const PROSE_LANGUAGES = new Set(['', 'console', 'diff', 'log', 'markdown', 'md', 'mermaid', 'text', 'txt'])

function languageTag(value?: string): string {
  return String(value || '').trim().toLowerCase().replace(/[^a-z0-9_+.-]/g, '').slice(0, 32)
}

function lineCount(value: string): number {
  return value.split('\n').length
}

function plainTitle(value: string, tag: 'h1' | 'title'): string {
  const found = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, 'i').exec(value)?.[1] || ''
  return found.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80)
}

function codeTitle(language: string, content: string): string {
  const file = /^\s*(?:\/\/|#|<!--)\s*([\w./-]+\.[a-z0-9]{1,8})\b/i.exec(content)?.[1]
  if (file) return file
  const declaration = /(?:^|\n)\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|def|fn)\s+([\w$]+)/.exec(content)?.[1]
  return declaration || language || 'Code'
}

/** Streaming-safe, bounded-shape detection. Small snippets remain inline. */
export function detectRendererArtifact(language: string | undefined, source: string | undefined): RendererArtifactDetection | null {
  const content = String(source || '').trim()
  const lang = languageTag(language)
  if (!content) return null

  const htmlHint = lang === 'html' || lang === 'htm' || lang === 'xhtml'
  if (htmlHint) {
    const substantial = HTML_DOCUMENT.test(content) ? content.length >= 160 : content.length >= 1_200 && HTML_TAG.test(content)
    return substantial
      ? { kind: 'html', language: lang, title: plainTitle(content, 'title') || plainTitle(content, 'h1') || 'HTML' }
      : null
  }

  if (lang === 'svg') {
    return content.length >= 2_000 && SVG_ROOT.test(content)
      ? { kind: 'svg', language: lang, title: plainTitle(content, 'title') || 'SVG' }
      : null
  }

  if (PROSE_LANGUAGES.has(lang) || (content.length < 3_000 && lineCount(content) < 48)) return null
  return { kind: 'code', language: lang, title: codeTitle(lang, content) }
}

/** FNV-1a is for deterministic de-duplication, not security. */
export function rendererArtifactHash(content: string): string {
  let hash = 0x811c9dc5
  for (let index = 0; index < content.length; index += 1) {
    hash ^= content.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193)
  }
  return (hash >>> 0).toString(36)
}

export function rendererArtifactId(detection: RendererArtifactDetection): string {
  const slug = detection.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 48) || 'untitled'
  return `${detection.kind}:${detection.language}:${slug}`
}

/** Append one unique version and cap retained content. Oldest versions leave
 * first; caller storage remains immutable. */
export function addRendererArtifactVersion(
  artifact: VersionedRendererArtifact | null,
  detection: RendererArtifactDetection,
  content: string,
  options: { at?: number; maxVersions?: number } = {}
): VersionedRendererArtifact {
  const normalized = content.trim()
  const hash = rendererArtifactHash(normalized)
  const id = rendererArtifactId(detection)
  if (artifact && artifact.id === id && artifact.versions.some(version => version.hash === hash)) return artifact
  const maxVersions = Math.max(1, Math.floor(options.maxVersions ?? 20))
  const versions = [...(artifact?.id === id ? artifact.versions : []), { content: normalized, createdAt: options.at ?? Date.now(), hash }]
    .slice(-maxVersions)
  return { ...detection, id, versions }
}

export interface ArtifactSandboxPolicy {
  /** Value for iframe `sandbox`; empty means scripts are disabled. */
  sandbox: string
  /** Defense in depth for generated srcDoc. */
  contentSecurityPolicy: string
  referrerPolicy: 'no-referrer'
  sanitizeSvg: boolean
}

/** Generated HTML may run scripts only in an opaque origin. It never receives
 * same-origin, navigation, popups, forms, downloads, or modals capability. SVG
 * is sanitized and receives no script capability. */
export function artifactSandboxPolicy(kind: RendererArtifactKind, allowHtmlScripts = true): ArtifactSandboxPolicy {
  const html = kind === 'html'
  return {
    sandbox: html && allowHtmlScripts ? 'allow-scripts' : '',
    contentSecurityPolicy: html
      ? "default-src 'none'; img-src data: https:; style-src 'unsafe-inline'; font-src data: https:; script-src 'unsafe-inline'"
      : "default-src 'none'; img-src data:; style-src 'unsafe-inline'",
    referrerPolicy: 'no-referrer',
    sanitizeSvg: kind === 'svg'
  }
}

export function composeSandboxedHtml(content: string, policy = artifactSandboxPolicy('html')): string {
  const csp = `<meta http-equiv="Content-Security-Policy" content="${policy.contentSecurityPolicy.replace(/"/g, '&quot;')}">`
  if (/<html[\s>]|<!doctype\s+html/i.test(content)) {
    return /<head[\s>]/i.test(content) ? content.replace(/<head([^>]*)>/i, `<head$1>${csp}`) : `${csp}${content}`
  }
  return `<!doctype html><html><head><meta charset="utf-8">${csp}</head><body>${content}</body></html>`
}
