import { NextRequest, NextResponse } from "next/server";
import { resolveBearer } from "@/lib/tokens";
import { rateLimit } from "@/lib/ratelimit";
import {
  GATEWAY_VENDORS,
  checkGatewayEntitlement,
  gatewayRequestCostMicros,
  recordGatewayUsage,
  vendorUpstreamKey,
  vendorUpstreamOrigin,
} from "@/lib/gateway";

export const runtime = "nodejs";

// Hop-by-hop / connection-level headers we must not forward either way.
const STRIP_REQUEST_HEADERS = new Set([
  "host",
  "connection",
  "content-length",
  "authorization",
  "x-browser-use-api-key",
  "accept-encoding",
  "cookie",
]);
const STRIP_RESPONSE_HEADERS = new Set([
  "content-encoding",
  "content-length",
  "transfer-encoding",
  "connection",
  "set-cookie",
]);

type Ctx = { params: Promise<{ vendor: string; path?: string[] }> };

/**
 * Tool-gateway passthrough. The Clioloop agent authenticates with its
 * subscriber OAuth token and speaks each vendor's native API; the portal
 * gates on plan entitlement, swaps in the house upstream key, forwards the
 * request verbatim, and meters the call against the monthly allowance.
 */
async function proxy(req: NextRequest, ctx: Ctx) {
  const { vendor: vendorId, path = [] } = await ctx.params;
  const vendor = GATEWAY_VENDORS[vendorId];
  if (!vendor) {
    return NextResponse.json(
      { error: "unknown_vendor", message: `No such gateway vendor: ${vendorId}` },
      { status: 404 },
    );
  }

  const identity = resolveBearer(
    req.headers.get("authorization") ?? req.headers.get("x-browser-use-api-key"),
  );
  if (!identity) {
    return NextResponse.json(
      { error: "invalid_token", message: "Connect the Clioloop agent to the Omni Loop Portal first." },
      { status: 401 },
    );
  }

  const retry = rateLimit("gateway", identity.user.id);
  if (retry !== null) {
    return NextResponse.json(
      { error: "rate_limited", message: `Too many requests — try again in ${retry}s.` },
      { status: 429, headers: { "Retry-After": String(retry) } },
    );
  }

  const costMicros = gatewayRequestCostMicros(vendor, req.method, path);
  const denial = checkGatewayEntitlement(identity.user, vendor, costMicros);
  if (denial) {
    return NextResponse.json(
      { error: denial.error, message: denial.message },
      { status: denial.status },
    );
  }

  const upstreamUrl =
    vendorUpstreamOrigin(vendor) +
    "/" +
    path.map(encodeURIComponent).join("/") +
    (req.nextUrl.search || "");

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!STRIP_REQUEST_HEADERS.has(key.toLowerCase())) headers.set(key, value);
  });
  for (const [key, value] of Object.entries(vendor.authHeaders(vendorUpstreamKey(vendor)))) {
    headers.set(key, value);
  }

  // Buffer the body rather than streaming: vendor payloads are small, and
  // buffering keeps Content-Length intact for upstreams that dislike
  // chunked transfer encoding.
  const body =
    req.method === "GET" || req.method === "HEAD"
      ? undefined
      : Buffer.from(await req.arrayBuffer());

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      method: req.method,
      headers,
      body,
      redirect: "manual",
    });
  } catch (err) {
    return NextResponse.json(
      { error: "upstream_unreachable", message: `Could not reach the ${vendor.id} upstream: ${err}` },
      { status: 502 },
    );
  }

  recordGatewayUsage(identity.user.id, vendor, costMicros);

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!STRIP_RESPONSE_HEADERS.has(key.toLowerCase())) responseHeaders.set(key, value);
  });

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
  proxy as HEAD,
};
