import type { Metadata, Viewport } from "next";
import { Bodoni_Moda, Instrument_Sans, JetBrains_Mono } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";
import { Footer, Nav } from "@/components/chrome";
import { SITE_URL } from "@/lib/site";
import { mediaUrl } from "@/lib/media";

// The Conductor type system: a concert-poster Didone for display sizes only,
// a quiet grotesque for everything else, mono for terminals and labels.
const display = Bodoni_Moda({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});
const body = Instrument_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});
const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0a0e16",
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Clioloop — the autonomous AI assistant with Agentic Fusion",
    template: "%s · Clioloop",
  },
  description:
    "Clioloop is a self-improving AI assistant with Agentic Fusion — planner and reviewer models fuse one answer to create frontier intelligence on open models. 300+ models, AI music generation, web search, image and video generation through one login. No API keys.",
  applicationName: "Clioloop",
  keywords: [
    "AI assistant",
    "autonomous AI agent",
    "AI agent",
    "agentic fusion",
    "AI music generator",
    "AI music generation",
    "generate songs with AI",
    "model fusion",
    "open models",
    "300+ AI models",
    "OpenRouter",
    "self-improving AI",
    "AI coding assistant",
    "AI assistant for Telegram",
    "AI assistant for WhatsApp",
    "KI-Assistent",
    "assistant IA",
    "asistente de IA",
    "assistente de IA",
    "AIアシスタント",
    "AI助手",
    "Clioloop",
    "Omni Loop",
  ],
  authors: [{ name: "Omni Loop Research Labs" }],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "Clioloop · Omni Loop Portal",
    title: "Clioloop — the autonomous AI assistant with Agentic Fusion",
    description:
      "One login, an orchestra of 300+ models: Agentic Fusion, AI music generation, web search, image and video generation, cloud browser. No API keys.",
    url: SITE_URL,
  },
  twitter: {
    card: "summary_large_image",
    title: "Clioloop — the autonomous AI assistant with Agentic Fusion",
    description:
      "One login, an orchestra of 300+ models: Agentic Fusion, AI music generation and the full tool gateway. No API keys.",
  },
  robots: { index: true, follow: true },
};

// Organization + WebSite structured data, site-wide.
const ORG_JSONLD = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Clioloop",
  alternateName: "Omni Loop",
  url: SITE_URL,
  logo: `${SITE_URL}/brand/banner.png`,
  sameAs: ["https://github.com/Clioloop/Clioloop-agent"],
};
const WEBSITE_JSONLD = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "Clioloop · Omni Loop Portal",
  url: SITE_URL,
  inLanguage: ["en", "de", "fr", "es", "pt", "ja", "zh"],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const lang = (await headers()).get("x-olp-locale") ?? "en";
  return (
    <html lang={lang}>
      <body className={`${display.variable} ${body.variable} ${mono.variable}`}>
        {/* Scroll-reveal styles only apply once JS is confirmed present, so
            content is never hidden for crawlers or no-JS readers. */}
        <script dangerouslySetInnerHTML={{ __html: `document.documentElement.classList.add("js")` }} />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(ORG_JSONLD) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(WEBSITE_JSONLD) }}
        />
        <video
          className="backdrop-video"
          aria-hidden
          autoPlay
          loop
          muted
          playsInline
          poster={mediaUrl("img/banner.png")}
          preload="metadata"
        >
          {/* WebM first: Linux browsers often lack the H.264 codec. */}
          <source src={mediaUrl("video/backgroundvideoloop.webm")} type="video/webm" />
          <source src={mediaUrl("video/backgroundvideoloop.mp4")} type="video/mp4" />
        </video>
        <div className="backdrop" aria-hidden />
        <Nav />
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
