import { conductorOgImage, OG_SIZE } from "@/lib/og";

export const size = OG_SIZE;
export const contentType = "image/png";
export const alt = "Clioloop pricing — one login, every model";

export default function Image() {
  return conductorOgImage(
    "Four seats, same hall.",
    "Free · Pro €20 · Max €100 · Max 10x €250 — no API keys",
  );
}
