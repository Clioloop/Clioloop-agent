import type { Dictionary } from "@/i18n/dictionaries/en";
import IntroOverlay from "@/components/IntroOverlay";
import Reveal from "./Reveal";
import Hero from "./Hero";
import FusionSection from "./FusionSection";
import MusicSection from "./MusicSection";
import CardsSection from "./CardsSection";
import InstallSection from "./InstallSection";
import HowItWorks from "./HowItWorks";
import CommandsSection from "./CommandsSection";
import PricingTeaser from "./PricingTeaser";
import FinalCta from "./FinalCta";
import type { DemoTrackInfo } from "./demoTracks";

// The whole landing page, dictionary-driven so / and /{locale} render the
// same sections from different dictionaries. Media URLs are resolved by the
// server page (lib/media.ts) and passed down.
export default function LandingSections({
  t,
  demoTracks,
  introWebm,
  introMp4,
  pricingHref,
}: {
  t: Dictionary["landing"];
  demoTracks: DemoTrackInfo[];
  introWebm: string;
  introMp4: string;
  pricingHref: string;
}) {
  return (
    <div className="page">
      <IntroOverlay webmSrc={introWebm} mp4Src={introMp4} />
      <div className="container">
        <Reveal>
          <Hero t={t.hero} />
          <div className="staff-divider" aria-hidden />
          <FusionSection t={t.fusion} />
          <MusicSection t={t.music} demoTracks={demoTracks} />
          <div className="staff-divider" aria-hidden />
          <CardsSection
            id="autonomy"
            eyebrow={t.autonomy.eyebrow}
            h2Lead={t.autonomy.h2Lead}
            h2Italic={t.autonomy.h2Italic}
            lede={t.autonomy.lede}
            cards={t.autonomy.cards}
            ctaHref="/docs"
            ctaLabel={t.autonomy.ctaDocs}
          />
          <CardsSection
            id="features"
            eyebrow={t.tools.eyebrow}
            h2Lead={t.tools.h2Lead}
            h2Italic={t.tools.h2Italic}
            lede={t.tools.lede}
            cards={t.tools.cards}
          />
          <CardsSection
            id="anywhere"
            eyebrow={t.surfaces.eyebrow}
            h2Lead={t.surfaces.h2Lead}
            h2Italic={t.surfaces.h2Italic}
            lede={t.surfaces.lede}
            cards={t.surfaces.cards}
          />
          <div className="staff-divider" aria-hidden />
          <InstallSection t={t.install} />
          <HowItWorks t={t.how} />
          <CommandsSection t={t.commands} />
          <div className="staff-divider" aria-hidden />
          <PricingTeaser t={t.pricingTeaser} pricingHref={pricingHref} />
          <FinalCta t={t.cta} pricingHref={pricingHref} />
        </Reveal>
      </div>
    </div>
  );
}
