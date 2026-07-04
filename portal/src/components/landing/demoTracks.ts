import { mediaUrl } from "@/lib/media";

// Real, unedited Clioloop music generations — one per language, proving the
// "your lyrics or generated lyrics, any language" claim. Language names are
// written in their own language on purpose (self-labeling, no translation).
export type DemoTrackInfo = { src: string; title: string; language: string };

const TRACKS: { file: string; title: string; language: string; lang: string }[] = [
  { file: "audio/demo-ultraviolet.mp3", title: "Ultraviolet", language: "English", lang: "en" },
  { file: "audio/demo-liberte-sauvage.mp3", title: "Liberté Sauvage", language: "Français", lang: "fr" },
  { file: "audio/demo-dulce-veneno.mp3", title: "Dulce Veneno", language: "Español", lang: "es" },
  { file: "audio/demo-neonovyy-put.mp3", title: "Неоновый путь", language: "Русский", lang: "ru" },
];

/** Track list for the music showcase, with the page's language first. */
export function demoTracks(locale: string): DemoTrackInfo[] {
  const ordered = [...TRACKS].sort((a, b) =>
    a.lang === locale ? -1 : b.lang === locale ? 1 : 0,
  );
  return ordered.map(({ file, title, language }) => ({
    src: mediaUrl(file),
    title,
    language,
  }));
}
