import type { Dictionary } from "./en";

export const es: Dictionary = {
  meta: {
    landingTitle: "Clioloop — el asistente de IA autónomo con Agentic Fusion y generador de música IA",
    landingDescription:
      "Clioloop es un asistente de IA que se mejora a sí mismo: Agentic Fusion dirige más de 300 modelos hacia una sola respuesta, compone canciones completas con IA, busca en la web, crea imágenes y vídeo — un solo inicio de sesión, sin claves API.",
    pricingTitle: "Precios — 300+ modelos, Agentic Fusion y música IA, un solo login",
    pricingDescription:
      "Planes de Clioloop: empieza gratis con un modelo o pasa a Pro para 300+ modelos, la pasarela de herramientas y Agentic Fusion. Max añade generación de música y vídeo con IA y 5–10× de uso. Sin claves API.",
  },

  chrome: {
    features: "Funciones",
    music: "Música",
    pricing: "Precios",
    docs: "Docs",
    dashboard: "Panel",
    login: "Iniciar sesión",
    getStarted: "Empezar",
    footerTagline: "Omni Loop Portal · la pasarela de suscripción para",
    languages: "Idiomas",
  },

  landing: {
    hero: {
      badge: "un login · 300+ modelos · agentic fusion",
      h1Lead: "Cada modelo.",
      h1Italic: "Una orquesta.",
      lede:
        "Clioloop es el asistente de IA autónomo que dirige más de 300 modelos como una orquesta: los planificadores proponen la ruta, tu modelo actúa a la vista, revisores independientes critican — y todo se fusiona en una respuesta en la que puedes confiar. Un login, sin claves API. Hasta escribe canciones.",
      ctaWindows: "⬇ Descargar para Windows",
      ctaMusic: "♪ Escúchalo",
      ctaInstall: "Instalar en Linux / macOS",
      terminalTitle: "instalar clioloop",
      ensembleLabel: "el conjunto",
      ensembleSub: "agentic fusion",
      legendPlanners: "planificadores",
      legendModel: "tu modelo",
      legendReviewers: "revisores",
      legendFused: "una respuesta",
      strip: [
        { label: "Modelos", value: "300+" },
        { label: "Agentic Fusion", value: "desde Pro" },
        { label: "Música IA", value: "desde Max" },
        { label: "Búsqueda web", value: "Incluida" },
        { label: "Vídeo IA", value: "desde Max" },
        { label: "Navegador cloud", value: "Incluido" },
      ],
    },

    fusion: {
      eyebrow: "el buque insignia · desde el plan pro",
      h2Lead: "Agentic Fusion:",
      h2Italic: "muchos modelos, una sola interpretación.",
      lede:
        "Ejecuta /fusion y pon un conjunto entero a trabajar en una sola tarea. Los planificadores proponen rutas, tu modelo principal hace el trabajo real con todas las herramientas y a la vista, revisores independientes critican el borrador, y un bucle de veredicto revisa hasta que aprueban. La calidad nace de la síntesis: modelos abiertos baratos se combinan en algo que rivaliza con un modelo frontier, a una fracción del coste.",
      tierPlanners: "1 · planificadores — solo lectura, en paralelo",
      chipAdvisor: "asesor",
      chipMore: "+ hasta 5",
      flowRoutes: "rutas ↓",
      coreLabel: "tu modelo principal",
      coreSub: "todas las herramientas · visible",
      flowDraft: "borrador ↓",
      tierReviewers: "2 · revisores — solo lectura, ven imágenes",
      chipReviewer: "revisor",
      flowVerdict: "↺ revisar · aprobar ↓",
      final: "una respuesta fusionada",
      points: [
        {
          icon: "🛡️",
          title: "Seguro por construcción",
          body:
            "Planificadores y revisores son de solo lectura a nivel de esquema: pueden investigar y criticar, pero nunca tocar tus archivos ni ejecutar comandos.",
        },
        {
          icon: "👁️",
          title: "Trabajo a la vista",
          body:
            "Tu modelo principal trabaja en directo, no en una caja negra. Los revisores incluso tienen visión y ven las imágenes que genera.",
        },
        {
          icon: "✓",
          title: "Revisado antes de llegar a ti",
          body:
            "Un bucle de veredicto revisa el borrador hasta que los revisores aprueban: la respuesta que te llega ya pasó la revisión.",
        },
        {
          icon: "🧩",
          title: "Cualquier combinación de modelos",
          body:
            "Mezcla modelos open-weight, de OpenRouter y gestionados como planificadores, revisores y modelo principal. Elígelos en un selector rápido en cualquier cliente.",
        },
      ],
      ctaResearch: "📊 Leer la investigación →",
      ctaHow: "Cómo funciona Agentic Fusion →",
    },

    music: {
      eyebrow: "generador de música ia · desde el plan max",
      h2Lead: "Un generador de música IA completo,",
      h2Italic: "en la banda.",
      lede:
        "Pídele una canción a Clioloop y la compone: temas completos con voces, con tus letras o las suyas, en cualquier género. Cada generación devuelve dos tomas, y puedes alargar temas, hacer versiones, añadir voces o separar pistas — desde el chat que ya tienes abierto.",
      caps: [
        "Canciones completas con voces — o solo instrumental",
        "Tus letras o letras generadas, en cualquier idioma",
        "Prompts de estilo y género de hasta 1000 caracteres",
        "Alargar, versionar, añadir voces, separar stems",
        "Dos tomas por generación",
        "En todas las superficies — terminal, escritorio, Telegram, WhatsApp…",
      ],
      playerTitle: "Obertura — compuesta por Clioloop",
      playerSub: "Demo generada por IA",
      playerPlay: "Reproducir la demo",
      playerPause: "Pausa",
      note: "La generación de música está incluida desde el plan Max. Cada canción aquí es una generación real, sin editar.",
    },

    autonomy: {
      eyebrow: "el bucle autónomo",
      h2Lead: "No se detiene",
      h2Italic: "hasta cumplir el objetivo.",
      lede:
        "Clioloop es un agente open source que vive en tu terminal, escritorio, navegador y apps de chat. Dale un objetivo y sigue trabajando — planifica, usa herramientas, comprueba su propio progreso — y recuerda lo que aprende de ti.",
      cards: [
        {
          icon: "🎯",
          title: "Objetivos permanentes",
          body:
            "/goal inicia un bucle: tras cada turno, un juez decide si el objetivo está cumplido. Si no, Clioloop da el siguiente paso automáticamente, con un banner de progreso en directo.",
        },
        {
          icon: "🗂️",
          title: "Kanban multiagente",
          body:
            "Divide el trabajo grande en un tablero de tareas. Agentes trabajadores las toman, las ejecutan e informan — visible en el panel y en la app de escritorio.",
        },
        {
          icon: "🧠",
          title: "Memoria y autoaprendizaje",
          body:
            "Una memoria persistente se actualiza sola mientras aprende tus preferencias y proyectos — la próxima sesión ya te conoce.",
        },
        {
          icon: "📚",
          title: "Habilidades",
          body:
            "Carga paquetes de experiencia para la tarea en curso — y deja que el agente mejore sus propias habilidades mientras trabaja.",
        },
        {
          icon: "⏰",
          title: "Ejecuciones programadas",
          body:
            "Pon al agente en un cron: investigaciones recurrentes, informes, comprobaciones — se ejecuta y te envía el resultado.",
        },
        {
          icon: "🔌",
          title: "Herramientas y MCP",
          body: "Edición de archivos, shell, ejecución de código — más cualquier servidor MCP que conectes.",
        },
      ],
      ctaDocs: "Leer docs y tutoriales →",
    },

    tools: {
      eyebrow: "la pasarela de herramientas",
      h2Lead: "Cada instrumento,",
      h2Italic: "una sola suscripción.",
      lede:
        "El portal mide las herramientas alojadas contra tu plan — sin cuentas de proveedores separadas, sin claves API extra.",
      cards: [
        {
          icon: "🔎",
          title: "Búsqueda y extracción web",
          body: "Búsqueda web en vivo, scraping y extracción estructurada para bucles de investigación.",
        },
        { icon: "🎨", title: "Generación de imágenes", body: "Generación de imágenes rápida en hardware dedicado." },
        {
          icon: "🎬",
          title: "Generación de vídeo",
          body: "Texto a vídeo e imagen a vídeo hasta 1080p. Desde el plan Max.",
        },
        {
          icon: "🎙️",
          title: "Texto a voz premium",
          body: "Voces de estudio para lecturas y respuestas de voz.",
        },
        {
          icon: "🌐",
          title: "Navegador cloud",
          body: "Un navegador alojado para logins, formularios y sitios que bloquean bots.",
        },
        {
          icon: "🧾",
          title: "Una sola factura",
          body: "Todo se mide contra tu suscripción — el panel muestra el uso en vivo por mes y por herramienta.",
        },
      ],
    },

    surfaces: {
      eyebrow: "donde tú estés",
      h2Lead: "Un agente,",
      h2Italic: "en cada sala.",
      lede:
        "La misma cuenta, la misma sesión y la misma memoria — del terminal a tus apps de chat. Clioloop es un asistente de IA para Telegram, WhatsApp, Signal, Slack, iMessage y más.",
      cards: [
        {
          icon: "⌨️",
          title: "Terminal y TUI",
          body: "Una interfaz de terminal completa con markdown, resaltado de sintaxis e imágenes en línea.",
        },
        {
          icon: "🖥️",
          title: "App de escritorio",
          body: "Una app nativa con bandeja del sistema, para macOS, Linux y Windows.",
        },
        { icon: "📊", title: "Panel web", body: "Gestiona sesiones, el tablero Kanban y el uso desde el navegador." },
        {
          icon: "💬",
          title: "Tus apps de chat",
          body:
            "Telegram, WhatsApp, Signal, Slack, iMessage, Matrix, Discord, correo, SMS — la pasarela mantiene una sola sesión en todas.",
        },
        { icon: "🧑‍💻", title: "Editores", body: "La integración LSP lleva el agente a VS Code y otros editores." },
        {
          icon: "🔗",
          title: "API de pasarela",
          body: "APIs REST y WebSocket para manejar el agente desde tu propio software.",
        },
      ],
    },

    install: {
      eyebrow: "consigue clioloop",
      h2Lead: "Instala en una línea —",
      h2Italic: "o con un clic.",
      lede: "Clioloop funciona en Linux, macOS y Windows. Totalmente open source — puedes leer cada línea en",
      linuxTitle: "Linux y macOS",
      linuxBody: "Un comando instala la CLI, la TUI y la app de escritorio:",
      linuxAfter: "Luego ejecuta clio setup y elige un modelo.",
      windowsTitle: "Windows",
      windowsBody: "Descarga el instalador y ejecútalo:",
      windowsCta: "⬇ Descargar para Windows",
      windowsPs: "O instala desde PowerShell:",
      windowsWarn:
        "Aviso: el instalador aún no está firmado, así que Windows SmartScreen puede avisar. Es lo esperado — haz clic en Más información → Ejecutar de todas formas. Todo es open source y auditable en GitHub.",
      connectTitle: "Después conecta",
      connectBody:
        "Ejecuta el asistente de configuración y elige Omni Loop Portal para un solo login y 300+ modelos — o trae tus propias claves de proveedor.",
      connectAfter: "Leer la guía de configuración completa →",
    },

    how: {
      eyebrow: "cómo funciona",
      h2Lead: "Conectado en",
      h2Italic: "menos de un minuto.",
      lede: "La configuración rápida es el camino por defecto en todas las superficies de Clioloop.",
      steps: [
        {
          title: "Ejecuta la configuración",
          body: "Instala Clioloop y ejecuta el asistente. «Omni Loop Portal» es la primera opción.",
          code: "clio setup",
        },
        {
          title: "Aprueba en el navegador",
          body:
            "Tu navegador abre este portal con un código de dispositivo (RFC 8628). Inicia sesión, comprueba el código y aprueba.",
          code: "WXYZ-2345 ✓",
        },
        {
          title: "Elige un modelo y a girar",
          body:
            "Elige del catálogo en vivo y empieza. Los tokens rotativos de un solo uso se renuevan solos — nunca tocas una clave.",
          code: "clio",
        },
      ],
    },

    commands: {
      eyebrow: "comandos",
      h2Lead: "Todo lo que hace Clioloop,",
      h2Italic: "desde una CLI.",
      lede:
        "clio a secas inicia un chat interactivo. Añade un subcomando para todo lo demás — o usa comandos slash en plena conversación.",
      col1Title: "Configurar y conectar",
      col1: [
        { cmd: "clio setup", desc: "asistente de primer arranque" },
        { cmd: "clio auth", desc: "iniciar sesión / añadir proveedores" },
        { cmd: "clio model", desc: "elegir modelo y proveedor" },
        { cmd: "clio status", desc: "claves, modelo, salud" },
        { cmd: "clio doctor", desc: "diagnosticar problemas" },
        { cmd: "clio update", desc: "actualizar Clioloop" },
      ],
      col2Title: "Ejecutar y superficies",
      col2: [
        { cmd: "clio", desc: "chat interactivo" },
        { cmd: "clio --tui", desc: "interfaz de terminal completa" },
        { cmd: "clio desktop", desc: "app de escritorio" },
        { cmd: "clio dashboard", desc: "panel web" },
        { cmd: "clio gateway", desc: "Telegram/Slack/WhatsApp…" },
        { cmd: "clio send", desc: "enviar a un canal desde scripts" },
      ],
      col3Title: "Trabajar y automatizar",
      col3: [
        { cmd: "clio kanban", desc: "tablero de tareas multiagente" },
        { cmd: "clio cron", desc: "trabajos programados" },
        { cmd: "clio skills", desc: "gestionar paquetes de habilidades" },
        { cmd: "clio mcp", desc: "conectar servidores MCP" },
        { cmd: "clio memory", desc: "ver/editar la memoria" },
        { cmd: "clio sessions", desc: "gestionar sesiones y perfiles" },
      ],
      slashEyebrow: "en sesión",
      slashTitle: "Comandos slash, en plena conversación",
      slash: [
        { cmd: "/goal", desc: "seguir trabajando hasta que un juez dé el objetivo por cumplido" },
        { cmd: "/music", desc: "generar una canción — voces, letras, cualquier género (Max)" },
        { cmd: "/model", desc: "cambiar de modelo o proveedor sin reiniciar" },
        { cmd: "/kanban", desc: "abrir el tablero de tareas" },
        { cmd: "/skills", desc: "cargar experiencia para la tarea en curso" },
        { cmd: "/fusion", desc: "planificadores + revisores + tu modelo → una respuesta (Pro)" },
        { cmd: "/help", desc: "listar todos los comandos de tu versión" },
      ],
    },

    pricingTeaser: {
      eyebrow: "precios",
      h2Lead: "Cuatro asientos,",
      h2Italic: "la misma sala.",
      lede: "Empieza gratis con un modelo. Sube de plan cuando la orquesta deba crecer.",
      perMonth: "/mes",
      taglines: {
        free: "Prueba Clioloop con un modelo gratuito",
        pro: "300+ modelos, herramientas y Agentic Fusion",
        max: "Añade música y vídeo IA, uso 5×",
        max20x: "Uso 10× para flotas grandes",
      },
      cta: "Ver todos los precios →",
    },

    cta: {
      eyebrow: "∞ empieza el bucle",
      h2Lead: "Dale a tu agente",
      h2Italic: "la orquesta entera.",
      body:
        "Empieza gratis con un modelo, o pasa a Pro para el catálogo completo de 300+ modelos, la pasarela de herramientas y Agentic Fusion. Cancela cuando quieras.",
      pricing: "Ver precios",
      docs: "Explorar las docs",
    },
  },

  pricing: {
    eyebrow: "precios",
    h2Lead: "Un login. Cada modelo.",
    h2Italic: "Agentic Fusion.",
    lede:
      "Todos los planes incluyen la experiencia Clioloop completa: configuración en un clic en CLI, TUI, escritorio y panel, inferencia en streaming, medición de uso y tokens de dispositivo rotativos. Sin claves API — tu suscripción es la credencial. Herramientas alojadas y Agentic Fusion desde Pro; música IA desde Max.",
    perMonth: "/mes",
    flags: { pro: "El más popular", max20x: "Para flotas" },
    startFree: "Empieza gratis",
    choose: "Elegir",
    taglines: {
      free: "Prueba Clioloop con DeepSeek V4 Pro — gratis",
      pro: "300+ modelos de OpenRouter, una suscripción",
      max: "Generación de música y vídeo — uso Pro 5×",
      max20x: "Uso Pro 10× para flotas y enjambres",
    },
    features: {
      free: [
        { text: "1 modelo gratuito para probar" },
        { text: "Sin herramientas alojadas — ni web, imagen, TTS o navegador", kind: "off" },
        { text: "Sin Agentic Fusion (desde Pro)", kind: "off" },
        { text: "1 dispositivo conectado" },
        { text: "Verificación de tarjeta necesaria — nunca se cobra" },
      ],
      pro: [
        { text: "Catálogo completo de 300+ modelos de OpenRouter" },
        { text: "Agentic Fusion — planificadores + revisores fusionan una respuesta", kind: "fusion" },
        { text: "Pasarela de herramientas: búsqueda web y extracción · imágenes · TTS premium · navegador cloud" },
        { text: "Dispositivos ilimitados" },
        { text: "Panel de uso" },
        { text: "Soporte por correo" },
      ],
      max: [
        { text: "300+ modelos frontier — Claude, GPT, Gemini, Grok" },
        { text: "Todo lo de Pro, incl. Agentic Fusion", kind: "fusion" },
        { text: "Generación de música IA — canciones completas con voces y stems", kind: "music" },
        { text: "Generación de vídeo" },
        { text: "Uso mensual 5× Pro" },
        { text: "Bucles largos · enrutado prioritario" },
      ],
      max20x: [
        { text: "Todo lo de Max, incl. música y vídeo", kind: "music" },
        { text: "Uso mensual 10× Pro" },
        { text: "Enjambres de agentes en paralelo" },
        { text: "Máxima prioridad de enrutado" },
        { text: "Canal de soporte directo" },
      ],
    },
    faqTitle: "Preguntas sobre precios",
    faq: [
      {
        q: "¿Por qué Free pide una tarjeta?",
        a: "Una verificación de tarjeta única mantiene a los bots y el abuso fuera del modelo gratuito. En el plan Free nunca se te cobra — la verificación es una autorización de 0 €.",
      },
      {
        q: "¿Cuánto cuesta Agentic Fusion?",
        a: "Fusion está incluido desde Pro sin coste extra. Las llamadas de planificadores y revisores se miden contra tu cuota mensual normal, como cualquier otra inferencia. Ejecuta Fusion en una sesión nueva y reinicia tras la respuesta final para que el siguiente panel no herede contexto viejo.",
      },
      {
        q: "¿Cómo funciona la generación de música IA?",
        a: "En Max y Max 10x, pide una canción en cualquier superficie de Clioloop: temas completos con voces, tus letras o generadas, cualquier género — más alargar, versionar y separar stems. Cada generación devuelve dos tomas y se mide por generación.",
      },
      {
        q: "¿Qué significa «uso»?",
        a: "Cada petición se mide al coste real del modelo upstream. Tu plan incluye una cuota mensual; el panel muestra el consumo en vivo por mes y por modelo.",
      },
      {
        q: "¿Puedo cambiar de plan en cualquier momento?",
        a: "Sí — las subidas se aplican al instante y las bajadas en el siguiente ciclo de facturación, a través del portal de Stripe en tu panel.",
      },
    ],
  },
};
