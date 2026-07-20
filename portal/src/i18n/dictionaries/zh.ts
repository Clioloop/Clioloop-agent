import type { Dictionary } from "./en";

export const zh: Dictionary = {
  meta: {
    landingTitle: "Clioloop — 拥有 Agentic Fusion 与 AI 音乐生成的自主 AI 助手",
    landingDescription:
      "Clioloop 是一个自我进化的 AI 助手：Agentic Fusion 指挥 300 多个模型汇成一个答案，用 AI 创作完整歌曲，还能搜索网页、生成图像和视频 — 一次登录，无需 API 密钥。",
    pricingTitle: "价格 — 300+ 模型、Agentic Fusion 与 AI 音乐生成，一次登录",
    pricingDescription:
      "Clioloop 套餐：免费从一个模型开始，或升级 Pro 解锁 300+ 模型、工具网关与 Agentic Fusion。Max 增加 AI 音乐与视频生成，用量提升 5–10 倍。无需 API 密钥。",
  },

  chrome: {
    features: "功能",
    music: "音乐",
    pricing: "价格",
    docs: "文档",
    dashboard: "控制台",
    login: "登录",
    getStarted: "开始使用",
    footerTagline: "Omni Loop Portal · 订阅网关，服务于",
    languages: "语言",
  },

  landing: {
    hero: {
      badge: "一次登录 · 300+ 模型 · agentic fusion",
      h1Lead: "每一个模型，",
      h1Italic: "同一个乐团。",
      lede:
        "Clioloop 是一个自主 AI 助手，像指挥乐团一样指挥 300 多个模型：规划者提出路线，你的模型公开演奏，独立评审员提出批评 — 一切融合成一个值得信赖的答案。一次登录，无需 API 密钥。它甚至会写歌。",
      ctaWindows: "⬇ 下载 Windows 版",
      ctaMusic: "♪ 听它演奏",
      ctaInstall: "在 Linux / macOS 上安装",
      terminalTitle: "安装 clioloop",
      ensembleLabel: "乐团",
      ensembleSub: "agentic fusion",
      legendPlanners: "规划者",
      legendModel: "你的模型",
      legendReviewers: "评审员",
      legendFused: "一个答案",
      strip: [
        { label: "模型", value: "300+" },
        { label: "Agentic Fusion", value: "Pro 起" },
        { label: "AI 音乐", value: "Max 起" },
        { label: "网页搜索", value: "包含" },
        { label: "视频生成", value: "Max 起" },
        { label: "云端浏览器", value: "包含" },
      ],
    },

    fusion: {
      eyebrow: "旗舰功能 · pro 套餐起",
      h2Lead: "Agentic Fusion —",
      h2Italic: "众多模型，一场演出。",
      lede:
        "运行 /fusion，让整个乐团投入同一项任务。规划者提出路线，你的主模型公开使用全部工具完成真正的工作，独立评审员批评草稿，裁决循环反复修改直到通过。质量来自综合 — 廉价的开源模型组合起来，能以极低成本媲美前沿模型。",
      tierPlanners: "1 · 规划者 — 只读，并行运行",
      chipAdvisor: "顾问",
      chipMore: "+ 最多 5 个",
      flowRoutes: "路线 ↓",
      coreLabel: "你的主模型",
      coreSub: "全部工具 · 公开可见",
      flowDraft: "草稿 ↓",
      tierReviewers: "2 · 评审员 — 只读，可查看图像",
      chipReviewer: "评审员",
      flowVerdict: "↺ 修改 · 通过 ↓",
      final: "一个融合的答案",
      points: [
        {
          icon: "🛡️",
          title: "结构上安全",
          body:
            "规划者和评审员在 schema 层面即为只读 — 它们可以调研和批评，但永远无法接触你的文件或执行命令。",
        },
        {
          icon: "👁️",
          title: "全程可见的工作",
          body: "你的主模型实时工作，而不是黑箱。评审员甚至具备视觉能力，能看到生成的图像。",
        },
        {
          icon: "✓",
          title: "送达前已通过评审",
          body: "裁决循环不断修改草稿直到评审员通过 — 你收到的答案已经通过了审查。",
        },
        {
          icon: "🧩",
          title: "任意模型组合",
          body:
            "把开源权重、OpenRouter 和托管模型自由组合为规划者、评审员和主模型。在任何客户端里快速选择。",
        },
      ],
      ctaResearch: "📊 阅读研究 →",
      ctaHow: "Agentic Fusion 如何工作 →",
    },

    music: {
      eyebrow: "ai 音乐生成 · max 套餐起",
      h2Lead: "一个完整的 AI 音乐生成器,",
      h2Italic: "就在乐队里。",
      lede:
        "向 Clioloop 要一首歌，它就会作曲：带人声的完整歌曲，歌词由你写或由它写，任何曲风。每次生成返回两个版本，还能延长曲目、翻唱、加人声或分离音轨 — 就在你已经打开的聊天里。",
      caps: [
        "带人声的完整歌曲 — 或纯伴奏",
        "你的歌词或生成歌词，任何语言",
        "风格与曲风提示最长 1000 字符",
        "延长、翻唱、加人声、分离音轨",
        "每次生成两个版本",
        "所有界面可用 — 终端、桌面、Telegram、WhatsApp…",
      ],
      playerTitle: "序曲 — 由 Clioloop 作曲",
      playerSub: "AI 生成的演示曲目",
      playerPlay: "播放演示",
      playerPause: "暂停",
      note: "音乐生成从 Max 套餐开始提供。这里的每首歌都是真实、未经编辑的生成结果。",
    },

    autonomy: {
      eyebrow: "自主循环",
      h2Lead: "不达目标,",
      h2Italic: "绝不停止。",
      lede:
        "Clioloop 是一个开源智能体，活跃在你的终端、桌面、浏览器和聊天应用中。给它一个目标，它就持续工作 — 规划、调用工具、检查自己的进度 — 并记住关于你的一切。",
      cards: [
        {
          icon: "🎯",
          title: "常驻目标",
          body:
            "/goal 启动循环：每一轮后由裁判判断目标是否达成。若未达成，Clioloop 自动执行下一步，并实时显示进度横幅。",
        },
        {
          icon: "🗂️",
          title: "多智能体看板",
          body: "把大工程拆成任务看板。工作智能体领取、执行并汇报 — 在控制台和桌面应用中都能看到。",
        },
        {
          icon: "🧠",
          title: "记忆与自我学习",
          body: "持久记忆随着它了解你的偏好和项目自动更新 — 下一次会话它已经认识你。",
        },
        {
          icon: "📚",
          title: "技能",
          body: "为手头任务加载专业技能包 — 并让智能体在工作中提升自己的技能。",
        },
        {
          icon: "⏰",
          title: "定时运行",
          body: "把智能体放上 cron：周期性调研、报告、巡检 — 它运行后把结果发给你。",
        },
        {
          icon: "🔌",
          title: "工具与 MCP",
          body: "文件编辑、shell、代码执行 — 以及你接入的任何 MCP 服务器。",
        },
      ],
      ctaDocs: "阅读文档与教程 →",
    },

    tools: {
      eyebrow: "工具网关",
      h2Lead: "每一件乐器,",
      h2Italic: "一份订阅。",
      lede: "门户按你的套餐计量托管工具 — 无需单独的供应商账号，也不需要额外的 API 密钥。",
      cards: [
        {
          icon: "🔎",
          title: "网页搜索与提取",
          body: "实时网页搜索、抓取与结构化提取，服务于调研循环。",
        },
        { icon: "🎨", title: "图像生成", body: "专用硬件上的快速图像生成。" },
        { icon: "🎬", title: "视频生成", body: "文生视频与图生视频，最高 1080p。Max 套餐起。" },
        { icon: "🎙️", title: "高级语音合成", body: "录音棚级的声音，用于朗读和语音回复。" },
        {
          icon: "🌐",
          title: "云端浏览器",
          body: "托管浏览器，用于登录、表单和屏蔽机器人的网站。",
        },
        {
          icon: "🧾",
          title: "一张账单",
          body: "一切按订阅计量 — 控制台按月、按工具实时展示用量。",
        },
      ],
    },

    surfaces: {
      eyebrow: "无处不在",
      h2Lead: "一个智能体,",
      h2Italic: "在每个房间。",
      lede:
        "同一个账号、同一个会话、同一份记忆 — 从终端到你的聊天应用。Clioloop 是可用于 Telegram、WhatsApp、Signal、Slack、iMessage 等平台的 AI 助手。",
      cards: [
        {
          icon: "⌨️",
          title: "终端与 TUI",
          body: "功能完整的终端界面，支持 markdown、语法高亮和内联图片。",
        },
        {
          icon: "🖥️",
          title: "桌面应用",
          body: "带系统托盘的原生应用，支持 macOS、Linux 和 Windows。",
        },
        { icon: "📊", title: "网页控制台", body: "在浏览器中管理会话、看板和用量。" },
        {
          icon: "💬",
          title: "你的聊天应用",
          body:
            "Telegram、WhatsApp、Signal、Slack、iMessage、Matrix、Discord、邮件、短信 — 网关在所有平台间保持同一个会话。",
        },
        { icon: "🧑‍💻", title: "编辑器", body: "LSP 集成把智能体带进 VS Code 等编辑器。" },
        {
          icon: "🔗",
          title: "网关 API",
          body: "REST 与 WebSocket API，让你从自己的软件驱动智能体。",
        },
      ],
    },

    install: {
      eyebrow: "获取 clioloop",
      h2Lead: "一行命令安装 —",
      h2Italic: "或一键完成。",
      lede: "Clioloop 支持 Linux、macOS 和 Windows。完全开源 — 每一行代码都可以在这里阅读：",
      linuxTitle: "Linux 与 macOS",
      linuxBody: "一条命令安装 CLI、TUI 和桌面应用：",
      linuxAfter: "然后运行 clio setup 并选择模型。",
      windowsTitle: "Windows",
      windowsBody: "下载安装程序并运行：",
      windowsCta: "⬇ 下载 Windows 版",
      windowsPs: "或通过 PowerShell 安装：",
      windowsWarn:
        "提示：安装程序尚未代码签名，Windows SmartScreen 可能会警告。这是正常的 — 点击「更多信息」→「仍要运行」。一切开源，可在 GitHub 上审计。",
      connectTitle: "然后连接",
      connectBody:
        "运行设置向导并选择 Omni Loop Portal，一次登录即可使用 300+ 模型 — 也可以使用自己的供应商密钥。",
      connectAfter: "阅读完整设置指南 →",
    },

    how: {
      eyebrow: "工作原理",
      h2Lead: "连接只需,",
      h2Italic: "不到一分钟。",
      lede: "快速设置是所有 Clioloop 界面的默认路径。",
      steps: [
        {
          title: "运行设置",
          body: "安装 Clioloop 并运行向导。「Omni Loop Portal」是第一个选项。",
          code: "clio setup",
        },
        {
          title: "在浏览器中批准",
          body: "浏览器会带着设备码打开本门户 (RFC 8628)。登录，核对设备码，点击批准。",
          code: "WXYZ-2345 ✓",
        },
        {
          title: "选择模型，开始循环",
          body: "从实时目录中选择并开始。一次性轮换令牌自动刷新 — 你永远不用碰密钥。",
          code: "clio",
        },
      ],
    },

    commands: {
      eyebrow: "命令",
      h2Lead: "Clioloop 的一切能力,",
      h2Italic: "尽在一个 CLI。",
      lede: "单独运行 clio 即可开始交互聊天。其余功能用子命令 — 对话中还可以使用斜杠命令。",
      col1Title: "设置与连接",
      col1: [
        { cmd: "clio setup", desc: "首次运行向导" },
        { cmd: "clio auth", desc: "登录 / 添加供应商" },
        { cmd: "clio model", desc: "选择模型与供应商" },
        { cmd: "clio status", desc: "密钥、模型、健康状态" },
        { cmd: "clio doctor", desc: "诊断问题" },
        { cmd: "clio update", desc: "升级 Clioloop" },
      ],
      col2Title: "运行与界面",
      col2: [
        { cmd: "clio", desc: "交互聊天" },
        { cmd: "clio --tui", desc: "完整终端界面" },
        { cmd: "clio desktop", desc: "桌面应用" },
        { cmd: "clio dashboard", desc: "网页控制台" },
        { cmd: "clio gateway", desc: "Telegram/Slack/WhatsApp…" },
        { cmd: "clio send", desc: "从脚本向频道发消息" },
      ],
      col3Title: "工作与自动化",
      col3: [
        { cmd: "clio kanban", desc: "多智能体任务看板" },
        { cmd: "clio cron", desc: "定时任务" },
        { cmd: "clio skills", desc: "管理技能包" },
        { cmd: "clio mcp", desc: "接入 MCP 服务器" },
        { cmd: "clio memory", desc: "查看/编辑记忆" },
        { cmd: "clio sessions", desc: "管理会话与配置" },
      ],
      slashEyebrow: "会话中",
      slashTitle: "对话中的斜杠命令",
      slash: [
        { cmd: "/goal", desc: "持续工作，直到裁判判定目标达成" },
        { cmd: "/music", desc: "生成一首歌 — 人声、歌词、任何曲风 (Max)" },
        { cmd: "/model", desc: "无需重启即可切换模型或供应商" },
        { cmd: "/kanban", desc: "打开任务看板" },
        { cmd: "/skills", desc: "为当前任务加载专业技能" },
        { cmd: "/fusion", desc: "规划者 + 评审员 + 你的模型 → 一个答案 (Pro)" },
        { cmd: "/help", desc: "列出当前版本的所有命令" },
      ],
    },

    pricingTeaser: {
      eyebrow: "价格",
      h2Lead: "四个座位,",
      h2Italic: "同一个音乐厅。",
      lede: "免费从一个模型开始。乐团需要扩编时再升级。",
      perMonth: "/月",
      taglines: {
        free: "用免费模型体验 Clioloop",
        pro: "300+ 模型、工具与 Agentic Fusion",
        max: "增加 AI 音乐与视频生成，5 倍用量",
        max20x: "10 倍用量，适合大规模集群",
      },
      cta: "查看完整价格 →",
    },

    cta: {
      eyebrow: "∞ 开始循环",
      h2Lead: "把整个乐团,",
      h2Italic: "交给你的智能体。",
      body:
        "免费从一个模型开始，或升级 Pro 解锁 300+ 模型全目录、工具网关与 Agentic Fusion。随时可取消。",
      pricing: "查看价格",
      docs: "浏览文档",
    },
  },

  pricing: {
    eyebrow: "价格",
    h2Lead: "一次登录。每一个模型。",
    h2Italic: "Agentic Fusion。",
    lede:
      "每个套餐都包含完整的 Clioloop 体验：CLI、TUI、桌面与控制台的一键设置、流式推理、用量计量和轮换设备令牌。无需 API 密钥 — 你的订阅就是凭证。托管工具与 Agentic Fusion 从 Pro 起；AI 音乐生成从 Max 起。",
    perMonth: "/月",
    flags: { pro: "最受欢迎", max20x: "适合集群" },
    startFree: "免费开始",
    choose: "选择",
    taglines: {
      free: "用 DeepSeek V4 Pro 体验 Clioloop — 免费",
      pro: "300+ OpenRouter 模型，一份订阅",
      max: "音乐与视频生成 — 5 倍 Pro 用量",
      max20x: "10 倍 Pro 用量，适合集群与蜂群",
    },
    features: {
      free: [
        { text: "1 个免费模型试用" },
        { text: "无托管工具 — 不含网页、图像、TTS 或浏览器", kind: "off" },
        { text: "无 Agentic Fusion（Pro 起）", kind: "off" },
        { text: "1 台连接设备" },
        { text: "需要银行卡验证 — 永不扣费" },
      ],
      pro: [
        { text: "300+ OpenRouter 模型全目录" },
        { text: "Agentic Fusion — 规划者 + 评审员融合出一个答案", kind: "fusion" },
        { text: "工具网关：网页搜索与提取 · 图像生成 · 高级 TTS · 云端浏览器" },
        { text: "设备数量不限" },
        { text: "用量控制台" },
        { text: "邮件支持" },
      ],
      max: [
        { text: "300+ 前沿模型 — Claude、GPT、Gemini、Grok" },
        { text: "Pro 的全部功能，含 Agentic Fusion", kind: "fusion" },
        { text: "AI 音乐生成 — 带人声与音轨的完整歌曲", kind: "music" },
        { text: "视频生成" },
        { text: "月用量为 Pro 的 5 倍" },
        { text: "长时循环 · 优先路由" },
      ],
      max20x: [
        { text: "Max 的全部功能，含音乐与视频生成", kind: "music" },
        { text: "月用量为 Pro 的 10 倍" },
        { text: "并行智能体蜂群" },
        { text: "最高路由优先级" },
        { text: "直达支持渠道" },
      ],
    },
    faqTitle: "价格相关问题",
    faq: [
      {
        q: "为什么 Free 需要银行卡？",
        a: "一次性的银行卡验证可以把机器人和滥用挡在免费模型之外。Free 套餐永远不会扣费 — 验证只是一笔 0 欧元的预授权。",
      },
      {
        q: "Agentic Fusion 收费吗？",
        a: "Fusion 从 Pro 起免费包含。规划者和评审员的调用和其他推理一样，计入你的正常月度用量。请在全新会话中运行 Fusion，并在最终答案后重置，以免下一组面板继承旧上下文。",
      },
      {
        q: "AI 音乐生成怎么用？",
        a: "在 Max 和 Max 10x 上，在任何 Clioloop 界面里要一首歌即可：带人声的完整曲目、你的歌词或生成歌词、任何曲风 — 还有延长、翻唱和音轨分离。每次生成返回两个版本，按生成次数计量。",
      },
      {
        q: "「用量」是什么意思？",
        a: "每个请求都按上游模型的真实成本计量。套餐包含月度额度；控制台按月、按模型实时显示消耗。",
      },
      {
        q: "可以随时更换套餐吗？",
        a: "可以 — 升级立即生效，降级在下一个账单周期生效，都通过控制台里的 Stripe 门户办理。",
      },
    ],
  },
};
