import type { Metadata } from "next";
import "./globals.css";
import { Footer, Nav } from "@/components/chrome";

export const metadata: Metadata = {
  title: "Omni Loop Portal — model access for Clioloop",
  description:
    "One subscription, every frontier model. Connect your Clioloop agent to 300+ models with a single login — CLI, TUI, desktop and dashboard.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
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
