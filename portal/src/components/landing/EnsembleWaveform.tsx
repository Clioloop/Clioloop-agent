import type { CSSProperties } from "react";

// The signature: the fusion pipeline as an orchestra's waveform. Each group
// of bars is a section of players; they join one after another (CSS handles
// the staggering via --i/--g), keep breathing, and the brass cluster at the
// end is the fused answer. Static (full-height) under reduced motion.
const GROUPS = [
  { cls: "g-planners", heights: [0.32, 0.5, 0.4, 0.62, 0.45, 0.7, 0.5, 0.38, 0.58, 0.42] },
  { cls: "g-model", heights: [0.45, 0.68, 0.55, 0.85, 0.6, 0.95, 0.75, 0.55, 0.8, 0.62, 0.7, 0.5] },
  { cls: "g-reviewers", heights: [0.4, 0.3, 0.52, 0.36, 0.6, 0.44, 0.34, 0.55, 0.4, 0.3] },
  { cls: "g-fused", heights: [0.6, 0.85, 0.7, 1, 0.8, 0.95, 0.75, 0.9] },
];

export default function EnsembleWaveform({
  label,
  sub,
  legend,
}: {
  label: string;
  sub: string;
  legend: { planners: string; model: string; reviewers: string; fused: string };
}) {
  return (
    <div className="ensemble" aria-hidden>
      <div className="ens-head">
        <span>{label}</span>
        <span>{sub}</span>
      </div>
      <div className="ens-wave">
        {GROUPS.map((group, gi) => (
          <div key={group.cls} className={`ens-group ${group.cls}`}>
            {group.heights.map((h, i) => (
              <i
                key={i}
                style={
                  {
                    "--h": h,
                    "--i": i,
                    "--g": gi,
                    "--sway": 0.58 + (i % 3) * 0.13,
                  } as CSSProperties
                }
              />
            ))}
          </div>
        ))}
      </div>
      <div className="ens-legend">
        <span className="l-planners">
          <i /> {legend.planners}
        </span>
        <span className="l-model">
          <i /> {legend.model}
        </span>
        <span className="l-reviewers">
          <i /> {legend.reviewers}
        </span>
        <span className="l-fused">
          <i /> {legend.fused}
        </span>
      </div>
    </div>
  );
}
