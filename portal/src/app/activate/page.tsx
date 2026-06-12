import { Suspense } from "react";
import type { Metadata } from "next";
import ActivateForm from "@/components/ActivateForm";

export const metadata: Metadata = { title: "Activate a device — Omni Loop Portal" };

export default function ActivatePage() {
  return (
    <Suspense>
      <ActivateForm />
    </Suspense>
  );
}
