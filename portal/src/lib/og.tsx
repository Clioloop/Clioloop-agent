import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const OG_SIZE = { width: 1200, height: 630 };

// Shared Conductor-styled social card: midnight stage, score staff, brass
// display headline. satori needs raw font data — next/font can't help here,
// so a static Bodoni Moda cut is checked into src/assets/fonts.
export async function conductorOgImage(title: string, subtitle: string) {
  const bodoni = await readFile(
    join(process.cwd(), "src/assets/fonts/BodoniModa-SemiBold.ttf"),
  );
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 84px",
          background: "linear-gradient(180deg, #101724 0%, #0a0e16 70%)",
          color: "#f2ede3",
          position: "relative",
        }}
      >
        {/* score staff */}
        <div
          style={{
            position: "absolute",
            left: 84,
            right: 84,
            top: 300,
            height: 61,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} style={{ height: 1, background: "rgba(212, 162, 78, 0.22)" }} />
          ))}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <svg width="72" height="36" viewBox="0 0 64 32" fill="none">
            <path
              d="M32 16C27 7 14 7 14 16C14 25 27 25 32 16C37 7 50 7 50 16C50 25 37 25 32 16Z"
              stroke="#d4a24e"
              strokeWidth="5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <div style={{ fontSize: 30, letterSpacing: 6, color: "#d4a24e" }}>CLIOLOOP</div>
        </div>

        <div
          style={{
            fontFamily: "Bodoni",
            fontSize: 84,
            lineHeight: 1.05,
            maxWidth: 1000,
          }}
        >
          {title}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 28, color: "#98a0b0" }}>{subtitle}</div>
          <div style={{ fontSize: 26, color: "#d4a24e", letterSpacing: 3 }}>
            portal.clioloop.com
          </div>
        </div>
      </div>
    ),
    {
      ...OG_SIZE,
      fonts: [{ name: "Bodoni", data: bodoni, weight: 600, style: "normal" }],
    },
  );
}
