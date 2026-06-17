import { Suspense } from "react";
import type { Metadata } from "next";
import Dashboard from "@/components/Dashboard";

export const metadata: Metadata = { title: "Dashboard — Omni Loop Portal" };

export default function DashboardPage() {
  return (
    <Suspense>
      <Dashboard />
    </Suspense>
  );
}
