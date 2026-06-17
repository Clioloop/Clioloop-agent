"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function PlanButton({
  plan,
  label,
  featured,
}: {
  plan: string;
  label: string;
  featured?: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const choose = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan }),
      });
      if (res.status === 401) {
        router.push(`/signup?plan=${plan}`);
        return;
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Checkout failed");
      window.location.href = data.url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setBusy(false);
    }
  };

  return (
    <>
      <button
        className={`btn btn-block ${featured ? "btn-primary" : "btn-ghost"}`}
        onClick={choose}
        disabled={busy}
      >
        {busy ? <span className="spin" /> : label}
      </button>
      {error && (
        <p style={{ color: "var(--red)", fontSize: 13, marginTop: 10, textAlign: "center" }}>
          {error}
        </p>
      )}
    </>
  );
}
