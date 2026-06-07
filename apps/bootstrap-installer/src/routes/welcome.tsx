import { type CSSProperties, useState } from 'react'
import { Button } from '../components/button'
import { startInstall } from '../store'
import { ArrowRight, KeyRound } from 'lucide-react'

/*
 * Welcome screen.
 *
 * Mirrors the desktop's chat intro (apps/desktop/src/components/chat/intro.tsx):
 *   - CLIOLOOP wordmark rendered in Collapse Bold, uppercase, tracked
 *   - mix-blend-plus-lighter so the type "glows" on the canvas
 *   - fit-text utility so the wordmark sizes itself to the column
 *
 * No install-path footer. The default install location is correct for
 * 99% of users; the rest will use the CLI installer with a -ClioHome
 * flag. Showing %LOCALAPPDATA% to grandma is developer-brain.
 */
export default function Welcome() {
  const [token, setToken] = useState('')
  const [showToken, setShowToken] = useState(false)

  return (
    <div className="clio-fade-in flex h-full flex-col items-center justify-center gap-8 px-12 py-10">
      {/* Hero — same recipe the desktop's chat/intro.tsx uses */}
      <div className="w-full max-w-2xl min-w-0 text-center">
        <p
          className="fit-text mx-auto mb-4 w-full font-['Collapse'] font-bold uppercase leading-[0.9] tracking-[0.08em] text-primary"
          style={
            {
              '--fit-text-line-height': '0.9',
              '--fit-text-max': '6rem',
              '--fit-text-min': '2.5rem'
            } as CSSProperties
          }
        >
          <span>
            <span>CLIOLOOP</span>
          </span>
          <span aria-hidden="true">CLIOLOOP</span>
        </p>

        <p className="m-0 text-center text-base leading-normal tracking-tight text-foreground/75">
          The agent that grows with you. We&rsquo;ll set things up in the
          background &mdash; takes a few minutes.
        </p>
      </div>

      {/* GitHub token input — collapsed by default, shown for private repos */}
      <div className="w-full max-w-sm">
        <button
          type="button"
          onClick={() => setShowToken(!showToken)}
          className="mb-2 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <KeyRound size={12} />
          {showToken ? 'Hide' : 'Private repo? Add GitHub token'}
        </button>
        {showToken && (
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            spellCheck={false}
            autoComplete="off"
          />
        )}
      </div>

      <Button
        onClick={() => void startInstall({ githubToken: token || undefined })}
        size="lg"
        className="group inline-flex items-center gap-2 px-6"
      >
        Install Clioloop
        <ArrowRight
          size={18}
          className="transition-transform group-hover:translate-x-0.5"
        />
      </Button>
    </div>
  )
}
