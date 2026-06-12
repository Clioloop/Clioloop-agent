"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

interface AdminUser {
  id: string;
  email: string;
  name: string;
  card_verified: number;
  email_verified: number;
  banned: number;
  created_at: number;
  plan: string;
  plan_status: string;
  used_micros: number;
  devices: number;
}

const eur = (m: number) => `€${(m / 1_000_000).toFixed(2)}`;

export default function AdminPage() {
  const router = useRouter();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [totals, setTotals] = useState<{ users: number; month_micros: number } | null>(null);
  const [month, setMonth] = useState("");

  const reload = useCallback(async () => {
    const res = await fetch("/api/admin");
    if (!res.ok) {
      router.replace("/dashboard");
      return;
    }
    const data = await res.json();
    setUsers(data.users);
    setTotals(data.totals);
    setMonth(data.month);
  }, [router]);

  useEffect(() => {
    reload();
  }, [reload]);

  const act = async (action: string, userId: string) => {
    await fetch("/api/admin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, user_id: userId }),
    });
    reload();
  };

  if (!users) {
    return (
      <div className="page">
        <div className="container" style={{ textAlign: "center", paddingTop: 80 }}>
          <span className="spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="container fade-up">
        <span className="eyebrow">admin</span>
        <h1 style={{ fontSize: 30, margin: "16px 0 6px" }}>Accounts</h1>
        <p style={{ color: "var(--text-dim)", fontSize: 14, marginBottom: 24 }}>
          {totals?.users} users · {eur(totals?.month_micros ?? 0)} metered in {month}
        </p>

        <div className="panel" style={{ overflowX: "auto", padding: 0 }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
            <thead>
              <tr style={{ fontFamily: "var(--mono)", fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--text-faint)" }}>
                {["Email", "Plan", "Usage", "Devices", "Flags", "Joined", "Actions"].map((h) => (
                  <th key={h} style={{ textAlign: "left", padding: "12px 16px", borderBottom: "1px solid var(--line)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} style={{ borderBottom: "1px solid rgba(47,230,185,0.07)", opacity: u.banned ? 0.5 : 1 }}>
                  <td style={{ padding: "10px 16px" }}>
                    {u.email}
                    {u.name && <span style={{ color: "var(--text-faint)" }}> · {u.name}</span>}
                  </td>
                  <td style={{ padding: "10px 16px" }}>
                    <span className="badge">{u.plan}</span>
                    {u.plan_status !== "active" && (
                      <span className="badge badge-amber" style={{ marginLeft: 6 }}>{u.plan_status}</span>
                    )}
                  </td>
                  <td style={{ padding: "10px 16px", fontFamily: "var(--mono)" }}>{eur(u.used_micros)}</td>
                  <td style={{ padding: "10px 16px", fontFamily: "var(--mono)" }}>{u.devices}</td>
                  <td style={{ padding: "10px 16px", fontFamily: "var(--mono)", fontSize: 11 }}>
                    {u.banned ? "BANNED" : [u.email_verified ? "email✓" : "email✗", u.card_verified ? "card✓" : "card✗"].join(" ")}
                  </td>
                  <td style={{ padding: "10px 16px", color: "var(--text-faint)", whiteSpace: "nowrap" }}>
                    {new Date(u.created_at * 1000).toLocaleDateString()}
                  </td>
                  <td style={{ padding: "10px 16px", whiteSpace: "nowrap" }}>
                    {u.banned ? (
                      <button className="btn btn-ghost btn-sm" onClick={() => act("unban", u.id)}>Unban</button>
                    ) : (
                      <button className="btn btn-danger btn-sm" onClick={() => act("ban", u.id)}>Ban</button>
                    )}{" "}
                    <button className="btn btn-ghost btn-sm" onClick={() => act("revoke_devices", u.id)} disabled={!u.devices}>
                      Revoke devices
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
