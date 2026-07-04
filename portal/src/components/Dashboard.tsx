"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

interface Me {
  user: { email: string; name: string; card_verified: boolean; email_verified: boolean };
  plan: {
    id: string;
    name: string;
    price_eur: number;
    status: string;
    renews_at: number | null;
    free_models_only: boolean;
  };
  usage: { month: string; used_micros: number; limit_micros: number };
  services: Record<string, boolean>;
  connected_devices: number;
  mock_billing: boolean;
}


const SERVICE_LABELS: [string, string][] = [
  ["web", "Web search & extract"],
  ["browser", "Cloud browser"],
  ["image_gen", "Image generation"],
  ["video_gen", "Video generation"],
  ["music_gen", "Music generation"],
  ["tts", "Premium TTS"],
];

export default function Dashboard() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  const reload = useCallback(async () => {
    const res = await fetch("/api/me");
    if (res.status === 401) {
      router.replace("/login?next=/dashboard");
      return;
    }
    setMe(await res.json());
  }, [router]);

  useEffect(() => {
    reload();
  }, [reload]);

  const [resent, setResent] = useState(false);
  const resendVerification = async () => {
    const res = await fetch("/api/auth/verify", { method: "POST" });
    if (res.ok) setResent(true);
  };

  if (!me) {
    return (
      <div className="page">
        <div className="container" style={{ textAlign: "center", paddingTop: 80 }}>
          <span className="spin" />
        </div>
      </div>
    );
  }

  const pct = Math.min(100, (me.usage.used_micros / Math.max(1, me.usage.limit_micros)) * 100);

  const manageBilling = async () => {
    const res = await fetch("/api/billing/manage", { method: "POST" });
    const data = await res.json();
    if (res.ok && data.url) window.location.href = data.url;
  };

  const verifyCard = async () => {
    const res = await fetch("/api/billing/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan: "free" }),
    });
    const data = await res.json();
    if (res.ok && data.url) window.location.href = data.url;
  };

  return (
    <div className="page">
      <div className="container fade-up">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 12,
            marginBottom: 28,
          }}
        >
          <div>
            <h1 style={{ fontSize: 30, letterSpacing: "-0.02em" }}>
              {me.user.name ? `Hey, ${me.user.name}` : "Your account"}
            </h1>
            <p style={{ color: "var(--text-dim)", fontSize: 14.5 }}>{me.user.email}</p>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <span className="badge badge-violet">{me.plan.name} plan</span>
            {me.plan.status !== "active" && (
              <span className="badge badge-amber">{me.plan.status}</span>
            )}
            {/* Plain <a>: /api/auth/logout is an API route — <Link> would
                prefetch it and log the user out on hover. */}
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a href="/api/auth/logout" className="btn btn-ghost btn-sm">
              Log out
            </a>
          </div>
        </div>

        {me.mock_billing && (
          <div className="form-success" style={{ marginBottom: 20 }}>
            Billing is in mock mode (no Stripe key configured) — plan changes apply
            instantly without payment. Perfect for local development.
          </div>
        )}

        {!me.user.email_verified && (
          <div
            className="panel"
            style={{ borderColor: "rgba(139,92,246,0.4)", marginBottom: 20 }}
          >
            <h2>📬 Verify your email</h2>
            <p style={{ color: "var(--text-dim)", fontSize: 14.5, marginBottom: 14 }}>
              We sent a link to <strong>{me.user.email}</strong>. Verifying unlocks
              device connections and plan changes.
            </p>
            {resent ? (
              <span className="badge">✓ sent — check your inbox</span>
            ) : (
              <button className="btn btn-ghost btn-sm" onClick={resendVerification}>
                Resend email
              </button>
            )}
          </div>
        )}

        {me.plan.id === "free" && !me.user.card_verified && (
          <div
            className="panel"
            style={{ borderColor: "rgba(251,191,36,0.4)", background: "rgba(251,191,36,0.05)" }}
          >
            <h2>⚠️ Verify your card to activate the Free plan</h2>
            <p style={{ color: "var(--text-dim)", fontSize: 14.5, marginBottom: 16 }}>
              The Free plan needs a one-time card verification (a €0 authorization — you
              will never be charged). This keeps the free model available for everyone.
            </p>
            <button className="btn btn-primary" onClick={verifyCard}>
              Verify card
            </button>
          </div>
        )}

        <div className="dash-grid">
          <div>
            {/* Usage */}
            <div className="panel">
              <h2>Usage — {me.usage.month}</h2>
              <div className="usage-bar">
                <div style={{ width: `${pct}%` }} />
              </div>
              <div className="stat-row">
                <span>Used this month</span>
                <span>{pct.toFixed(1)}%</span>
              </div>
              <div className="stat-row">
                <span>Connected devices</span>
                <span>{me.connected_devices}</span>
              </div>
              {me.plan.free_models_only && (
                <p style={{ color: "var(--text-faint)", fontSize: 13, marginTop: 12 }}>
                  The Free plan includes one free model.{" "}
                  <Link href="/pricing">Upgrade</Link> for many more models and the
                  frontier catalog.
                </p>
              )}
            </div>

            {/* Tool Gateway services */}
            <div className="panel">
              <h2>Tool Gateway</h2>
              <p style={{ color: "var(--text-dim)", fontSize: 14, marginBottom: 12 }}>
                Agent services bundled with your plan — your Clioloop tools route
                through the portal automatically once connected. No vendor accounts,
                no API keys.
              </p>
              {SERVICE_LABELS.map(([key, label]) => (
                <div key={key} className="service-row">
                  <span>{label}</span>
                  {me.services?.[key] ? (
                    <span className="service-on">● INCLUDED</span>
                  ) : (
                    <span className="service-off">○ NOT IN PLAN</span>
                  )}
                </div>
              ))}
              {!me.services?.video_gen && (
                <p style={{ color: "var(--text-faint)", fontSize: 13, marginTop: 12 }}>
                  <Link href="/pricing">Upgrade</Link> to unlock more gateway services.
                </p>
              )}
            </div>
          </div>

          <div>
            {/* Plan */}
            <div className="panel">
              <h2>Plan</h2>
              <div className="plan-price" style={{ fontSize: 34, margin: "4px 0" }}>
                €{me.plan.price_eur}
                <span style={{ fontSize: 14, color: "var(--text-dim)", fontWeight: 500 }}>
                  {" "}
                  /month
                </span>
              </div>
              {me.plan.renews_at && (
                <p style={{ color: "var(--text-faint)", fontSize: 13, marginBottom: 14 }}>
                  Renews {new Date(me.plan.renews_at * 1000).toLocaleDateString()}
                </p>
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 14 }}>
                <Link href="/pricing" className="btn btn-primary btn-block">
                  Change plan
                </Link>
                <button className="btn btn-ghost btn-block" onClick={manageBilling}>
                  Manage billing
                </button>
              </div>
            </div>

            {/* Connect */}
            <div className="panel">
              <h2>Connect a device</h2>
              <p style={{ color: "var(--text-dim)", fontSize: 14 }}>
                The portal connects exclusively to the Clioloop agent. In any surface,
                pick <strong>Omni Loop Portal</strong>:
              </p>
              <div className="code-block">
                <span className="c-comment"># first-time setup</span>
                <br />
                <span className="c-cmd">clio setup</span>
                <br />
                <span className="c-comment"># or connect directly</span>
                <br />
                <span className="c-cmd">clio auth add managed</span>
              </div>
              <p style={{ color: "var(--text-faint)", fontSize: 13 }}>
                Then approve the device code in this portal. The desktop app and web
                dashboard have a &quot;Connect&quot; button that does the same.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
