import { NextRequest, NextResponse } from "next/server";
import { BearerIdentity, resolveBearer } from "./tokens";
import { getSessionUser } from "./session";
import { rateLimitResponse } from "./ratelimit";
import { UserRow } from "./db";

// Route-handler wrappers: every authenticated route repeats the same
// credential-resolution + 401 dance. These centralize it while letting a
// route keep its consumer-specific error envelope (the chat-completions
// route must stay OpenAI-shaped; account/info returns logged_in:false; the
// tool gateway uses {error, message}) via the `unauthorized` option.

interface BearerOptions {
  /** Override the 401 body when the credential is missing/invalid. */
  unauthorized?: () => NextResponse;
  /** Where to read the credential from (default: Authorization header). */
  credential?: (req: NextRequest) => string | null;
}

/** Wrap a route handler behind Bearer-token auth (device-flow OAuth). */
export function withBearer<C>(
  handler: (
    req: NextRequest,
    identity: BearerIdentity,
    ctx: C,
  ) => Promise<Response> | Response,
  options: BearerOptions = {},
): (req: NextRequest, ctx: C) => Promise<Response> {
  return async (req, ctx) => {
    const raw = options.credential
      ? options.credential(req)
      : req.headers.get("authorization");
    const identity = resolveBearer(raw);
    if (!identity) {
      return (
        options.unauthorized?.() ??
        NextResponse.json(
          {
            error: "invalid_token",
            message: "Provide a valid Omni Loop Portal token.",
          },
          { status: 401 },
        )
      );
    }
    return handler(req, identity, ctx);
  };
}

interface UserOptions {
  /** IP-keyed rate limit applied BEFORE auth (protects the auth path itself). */
  rateLimit?: Parameters<typeof rateLimitResponse>[0];
}

/** Wrap a route handler behind session-cookie auth (web dashboard). */
export function withUser<C>(
  handler: (req: NextRequest, user: UserRow, ctx: C) => Promise<Response> | Response,
  options: UserOptions = {},
): (req: NextRequest, ctx: C) => Promise<Response> {
  return async (req, ctx) => {
    if (options.rateLimit) {
      const limited = rateLimitResponse(options.rateLimit, req);
      if (limited) return limited;
    }
    const user = await getSessionUser();
    if (!user) {
      return NextResponse.json({ error: "not_authenticated" }, { status: 401 });
    }
    return handler(req, user, ctx);
  };
}
