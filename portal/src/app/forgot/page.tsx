"use client";

import Link from "next/link";
import { useState } from "react";

export default function ForgotPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const res = await fetch("/api/auth/forgot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    setBusy(false);
    if (res.ok) setSent(true);
    else setError((await res.json()).message ?? "Something went wrong — try again.");
  };

  return (
    <div className="page">
      <div className="container page-narrow fade-up">
        <div className="form-card">
          <h1>Reset your password</h1>
          <p className="form-sub">
            Enter your account email and we&apos;ll send a single-use reset link
            (valid 30 minutes).
          </p>
          {sent ? (
            <div className="form-success">
              If that address has an account, a reset link is on its way. Check
              your inbox — and the spam folder, just in case.
            </div>
          ) : (
            <form onSubmit={submit}>
              {error && <div className="form-error">{error}</div>}
              <div className="field">
                <label>Email</label>
                <input
                  className="input"
                  type="email"
                  required
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                />
              </div>
              <button className="btn btn-primary btn-block" disabled={busy}>
                {busy ? <span className="spin" /> : "Send reset link"}
              </button>
            </form>
          )}
          <p className="form-foot">
            Remembered it? <Link href="/login">Log in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
