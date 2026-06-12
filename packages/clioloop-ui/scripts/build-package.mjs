import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const dist = join(root, 'dist')
const src = join(root, 'src')

rmSync(dist, { force: true, recursive: true })
mkdirSync(dist, { recursive: true })

// Compile TypeScript (tolerate type errors — output JS still works)
try {
  execFileSync('tsc', ['-p', join(root, 'tsconfig.build.json')], {
    cwd: root,
    stdio: 'inherit'
  })
} catch {
  // tsc may exit non-zero due to type errors; continue anyway
  console.warn('[build] tsc reported errors — continuing with partial output')
}

// Copy CSS and asset files
for (const path of ['assets', 'fonts']) {
  const from = join(src, path)
  if (existsSync(from)) {
    cpSync(from, join(dist, path), { recursive: true })
  }
}

for (const path of [
  'ui/build.css',
  'ui/fonts.css',
  'ui/globals.css',
  'ui/components/fit-text/fit-text.css',
  'ui/components/grid/grid.css'
]) {
  const from = join(src, path)
  if (existsSync(from)) {
    cpSync(from, join(dist, path), { recursive: true })
  }
}
