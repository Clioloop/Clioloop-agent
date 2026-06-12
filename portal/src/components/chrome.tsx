import Link from "next/link";
import { getSessionUser } from "@/lib/session";

export function Logo() {
  return (
    <Link href="/" className="nav-brand">
      <span className="logo-mark" aria-hidden />
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
          ∞ Omni Loop Portal · the subscription gateway for{" "}
          <a href="https://github.com/Clioloop/Clioloop-agent" target="_blank" rel="noreferrer">
            Clioloop&nbsp;↗
          </a>{" "}
          · © {new Date().getFullYear()}
        </p>
        <div className="footer-links">
          <Link href="/pricing">Pricing</Link>
          <Link href="/docs">Docs</Link>
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
