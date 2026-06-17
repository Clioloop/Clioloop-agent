import Link from "next/link";
import { getSessionUser } from "@/lib/session";

/** Brand mark: a continuous infinity ribbon with a violet gradient stroke.
 *  No bounding box — scales crisply at any size via the viewBox. */
export function InfinityMark({ className }: { className?: string }) {
  return (
    <span className={className} aria-hidden>
      <svg viewBox="0 0 64 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="omni-inf" x1="0" y1="0" x2="64" y2="32" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#c4b5fd" />
            <stop offset="0.5" stopColor="#8b5cf6" />
            <stop offset="1" stopColor="#6d28d9" />
          </linearGradient>
        </defs>
        <path
          d="M32 16C27 7 14 7 14 16C14 25 27 25 32 16C37 7 50 7 50 16C50 25 37 25 32 16Z"
          stroke="url(#omni-inf)"
          strokeWidth="5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

export function Logo() {
  return (
    <Link href="/" className="nav-brand">
      <InfinityMark className="logo-mark" />
      Omni&nbsp;Loop&nbsp;<span style={{ color: "var(--accent)" }}>Portal</span>
    </Link>
  );
}

export async function Nav() {
  const user = await getSessionUser();
  return (
    <header className="nav">
      <div className="nav-inner">
        <Logo />
        <nav className="nav-links">
          <Link href="/#features">Features</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/docs">Docs</Link>
          <a href="https://github.com/Clioloop/Clioloop-agent" target="_blank" rel="noreferrer">
            GitHub
          </a>
        </nav>
        <div className="nav-actions">
          {user ? (
            <>
              <span
                style={{
                  color: "var(--text-faint)",
                  fontSize: 12,
                  fontFamily: "var(--mono)",
                }}
              >
                {user.email}
              </span>
              <Link href="/dashboard" className="btn btn-primary btn-sm">
                Dashboard
              </Link>
            </>
          ) : (
            <>
              <Link href="/login" className="btn btn-ghost btn-sm">
                Log in
              </Link>
              <Link href="/signup" className="btn btn-primary btn-sm">
                Get started
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <p>
          <InfinityMark className="footer-mark" /> Omni Loop Portal · the subscription gateway for{" "}
          <a href="https://github.com/Clioloop/Clioloop-agent" target="_blank" rel="noreferrer">
            Clioloop&nbsp;↗
          </a>{" "}
          · © {new Date().getFullYear()}
        </p>
        <div className="footer-links">
          <Link href="/pricing">Pricing</Link>
          <Link href="/docs">Docs</Link>
          <Link href="/docs/fusion">Fusion</Link>
          <Link href="/docs/getting-started">Get started</Link>
          <Link href="/activate">Activate</Link>
          <Link href="/terms">Terms</Link>
          <Link href="/privacy">Privacy</Link>
          <a href="https://github.com/Clioloop/Clioloop-agent" target="_blank" rel="noreferrer">
            GitHub
          </a>
        </div>
      </div>
    </footer>
  );
}
