"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const next = params.get("next");
  const plan = params.get("plan");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/api/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mode === "signup" ? { email, password, name } : { email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Something went wrong");

      if (plan && plan !== "free") {
        // Came from pricing: continue straight into checkout for that plan.
        const co = await fetch("/api/billing/checkout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plan }),
        });
        const coData = await co.json();
        if (co.ok && coData.url) {
          window.location.href = coData.url;
          return;
        }
      }
      router.push(next || "/dashboard");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="container page-narrow fade-up">
        <div className="form-card">
          <h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1>
          <p className="form-sub">
            {mode === "login"
              ? "Log in to manage your plan, devices and usage."
              : "One account connects every Clioloop surface to 300+ models."}
          </p>
          {error && <div className="form-error">{error}</div>}
          <form onSubmit={submit}>
            {mode === "signup" && (
              <div className="field">
                <label htmlFor="name">Name (optional)</label>
                <input
                  id="name"
                  className="input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ada Lovelace"
                  autoComplete="name"
                />
              </div>
            )}
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                className="input"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
              />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                className="input"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === "signup" ? "At least 8 characters" : "••••••••"}
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
              />
            </div>
            <button className="btn btn-primary btn-block btn-lg" disabled={busy}>
              {busy ? <span className="spin" /> : mode === "login" ? "Log in" : "Create account"}
            </button>
          </form>
          <p className="form-foot">
            {mode === "login" ? (
              <>
                New here?{" "}
                <Link href={`/signup${plan ? `?plan=${plan}` : ""}`}>Create an account</Link>
                {" · "}
                <Link href="/forgot">Forgot password?</Link>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <Link href={`/login${plan ? `?plan=${plan}` : ""}`}>Log in</Link>
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
