import type { Metadata } from "next";
import { en } from "@/i18n/dictionaries";
import { langAlternates } from "@/i18n/locales";
import LandingSections from "@/components/landing/LandingSections";
import { demoTracks } from "@/components/landing/demoTracks";
import { mediaUrl, MEDIA_ORIGIN } from "@/lib/media";
import { SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  title: en.meta.landingTitle,
  description: en.meta.landingDescription,
  alternates: { canonical: "/", languages: langAlternates("/") },
};

// SoftwareApplication structured data lives on the home page so the product,
// its offers and the Fusion/music features are indexable.
const APP_JSONLD = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Clioloop",
  alternateName: "Omni Loop",
  applicationCategory: "DeveloperApplication",
  operatingSystem: "macOS, Linux, Windows",
  description: en.meta.landingDescription,
  url: SITE_URL,
  offers: [
    { "@type": "Offer", name: "Free", price: "0", priceCurrency: "EUR" },
    { "@type": "Offer", name: "Pro", price: "20", priceCurrency: "EUR" },
    { "@type": "Offer", name: "Max", price: "100", priceCurrency: "EUR" },
    { "@type": "Offer", name: "Max 10x", price: "250", priceCurrency: "EUR" },
  ],
  featureList: [
    "Agentic Fusion — planner and reviewer models fuse one answer",
    "300+ frontier and open models through one login",
    "AI music generation — full songs with vocals, lyrics and stems",
    "Video generation, image generation and premium text-to-speech",
    "Web search & extract and a cloud browser",
    "Standing goals and autonomous loops",
    "Multi-agent Kanban, memory and self-learning skills",
    "Messaging gateway: Telegram, WhatsApp, Signal, Slack, iMessage, Matrix and more",
  ],
};

// The lighter 720p intro lives on the CDN; the committed originals are the
// no-configuration fallback for local dev.
const introWebm = MEDIA_ORIGIN ? mediaUrl("video/introclio-720.webm") : "/brand/introclio.webm";
const introMp4 = MEDIA_ORIGIN ? mediaUrl("video/introclio-720.mp4") : "/brand/introclio.mp4";

export default function LandingPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(APP_JSONLD) }}
      />
      <LandingSections
        t={en.landing}
        demoTracks={demoTracks("en")}
        introWebm={introWebm}
        introMp4={introMp4}
        pricingHref="/pricing"
      />
    </>
  );
}
