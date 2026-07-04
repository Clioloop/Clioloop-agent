import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

// Brass infinity mark on the midnight stage — rendered at request time so no
// binary icon needs to live in the repo.
export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #101724 0%, #0a0e16 100%)",
        }}
      >
        <svg width="132" height="66" viewBox="0 0 64 32" fill="none">
          <path
            d="M32 16C27 7 14 7 14 16C14 25 27 25 32 16C37 7 50 7 50 16C50 25 37 25 32 16Z"
            stroke="#d4a24e"
            strokeWidth="5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    ),
    size,
  );
}
