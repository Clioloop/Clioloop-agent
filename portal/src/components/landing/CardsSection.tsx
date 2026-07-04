import Link from "next/link";

// Shared shape for the autonomy / tools / surfaces sections: an eyebrow'd
// display heading over a hairline card grid, with an optional trailing CTA.
export type Card = { icon: string; title: string; body: string };

export default function CardsSection({
  id,
  eyebrow,
  h2Lead,
  h2Italic,
  lede,
  cards,
  ctaHref,
  ctaLabel,
}: {
  id: string;
  eyebrow: string;
  h2Lead: string;
  h2Italic: string;
  lede: string;
  cards: Card[];
  ctaHref?: string;
  ctaLabel?: string;
}) {
  return (
    <section className="section" id={id} data-reveal>
      <div className="section-head">
        <span className="eyebrow">{eyebrow}</span>
        <h2>
          {h2Lead} <span className="display-italic">{h2Italic}</span>
        </h2>
        <p>{lede}</p>
      </div>
      <div className="grid-3">
        {cards.map((card) => (
          <div className="card" key={card.title}>
            <div className="card-icon">{card.icon}</div>
            <h3>{card.title}</h3>
            <p>{card.body}</p>
          </div>
        ))}
      </div>
      {ctaHref && ctaLabel && (
        <div className="hero-actions" style={{ marginTop: 28 }}>
          <Link href={ctaHref} className="btn btn-ghost btn-lg">
            {ctaLabel}
          </Link>
        </div>
      )}
    </section>
  );
}
