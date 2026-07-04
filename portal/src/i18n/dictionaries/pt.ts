import type { Dictionary } from "./en";

export const pt: Dictionary = {
  meta: {
    landingTitle: "Clioloop — o assistente de IA autônomo com Agentic Fusion e gerador de música IA",
    landingDescription:
      "O Clioloop é um assistente de IA que se aperfeiçoa sozinho: o Agentic Fusion rege mais de 300 modelos até uma única resposta, compõe músicas completas com IA, pesquisa na web, cria imagens e vídeo — um único login, sem chaves de API.",
    pricingTitle: "Preços — 300+ modelos, Agentic Fusion e música IA, um único login",
    pricingDescription:
      "Planos do Clioloop: comece grátis com um modelo ou passe ao Pro para 300+ modelos, o gateway de ferramentas e o Agentic Fusion. O Max adiciona geração de música e vídeo com IA e 5–10× de uso. Sem chaves de API.",
  },

  chrome: {
    features: "Recursos",
    music: "Música",
    pricing: "Preços",
    docs: "Docs",
    dashboard: "Painel",
    login: "Entrar",
    getStarted: "Começar",
    footerTagline: "Omni Loop Portal · o gateway de assinatura do",
    languages: "Idiomas",
  },

  landing: {
    hero: {
      badge: "um login · 300+ modelos · agentic fusion",
      h1Lead: "Cada modelo.",
      h1Italic: "Uma orquestra.",
      lede:
        "O Clioloop é o assistente de IA autônomo que rege mais de 300 modelos como uma orquestra: planejadores propõem a rota, o seu modelo executa às claras, revisores independentes criticam — e tudo se funde numa resposta em que você pode confiar. Um login, sem chaves de API. Ele até escreve músicas.",
      ctaWindows: "⬇ Baixar para Windows",
      ctaMusic: "♪ Ouça tocar",
      ctaInstall: "Instalar no Linux / macOS",
      terminalTitle: "instalar clioloop",
      ensembleLabel: "o conjunto",
      ensembleSub: "agentic fusion",
      legendPlanners: "planejadores",
      legendModel: "seu modelo",
      legendReviewers: "revisores",
      legendFused: "uma resposta",
      strip: [
        { label: "Modelos", value: "300+" },
        { label: "Agentic Fusion", value: "a partir do Pro" },
        { label: "Música IA", value: "a partir do Max" },
        { label: "Busca web", value: "Incluída" },
        { label: "Vídeo IA", value: "a partir do Max" },
        { label: "Navegador cloud", value: "Incluído" },
      ],
    },

    fusion: {
      eyebrow: "o carro-chefe · a partir do plano pro",
      h2Lead: "Agentic Fusion —",
      h2Italic: "muitos modelos, uma só execução.",
      lede:
        "Rode /fusion e coloque um conjunto inteiro numa única tarefa. Planejadores propõem rotas, seu modelo principal faz o trabalho de verdade, com todas as ferramentas e às claras, revisores independentes criticam o rascunho, e um laço de veredito revisa até aprovarem. A qualidade vem da síntese — modelos abertos baratos se combinam em algo que rivaliza com um modelo frontier, por uma fração do custo.",
      tierPlanners: "1 · planejadores — somente leitura, em paralelo",
      chipAdvisor: "conselheiro",
      chipMore: "+ até 5",
      flowRoutes: "rotas ↓",
      coreLabel: "seu modelo principal",
      coreSub: "todas as ferramentas · visível",
      flowDraft: "rascunho ↓",
      tierReviewers: "2 · revisores — somente leitura, veem imagens",
      chipReviewer: "revisor",
      flowVerdict: "↺ revisar · aprovar ↓",
      final: "uma resposta fundida",
      points: [
        {
          icon: "🛡️",
          title: "Seguro por construção",
          body:
            "Planejadores e revisores são somente leitura no nível do esquema — podem pesquisar e criticar, mas nunca tocar nos seus arquivos nem executar comandos.",
        },
        {
          icon: "👁️",
          title: "Trabalho à vista",
          body:
            "Seu modelo principal trabalha ao vivo, não numa caixa-preta. Os revisores até têm visão e enxergam as imagens geradas.",
        },
        {
          icon: "✓",
          title: "Revisado antes de chegar",
          body:
            "Um laço de veredito revisa o rascunho até os revisores aprovarem — a resposta que chega até você já passou pela revisão.",
        },
        {
          icon: "🧩",
          title: "Qualquer combinação de modelos",
          body:
            "Misture modelos open-weight, do OpenRouter e gerenciados como planejadores, revisores e modelo principal. Escolha num seletor rápido em qualquer cliente.",
        },
      ],
      ctaResearch: "📊 Ler a pesquisa →",
      ctaHow: "Como funciona o Agentic Fusion →",
    },

    music: {
      eyebrow: "gerador de música ia · a partir do plano max",
      h2Lead: "Um gerador de música IA completo,",
      h2Italic: "na banda.",
      lede:
        "Peça uma música ao Clioloop e ele compõe: faixas completas com vocais, letras suas ou dele, em qualquer gênero. Cada geração devolve duas versões, e você pode estender faixas, fazer covers, adicionar vocais ou separar stems — direto do chat que já está aberto.",
      caps: [
        "Músicas completas com vocais — ou só instrumental",
        "Suas letras ou letras geradas, em qualquer idioma",
        "Prompts de estilo e gênero de até 1000 caracteres",
        "Estender, cover, adicionar vocais, separar stems",
        "Duas versões por geração",
        "Em todas as superfícies — terminal, desktop, Telegram, WhatsApp…",
      ],
      playerTitle: "Abertura — composta pelo Clioloop",
      playerSub: "Demo gerada por IA",
      playerPlay: "Tocar a demo",
      playerPause: "Pausar",
      note: "A geração de música está incluída a partir do plano Max. Cada música aqui é uma geração real, sem edição.",
    },

    autonomy: {
      eyebrow: "o laço autônomo",
      h2Lead: "Ele não para",
      h2Italic: "até cumprir a meta.",
      lede:
        "O Clioloop é um agente open source que vive no seu terminal, desktop, navegador e apps de conversa. Dê uma meta e ele continua trabalhando — planejando, usando ferramentas, conferindo o próprio progresso — e lembra o que aprende sobre você.",
      cards: [
        {
          icon: "🎯",
          title: "Metas permanentes",
          body:
            "/goal inicia um laço: após cada turno, um juiz decide se a meta foi cumprida. Se não, o Clioloop dá o próximo passo sozinho, com um banner de progresso ao vivo.",
        },
        {
          icon: "🗂️",
          title: "Kanban multiagente",
          body:
            "Divida o trabalho grande num quadro de tarefas. Agentes trabalhadores as pegam, executam e reportam — visível no painel e no app de desktop.",
        },
        {
          icon: "🧠",
          title: "Memória e autoaprendizado",
          body:
            "Uma memória persistente se atualiza sozinha enquanto ele aprende suas preferências e projetos — a próxima sessão já conhece você.",
        },
        {
          icon: "📚",
          title: "Habilidades",
          body:
            "Carregue pacotes de especialidade para a tarefa do momento — e deixe o agente melhorar as próprias habilidades enquanto trabalha.",
        },
        {
          icon: "⏰",
          title: "Execuções agendadas",
          body:
            "Coloque o agente num cron: pesquisas recorrentes, relatórios, verificações — ele roda e envia o resultado para você.",
        },
        {
          icon: "🔌",
          title: "Ferramentas e MCP",
          body: "Edição de arquivos, shell, execução de código — mais qualquer servidor MCP que você conectar.",
        },
      ],
      ctaDocs: "Ler docs e tutoriais →",
    },

    tools: {
      eyebrow: "o gateway de ferramentas",
      h2Lead: "Cada instrumento,",
      h2Italic: "uma assinatura.",
      lede:
        "O portal mede as ferramentas hospedadas contra o seu plano — sem contas separadas de fornecedores, sem chaves de API extras.",
      cards: [
        {
          icon: "🔎",
          title: "Busca e extração web",
          body: "Busca web ao vivo, scraping e extração estruturada para laços de pesquisa.",
        },
        { icon: "🎨", title: "Geração de imagens", body: "Geração de imagens rápida em hardware dedicado." },
        {
          icon: "🎬",
          title: "Geração de vídeo",
          body: "Texto-para-vídeo e imagem-para-vídeo até 1080p. A partir do plano Max.",
        },
        {
          icon: "🎙️",
          title: "Texto-para-fala premium",
          body: "Vozes de estúdio para leituras e respostas por voz.",
        },
        {
          icon: "🌐",
          title: "Navegador cloud",
          body: "Um navegador hospedado para logins, formulários e sites que bloqueiam robôs.",
        },
        {
          icon: "🧾",
          title: "Uma só fatura",
          body: "Tudo é medido contra a sua assinatura — o painel mostra o uso ao vivo por mês e por ferramenta.",
        },
      ],
    },

    surfaces: {
      eyebrow: "onde você estiver",
      h2Lead: "Um agente,",
      h2Italic: "em cada sala.",
      lede:
        "A mesma conta, a mesma sessão e a mesma memória — do terminal aos seus apps de conversa. O Clioloop é um assistente de IA para Telegram, WhatsApp, Signal, Slack, iMessage e mais.",
      cards: [
        {
          icon: "⌨️",
          title: "Terminal e TUI",
          body: "Uma interface de terminal completa com markdown, realce de sintaxe e imagens inline.",
        },
        {
          icon: "🖥️",
          title: "App de desktop",
          body: "Um app nativo com bandeja do sistema, para macOS, Linux e Windows.",
        },
        { icon: "📊", title: "Painel web", body: "Gerencie sessões, o quadro Kanban e o uso pelo navegador." },
        {
          icon: "💬",
          title: "Seus apps de conversa",
          body:
            "Telegram, WhatsApp, Signal, Slack, iMessage, Matrix, Discord, e-mail, SMS — o gateway mantém uma única sessão em todos.",
        },
        { icon: "🧑‍💻", title: "Editores", body: "A integração LSP leva o agente ao VS Code e outros editores." },
        {
          icon: "🔗",
          title: "API do gateway",
          body: "APIs REST e WebSocket para comandar o agente a partir do seu próprio software.",
        },
      ],
    },

    install: {
      eyebrow: "obtenha o clioloop",
      h2Lead: "Instale em uma linha —",
      h2Italic: "ou em um clique.",
      lede: "O Clioloop roda em Linux, macOS e Windows. Totalmente open source — cada linha pode ser lida no",
      linuxTitle: "Linux e macOS",
      linuxBody: "Um comando instala a CLI, a TUI e o app de desktop:",
      linuxAfter: "Depois rode clio setup e escolha um modelo.",
      windowsTitle: "Windows",
      windowsBody: "Baixe o instalador e execute:",
      windowsCta: "⬇ Baixar para Windows",
      windowsPs: "Ou instale pelo PowerShell:",
      windowsWarn:
        "Atenção: o instalador ainda não é assinado, então o Windows SmartScreen pode avisar. É esperado — clique em Mais informações → Executar assim mesmo. Tudo é open source e auditável no GitHub.",
      connectTitle: "Depois conecte",
      connectBody:
        "Rode o assistente de configuração e escolha Omni Loop Portal para um login e 300+ modelos — ou traga suas próprias chaves de fornecedor.",
      connectAfter: "Ler o guia de configuração completo →",
    },

    how: {
      eyebrow: "como funciona",
      h2Lead: "Conectado em",
      h2Italic: "menos de um minuto.",
      lede: "A configuração rápida é o caminho padrão em todas as superfícies do Clioloop.",
      steps: [
        {
          title: "Rode a configuração",
          body: 'Instale o Clioloop e rode o assistente. "Omni Loop Portal" é a primeira opção.',
          code: "clio setup",
        },
        {
          title: "Aprove no navegador",
          body:
            "Seu navegador abre este portal com um código de dispositivo (RFC 8628). Entre, confira o código, aprove.",
          code: "WXYZ-2345 ✓",
        },
        {
          title: "Escolha um modelo e gire",
          body:
            "Escolha no catálogo ao vivo e comece. Tokens rotativos de uso único se renovam sozinhos — você nunca toca numa chave.",
          code: "clio",
        },
      ],
    },

    commands: {
      eyebrow: "comandos",
      h2Lead: "Tudo o que o Clioloop faz,",
      h2Italic: "de uma só CLI.",
      lede:
        "clio sozinho abre um chat interativo. Adicione um subcomando para todo o resto — ou use comandos slash no meio da conversa.",
      col1Title: "Configurar e conectar",
      col1: [
        { cmd: "clio setup", desc: "assistente de primeira execução" },
        { cmd: "clio auth", desc: "entrar / adicionar fornecedores" },
        { cmd: "clio model", desc: "escolher modelo e fornecedor" },
        { cmd: "clio status", desc: "chaves, modelo, saúde" },
        { cmd: "clio doctor", desc: "diagnosticar problemas" },
        { cmd: "clio update", desc: "atualizar o Clioloop" },
      ],
      col2Title: "Executar e superfícies",
      col2: [
        { cmd: "clio", desc: "chat interativo" },
        { cmd: "clio --tui", desc: "interface de terminal completa" },
        { cmd: "clio desktop", desc: "app de desktop" },
        { cmd: "clio dashboard", desc: "painel web" },
        { cmd: "clio gateway", desc: "Telegram/Slack/WhatsApp…" },
        { cmd: "clio send", desc: "mandar mensagem a um canal via script" },
      ],
      col3Title: "Trabalhar e automatizar",
      col3: [
        { cmd: "clio kanban", desc: "quadro de tarefas multiagente" },
        { cmd: "clio cron", desc: "tarefas agendadas" },
        { cmd: "clio skills", desc: "gerenciar pacotes de habilidades" },
        { cmd: "clio mcp", desc: "conectar servidores MCP" },
        { cmd: "clio memory", desc: "ver/editar a memória" },
        { cmd: "clio sessions", desc: "gerenciar sessões e perfis" },
      ],
      slashEyebrow: "na sessão",
      slashTitle: "Comandos slash, no meio da conversa",
      slash: [
        { cmd: "/goal", desc: "continuar trabalhando até a meta ser julgada cumprida" },
        { cmd: "/music", desc: "gerar uma música — vocais, letras, qualquer gênero (Max)" },
        { cmd: "/model", desc: "trocar de modelo ou fornecedor sem reiniciar" },
        { cmd: "/kanban", desc: "abrir o quadro de tarefas" },
        { cmd: "/skills", desc: "carregar especialidade para a tarefa" },
        { cmd: "/fusion", desc: "planejadores + revisores + seu modelo → uma resposta (Pro)" },
        { cmd: "/help", desc: "listar todos os comandos da sua versão" },
      ],
    },

    pricingTeaser: {
      eyebrow: "preços",
      h2Lead: "Quatro lugares,",
      h2Italic: "a mesma sala.",
      lede: "Comece grátis com um modelo. Suba de plano quando a orquestra precisar crescer.",
      perMonth: "/mês",
      taglines: {
        free: "Experimente o Clioloop com um modelo grátis",
        pro: "300+ modelos, ferramentas e Agentic Fusion",
        max: "Adiciona música e vídeo IA, uso 5×",
        max20x: "Uso 10× para frotas grandes",
      },
      cta: "Ver todos os preços →",
    },

    cta: {
      eyebrow: "∞ comece o laço",
      h2Lead: "Dê ao seu agente",
      h2Italic: "a orquestra inteira.",
      body:
        "Comece grátis com um modelo, ou vá de Pro para o catálogo completo de 300+ modelos, o gateway de ferramentas e o Agentic Fusion. Cancele quando quiser.",
      pricing: "Ver preços",
      docs: "Explorar as docs",
    },
  },

  pricing: {
    eyebrow: "preços",
    h2Lead: "Um login. Cada modelo.",
    h2Italic: "Agentic Fusion.",
    lede:
      "Todos os planos incluem a experiência Clioloop completa: configuração em um clique na CLI, TUI, desktop e painel, inferência em streaming, medição de uso e tokens de dispositivo rotativos. Sem chaves de API — sua assinatura é a credencial. Ferramentas hospedadas e Agentic Fusion a partir do Pro; música IA a partir do Max.",
    perMonth: "/mês",
    flags: { pro: "Mais popular", max20x: "Para frotas" },
    startFree: "Começar grátis",
    choose: "Escolher",
    taglines: {
      free: "Experimente o Clioloop com o GLM 5.2 — grátis",
      pro: "300+ modelos OpenRouter, uma assinatura",
      max: "Geração de música e vídeo — uso Pro 5×",
      max20x: "Uso Pro 10× para frotas e enxames",
    },
    features: {
      free: [
        { text: "1 modelo grátis para testar" },
        { text: "Sem ferramentas hospedadas — sem web, imagem, TTS ou navegador", kind: "off" },
        { text: "Sem Agentic Fusion (a partir do Pro)", kind: "off" },
        { text: "1 dispositivo conectado" },
        { text: "Verificação de cartão necessária — nunca cobrado" },
      ],
      pro: [
        { text: "Catálogo completo de 300+ modelos OpenRouter" },
        { text: "Agentic Fusion — planejadores + revisores fundem uma resposta", kind: "fusion" },
        { text: "Gateway de ferramentas: busca web e extração · imagens · TTS premium · navegador cloud" },
        { text: "Dispositivos ilimitados" },
        { text: "Painel de uso" },
        { text: "Suporte por e-mail" },
      ],
      max: [
        { text: "300+ modelos frontier — Claude, GPT, Gemini, Grok" },
        { text: "Tudo do Pro, incl. Agentic Fusion", kind: "fusion" },
        { text: "Geração de música IA — músicas completas com vocais e stems", kind: "music" },
        { text: "Geração de vídeo" },
        { text: "Uso mensal 5× Pro" },
        { text: "Laços longos · roteamento prioritário" },
      ],
      max20x: [
        { text: "Tudo do Max, incl. música e vídeo", kind: "music" },
        { text: "Uso mensal 10× Pro" },
        { text: "Enxames de agentes em paralelo" },
        { text: "Prioridade máxima de roteamento" },
        { text: "Canal de suporte direto" },
      ],
    },
    faqTitle: "Dúvidas sobre preços",
    faq: [
      {
        q: "Por que o Free pede cartão?",
        a: "Uma verificação única de cartão mantém bots e abuso longe do modelo grátis. No plano Free você nunca é cobrado — a verificação é uma autorização de € 0.",
      },
      {
        q: "Quanto custa o Agentic Fusion?",
        a: "O Fusion está incluído a partir do Pro sem custo extra. As chamadas de planejadores e revisores são medidas contra sua cota mensal normal, como qualquer outra inferência. Rode o Fusion numa sessão nova e reinicie após a resposta final para o próximo painel não herdar contexto velho.",
      },
      {
        q: "Como funciona a geração de música IA?",
        a: "No Max e Max 10x, peça uma música em qualquer superfície do Clioloop: faixas completas com vocais, letras suas ou geradas, qualquer gênero — mais estender, cover e separar stems. Cada geração devolve duas versões e é medida por geração.",
      },
      {
        q: "O que significa “uso”?",
        a: "Cada requisição é medida ao custo real do modelo upstream. Seu plano inclui uma cota mensal; o painel mostra o consumo ao vivo por mês e por modelo.",
      },
      {
        q: "Posso trocar de plano a qualquer momento?",
        a: "Sim — upgrades valem na hora e downgrades no próximo ciclo de cobrança, pelo portal da Stripe no seu painel.",
      },
    ],
  },
};
