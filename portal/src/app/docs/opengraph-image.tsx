import { conductorOgImage, OG_SIZE } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Clioloop documentation";

export default function Image() {
  return conductorOgImage(
    "The conductor's manual.",
    "Docs — setup, Agentic Fusion, goals, tools, music generation",
  );
}
