import type { Metadata } from "next";
import Link from "next/link";
import DocsShell from "@/components/DocsShell";

export const metadata: Metadata = {
  title: "Tools & the tool gateway",
  description:
    "Clioloop's tools: file editing, shell, web search & extract, a cloud browser, image and video generation, text-to-speech, code execution and MCP servers — many routed through the Omni Loop Portal tool gateway and billed against one subscription.",
  alternates: { canonical: "/docs/tools" },
};

export default function ToolsDoc() {
  return (
    <DocsShell
      current="tools"
      title="Tools & the tool gateway"
      description="File edits, shell, web, browser, image/video, TTS and MCP — through one subscription."
    >
      <div className="docs-breadcrumb">
        <Link href="/docs">Docs</Link> / Tools &amp; gateway
      </div>
      <h1>Tools &amp; the tool gateway</h1>
      <p>
        Clioloop&apos;s power comes from its tools. The agent reads and writes files, runs
        commands, browses the web, generates images and speech, executes code and connects
        to any MCP server — and several of those tools route through the Omni Loop Portal
        <strong> tool gateway</strong>, billed against your subscription instead of four
        separate vendor accounts.
      </p>

      <h2 id="builtin">Built-in tools</h2>
      <ul>
        <li><strong>Files</strong> — <code>read_file</code>, <code>write_file</code>, <code>patch</code>, <code>search_files</code></li>
        <li><strong>Terminal</strong> — <code>terminal</code> and background <code>process</code> management</li>
        <li><strong>Web</strong> — <code>web_search</code> and <code>web_extract</code></li>
        <li><strong>Browser</strong> — a full CDP-driven browser: navigate, click, type, scroll, screenshot, read console</li>
        <li><strong>Vision &amp; media</strong> — <code>vision_analyze</code>, <code>image_generate</code>, <code>video_generate</code>, <code>text_to_speech</code></li>
        <li><strong>Code &amp; planning</strong> — <code>execute_code</code> (Python/JS/bash), <code>todo</code>, <code>memory</code>, <code>delegate_task</code></li>
        <li><strong>Messaging &amp; more</strong> — <code>send_message</code>, Home Assistant control, Kanban, scheduled jobs</li>
      </ul>

      <h2 id="gateway">The Omni Loop tool gateway</h2>
      <p>
        These hosted tools are entitlements of your plan — there&apos;s nothing to
        configure. Once a device is connected, entitled tools route through the portal,
        which swaps your token for the house upstream key and meters the call:
      </p>
      <table>
        <thead>
          <tr><th>Tool</th><th>What it does</th><th>Plans</th></tr>
        </thead>
        <tbody>
          <tr><td>Web search &amp; extract</td><td>Search and read pages (self-hosted)</td><td>Pro and up</td></tr>
          <tr><td>Image generation</td><td>Fast, high-quality images</td><td>Pro and up</td></tr>
          <tr><td>Premium TTS</td><td>Studio-quality voices for voice replies</td><td>Pro and up</td></tr>
          <tr><td>Cloud browser</td><td>Hosted browser sessions for automation</td><td>Pro and up</td></tr>
          <tr><td>Video generation</td><td>Text/image-to-video</td><td>Max &amp; Max 10x</td></tr>
        </tbody>
      </table>
      <div className="callout">
        <strong>Free plan:</strong> no hosted tools. The Free tier is for trying a single
        model — web, image, TTS, browser and video all unlock on{" "}
        <Link href="/pricing">Pro and up</Link>. A free local TTS voice is always
        available regardless of plan.
      </div>

      <h2 id="manage">Manage tools in a session</h2>
      <div className="code-block">
        <span className="c-cmd">/tools list</span>{" "}
        <span className="c-comment"># show enabled tools</span>
        <br />
        <span className="c-cmd">/tools disable terminal</span>{" "}
        <span className="c-comment"># turn a tool off for this session</span>
        <br />
        <span className="c-cmd">/toolsets</span>{" "}
        <span className="c-comment"># list available toolset bundles</span>
      </div>

      <h2 id="mcp">MCP servers</h2>
      <p>
        Connect any Model Context Protocol server to extend the agent with your own tools:
      </p>
      <div className="code-block">
        <span className="c-cmd">clio mcp</span>{" "}
        <span className="c-comment"># add and manage MCP servers</span>
      </div>
      <p>
        Gateway calls are metered against the same monthly allowance as inference — see{" "}
        <Link href="/pricing">pricing</Link>.
      </p>
    </DocsShell>
  );
}
