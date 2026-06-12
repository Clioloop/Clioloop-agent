"use client";

import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useState } from "react";

function ResetForm() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setBusy(true);
    setError("");
    const res = await fetch("/api/auth/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, password }),
    });
    const data = await res.json();
    setBusy(false);
    if (res.ok) {
      setDone(true);
      setTimeout(() => router.push("/login"), 2500);
    } else {
      setError(data.error ?? "Something went wrong — try again.");
    }
  };

  return (
    <div className="form-card">
      <h1>Choose a new password</h1>
      <p className="form-sub">
        This also signs out every connected device, so reconnect them with{" "}
        <code>clio setup</code> afterwards.
      </p>
      {done ? (
        <div className="form-success">
          Password updated — taking you to the login…
        </div>
      ) : !token ? (
        <div className="form-error">
          This page needs a reset link from your email.{" "}
          <Link href="/forgot">Request one here.</Link>
        </div>
      ) : (
        <form onSubmit={submit}>
          {error && <div className="form-error">{error}</div>}
          <div className="field">
            <label>New password</label>
            <input
              className="input"
              type="password"
              required
              minLength={8}
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
            />
          </div>
          <div className="field">
            <label>Confirm password</label>
            <input
              className="input"
              type="password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </div>
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? <span className="spin" /> : "Set new password"}
          </button>
        </form>
      )}
    </div>
  );
}

export default function ResetPage() {
  return (
    <div className="page">
      <div className="container page-narrow fade-up">
        <Suspense>
          <ResetForm />
        </Suspense>
      </div>
    </div>
  );
}
