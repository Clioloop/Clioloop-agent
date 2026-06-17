import { NextRequest, NextResponse } from "next/server";
import { getDb, now } from "@/lib/db";
import { issueTokenPair, rotateRefreshToken } from "@/lib/tokens";
import { portalBaseUrl } from "@/lib/billing";
import { rateLimitResponse } from "@/lib/ratelimit";

export const runtime = "nodejs";

const DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code";

function oauthError(error: string, description: string, status = 400) {
  return NextResponse.json({ error, error_description: description }, { status });
}

/**
 * OAuth token endpoint consumed by the Clioloop CLI.
 *  - device_code grant: form {grant_type, client_id, device_code}
 *  - refresh grant:     form {grant_type: "refresh_token", client_id} with the
 *    refresh token in the `x-managed-refresh-token` header (single-use,
 *    rotated; reuse revokes the whole session family).
 */
export async function POST(req: NextRequest) {
  const limited = rateLimitResponse("oauth_token", req);
  if (limited) return limited;

  const form = await req.formData().catch(() => null);
  const grantType = String(form?.get("grant_type") ?? "").trim();
  const clientId = String(form?.get("client_id") ?? "clio-cli").trim();

  if (grantType === DEVICE_GRANT) {
    const deviceCode = String(form?.get("device_code") ?? "").trim();
    if (!deviceCode) return oauthError("invalid_request", "device_code is required");

    const db = getDb();
    const row = db
      .prepare("SELECT * FROM device_codes WHERE device_code = ?")
      .get(deviceCode) as
      | { device_code: string; status: string; user_id: string | null; scope: string; expires_at: number }
      | undefined;

    if (!row) return oauthError("invalid_grant", "Unknown device code");
    if (row.expires_at < now()) {
      return oauthError("expired_token", "The device code has expired — restart the login");
    }
    switch (row.status) {
      case "pending":
        return oauthError("authorization_pending", "Waiting for the user to approve the device");
      case "denied":
        return oauthError("access_denied", "The user denied this device");
      case "consumed":
        return oauthError("invalid_grant", "This device code was already used");
      case "approved": {
        if (!row.user_id) return oauthError("invalid_grant", "Grant has no associated user");
        db.prepare("UPDATE device_codes SET status = 'consumed' WHERE device_code = ?").run(deviceCode);
        const pair = issueTokenPair(row.user_id, clientId, row.scope || "inference:invoke");
        // The Clioloop CLI honors a portal-provided inference URL, keeping
        // clients correct even when the portal moves hosts.
        return NextResponse.json({ ...pair, inference_base_url: `${portalBaseUrl()}/api/v1` });
      }
      default:
        return oauthError("invalid_grant", "Device code is in an unexpected state");
    }
  }

  if (grantType === "refresh_token") {
    const refreshToken =
      req.headers.get("x-managed-refresh-token")?.trim() ||
      String(form?.get("refresh_token") ?? "").trim();
    if (!refreshToken) return oauthError("invalid_request", "refresh token is required");

    const result = rotateRefreshToken(refreshToken);
    if (!result.ok) {
      if (result.error === "refresh_token_reused") {
        return oauthError(
          "refresh_token_reused",
          "Refresh-token reuse detected; the session chain was revoked. Re-authenticate.",
          401,
        );
      }
      return oauthError("invalid_grant", "Refresh token is invalid or revoked", 401);
    }
    return NextResponse.json(result.pair);
  }

  return oauthError("unsupported_grant_type", `Unsupported grant_type: ${grantType || "(empty)"}`);
}
