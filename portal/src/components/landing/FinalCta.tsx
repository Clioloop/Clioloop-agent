import Link from "next/link";
import type { Dictionary } from "@/i18n/dictionaries/en";

export default function FinalCta({
  t,
  pricingHref,
}: {
  t: Dictionary["landing"]["cta"];
  pricingHref: string;
}) {
  return (
    <section className="section" data-reveal>
      <div className="cta-banner">
        <span className="eyebrow">{t.eyebrow}</span>
        <h2 style={{ marginTop: 18 }}>
          {t.h2Lead} <span className="display-italic">{t.h2Italic}</span>
        </h2>
        <p>{t.body}</p>
        <div className="hero-actions">
          <Link href={pricingHref} className="btn btn-primary btn-lg">
            {t.pricing}
          </Link>
          <Link href="/docs" className="btn btn-ghost btn-lg">
            {t.docs}
          </Link>
        </div>
      </div>
    </section>
  );
}
