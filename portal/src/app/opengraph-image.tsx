import { conductorOgImage, OG_SIZE } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Clioloop — every model, one orchestra";

export default function Image() {
  return conductorOgImage(
    "Every model. One orchestra.",
    "The autonomous AI assistant with Agentic Fusion & AI music generation",
  );
}
