"use client";

import { useRef, useState } from "react";
import type { DemoTrackInfo } from "./demoTracks";

// Custom audio player for the music showcase: brass play button, a score
// staff as the progress bar, and a track list — one generated song per
// language. Renders nothing if the tracks can't load before anything has
// played (e.g. local dev without the media CDN), so the section never shows
// a broken control.
function fmt(s: number): string {
  if (!Number.isFinite(s)) return "0:00";
  const m = Math.floor(s / 60);
  const r = Math.floor(s % 60);
  return `${m}:${r.toString().padStart(2, "0")}`;
}

export default function DemoTrack({
  tracks,
  sub,
  playLabel,
  pauseLabel,
}: {
  tracks: DemoTrackInfo[];
  sub: string;
  playLabel: string;
  pauseLabel: string;
}) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const staffRef = useRef<HTMLDivElement | null>(null);
  const everPlayedRef = useRef(false);
  const [selected, setSelected] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [failed, setFailed] = useState(false);

  if (failed || tracks.length === 0) return null;
  const track = tracks[selected];

  const toggle = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) audio.play().catch(() => setFailed(true));
    else audio.pause();
  };

  const select = (i: number) => {
    if (i === selected) {
      toggle();
      return;
    }
    setSelected(i);
    setTime(0);
    setDuration(0);
    const audio = audioRef.current;
    if (!audio) return;
    audio.src = tracks[i].src;
    audio.play().catch(() => setFailed(true));
  };

  const seek = (e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current;
    const staff = staffRef.current;
    if (!audio || !staff || !duration) return;
    const rect = staff.getBoundingClientRect();
    audio.currentTime = ((e.clientX - rect.left) / rect.width) * duration;
  };

  const progress = duration ? `${(time / duration) * 100}%` : "0%";

  return (
    <div className="player">
      <audio
        ref={audioRef}
        src={track.src}
        preload="none"
        onPlay={() => {
          everPlayedRef.current = true;
          setPlaying(true);
        }}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
        onError={() => {
          if (!everPlayedRef.current) setFailed(true);
          setPlaying(false);
        }}
      />
      <div className="player-row">
        <button
          className="player-btn"
          onClick={toggle}
          aria-label={playing ? pauseLabel : playLabel}
        >
          {playing ? "❚❚" : "▶"}
        </button>
        <div className="player-meta">
          <div className="player-title">
            {track.title} · {track.language}
          </div>
          <div className="player-sub">{sub}</div>
        </div>
      </div>
      <div
        className="player-staff"
        ref={staffRef}
        onClick={seek}
        style={{ "--p": progress } as React.CSSProperties}
      >
        <div />
      </div>
      <div className="player-time">
        <span>{fmt(time)}</span>
        <span>{fmt(duration)}</span>
      </div>
      <div className="player-tracks">
        {tracks.map((item, i) => (
          <button
            key={item.src}
            className={i === selected ? "is-current" : undefined}
            onClick={() => select(i)}
          >
            <span className="pt-lang">{item.language}</span>
            <span className="pt-title">{item.title}</span>
            <span className="pt-state">{i === selected && playing ? "❚❚" : "▶"}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
