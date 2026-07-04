import type { Metadata } from "next";
import { DICTS } from "@/i18n/dictionaries";
import { LOCALES, isLocale, langAlternates, type Locale } from "@/i18n/locales";
import LandingSections from "@/components/landing/LandingSections";
import { demoTracks } from "@/components/landing/demoTracks";
import { MEDIA_ORIGIN, mediaUrl } from "@/lib/media";
import { notFound } from "next/navigation";

export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}
// Unknown top-level slugs keep 404ing exactly as before.
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
    title: t.landingTitle,
    description: t.landingDescription,
    alternates: { canonical: `/${locale}`, languages: langAlternates("/") },
    openGraph: { title: t.landingTitle, description: t.landingDescription },
  };
}

const introWebm = MEDIA_ORIGIN ? mediaUrl("video/introclio-720.webm") : "/brand/introclio.webm";
const introMp4 = MEDIA_ORIGIN ? mediaUrl("video/introclio-720.mp4") : "/brand/introclio.mp4";

export default async function LocaleLandingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  return (
    <LandingSections
      t={DICTS[locale as Locale].landing}
      demoTracks={demoTracks(locale)}
      introWebm={introWebm}
      introMp4={introMp4}
      pricingHref={`/${locale}/pricing`}
    />
  );
}
