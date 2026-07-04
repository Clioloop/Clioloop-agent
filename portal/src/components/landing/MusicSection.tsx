import type { Dictionary } from "@/i18n/dictionaries/en";
import DemoTrack from "./DemoTrack";
import type { DemoTrackInfo } from "./demoTracks";

export default function MusicSection({
  t,
  demoTracks,
}: {
  t: Dictionary["landing"]["music"];
  demoTracks: DemoTrackInfo[];
}) {
  return (
    <section className="section" id="music" data-reveal>
      <div className="section-head">
        <span className="eyebrow">{t.eyebrow}</span>
        <h2>
          {t.h2Lead} <span className="display-italic">{t.h2Italic}</span>
        </h2>
        <p>{t.lede}</p>
      </div>

      <div className="music-panel">
        <div>
          <ul className="music-caps">
            {t.caps.map((cap) => (
              <li key={cap}>{cap}</li>
            ))}
          </ul>
          <p style={{ color: "var(--faint)", fontSize: 13, marginTop: 16 }}>{t.note}</p>
        </div>
        <DemoTrack
          tracks={demoTracks}
          sub={t.playerSub}
          playLabel={t.playerPlay}
          pauseLabel={t.playerPause}
        />
      </div>
    </section>
  );
}
