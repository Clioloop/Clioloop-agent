import type { Metadata } from "next";
import Link from "next/link";
import DocsShell from "@/components/DocsShell";

export const metadata: Metadata = {
  title: "Models & switching — 300+ models, one login",
  description:
    "Switch between 300+ frontier and open models with /model — Claude, GPT, Gemini, Grok, DeepSeek, Qwen, Kimi and every notable open-weight model. One login through the Omni Loop Portal, no API keys.",
  alternates: { canonical: "/docs/models" },
};

export default function ModelsDoc() {
  return (
    <DocsShell
      current="models"
      title="Models & switching"
      description="Work across 300+ models and switch mid-session with /model."
    >
      <div className="docs-breadcrumb">
        <Link href="/docs">Docs</Link> / Models &amp; switching
      </div>
      <h1>Models &amp; switching</h1>
      <p>
        One Omni Loop Portal login gives Clioloop access to <strong>300+ models</strong> —
        Claude, GPT, Gemini, Grok, DeepSeek, Qwen, Kimi and every notable open-weight
        model — through a single OpenAI-compatible endpoint. No API keys to juggle.
      </p>

      <h2 id="naming">Model names</h2>
      <p>
        Most model IDs use <code>vendor/model</code> naming, for example{" "}
        <code>anthropic/claude-sonnet-4.6</code>, <code>openai/gpt-5.2</code>,{" "}
        <code>deepseek/deepseek-v3.2</code> or <code>qwen/qwen3-235b</code>.
      </p>

      <h2 id="switch">Switch models</h2>
      <ul>
        <li><code>/model</code> — interactive picker with live pricing, in any surface</li>
        <li><code>clio -m vendor/model</code> — set the model for a one-off session</li>
        <li><code>/model --provider openrouter</code> — force a specific provider</li>
        <li><code>/model --global</code> — make the choice the default for future sessions</li>
        <li><code>/model --refresh</code> — refetch the live catalog</li>
      </ul>
      <div className="code-block">
        <span className="c-cmd">/model</span>{" "}
        <span className="c-comment"># browse the catalog and pick</span>
        <br />
        <span className="c-cmd">clio -m anthropic/claude-sonnet-4.6</span>
        <br />
        <span className="c-cmd">clio -m qwen/qwen3-235b --provider openrouter</span>
      </div>

      <h2 id="tiers">What each plan can use</h2>
      <table>
        <thead>
          <tr><th>Plan</th><th>Models</th></tr>
        </thead>
        <tbody>
          <tr><td>Free</td><td>1 free model to try</td></tr>
          <tr><td>Pro</td><td>Full 300+ OpenRouter catalog</td></tr>
          <tr><td>Max</td><td>300+ frontier models — Claude, GPT, Gemini, Grok</td></tr>
          <tr><td>Max 10x</td><td>300+ frontier models, 10× usage</td></tr>
        </tbody>
      </table>
      <p>
        See <Link href="/pricing">pricing</Link> for the full breakdown. Switching plans
        is instant on upgrade.
      </p>

      <h2 id="providers">Bring your own providers</h2>
      <p>
        The Portal is the no-key path, but Clioloop is multi-provider. <code>clio auth</code>{" "}
        can store your own keys for Anthropic, OpenAI, Google, Groq, OpenRouter, Ollama
        and more — and you can mix them freely, including as planners and reviewers inside{" "}
        <Link href="/docs/fusion">Agentic Fusion</Link>.
      </p>
    </DocsShell>
  );
}
