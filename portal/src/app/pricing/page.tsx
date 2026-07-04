import type { Metadata } from "next";
import { en } from "@/i18n/dictionaries";
import { langAlternates } from "@/i18n/locales";
import PricingSections from "@/components/landing/PricingSections";

export const metadata: Metadata = {
  title: en.meta.pricingTitle,
  description: en.meta.pricingDescription,
  alternates: { canonical: "/pricing", languages: langAlternates("/pricing") },
};

export default function PricingPage() {
  return <PricingSections t={en.pricing} />;
}
