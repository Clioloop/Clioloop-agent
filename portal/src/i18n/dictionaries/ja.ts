import type { Dictionary } from "./en";

export const ja: Dictionary = {
  meta: {
    landingTitle: "Clioloop — Agentic FusionとAI作曲を備えた自律型AIアシスタント",
    landingDescription:
      "Clioloopは自己改善するAIアシスタント。Agentic Fusionが300以上のモデルを指揮してひとつの回答にまとめ、AIで完全な楽曲を作曲し、Web検索・画像生成・動画生成もこなします。ログインひとつ、APIキー不要。",
    pricingTitle: "料金 — 300以上のモデル、Agentic Fusion、AI音楽生成をひとつのログインで",
    pricingDescription:
      "Clioloopのプラン: 無料で1モデルから始めるか、Proで300以上のモデル・ツールゲートウェイ・Agentic Fusionを解放。MaxはAI音楽・動画生成と5〜10倍の利用枠を追加。APIキー不要。",
  },

  chrome: {
    features: "機能",
    music: "ミュージック",
    pricing: "料金",
    docs: "ドキュメント",
    dashboard: "ダッシュボード",
    login: "ログイン",
    getStarted: "はじめる",
    footerTagline: "Omni Loop Portal · サブスクリプションゲートウェイ —",
    languages: "言語",
  },

  landing: {
    hero: {
      badge: "ログインひとつ · 300+モデル · agentic fusion",
      h1Lead: "すべてのモデルを、",
      h1Italic: "ひとつのオーケストラに。",
      lede:
        "Clioloopは300以上のモデルをオーケストラのように指揮する自律型AIアシスタント。プランナーが道筋を提案し、あなたのモデルが公開の場で演奏し、独立したレビュアーが批評する — そしてすべてが信頼できるひとつの回答に融合します。ログインひとつ、APIキー不要。作曲までこなします。",
      ctaWindows: "⬇ Windows版をダウンロード",
      ctaMusic: "♪ 聴いてみる",
      ctaInstall: "Linux / macOSにインストール",
      terminalTitle: "clioloopをインストール",
      ensembleLabel: "アンサンブル",
      ensembleSub: "agentic fusion",
      legendPlanners: "プランナー",
      legendModel: "あなたのモデル",
      legendReviewers: "レビュアー",
      legendFused: "ひとつの回答",
      strip: [
        { label: "モデル", value: "300+" },
        { label: "Agentic Fusion", value: "Pro以上" },
        { label: "AI作曲", value: "Max以上" },
        { label: "Web検索", value: "込み" },
        { label: "動画生成", value: "Max以上" },
        { label: "クラウドブラウザ", value: "込み" },
      ],
    },

    fusion: {
      eyebrow: "フラッグシップ · proプラン以上",
      h2Lead: "Agentic Fusion —",
      h2Italic: "多くのモデル、ひとつの演奏。",
      lede:
        "/fusionを実行すると、ひとつのタスクにアンサンブル全体が取り組みます。プランナーが道筋を提案し、メインモデルがすべてのツールを使って公開の場で本当の作業を行い、独立したレビュアーが草稿を批評、承認されるまで判定ループが修正を重ねます。品質は統合から生まれます — 安価なオープンモデルの組み合わせが、フロンティアモデルに匹敵する結果をわずかなコストで実現します。",
      tierPlanners: "1 · プランナー — 読み取り専用・並列",
      chipAdvisor: "アドバイザー",
      chipMore: "+ 最大5",
      flowRoutes: "道筋 ↓",
      coreLabel: "あなたのメインモデル",
      coreSub: "全ツール · 公開",
      flowDraft: "草稿 ↓",
      tierReviewers: "2 · レビュアー — 読み取り専用・画像も確認",
      chipReviewer: "レビュアー",
      flowVerdict: "↺ 修正 · 承認 ↓",
      final: "融合されたひとつの回答",
      points: [
        {
          icon: "🛡️",
          title: "構造的に安全",
          body:
            "プランナーとレビュアーはスキーマレベルで読み取り専用。調査と批評はできても、ファイルに触れたりコマンドを実行したりは決してできません。",
        },
        {
          icon: "👁️",
          title: "見える作業",
          body:
            "メインモデルはブラックボックスではなくライブで作業します。レビュアーはビジョンも備え、生成された画像まで確認できます。",
        },
        {
          icon: "✓",
          title: "届く前にレビュー済み",
          body:
            "判定ループがレビュアーの承認まで草稿を修正します — あなたに届く回答はすでにレビューを通過しています。",
        },
        {
          icon: "🧩",
          title: "モデルは自由に組み合わせ",
          body:
            "オープンウェイト、OpenRouter、マネージドモデルをプランナー・レビュアー・メインに自由に配置。どのクライアントでもクイックピッカーで選べます。",
        },
      ],
      ctaResearch: "📊 研究を読む →",
      ctaHow: "Agentic Fusionの仕組み →",
    },

    music: {
      eyebrow: "ai作曲 · maxプラン以上",
      h2Lead: "本格的なAI音楽生成が、",
      h2Italic: "バンドの一員に。",
      lede:
        "Clioloopに曲をリクエストすると作曲してくれます。ボーカル入りの完全な楽曲を、あなたの歌詞でも自動生成の歌詞でも、どんなジャンルでも。1回の生成で2テイクが届き、曲の延長・カバー・ボーカル追加・ステム分離も、いつものチャットからそのまま。",
      caps: [
        "ボーカル入りのフルソング — インストゥルメンタルも可",
        "自分の歌詞でも生成歌詞でも、どの言語でも",
        "スタイル・ジャンル指定は最大1000文字",
        "延長・カバー・ボーカル追加・ステム分離",
        "1回の生成で2テイク",
        "すべての画面で — ターミナル、デスクトップ、Telegram、WhatsApp…",
      ],
      playerTitle: "序曲 — Clioloop作曲",
      playerSub: "AI生成のデモトラック",
      playerPlay: "デモを再生",
      playerPause: "一時停止",
      note: "音楽生成はMaxプランから利用できます。ここにある曲はすべて編集なしの実際の生成結果です。",
    },

    autonomy: {
      eyebrow: "自律ループ",
      h2Lead: "目標を達成するまで、",
      h2Italic: "止まらない。",
      lede:
        "Clioloopはターミナル、デスクトップ、ブラウザ、チャットアプリに住むオープンソースのエージェント。目標を与えれば、計画し、ツールを使い、自ら進捗を確かめながら働き続け、あなたについて学んだことを覚えています。",
      cards: [
        {
          icon: "🎯",
          title: "常設ゴール",
          body:
            "/goalでループ開始: 各ターン後にジャッジが達成を判定。未達ならClioloopが自動で次の一手を打ち、進捗はライブバナーに表示されます。",
        },
        {
          icon: "🗂️",
          title: "マルチエージェントかんばん",
          body:
            "大きな仕事をタスクボードに分割。ワーカーエージェントが引き受けて実行し、報告します — ダッシュボードとデスクトップアプリで確認できます。",
        },
        {
          icon: "🧠",
          title: "記憶と自己学習",
          body:
            "永続メモリがあなたの好みやプロジェクトを学ぶたびに自動更新 — 次のセッションはもうあなたを知っています。",
        },
        {
          icon: "📚",
          title: "スキル",
          body: "目の前のタスクに合わせて専門知識パックを読み込み — 働きながら自分のスキルも磨きます。",
        },
        {
          icon: "⏰",
          title: "スケジュール実行",
          body: "エージェントをcronに: 定期リサーチ、レポート、チェック — 実行して結果を送ってくれます。",
        },
        {
          icon: "🔌",
          title: "ツールとMCP",
          body: "ファイル編集、シェル、コード実行 — さらに接続した任意のMCPサーバー。",
        },
      ],
      ctaDocs: "ドキュメントとチュートリアル →",
    },

    tools: {
      eyebrow: "ツールゲートウェイ",
      h2Lead: "すべての楽器を、",
      h2Italic: "ひとつのサブスクで。",
      lede:
        "ホスト型ツールはポータルがプランに対して従量計測 — ベンダーごとのアカウントも追加のAPIキーも不要です。",
      cards: [
        {
          icon: "🔎",
          title: "Web検索と抽出",
          body: "ライブWeb検索、スクレイピング、構造化抽出をリサーチループに。",
        },
        { icon: "🎨", title: "画像生成", body: "専用ハードウェアによる高速画像生成。" },
        { icon: "🎬", title: "動画生成", body: "テキストや画像から最大1080pの動画へ。Maxプラン以上。" },
        { icon: "🎙️", title: "プレミアム音声合成", body: "読み上げや音声返信のためのスタジオ品質ボイス。" },
        {
          icon: "🌐",
          title: "クラウドブラウザ",
          body: "ログイン、フォーム、ボットを弾くサイトのためのホスト型ブラウザ。",
        },
        {
          icon: "🧾",
          title: "請求はひとつ",
          body: "すべてサブスクに対して計測 — ダッシュボードで月別・ツール別の利用状況をライブ表示。",
        },
      ],
    },

    surfaces: {
      eyebrow: "あなたのいる場所で",
      h2Lead: "ひとつのエージェントが、",
      h2Italic: "すべての部屋に。",
      lede:
        "同じアカウント、同じセッション、同じ記憶 — ターミナルからチャットアプリまで。ClioloopはTelegram、WhatsApp、Signal、Slack、iMessageなどで使えるAIアシスタントです。",
      cards: [
        {
          icon: "⌨️",
          title: "ターミナルとTUI",
          body: "Markdown、シンタックスハイライト、インライン画像対応のフル機能ターミナルUI。",
        },
        {
          icon: "🖥️",
          title: "デスクトップアプリ",
          body: "システムトレイ付きのネイティブアプリ。macOS、Linux、Windows対応。",
        },
        { icon: "📊", title: "Webダッシュボード", body: "セッション、かんばんボード、利用状況をブラウザで管理。" },
        {
          icon: "💬",
          title: "チャットアプリ",
          body:
            "Telegram、WhatsApp、Signal、Slack、iMessage、Matrix、Discord、メール、SMS — ゲートウェイがすべてでひとつのセッションを維持。",
        },
        { icon: "🧑‍💻", title: "エディタ", body: "LSP連携でVS Codeなどのエディタにもエージェントを。" },
        {
          icon: "🔗",
          title: "ゲートウェイAPI",
          body: "REST・WebSocket APIで自作ソフトからエージェントを操作。",
        },
      ],
    },

    install: {
      eyebrow: "clioloopを入手",
      h2Lead: "1行でインストール —",
      h2Italic: "またはワンクリックで。",
      lede: "ClioloopはLinux、macOS、Windowsで動きます。完全オープンソース — すべてのコードはこちらで:",
      linuxTitle: "Linux & macOS",
      linuxBody: "1コマンドでCLI、TUI、デスクトップアプリをインストール:",
      linuxAfter: "その後 clio setup を実行してモデルを選択。",
      windowsTitle: "Windows",
      windowsBody: "インストーラをダウンロードして実行:",
      windowsCta: "⬇ Windows版をダウンロード",
      windowsPs: "またはPowerShellから:",
      windowsWarn:
        "注意: インストーラはまだコード署名されていないため、Windows SmartScreenが警告する場合があります。想定内です — 「詳細情報」→「実行」をクリックしてください。すべてオープンソースでGitHubで監査できます。",
      connectTitle: "そして接続",
      connectBody:
        "セットアップウィザードでOmni Loop Portalを選べば、ログインひとつで300以上のモデルへ — 自前のプロバイダーキーでもOK。",
      connectAfter: "セットアップガイド全文 →",
    },

    how: {
      eyebrow: "仕組み",
      h2Lead: "接続まで、",
      h2Italic: "1分未満。",
      lede: "クイックセットアップがすべてのClioloop画面の標準ルートです。",
      steps: [
        {
          title: "セットアップを実行",
          body: "Clioloopをインストールしてウィザードを起動。「Omni Loop Portal」が最初の選択肢です。",
          code: "clio setup",
        },
        {
          title: "ブラウザで承認",
          body:
            "ブラウザがデバイスコード付きでこのポータルを開きます (RFC 8628)。ログインし、コードを確認して承認。",
          code: "WXYZ-2345 ✓",
        },
        {
          title: "モデルを選んでループ開始",
          body:
            "ライブカタログから選んでスタート。使い捨てのローテーショントークンが自動更新 — キーに触れることはありません。",
          code: "clio",
        },
      ],
    },

    commands: {
      eyebrow: "コマンド",
      h2Lead: "Clioloopのすべてを、",
      h2Italic: "ひとつのCLIから。",
      lede:
        "clio単体で対話チャットを開始。それ以外はサブコマンドで — 会話の途中ではスラッシュコマンドも使えます。",
      col1Title: "セットアップと接続",
      col1: [
        { cmd: "clio setup", desc: "初回ウィザード" },
        { cmd: "clio auth", desc: "ログイン / プロバイダー追加" },
        { cmd: "clio model", desc: "モデルとプロバイダーを選択" },
        { cmd: "clio status", desc: "キー、モデル、ヘルス" },
        { cmd: "clio doctor", desc: "問題を診断" },
        { cmd: "clio update", desc: "Clioloopを更新" },
      ],
      col2Title: "実行と画面",
      col2: [
        { cmd: "clio", desc: "対話チャット" },
        { cmd: "clio --tui", desc: "フルターミナルUI" },
        { cmd: "clio desktop", desc: "デスクトップアプリ" },
        { cmd: "clio dashboard", desc: "Webダッシュボード" },
        { cmd: "clio gateway", desc: "Telegram/Slack/WhatsApp…" },
        { cmd: "clio send", desc: "スクリプトからチャンネルへ送信" },
      ],
      col3Title: "作業と自動化",
      col3: [
        { cmd: "clio kanban", desc: "マルチエージェントのタスクボード" },
        { cmd: "clio cron", desc: "スケジュールジョブ" },
        { cmd: "clio skills", desc: "スキルパックを管理" },
        { cmd: "clio mcp", desc: "MCPサーバーを接続" },
        { cmd: "clio memory", desc: "メモリを表示/編集" },
        { cmd: "clio sessions", desc: "セッションとプロファイルを管理" },
      ],
      slashEyebrow: "セッション中",
      slashTitle: "会話の途中で使えるスラッシュコマンド",
      slash: [
        { cmd: "/goal", desc: "目標達成と判定されるまで働き続ける" },
        { cmd: "/music", desc: "曲を生成 — ボーカル、歌詞、どんなジャンルでも (Max)" },
        { cmd: "/model", desc: "再起動せずにモデルやプロバイダーを切り替え" },
        { cmd: "/kanban", desc: "タスクボードを開く" },
        { cmd: "/skills", desc: "タスクに合わせた専門知識を読み込む" },
        { cmd: "/fusion", desc: "プランナー + レビュアー + あなたのモデル → ひとつの回答 (Pro)" },
        { cmd: "/help", desc: "このビルドの全コマンドを表示" },
      ],
    },

    pricingTeaser: {
      eyebrow: "料金",
      h2Lead: "4つの席、",
      h2Italic: "同じホール。",
      lede: "無料で1モデルから。オーケストラを大きくしたくなったらアップグレード。",
      perMonth: "/月",
      taglines: {
        free: "無料モデルでClioloopを試す",
        pro: "300+モデル、ツール、Agentic Fusion",
        max: "AI音楽・動画生成を追加、利用5倍",
        max20x: "大規模フリート向けの利用10倍",
      },
      cta: "料金の詳細 →",
    },

    cta: {
      eyebrow: "∞ ループを始めよう",
      h2Lead: "あなたのエージェントに、",
      h2Italic: "オーケストラ全体を。",
      body:
        "無料で1モデルから始めるか、Proで300以上の全カタログ・ツールゲートウェイ・Agentic Fusionを解放。いつでも解約できます。",
      pricing: "料金を見る",
      docs: "ドキュメントを見る",
    },
  },

  pricing: {
    eyebrow: "料金",
    h2Lead: "ログインひとつ。すべてのモデル。",
    h2Italic: "Agentic Fusion。",
    lede:
      "すべてのプランにClioloopのフル体験が含まれます: CLI・TUI・デスクトップ・ダッシュボードのワンクリック設定、ストリーミング推論、利用計測、ローテーションデバイストークン。APIキー不要 — サブスクリプションが資格情報です。ホスト型ツールとAgentic FusionはProから、AI音楽生成はMaxから。",
    perMonth: "/月",
    flags: { pro: "一番人気", max20x: "フリート向け" },
    startFree: "無料で始める",
    choose: "選択:",
    taglines: {
      free: "DeepSeek V4 ProでClioloopを試す — 無料",
      pro: "300+のOpenRouterモデル、ひとつのサブスク",
      max: "音楽・動画生成 — Proの5倍の利用枠",
      max20x: "フリートとスウォーム向け、Proの10倍",
    },
    features: {
      free: [
        { text: "お試し用の無料モデル1つ" },
        { text: "ホスト型ツールなし — Web、画像、TTS、ブラウザは不可", kind: "off" },
        { text: "Agentic Fusionなし (Pro以上)", kind: "off" },
        { text: "接続デバイス1台" },
        { text: "カード認証が必要 — 請求は一切なし" },
      ],
      pro: [
        { text: "300+のOpenRouterモデル全カタログ" },
        { text: "Agentic Fusion — プランナーとレビュアーがひとつの回答に融合", kind: "fusion" },
        { text: "ツールゲートウェイ: Web検索と抽出 · 画像生成 · プレミアムTTS · クラウドブラウザ" },
        { text: "デバイス無制限" },
        { text: "利用状況ダッシュボード" },
        { text: "メールサポート" },
      ],
      max: [
        { text: "300+のフロンティアモデル — Claude、GPT、Gemini、Grok" },
        { text: "Proの全機能、Agentic Fusion込み", kind: "fusion" },
        { text: "AI音楽生成 — ボーカルとステム付きのフルソング", kind: "music" },
        { text: "動画生成" },
        { text: "月間利用枠はProの5倍" },
        { text: "長時間ループ · 優先ルーティング" },
      ],
      max20x: [
        { text: "Maxの全機能、音楽・動画生成込み", kind: "music" },
        { text: "月間利用枠はProの10倍" },
        { text: "並列エージェントスウォーム" },
        { text: "最優先ルーティング" },
        { text: "直通サポートチャンネル" },
      ],
    },
    faqTitle: "料金についての質問",
    faq: [
      {
        q: "Freeにカードが必要なのはなぜ?",
        a: "一度きりのカード認証で、無料モデルをボットや不正利用から守っています。Freeプランで請求されることはありません — 認証は0ユーロのオーソリです。",
      },
      {
        q: "Agentic Fusionの料金は?",
        a: "FusionはPro以上に追加料金なしで含まれます。プランナーとレビュアーの呼び出しは他の推論と同様、通常の月間利用枠に対して計測されます。Fusionは新しいセッションで実行し、最終回答の後にリセットして、次のパネルに古いコンテキストを渡さないようにしてください。",
      },
      {
        q: "AI音楽生成はどう使う?",
        a: "MaxとMax 10xでは、どのClioloop画面からでも曲をリクエストできます: ボーカル入りのフルトラック、自分の歌詞でも生成歌詞でも、どんなジャンルでも — 延長・カバー・ステム分離も。1回の生成で2テイクが届き、生成単位で計測されます。",
      },
      {
        q: "「利用」とは何を指しますか?",
        a: "各リクエストは上流モデルの実コストで計測されます。プランには月間枠が含まれ、ダッシュボードで月別・モデル別の消費をライブで確認できます。",
      },
      {
        q: "プランはいつでも変更できますか?",
        a: "はい — アップグレードは即時、ダウングレードは次の請求サイクルから。ダッシュボードのStripeポータルで手続きできます。",
      },
    ],
  },
};
