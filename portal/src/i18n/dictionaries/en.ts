// Master dictionary. Every other locale file is typed against this shape,
// so a missing key fails the build. Command names, plan names and prices are
// NOT here — they come from code (lib/plans.ts) and stay untranslated.

/** A pricing feature line; kind renders the +/–/✦/♪ marker. */
export type FeatureLine = { text: string; kind?: "fusion" | "off" | "music" };

export const en = {
  meta: {
    landingTitle: "Clioloop — the autonomous AI assistant with Agentic Fusion & AI music generation",
    landingDescription:
      "Clioloop is a self-improving AI assistant: Agentic Fusion conducts 300+ models into one answer, generates full songs with AI, searches the web, creates images and video — one login, no API keys.",
    pricingTitle: "Pricing — 300+ models, Agentic Fusion and AI music generation, one login",
    pricingDescription:
      "Clioloop plans: start free with one model, or go Pro for 300+ models, the tool gateway and Agentic Fusion. Max adds AI music and video generation with 5×–10× usage. No API keys.",
  },

  chrome: {
    features: "Features",
    music: "Music",
    pricing: "Pricing",
    docs: "Docs",
    dashboard: "Dashboard",
    login: "Log in",
    getStarted: "Get started",
    footerTagline: "Omni Loop Portal · the subscription gateway for",
    languages: "Languages",
  },

  landing: {
    hero: {
      badge: "one login · 300+ models · agentic fusion",
      h1Lead: "Every model.",
      h1Italic: "One orchestra.",
      lede:
        "Clioloop is the autonomous AI assistant that conducts 300+ models like an orchestra: planners propose the route, your model performs in the open, independent reviewers critique — and it all fuses into one answer you can trust. One login, no API keys. It even writes songs.",
      ctaWindows: "⬇ Download for Windows",
      ctaMusic: "♪ Hear it play",
      ctaInstall: "Install on Linux / macOS",
      terminalTitle: "install clioloop",
      ensembleLabel: "the ensemble",
      ensembleSub: "agentic fusion",
      legendPlanners: "planners",
      legendModel: "your model",
      legendReviewers: "reviewers",
      legendFused: "one fused answer",
      strip: [
        { label: "Models", value: "300+" },
        { label: "Agentic Fusion", value: "Pro & up" },
        { label: "AI music gen", value: "Max & up" },
        { label: "Web search", value: "Included" },
        { label: "Video gen", value: "Max & up" },
        { label: "Cloud browser", value: "Included" },
      ],
    },

    fusion: {
      eyebrow: "the flagship · pro plan and up",
      h2Lead: "Agentic Fusion —",
      h2Italic: "many models, one performance.",
      lede:
        "Run /fusion and put a whole ensemble on a single task. Planners propose routes, your main model does the real, full-tool work in the open, independent reviewers critique the draft, and a verdict loop revises until they approve. The quality comes from the synthesis — cheap open models combine into something that rivals a frontier model, at a fraction of the cost.",
      tierPlanners: "1 · planners — read-only, in parallel",
      chipAdvisor: "advisor",
      chipMore: "+ up to 5",
      flowRoutes: "routes ↓",
      coreLabel: "your main model",
      coreSub: "full-tool work · visible",
      flowDraft: "draft ↓",
      tierReviewers: "2 · reviewers — read-only, can see images",
      chipReviewer: "reviewer",
      flowVerdict: "↺ revise · approve ↓",
      final: "one fused answer",
      points: [
        {
          icon: "🛡️",
          title: "Safe by construction",
          body:
            "Planners and reviewers are read-only at the schema level — they can research and critique, but they can never touch your files or run commands.",
        },
        {
          icon: "👁️",
          title: "Work you can watch",
          body:
            "Your main model does the work live, not in a black box. Reviewers even get vision so they can see the images it generates.",
        },
        {
          icon: "✓",
          title: "Reviewed before you see it",
          body:
            "A verdict loop revises the draft until reviewers approve — the answer that reaches you has already passed review.",
        },
        {
          icon: "🧩",
          title: "Any model combo",
          body:
            "Mix open-weight, OpenRouter and managed models as planners, reviewers and the main worker. Pick them in a quick picker in any client.",
        },
      ],
      ctaResearch: "📊 Read the Research →",
      ctaHow: "How Agentic Fusion works →",
    },

    music: {
      eyebrow: "ai music generator · max plan and up",
      h2Lead: "A full AI music generator,",
      h2Italic: "in the band.",
      lede:
        "Ask Clioloop for a song and it composes one: complete tracks with vocals, lyrics you write or it writes, in any genre. Each generation returns two takes, and you can extend tracks, make covers, add vocals or split stems — from the chat you already have open.",
      caps: [
        "Full songs with vocals — or instrumental only",
        "Your lyrics or generated lyrics, any language",
        "Style and genre prompts, up to 1000 characters",
        "Extend, cover, add vocals, split stems",
        "Two takes per generation",
        "Works in every surface — terminal, desktop, Telegram, WhatsApp…",
      ],
      playerTitle: "Overture — composed by Clioloop",
      playerSub: "AI-generated demo track",
      playerPlay: "Play the demo",
      playerPause: "Pause",
      note: "Music generation is included from the Max plan. Every song here is a real, unedited generation.",
    },

    autonomy: {
      eyebrow: "the autonomous loop",
      h2Lead: "It doesn't stop",
      h2Italic: "until the goal is met.",
      lede:
        "Clioloop is an open-source agent that lives in your terminal, desktop, browser and chat apps. Give it a goal and it keeps working — planning, running tools, checking its own progress — and it remembers what it learns about you.",
      cards: [
        {
          icon: "🎯",
          title: "Standing goals",
          body:
            "/goal starts a loop: after every turn a judge decides if the goal is met. If not, Clioloop takes the next step automatically, with a live banner showing progress.",
        },
        {
          icon: "🗂️",
          title: "Multi-agent Kanban",
          body:
            "Break big work into a board of tasks. Worker agents pick them up, run them and report back — visible in the dashboard and the desktop app.",
        },
        {
          icon: "🧠",
          title: "Memory & self-learning",
          body:
            "A persistent memory is updated automatically as it learns your preferences and projects — the next session already knows you.",
        },
        {
          icon: "📚",
          title: "Skills",
          body:
            "Load expertise packs for the task at hand — and let the agent improve its own skills as it works.",
        },
        {
          icon: "⏰",
          title: "Scheduled runs",
          body:
            "Put the agent on a cron: recurring research, reports, checks — it runs and messages you the result.",
        },
        {
          icon: "🔌",
          title: "Tools & MCP",
          body:
            "File editing, shell, code execution — plus any MCP server you connect.",
        },
      ],
      ctaDocs: "Read the docs & tutorials →",
    },

    tools: {
      eyebrow: "the tool gateway",
      h2Lead: "Every instrument,",
      h2Italic: "one subscription.",
      lede:
        "The portal meters hosted tools against your plan — no separate vendor accounts, no extra API keys.",
      cards: [
        {
          icon: "🔎",
          title: "Web search & extract",
          body: "Live web search, scraping and structured extraction for research loops.",
        },
        {
          icon: "🎨",
          title: "Image generation",
          body: "Fast image generation on dedicated hardware.",
        },
        {
          icon: "🎬",
          title: "Video generation",
          body: "Text-to-video and image-to-video up to 1080p. Max plan and up.",
        },
        {
          icon: "🎙️",
          title: "Premium text-to-speech",
          body: "Studio-grade voices for read-alouds and voice replies.",
        },
        {
          icon: "🌐",
          title: "Cloud browser",
          body: "A hosted browser for logins, forms and sites that block bots.",
        },
        {
          icon: "🧾",
          title: "One bill",
          body: "Everything is metered against your subscription — the dashboard shows live usage per month and per tool.",
        },
      ],
    },

    surfaces: {
      eyebrow: "everywhere you are",
      h2Lead: "One agent,",
      h2Italic: "in every room.",
      lede:
        "The same account, session and memory — from the terminal to your chat apps. Clioloop is an AI assistant for Telegram, WhatsApp, Signal, Slack, iMessage and more.",
      cards: [
        {
          icon: "⌨️",
          title: "Terminal & TUI",
          body: "A full terminal UI with markdown, syntax highlighting and inline images.",
        },
        {
          icon: "🖥️",
          title: "Desktop app",
          body: "A native desktop app with system tray, for macOS, Linux and Windows.",
        },
        {
          icon: "📊",
          title: "Web dashboard",
          body: "Manage sessions, the Kanban board and usage from the browser.",
        },
        {
          icon: "💬",
          title: "Your chat apps",
          body: "Telegram, WhatsApp, Signal, Slack, iMessage, Matrix, Discord, email, SMS — the gateway keeps one session across all of them.",
        },
        {
          icon: "🧑‍💻",
          title: "Editors",
          body: "LSP integration brings the agent into VS Code and other editors.",
        },
        {
          icon: "🔗",
          title: "Gateway API",
          body: "REST and WebSocket APIs to drive the agent from your own software.",
        },
      ],
    },

    install: {
      eyebrow: "get clioloop",
      h2Lead: "Install in one line —",
      h2Italic: "or one click.",
      lede: "Clioloop runs on Linux, macOS and Windows. Fully open source — read every line on GitHub.",
      linuxTitle: "Linux & macOS",
      linuxBody: "One command installs the CLI, TUI and desktop app:",
      linuxAfter: "Then run clio setup and pick a model.",
      windowsTitle: "Windows",
      windowsBody: "Download the installer and run it:",
      windowsCta: "⬇ Download for Windows",
      windowsPs: "Or install from PowerShell:",
      windowsWarn:
        "Heads up: the installer isn't code-signed yet, so Windows SmartScreen may warn. That's expected — click More info → Run anyway. Everything is open source and auditable on GitHub.",
      connectTitle: "Then connect",
      connectBody:
        "Run the setup wizard and choose Omni Loop Portal for one login and 300+ models — or bring your own provider keys.",
      connectAfter: "Read the full setup guide →",
    },

    how: {
      eyebrow: "how it works",
      h2Lead: "Connected in",
      h2Italic: "under a minute.",
      lede: "The quick setup is the default path in every Clioloop surface.",
      steps: [
        {
          title: "Run the setup",
          body: 'Install Clioloop and run the wizard. "Omni Loop Portal" is the first option.',
          code: "clio setup",
        },
        {
          title: "Approve in the browser",
          body:
            "Your browser opens this portal with a device code (RFC 8628). Log in, check the code matches, click approve.",
          code: "WXYZ-2345 ✓",
        },
        {
          title: "Pick a model & loop",
          body:
            "Choose from the live catalog and start. Single-use rotating tokens refresh automatically — you never touch a key.",
          code: "clio",
        },
      ],
    },

    commands: {
      eyebrow: "commands",
      h2Lead: "Everything Clioloop does,",
      h2Italic: "from one CLI.",
      lede:
        "clio on its own starts an interactive chat. Add a subcommand for everything else — or use slash commands mid-conversation.",
      col1Title: "Set up & connect",
      col1: [
        { cmd: "clio setup", desc: "first-run wizard" },
        { cmd: "clio auth", desc: "log in / add providers" },
        { cmd: "clio model", desc: "pick model & provider" },
        { cmd: "clio status", desc: "keys, model, health" },
        { cmd: "clio doctor", desc: "diagnose problems" },
        { cmd: "clio update", desc: "upgrade Clioloop" },
      ],
      col2Title: "Run & surfaces",
      col2: [
        { cmd: "clio", desc: "interactive chat" },
        { cmd: "clio --tui", desc: "full terminal UI" },
        { cmd: "clio desktop", desc: "desktop app" },
        { cmd: "clio dashboard", desc: "web dashboard" },
        { cmd: "clio gateway", desc: "Telegram/Slack/WhatsApp…" },
        { cmd: "clio send", desc: "message a channel from scripts" },
      ],
      col3Title: "Work & automate",
      col3: [
        { cmd: "clio kanban", desc: "multi-agent task board" },
        { cmd: "clio cron", desc: "scheduled jobs" },
        { cmd: "clio skills", desc: "manage skill packs" },
        { cmd: "clio mcp", desc: "connect MCP servers" },
        { cmd: "clio memory", desc: "view/edit memory" },
        { cmd: "clio sessions", desc: "manage sessions & profiles" },
      ],
      slashEyebrow: "in-session",
      slashTitle: "Slash commands, mid-conversation",
      slash: [
        { cmd: "/goal", desc: "keep working until a goal is judged done" },
        { cmd: "/music", desc: "generate a song — vocals, lyrics, any genre (Max)" },
        { cmd: "/model", desc: "switch model or provider without restarting" },
        { cmd: "/kanban", desc: "open the task board" },
        { cmd: "/skills", desc: "load expertise for the task at hand" },
        { cmd: "/fusion", desc: "planners + reviewers + your model → one fused answer (Pro)" },
        { cmd: "/help", desc: "list every command in your build" },
      ],
    },

    pricingTeaser: {
      eyebrow: "pricing",
      h2Lead: "Four seats,",
      h2Italic: "same hall.",
      lede: "Start free with one model. Upgrade when the orchestra should grow.",
      perMonth: "/month",
      taglines: {
        free: "Try Clioloop with one free model",
        pro: "300+ models, tools and Agentic Fusion",
        max: "Adds AI music & video generation, 5× usage",
        max20x: "10× usage for heavy fleets and swarms",
      },
      cta: "See full pricing →",
    },

    cta: {
      eyebrow: "∞ start looping",
      h2Lead: "Give your agent",
      h2Italic: "the whole orchestra.",
      body:
        "Start free with one model, or go Pro for the full 300+ catalog, the tool gateway and Agentic Fusion. Cancel anytime.",
      pricing: "See pricing",
      docs: "Browse the docs",
    },
  },

  pricing: {
    eyebrow: "pricing",
    h2Lead: "One login. Every model.",
    h2Italic: "Agentic Fusion.",
    lede:
      "Every plan includes the full Clioloop experience: one-click setup on CLI, TUI, desktop and dashboard, streaming inference, usage metering and rotating device tokens. No API keys — your subscription is the credential. Hosted tools and Agentic Fusion unlock on Pro; AI music generation on Max.",
    perMonth: "/month",
    flags: { pro: "Most popular", max20x: "Best for fleets" },
    startFree: "Start free",
    choose: "Choose",
    taglines: {
      free: "Try Clioloop with DeepSeek V4 Pro — free",
      pro: "300+ OpenRouter models, one subscription",
      max: "Music & video generation — 5× Pro usage",
      max20x: "10× Pro usage for heavy fleets and swarms",
    },
    features: {
      free: [
        { text: "1 free model to try" },
        { text: "No hosted tools — no web, image, TTS or browser", kind: "off" },
        { text: "No Agentic Fusion (Pro and up)", kind: "off" },
        { text: "1 connected device" },
        { text: "Card verification required — never charged" },
      ] as FeatureLine[],
      pro: [
        { text: "Full 300+ OpenRouter model catalog" },
        { text: "Agentic Fusion — planners + reviewers fuse one answer", kind: "fusion" },
        { text: "Tool gateway: web search & extract · image gen · premium TTS · cloud browser" },
        { text: "Unlimited devices" },
        { text: "Usage dashboard" },
        { text: "Email support" },
      ] as FeatureLine[],
      max: [
        { text: "300+ frontier models — Claude, GPT, Gemini, Grok" },
        { text: "Everything in Pro, incl. Agentic Fusion", kind: "fusion" },
        { text: "AI music generation — full songs with vocals & stems", kind: "music" },
        { text: "Video generation" },
        { text: "5× Pro monthly usage" },
        { text: "Long-running agent loops · priority routing" },
      ] as FeatureLine[],
      max20x: [
        { text: "Everything in Max, incl. music & video generation", kind: "music" },
        { text: "10× Pro monthly usage" },
        { text: "Parallel agent swarms" },
        { text: "Highest priority routing" },
        { text: "Direct support channel" },
      ] as FeatureLine[],
    },
    faqTitle: "Pricing questions",
    faq: [
      {
        q: "Why does Free need a card?",
        a: "A one-time card verification keeps bots and abuse off the free model. You are never charged on the Free plan — verification is a €0 authorization.",
      },
      {
        q: "What does Agentic Fusion cost?",
        a: "Fusion is included from Pro upward at no extra fee. The planner and reviewer model calls are metered against your normal monthly usage allowance, like any other inference. Run Fusion in a fresh session, then reset after the final fused answer so the next planner/reviewer panel does not inherit stale context.",
      },
      {
        q: "How does AI music generation work?",
        a: "On Max and Max 10x, ask for a song in any Clioloop surface: full tracks with vocals, your lyrics or generated ones, any genre — plus extend, cover and stem actions. Each generation returns two takes and is metered per generation.",
      },
      {
        q: "What does “usage” mean?",
        a: "Each request is metered at the upstream model's real cost. Your plan includes a monthly allowance; the dashboard shows live consumption per month and per model.",
      },
      {
        q: "Can I switch plans anytime?",
        a: "Yes — upgrades apply immediately and downgrades at the next billing cycle, handled through the Stripe billing portal in your dashboard.",
      },
    ],
  },
};

export type Dictionary = typeof en;
