// Large media (brand videos, demo audio) is served from Cloudflare R2 when
// MEDIA_BASE_URL is set (e.g. https://media.clioloop.com), with the committed
// /public/brand files as the fallback so local dev needs no configuration.
// Server-only on purpose: pages pass resolved URLs down as props.
const BASE = process.env.MEDIA_BASE_URL?.trim().replace(/\/+$/, "") || "";

export const mediaUrl = (path: string): string =>
  BASE ? `${BASE}/${path}` : `/brand/${path.split("/").pop()}`;

export const MEDIA_ORIGIN = BASE ? new URL(BASE).origin : null;
