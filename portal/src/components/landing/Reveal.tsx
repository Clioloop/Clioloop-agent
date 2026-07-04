"use client";

import { useEffect, useRef } from "react";

// One IntersectionObserver for the whole page: any [data-reveal] descendant
// gets .is-in when it scrolls into view; globals.css staggers its children.
// Styles only hide content under html.js (set in layout), so crawlers and
// no-JS readers always see everything. Reduced motion reveals instantly.
export default function Reveal({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const targets = root.querySelectorAll<HTMLElement>("[data-reveal]");
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      targets.forEach((t) => t.classList.add("is-in"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-in");
            io.unobserve(entry.target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );
    targets.forEach((t) => io.observe(t));
    return () => io.disconnect();
  }, []);

  return <div ref={ref}>{children}</div>;
}
