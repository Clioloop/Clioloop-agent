import type { Metadata } from "next";
import { DICTS } from "@/i18n/dictionaries";
import { LOCALES, isLocale, langAlternates, type Locale } from "@/i18n/locales";
import PricingSections from "@/components/landing/PricingSections";
import { notFound } from "next/navigation";

export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}
export const dynamicParams = false;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = DICTS[locale].meta;
  return {
    title: t.pricingTitle,
    description: t.pricingDescription,
    alternates: { canonical: `/${locale}/pricing`, languages: langAlternates("/pricing") },
    openGraph: { title: t.pricingTitle, description: t.pricingDescription },
  };
}

export default async function LocalePricingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return <PricingSections t={DICTS[locale as Locale].pricing} />;
}
