"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

// First-visit intro. Lifecycle:
//   full     — fullscreen video, sound on (muted fallback if autoplay-blocked)
//   dimming  — at 1:18 the site's dark wash fades in over the video (2.2s)
//   docked   — the video drops behind the page and IS the background; audio
//              keeps playing; site content fades in on top
//   closing  — when the video ends, it crossfades into the looping backdrop
//              video that has been playing underneath all along
// A mute/unmute control stays available through every phase. "Skip intro"
// (or Esc) ends the whole experience immediately.
//
// Landing page only, once per browser, never for reduced-motion users.

const SEEN_KEY = "olp_intro_seen";
const DOCK_AT_SECONDS = 78; // 1:18 — explanation ends, become the background
const DIM_MS = 2300;
const CLOSE_MS = 1600;

type Phase = "full" | "dimming" | "docked" | "closing" | "skipped";

export default function IntroOverlay({
  webmSrc = "/brand/introclio.webm",
  mp4Src = "/brand/introclio.mp4",
}: {
  webmSrc?: string;
  mp4Src?: string;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [show, setShow] = useState(false);
  const [phase, setPhase] = useState<Phase>("full");
  const [muted, setMuted] = useState(false);

  // Eligibility runs client-side only — render nothing during SSR/hydration.
  useEffect(() => {
    try {
      if (window.localStorage.getItem(SEEN_KEY)) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      window.localStorage.setItem(SEEN_KEY, String(Date.now()));
      setShow(true);
    } catch {
      // Storage unavailable — skip the intro.
    }
  }, []);

  // Autoplay with sound where allowed; muted fallback otherwise.
  useEffect(() => {
    if (!show) return;
    const video = videoRef.current;
    if (!video) return;
    video.muted = false;
    video.play().catch(() => {
      video.muted = true;
      setMuted(true);
      video.play().catch(() => setPhase("skipped")); // playback blocked entirely
    });
  }, [show]);

  // Esc skips (only while the intro owns the screen).
  useEffect(() => {
    if (!show || (phase !== "full" && phase !== "dimming")) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") skip();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [show, phase]);

  // Phase timers + body class for the content entrance.
  useEffect(() => {
    if (phase === "dimming") {
      const t = setTimeout(() => {
        setPhase("docked");
        document.body.classList.add("intro-docked-entrance");
      }, DIM_MS);
      return () => clearTimeout(t);
    }
    if (phase === "closing" || phase === "skipped") {
      const t = setTimeout(() => setShow(false), CLOSE_MS + 700);
      return () => clearTimeout(t);
    }
  }, [phase]);

  useEffect(() => () => document.body.classList.remove("intro-docked-entrance"), []);

  const skip = () => {
    videoRef.current?.pause();
    document.body.classList.add("intro-docked-entrance");
    setPhase("skipped");
  };

  const toggleMute = () => {
    const video = videoRef.current;
    if (!video) return;
    video.muted = !video.muted;
    setMuted(video.muted);
  };

  if (!show || typeof document === "undefined") return null;

  const overlayClass =
    "intro-overlay" +
    (phase === "dimming" ? " intro-dimming" : "") +
    (phase === "docked" ? " intro-docked" : "") +
    (phase === "closing" ? " intro-docked intro-closing" : "") +
    (phase === "skipped" ? " intro-skipped" : "");

  // Rendered into <body>: position:fixed must size against the viewport,
  // never an animated/transformed ancestor inside the page tree.
  return createPortal(
    <>
      <div className={overlayClass} aria-hidden={phase !== "full"}>
        <video
          ref={videoRef}
          className="intro-video"
          playsInline
          preload="auto"
          onTimeUpdate={(e) => {
            if (phase === "full" && e.currentTarget.currentTime >= DOCK_AT_SECONDS) {
              setPhase("dimming");
            }
          }}
          onEnded={() => setPhase("closing")}
          onError={() => setPhase("skipped")}
        >
          {/* WebM first: Linux browsers often lack the H.264 codec. */}
          <source src={webmSrc} type="video/webm" />
          <source src={mp4Src} type="video/mp4" onError={() => setPhase("skipped")} />
        </video>
        {/* The site's dark wash, faded in over the video during "dimming" so
            the dock handoff to the real backdrop layers is seamless. */}
        <div className="intro-wash" aria-hidden />
      </div>

      {/* Controls live outside the overlay so they stay clickable after the
          video drops behind the page (negative z-index). */}
      {(phase === "full" || phase === "dimming" || phase === "docked") && (
        <div className="intro-controls">
          <button className="btn btn-ghost btn-sm" onClick={toggleMute}>
            {muted ? "🔊 Unmute" : "🔇 Mute"}
          </button>
          {(phase === "full" || phase === "dimming") && (
            <button className="btn btn-ghost btn-sm" onClick={skip}>
              Skip intro
            </button>
          )}
        </div>
      )}
    </>,
    document.body,
  );
}
