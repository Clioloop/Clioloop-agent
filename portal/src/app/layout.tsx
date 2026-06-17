import type { Metadata } from "next";
import "./globals.css";
import { Footer, Nav } from "@/components/chrome";

const SITE_URL = "https://portal.clioloop.com";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Clioloop — Agentic Fusion AI assistant on open models",
    template: "%s · Clioloop",
  },
  description:
    "Clioloop is a self-improving AI assistant with Agentic Fusion — planner and reviewer models fuse one answer to create frontier intelligence on open models. 300+ models and a full tool gateway through one login. No API keys.",
  applicationName: "Clioloop",
  keywords: [
    "AI assistant",
    "frontier intelligence",
    "fusion",
    "agentic fusion",
    "model fusion",
    "open models",
    "AI agent",
    "autonomous agent",
    "Clioloop",
    "Omni Loop",
    "300+ models",
    "OpenRouter",
    "self-improving AI",
    "AI coding assistant",
  ],
  authors: [{ name: "Omni Loop Research Labs" }],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "Clioloop · Omni Loop Portal",
    title: "Clioloop — Agentic Fusion: frontier intelligence on open models",
    description:
      "A self-improving AI assistant with Agentic Fusion. 300+ models and a full tool gateway through one login. No API keys.",
    url: SITE_URL,
    images: [{ url: "/brand/banner.png", width: 1200, height: 630, alt: "Clioloop — Agentic Fusion" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Clioloop — Agentic Fusion: frontier intelligence on open models",
    description:
      "A self-improving AI assistant with Agentic Fusion. 300+ models and a full tool gateway through one login.",
    images: ["/brand/banner.png"],
  },
  robots: { index: true, follow: true },
};

// Organization-level structured data, site-wide.
const ORG_JSONLD = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Clioloop",
  alternateName: "Omni Loop",
  url: SITE_URL,
  logo: `${SITE_URL}/brand/banner.png`,
  sameAs: ["https://github.com/Clioloop/Clioloop-agent"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(ORG_JSONLD) }}
        />
        <video
          className="backdrop-video"
          aria-hidden
          autoPlay
          loop
          muted
          playsInline
          poster="/brand/banner.png"
          preload="metadata"
        >
          {/* WebM first: Linux browsers often lack the H.264 codec. */}
          <source src="/brand/backgroundvideoloop.webm" type="video/webm" />
          <source src="/brand/backgroundvideoloop.mp4" type="video/mp4" />
        </video>
        <div className="backdrop" aria-hidden />
        <Nav />
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
