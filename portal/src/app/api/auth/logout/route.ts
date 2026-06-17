import { NextResponse } from "next/server";
import { destroySession } from "@/lib/session";
import { portalBaseUrl } from "@/lib/billing";

export const runtime = "nodejs";

export async function POST() {
  await destroySession();
  return NextResponse.json({ ok: true });
}

export async function GET() {
  await destroySession();
  return NextResponse.redirect(`${portalBaseUrl()}/`);
}
