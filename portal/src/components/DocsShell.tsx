import Link from "next/link";

const SITE_URL = "https://portal.clioloop.com";

// Single source of truth for the docs section: order drives the sidebar, the
// prev/next pager and the sitemap intent. Keep slugs in sync with the route
// folders under src/app/docs/.
export const DOCS_NAV: { group: string; items: { slug: string; title: string }[] }[] = [
  {
    group: "Start here",
    items: [
      { slug: "", title: "Overview" },
      { slug: "getting-started", title: "Getting started" },
    ],
  },
  {
    group: "Core",
    items: [
      { slug: "fusion", title: "Agentic Fusion" },
      { slug: "goals", title: "Goals & loops" },
      { slug: "models", title: "Models & switching" },
      { slug: "tools", title: "Tools & gateway" },
    ],
  },
  {
    group: "Going further",
    items: [
      { slug: "surfaces", title: "Surfaces" },
      { slug: "kanban", title: "Multi-agent Kanban" },
      { slug: "skills", title: "Skills & memory" },
      { slug: "security", title: "Security & tokens" },
      { slug: "commands", title: "Command reference" },
    ],
  },
];

const FLAT = DOCS_NAV.flatMap((g) => g.items);

function href(slug: string) {
  return slug ? `/docs/${slug}` : "/docs";
}

export function docsPager(current: string) {
  const idx = FLAT.findIndex((i) => i.slug === current);
  return {
    prev: idx > 0 ? FLAT[idx - 1] : null,
    next: idx >= 0 && idx < FLAT.length - 1 ? FLAT[idx + 1] : null,
  };
}

/** TechArticle + BreadcrumbList JSON-LD for a docs page. */
export function DocsJsonLd({ title, description, slug }: { title: string; description: string; slug: string }) {
  const url = `${SITE_URL}${href(slug)}`;
  const data = [
    {
      "@context": "https://schema.org",
      "@type": "TechArticle",
      headline: title,
      description,
      url,
      isPartOf: { "@type": "WebSite", name: "Clioloop Docs", url: `${SITE_URL}/docs` },
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "Docs", item: `${SITE_URL}/docs` },
        ...(slug ? [{ "@type": "ListItem", position: 2, name: title, item: url }] : []),
      ],
    },
  ];
  return (
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />
  );
}

/** Shared shell for every docs page: sidebar nav + content + prev/next pager. */
export default function DocsShell({
  current,
  title,
  description,
  children,
}: {
  current: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  const { prev, next } = docsPager(current);
  return (
    <div className="page">
      <DocsJsonLd title={title} description={description} slug={current} />
      <div className="container">
        <div className="docs-layout">
          <aside className="docs-nav">
            {DOCS_NAV.map((g) => (
              <div className="docs-nav-group" key={g.group}>
                <span>{g.group}</span>
                {g.items.map((i) => (
                  <Link
                    key={i.slug || "overview"}
                    href={href(i.slug)}
                    className={i.slug === current ? "active" : undefined}
                  >
                    {i.title}
                  </Link>
                ))}
              </div>
            ))}
          </aside>

          <article className="docs-content fade-up">
            {children}
            {(prev || next) && (
              <nav className="docs-pager">
                {prev ? <Link href={href(prev.slug)}>← {prev.title}</Link> : <span />}
                {next ? <Link href={href(next.slug)}>{next.title} →</Link> : <span />}
              </nav>
            )}
          </article>
        </div>
      </div>
    </div>
  );
}
