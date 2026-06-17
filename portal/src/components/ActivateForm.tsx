"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

type Phase = "input" | "done" | "denied";

export default function ActivateForm() {
  const params = useSearchParams();
  const router = useRouter();
  const [code, setCode] = useState(params.get("code") ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState<Phase>("input");
  const [loggedIn, setLoggedIn] = useState<boolean | null>(null);

  useEffect(() => {
    fetch("/api/me").then((r) => setLoggedIn(r.ok));
  }, []);

  useEffect(() => {
    if (loggedIn === false) {
      const next = encodeURIComponent(`/activate${code ? `?code=${code}` : ""}`);
      router.replace(`/login?next=${next}`);
    }
  }, [loggedIn, code, router]);

  const act = async (action: "approve" | "deny") => {
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/device/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_code: code.trim(), action }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message ?? data.error ?? "Activation failed");
      setPhase(action === "approve" ? "done" : "denied");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Activation failed");
    } finally {
      setBusy(false);
    }
  };

  if (loggedIn === null || loggedIn === false) {
    return (
      <div className="page">
        <div className="container page-narrow" style={{ textAlign: "center", paddingTop: 80 }}>
          <span className="spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="container page-narrow fade-up">
        <div className="form-card" style={{ textAlign: "center" }}>
          {phase === "done" ? (
            <>
              <div style={{ fontSize: 52, marginBottom: 12 }}>✅</div>
              <h1>Device connected</h1>
              <p className="form-sub" style={{ marginTop: 8 }}>
                You can close this tab and head back to your terminal — Clioloop is
                finishing the login automatically.
              </p>
              <Link href="/dashboard" className="btn btn-ghost">
                Go to dashboard
              </Link>
            </>
          ) : phase === "denied" ? (
            <>
              <div style={{ fontSize: 52, marginBottom: 12 }}>🚫</div>
              <h1>Device denied</h1>
              <p className="form-sub" style={{ marginTop: 8 }}>
                The login attempt was rejected. If this wasn&apos;t you, consider changing
                your password.
              </p>
            </>
          ) : (
            <>
              <h1>Connect a device</h1>
              <p className="form-sub">
                A Clioloop install is asking to use your account. Make sure the code below
                matches what your terminal shows, then approve.
              </p>
              {error && <div className="form-error">{error}</div>}
              <div className="field">
                <input
                  className="input input-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  placeholder="XXXX-XXXX"
                  maxLength={9}
                  spellCheck={false}
                  autoFocus
                />
              </div>
              <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
                <button
                  className="btn btn-primary btn-lg"
                  style={{ flex: 1 }}
                  disabled={busy || code.trim().length < 9}
                  onClick={() => act("approve")}
                >
                  {busy ? <span className="spin" /> : "Approve device"}
                </button>
                <button
                  className="btn btn-ghost btn-lg"
                  disabled={busy}
                  onClick={() => act("deny")}
                >
                  Deny
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
