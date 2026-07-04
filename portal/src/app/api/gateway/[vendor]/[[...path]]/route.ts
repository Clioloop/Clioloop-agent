import { NextRequest, NextResponse } from "next/server";
import { withBearer } from "@/lib/handlers";
import { rateLimit } from "@/lib/ratelimit";
import {
  GATEWAY_VENDORS,
  checkGatewayEntitlement,
  gatewayRequestCostMicros,
  gatewayShouldRecordUsage,
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
const proxy = withBearer(async (req: NextRequest, identity, ctx: Ctx) => {
  const { vendor: vendorId, path = [] } = await ctx.params;
  const vendor = GATEWAY_VENDORS[vendorId];
  if (!vendor) {
    return NextResponse.json(
      { error: "unknown_vendor", message: `No such gateway vendor: ${vendorId}` },
      { status: 404 },
    );
  }

  const retry = rateLimit("gateway", identity.user.id);
  if (retry !== null) {
    return NextResponse.json(
      { error: "rate_limited", message: `Too many requests — try again in ${retry}s.` },
      { status: 429, headers: { "Retry-After": String(retry) } },
    );
  }

  // Buffer the body once. Vendor payloads are small, and Vidu metering needs
  // the requested duration/resolution before we forward the generation task.
  const body =
    req.method === "GET" || req.method === "HEAD"
      ? undefined
      : Buffer.from(await req.arrayBuffer());

  const costMicros = gatewayRequestCostMicros(vendor, req.method, path, body);
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

  let upstreamPayload: unknown = undefined;
  if (costMicros > 0) {
    try {
      upstreamPayload = await upstream.clone().json();
    } catch {
      upstreamPayload = undefined;
    }
  }
  if (gatewayShouldRecordUsage(vendor, req.method, path, upstream.status, upstreamPayload)) {
    recordGatewayUsage(identity.user.id, vendor, costMicros);
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!STRIP_RESPONSE_HEADERS.has(key.toLowerCase())) responseHeaders.set(key, value);
  });

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}, {
  credential: (req) =>
    req.headers.get("authorization") ?? req.headers.get("x-browser-use-api-key"),
  unauthorized: () =>
    NextResponse.json(
      { error: "invalid_token", message: "Connect the Clioloop agent to the Omni Loop Portal first." },
      { status: 401 },
    ),
});

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
  proxy as HEAD,
};
