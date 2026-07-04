import { NextRequest, NextResponse } from "next/server";

// Defense-in-depth only. Real auth lives in the per-route wrappers
// (src/lib/handlers.ts) and getSessionUser(); this layer just keeps
// cookieless requests out of the account surfaces, and stamps the request
// with locale/pathname headers that the root layout and chrome read.
//
// The matcher deliberately excludes the CLI hot paths (inference, oauth,
// gateway, Stripe webhook — including the deploy-time /api/v1/fusion
// overlay) so nothing here can slow down or break machine clients.

const LOCALE_RE = /^\/(de|fr|es|pt|ja|zh)(?=\/|$)/;
const SESSION_COOKIE = "olp_session";

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const hasSession = req.cookies.has(SESSION_COOKIE);

  if ((pathname.startsWith("/dashboard") || pathname.startsWith("/admin")) && !hasSession) {
    const login = new URL(`/login?next=${encodeURIComponent(pathname)}`, req.url);
    return NextResponse.redirect(login);
  }
  if (pathname.startsWith("/api/admin") && !hasSession) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const headers = new Headers(req.headers);
  headers.set("x-olp-locale", LOCALE_RE.exec(pathname)?.[1] ?? "en");
  headers.set("x-olp-pathname", pathname);
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: [
    "/((?!_next|brand|research|api/v1|api/oauth|api/gateway|api/billing/webhook|api/telegram|favicon\\.ico).*)",
  ],
};
