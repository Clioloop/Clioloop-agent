import crypto from "node:crypto";
import { getDb, now, UserRow } from "./db";
import { hashToken } from "./tokens";
import { portalBaseUrl } from "./billing";

// ─── Email delivery (Resend) ─────────────────────────────────────────────────
// Without RESEND_API_KEY the portal runs in console mode: links are logged
// instead of sent, which keeps local development fully offline.

const FROM = () =>
  process.env.EMAIL_FROM?.trim() || "Omni Loop Portal <noreply@clioloop.com>";

export function emailConfigured(): boolean {
  return !!process.env.RESEND_API_KEY?.trim();
}

async function send(to: string, subject: string, html: string, actionUrl?: string): Promise<void> {
  if (!emailConfigured()) {
    console.log(
      `[email:console-mode] to=${to} subject=${JSON.stringify(subject)}` +
        (actionUrl ? ` url=${actionUrl}` : ""),
    );
    return;
  }
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.RESEND_API_KEY!.trim()}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ from: FROM(), to: [to], subject, html }),
  });
  if (!res.ok) {
    throw new Error(`resend ${res.status}: ${(await res.text()).slice(0, 200)}`);
  }
}

// ─── Branded template ────────────────────────────────────────────────────────

function layout(heading: string, bodyHtml: string, ctaLabel: string, ctaUrl: string): string {
  return `
  <div style="background:#0c0a14;padding:40px 16px;font-family:-apple-system,Segoe UI,Roboto,sans-serif">
    <div style="max-width:480px;margin:0 auto;border:1px solid rgba(139,92,246,0.2);background:#14101f;padding:36px">
      <div style="font-family:monospace;font-size:12px;letter-spacing:3px;text-transform:uppercase;color:#8b5cf6;margin-bottom:24px">
        &#8734; Omni Loop Portal
      </div>
      <h1 style="color:#f2efe6;font-size:22px;margin:0 0 14px">${heading}</h1>
      <div style="color:#9d93a6;font-size:14.5px;line-height:1.7">${bodyHtml}</div>
      <a href="${ctaUrl}"
         style="display:inline-block;margin-top:26px;background:#8b5cf6;color:#0c0a14;font-family:monospace;font-size:13px;font-weight:600;letter-spacing:2px;text-transform:uppercase;text-decoration:none;padding:13px 26px">
        ${ctaLabel}
      </a>
      <p style="color:#5d7068;font-size:12px;margin-top:26px;line-height:1.6">
        Or paste this link into your browser:<br>
        <span style="font-family:monospace;color:#9d93a6;word-break:break-all">${ctaUrl}</span>
      </p>
    </div>
    <p style="max-width:480px;margin:18px auto 0;color:#5d7068;font-size:11.5px;font-family:monospace">
      Sent by the Omni Loop Portal &middot; the subscription gateway for the Clioloop agent.
      If you didn't request this, you can safely ignore it.
    </p>
  </div>`;
}

// ─── Action tokens (single-use, hashed, expiring) ────────────────────────────

const TOKEN_TTL: Record<string, number> = {
  verify: 24 * 3600,
  reset: 30 * 60,
};

export function createActionToken(userId: string, kind: "verify" | "reset"): string {
  const db = getDb();
  const token = `olp_${kind}_` + crypto.randomBytes(32).toString("base64url");
  // Invalidate any previous outstanding token of the same kind.
  db.prepare("UPDATE action_tokens SET used = 1 WHERE user_id = ? AND kind = ?").run(userId, kind);
  db.prepare(
    `INSERT INTO action_tokens (id, user_id, kind, token_hash, created_at, expires_at)
     VALUES (?, ?, ?, ?, ?, ?)`,
  ).run(crypto.randomUUID(), userId, kind, hashToken(token), now(), now() + TOKEN_TTL[kind]);
  return token;
}

/** Consume a token: marks it used and returns the user id, or null. */
export function consumeActionToken(token: string, kind: "verify" | "reset"): string | null {
  const db = getDb();
  const row = db
    .prepare(
      `SELECT id, user_id FROM action_tokens
       WHERE token_hash = ? AND kind = ? AND used = 0 AND expires_at > ?`,
    )
    .get(hashToken(token), kind, now()) as { id: string; user_id: string } | undefined;
  if (!row) return null;
  db.prepare("UPDATE action_tokens SET used = 1 WHERE id = ?").run(row.id);
  return row.user_id;
}

// ─── The two emails ──────────────────────────────────────────────────────────

export async function sendVerificationEmail(user: UserRow): Promise<void> {
  const token = createActionToken(user.id, "verify");
  const url = `${portalBaseUrl()}/api/auth/verify?token=${encodeURIComponent(token)}`;
  await send(
    user.email,
    "Verify your email — Omni Loop Portal",
    layout(
      "Verify your email",
      `Welcome${user.name ? `, ${user.name}` : ""}! Confirm this address to activate
       device connections and plan upgrades on your account.
       <br><br>This link is valid for 24 hours.`,
      "Verify email",
      url,
    ),
    url,
  );
}

export async function sendPasswordResetEmail(user: UserRow): Promise<void> {
  const token = createActionToken(user.id, "reset");
  const url = `${portalBaseUrl()}/reset?token=${encodeURIComponent(token)}`;
  await send(
    user.email,
    "Reset your password — Omni Loop Portal",
    layout(
      "Reset your password",
      `Someone (hopefully you) asked to reset the password for <strong style="color:#f2efe6">${user.email}</strong>.
       <br><br>This link is valid for 30 minutes and can be used once.`,
      "Choose a new password",
      url,
    ),
    url,
  );
}
