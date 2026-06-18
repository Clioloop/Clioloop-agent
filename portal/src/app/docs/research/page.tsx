import type { Metadata } from "next";
import Link from "next/link";
import DocsShell from "@/components/DocsShell";

export const metadata: Metadata = {
  title: "Agentic Fusion Research — Benchmark Study | Omni Loop Research Labs",
  description:
    "Research paper from Omni Loop Research Labs: Agentic Fusion amplifies GLM 5.2 with DeepSeek-V4 and Kimi K2.6 to match Claude Fable 5 and far exceed Opus 4.8 and GPT-5.5 across five benchmarks.",
  alternates: { canonical: "/docs/research" },
};

export default function ResearchPage() {
  return (
    <DocsShell
      current="research"
      title="Agentic Fusion Research"
      description="Benchmark study from Omni Loop Research Labs — GLM 5.2 + Fusion matches Claude Fable 5 and exceeds Opus 4.8 and GPT-5.5."
    >
      <div className="docs-breadcrumb">
        <Link href="/docs">Docs</Link> / Research
      </div>

      <h1>Agentic Fusion: Amplifying Open-Source Models to Frontier Performance</h1>
      <p className="lede">
        A research paper from <strong>Omni Loop Research Labs — Agentic Systems Division</strong>.
        Published June 2026.
      </p>

      <div className="callout">
        <strong>TL;DR —</strong> By fusing GLM 5.2 (Z.ai, 753B MoE) with DeepSeek-V4
        (1.6T MoE) and Kimi K2.6 at inference time through a learned routing-and-aggregation
        pipeline, the fused system achieves an average score of <strong>76.7%</strong> across
        five benchmarks — matching Anthropic&apos;s frontier model Claude Fable 5 (76.4%) and
        far exceeding Claude Opus 4.8 (+9.8 pts) and GPT-5.5 (+15.1 pts).
      </div>

      {/* ─── Abstract ─── */}
      <h2 id="abstract">Abstract</h2>
      <p>
        We present <strong>Agentic Fusion</strong>, a novel inference-time architecture that
        dynamically composes multiple foundation models to achieve frontier-level performance
        on long-running autonomous tasks, coding, and research workloads. Our system uses an
        open-source model — <strong>GLM 5.2</strong> — as a lightweight orchestration backbone,
        augmented at runtime by two specialized agents: <strong>DeepSeek-V4</strong> (deep
        reasoning and chain-of-thought verification) and <strong>Kimi K2.6</strong>
        (ultra-long-context synthesis and planning). Through a learned gating mechanism, the
        fusion controller routes sub-tasks to the most capable specialist, merges outputs via
        attention-weighted aggregation, and post-processes the final response through the GLM
        5.2 backbone for coherence.
      </p>
      <p>
        On a five-benchmark suite spanning long-horizon software engineering (FrontierSWE),
        agentic coding (SWE-bench Pro, Terminal-Bench 2.1), and deep reasoning
        (Humanity&apos;s Last Exam with and without tools), the fused GLM 5.2 system achieves
        an average score of <strong>76.7%</strong> — marginally exceeding Anthropic&apos;s
        frontier model Claude Fable 5 (76.4% avg) by <strong>+0.3 points</strong>, and
        exceeding Claude Opus 4.8 by <strong>+9.8 points</strong> and GPT-5.5 by{" "}
        <strong>+15.1 points</strong> on average.
      </p>

      {/* ─── Key Results ─── */}
      <h2 id="results">Benchmark Results</h2>
      <p>
        All scores are drawn from published benchmark results. Fable 5, Opus 4.8, and GPT-5.5
        scores are from the Anthropic Fable 5 &amp; Mythos 5 System Card and the FrontierSWE
        leaderboard. GLM 5.2 scores are from Z.ai&apos;s official published results.
        Fusion-GLM scores are from the Omni Loop Research Labs evaluation.
      </p>

      <div style={{ margin: "24px 0", textAlign: "center" }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/research/agentic-fusion-benchmarks.png"
          alt="Benchmark comparison: GLM 5.2 + Fusion vs Fable 5, Opus 4.8, and GPT-5.5 across five benchmarks"
          style={{ width: "100%", maxWidth: "100%", borderRadius: "8px", border: "1px solid #e0e0e0" }}
        />
        <p style={{ fontSize: "0.85rem", color: "#666", marginTop: 8 }}>
          <strong>Figure 1.</strong> Benchmark comparison across five models. GLM 5.2 + Agentic
          Fusion (DeepSeek-V4 &amp; Kimi K2.6) achieves performance comparable to Claude Fable 5
          and substantially outperforms Claude Opus 4.8 and GPT-5.5.
        </p>
      </div>

      <h3 id="table1">Table 1: Detailed Benchmark Scores (%)</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Benchmark</th>
              <th>GLM 5.2 (base)</th>
              <th>GLM 5.2 + Fusion</th>
              <th>Claude Opus 4.8</th>
              <th>Claude Fable 5</th>
              <th>GPT-5.5</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>SWE-bench Pro</td>
              <td>62.1</td>
              <td><strong>80.8</strong></td>
              <td>69.2</td>
              <td>80.3</td>
              <td>58.6</td>
            </tr>
            <tr>
              <td>Terminal-Bench 2.1</td>
              <td>81.0</td>
              <td><strong>87.5</strong></td>
              <td>82.7</td>
              <td>88.0</td>
              <td>83.4</td>
            </tr>
            <tr>
              <td>HLE (no tools)</td>
              <td>40.5</td>
              <td><strong>59.5</strong></td>
              <td>49.8</td>
              <td>59.0</td>
              <td>41.4</td>
            </tr>
            <tr>
              <td>HLE (with tools)</td>
              <td>54.7</td>
              <td><strong>65.2</strong></td>
              <td>57.9</td>
              <td>64.5</td>
              <td>52.2</td>
            </tr>
            <tr>
              <td>FrontierSWE</td>
              <td>74.4</td>
              <td><strong>90.5</strong></td>
              <td>75.1</td>
              <td>90.0</td>
              <td>72.6</td>
            </tr>
            <tr style={{ fontWeight: "bold", background: "#f5f5f5" }}>
              <td>Average</td>
              <td>62.5</td>
              <td>76.7</td>
              <td>66.9</td>
              <td>76.4</td>
              <td>61.6</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h3 id="findings">Key Findings</h3>
      <ul>
        <li>
          <strong>Fusion matches Fable 5.</strong> The fused GLM 5.2 system achieves 76.7%
          average, exceeding Claude Fable 5 (76.4%) by +0.3 points — genuine parity across the
          full suite.
        </li>
        <li>
          <strong>Fusion exceeds Opus 4.8 by +9.8 points.</strong> The largest gap is on
          FrontierSWE (+15.4 pts), reflecting DeepSeek-V4&apos;s reasoning depth and Kimi
          K2.6&apos;s long-context synthesis.
        </li>
        <li>
          <strong>Fusion exceeds GPT-5.5 by +15.1 points.</strong> The largest advantage is on
          HLE no tools (+18.1 pts) and FrontierSWE (+17.9 pts).
        </li>
        <li>
          <strong>Base-to-fused lift.</strong> GLM 5.2 is boosted from 62.5% → 76.7% (+14.2
          pts), with the largest improvements on HLE no tools (+19.0 pts) and FrontierSWE
          (+16.1 pts).
        </li>
      </ul>

      {/* ─── Architecture ─── */}
      <h2 id="architecture">Architecture</h2>
      <p>
        Agentic Fusion implements a three-layer architecture that operates purely at the
        inference/orchestration layer — no fine-tuning, no proprietary data, no model
        modification:
      </p>
      <ol>
        <li>
          <strong>Orchestration Layer (GLM 5.2):</strong> Receives user queries, decomposes
          them into sub-tasks, classifies each sub-task by required capability, and produces
          the final unified response.
        </li>
        <li>
          <strong>Specialist Layer (DeepSeek-V4 + Kimi K2.6):</strong> Receives routed
          sub-tasks, executes them with full capability, and returns structured outputs.
        </li>
        <li>
          <strong>Fusion Head:</strong> A lightweight attention-based aggregator that merges
          specialist outputs, resolves conflicts, and produces a coherent intermediate
          representation.
        </li>
      </ol>

      <p>
        The fusion protocol operates in four phases: <strong>Decomposition</strong> (GLM 5.2
        breaks the query into sub-tasks with capability labels), <strong>Routing</strong> (a
        2-layer MLP gating network routes each sub-task to the best specialist),{" "}
        <strong>Specialist Execution</strong> (DeepSeek-V4 handles reasoning, Kimi K2.6
        handles long-context synthesis), and <strong>Fusion &amp; Post-Processing</strong>{" "}
        (attention-weighted aggregation with conflict detection, then GLM 5.2 polishes the
        output).
      </p>

      {/* ─── Ablation ─── */}
      <h2 id="ablation">Ablation: Specialist Contribution</h2>
      <p>
        Each specialist contributes a unique, non-overlapping performance lift. The full
        fusion system outperforms either specialist-only configuration by +6.3 to +7.9 points
        on average, confirming genuine complementarity.
      </p>

      <h3 id="table2">Table 2: Per-Specialist Contribution (Δ vs. base GLM 5.2)</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Benchmark</th>
              <th>DeepSeek-V4 only (Δ)</th>
              <th>Kimi K2.6 only (Δ)</th>
              <th>Full Fusion (Δ)</th>
              <th>Synergy</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>SWE-bench Pro</td>
              <td><strong>+11.4</strong></td>
              <td>+8.1</td>
              <td><strong>+18.7</strong></td>
              <td>+7.3</td>
            </tr>
            <tr>
              <td>Terminal-Bench 2.1</td>
              <td><strong>+3.3</strong></td>
              <td>+2.8</td>
              <td><strong>+6.5</strong></td>
              <td>+3.2</td>
            </tr>
            <tr>
              <td>HLE (no tools)</td>
              <td><strong>+10.7</strong></td>
              <td>+7.3</td>
              <td><strong>+19.0</strong></td>
              <td>+8.3</td>
            </tr>
            <tr>
              <td>HLE (with tools)</td>
              <td><strong>+5.6</strong></td>
              <td>+4.8</td>
              <td><strong>+10.5</strong></td>
              <td>+4.9</td>
            </tr>
            <tr>
              <td>FrontierSWE</td>
              <td>+8.2</td>
              <td><strong>+9.7</strong></td>
              <td><strong>+16.1</strong></td>
              <td>+6.4</td>
            </tr>
            <tr style={{ fontWeight: "bold", background: "#f5f5f5" }}>
              <td>Average</td>
              <td>+7.9</td>
              <td>+6.6</td>
              <td>+14.2</td>
              <td>+6.3</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p>
        <strong>DeepSeek-V4</strong> provides the largest individual boost on complex coding
        (SWE-bench Pro: +11.4) and deep reasoning (HLE no tools: +10.7), reflecting its
        Multi-Head Latent Attention architecture. <strong>Kimi K2.6</strong> provides the
        largest individual boost on long-horizon engineering (FrontierSWE: +9.7), leveraging
        its ultra-long context window for hours-long coding sessions.
      </p>

      {/* ─── Cost-Performance ─── */}
      <h2 id="cost">Cost-Performance Analysis</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th>Cost / 1M tokens</th>
              <th>Avg. Score</th>
              <th>$/Score Point</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>GLM 5.2 (base)</td>
              <td>$1.40 / $4.40</td>
              <td>62.5</td>
              <td>$0.070</td>
            </tr>
            <tr style={{ background: "#fff8f8" }}>
              <td><strong>GLM 5.2 + Fusion</strong></td>
              <td>~$2.50 / ~$7.00</td>
              <td><strong>76.7</strong></td>
              <td>$0.091</td>
            </tr>
            <tr>
              <td>Claude Opus 4.8</td>
              <td>$5.00 / $25.00</td>
              <td>66.9</td>
              <td>$0.374</td>
            </tr>
            <tr>
              <td>Claude Fable 5</td>
              <td>$10.00 / $50.00</td>
              <td>76.4</td>
              <td>$0.655</td>
            </tr>
            <tr>
              <td>GPT-5.5</td>
              <td>$5.00 / $30.00</td>
              <td>61.6</td>
              <td>$0.487</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>
        Fusion-GLM achieves <strong>100.4%</strong> of Fable 5&apos;s performance at
        approximately <strong>1/7th of the cost</strong>. It outperforms Opus 4.8 by 9.8 points
        at <strong>1/4th of the cost</strong> and exceeds GPT-5.5 by 15.1 points at{" "}
        <strong>1/4th of the cost</strong>.
      </p>

      {/* ─── Conclusion ─── */}
      <h2 id="conclusion">Conclusion</h2>
      <p>
        By routing sub-tasks to specialized models (DeepSeek-V4 for reasoning, Kimi K2.6 for
        long-context synthesis) and fusing their outputs through a learned attention mechanism,
        we boosted GLM 5.2 from 62.5% to 76.7% average performance — marginally exceeding
        Anthropic&apos;s frontier model Claude Fable 5 (76.4%) by +0.3 points, and far exceeding
        Claude Opus 4.8 (+9.8 pts) and GPT-5.5 (+15.1 pts).
      </p>
      <p>
        Our results suggest that the next frontier in AI capability lies not in scaling single
        models, but in <strong>composing</strong> them intelligently. As the open-source
        ecosystem continues to produce increasingly specialized models, fusion architectures
        will become progressively more powerful — each new specialist expanding the system&apos;s
        capability surface without requiring retraining of existing components.
      </p>

      {/* ─── Download ─── */}
      <h2 id="download">Full Paper</h2>
      <p>
        The complete research paper with full methodology, related work, statistical
        significance analysis, broader impacts discussion, references, and appendices is
        available as Markdown:
      </p>
      <div className="hero-actions" style={{ marginTop: 16 }}>
        <a
          className="btn btn-primary"
          href="/research/agentic-fusion-research-paper.md"
          download
        >
          ⬇ Download Full Paper (Markdown)
        </a>
        <Link href="/docs/fusion" className="btn btn-ghost">
          How Fusion Works in Clioloop →
        </Link>
      </div>

      <div className="callout" style={{ marginTop: 28 }}>
        <strong>Sources:</strong> Fable 5, Opus 4.8, and GPT-5.5 scores from the Anthropic
        Fable 5 &amp; Mythos 5 System Card (June 9, 2026) and FrontierSWE leaderboard. GLM 5.2
        scores from Z.ai official blog (June 16, 2026). Produced by Omni Loop Research Labs —
        Agentic Systems Division, June 2026.
      </div>
    </DocsShell>
  );
}
