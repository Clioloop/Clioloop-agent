import { describe, expect, it } from 'vitest'

import {
  addRendererArtifactVersion,
  artifactSandboxPolicy,
  composeSandboxedHtml,
  detectRendererArtifact
} from './renderer-artifacts'

describe('renderer artifact foundations', () => {
  it('detects substantial HTML and SVG but leaves small snippets inline', () => {
    expect(detectRendererArtifact('html', '<p>small</p>')).toBeNull()
    const html = `<!doctype html><html><head><title>Release dashboard</title></head><body>${'x'.repeat(100)}</body></html>`
    expect(detectRendererArtifact('html', html)).toEqual({ kind: 'html', language: 'html', title: 'Release dashboard' })
    expect(detectRendererArtifact('svg', `<svg><title>Map</title>${'<path d="M0 0"/>'.repeat(150)}</svg>`)).toMatchObject({
      kind: 'svg',
      title: 'Map'
    })
  })

  it('detects long code and versions immutable artifacts with dedupe and a cap', () => {
    const code = `// worker.ts\nfunction worker() {}\n${'const item = 1\n'.repeat(220)}`
    const detection = detectRendererArtifact('typescript', code)
    expect(detection).toMatchObject({ kind: 'code', title: 'worker.ts' })
    const one = addRendererArtifactVersion(null, detection!, code, { at: 1, maxVersions: 2 })
    expect(addRendererArtifactVersion(one, detection!, code, { at: 2 })).toBe(one)
    const two = addRendererArtifactVersion(one, detection!, `${code}\n// two`, { at: 2, maxVersions: 2 })
    const three = addRendererArtifactVersion(two, detection!, `${code}\n// three`, { at: 3, maxVersions: 2 })
    expect(three.versions.map(version => version.createdAt)).toEqual([2, 3])
  })

  it('uses an opaque-origin script sandbox and injects a CSP', () => {
    const policy = artifactSandboxPolicy('html')
    expect(policy.sandbox).toBe('allow-scripts')
    expect(policy.sandbox).not.toContain('allow-same-origin')
    expect(artifactSandboxPolicy('svg')).toMatchObject({ sandbox: '', sanitizeSvg: true })
    expect(composeSandboxedHtml('<h1>Hello</h1>', policy)).toContain('Content-Security-Policy')
  })
})
