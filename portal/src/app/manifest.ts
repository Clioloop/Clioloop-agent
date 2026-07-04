import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Clioloop · Omni Loop Portal",
    short_name: "Clioloop",
    description:
      "The autonomous AI assistant with Agentic Fusion — 300+ models, AI music generation and a full tool gateway through one login.",
    start_url: "/",
    display: "standalone",
    background_color: "#0a0e16",
    theme_color: "#0a0e16",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
      { src: "/apple-icon", sizes: "180x180", type: "image/png" },
    ],
  };
}
