import Link from "next/link";
import { headers } from "next/headers";
import { getSessionUser } from "@/lib/session";
import { LOCALES, LOCALE_LABELS, isLocale, type Locale } from "@/i18n/locales";
import { DICTS } from "@/i18n/dictionaries";

/** Brand mark: a continuous infinity ribbon with a brass gradient stroke.
 *  No bounding box — scales crisply at any size via the viewBox. */
export function InfinityMark({ className }: { className?: string }) {
  return (
    <span className={className} aria-hidden>
      <svg viewBox="0 0 64 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="omni-inf" x1="0" y1="0" x2="64" y2="32" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#e8c47c" />
            <stop offset="0.5" stopColor="#d4a24e" />
            <stop offset="1" stopColor="#9a7433" />
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

// Locale + path context stamped onto the request by middleware.ts; the
// chrome uses it to translate its labels and localize the pricing link.
async function localeContext(): Promise<{ locale: Locale | "en"; pathname: string }> {
  const h = await headers();
  const raw = h.get("x-olp-locale") ?? "en";
  return {
    locale: raw !== "en" && isLocale(raw) ? raw : "en",
    pathname: h.get("x-olp-pathname") ?? "/",
  };
}

const homeHref = (locale: Locale | "en") => (locale === "en" ? "/" : `/${locale}`);
const pricingHref = (locale: Locale | "en") =>
  locale === "en" ? "/pricing" : `/${locale}/pricing`;

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="nav-brand">
      <InfinityMark className="logo-mark" />
      Clio<span style={{ color: "var(--brass)" }}>loop</span>
    </Link>
  );
}

export async function Nav() {
  const [user, { locale }] = await Promise.all([getSessionUser(), localeContext()]);
  const t = DICTS[locale].chrome;
  return (
    <header className="nav">
      <div className="nav-inner">
        <Logo href={homeHref(locale)} />
        <nav className="nav-links">
          <Link href={`${homeHref(locale)}#features`}>{t.features}</Link>
          <Link href={`${homeHref(locale)}#music`}>{t.music}</Link>
          <Link href={pricingHref(locale)}>{t.pricing}</Link>
          <Link href="/docs">{t.docs}</Link>
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
                {t.dashboard}
              </Link>
            </>
          ) : (
            <>
              <Link href="/login" className="btn btn-ghost btn-sm">
                {t.login}
              </Link>
              <Link href="/signup" className="btn btn-primary btn-sm">
                {t.getStarted}
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export async function Footer() {
  const { locale, pathname } = await localeContext();
  const t = DICTS[locale].chrome;
  // The locale switcher maps the current page to its translations; only the
  // landing and pricing pages exist in other languages.
  const onPricing = pathname === "/pricing" || /^\/(de|fr|es|pt|ja|zh)\/pricing$/.test(pathname);
  const switchHref = (target: Locale | "en") =>
    onPricing ? pricingHref(target) : homeHref(target);
  return (
    <footer className="footer">
      <div className="footer-inner">
        <p>
          <InfinityMark className="footer-mark" /> {t.footerTagline}{" "}
          <a href="https://github.com/Clioloop/Clioloop-agent" target="_blank" rel="noreferrer">
            Clioloop&nbsp;↗
          </a>{" "}
          · © {new Date().getFullYear()}
        </p>
        <div className="footer-links">
          <Link href={pricingHref(locale)}>{t.pricing}</Link>
          <Link href="/docs">{t.docs}</Link>
          <Link href="/docs/fusion">Fusion</Link>
          <Link href="/docs/getting-started">{t.getStarted}</Link>
          <Link href="/activate">Activate</Link>
          <Link href="/terms">Terms</Link>
          <Link href="/privacy">Privacy</Link>
          <a href="https://github.com/Clioloop/Clioloop-agent" target="_blank" rel="noreferrer">
            GitHub
          </a>
        </div>
        <div className="footer-locales">
          <span>{t.languages}:</span>
          {(["en", ...LOCALES] as const).map((code) => (
            <Link key={code} href={switchHref(code)} lang={code} hrefLang={code}>
              {LOCALE_LABELS[code]}
            </Link>
          ))}
        </div>
      </div>
    </footer>
  );
}
