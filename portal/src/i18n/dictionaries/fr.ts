import type { Dictionary } from "./en";

export const fr: Dictionary = {
  meta: {
    landingTitle: "Clioloop — l'assistant IA autonome avec Agentic Fusion et générateur de musique IA",
    landingDescription:
      "Clioloop est un assistant IA auto-améliorant : Agentic Fusion dirige plus de 300 modèles vers une seule réponse, compose des chansons complètes par IA, cherche sur le web, crée images et vidéos — une seule connexion, aucune clé API.",
    pricingTitle: "Tarifs — 300+ modèles, Agentic Fusion et musique IA, une seule connexion",
    pricingDescription:
      "Les offres Clioloop : commencez gratuitement avec un modèle, ou passez à Pro pour 300+ modèles, la passerelle d'outils et Agentic Fusion. Max ajoute la génération de musique et de vidéo IA avec 5 à 10× d'usage. Aucune clé API.",
  },

  chrome: {
    features: "Fonctions",
    music: "Musique",
    pricing: "Tarifs",
    docs: "Docs",
    dashboard: "Tableau de bord",
    login: "Connexion",
    getStarted: "Commencer",
    footerTagline: "Omni Loop Portal · la passerelle d'abonnement pour",
    languages: "Langues",
  },

  landing: {
    hero: {
      badge: "une connexion · 300+ modèles · agentic fusion",
      h1Lead: "Chaque modèle.",
      h1Italic: "Un orchestre.",
      lede:
        "Clioloop est l'assistant IA autonome qui dirige plus de 300 modèles comme un orchestre : des planificateurs proposent la route, votre modèle joue à découvert, des relecteurs indépendants critiquent — et tout fusionne en une réponse digne de confiance. Une connexion, aucune clé API. Il écrit même des chansons.",
      ctaWindows: "⬇ Télécharger pour Windows",
      ctaMusic: "♪ Écouter",
      ctaInstall: "Installer sur Linux / macOS",
      terminalTitle: "installer clioloop",
      ensembleLabel: "l'ensemble",
      ensembleSub: "agentic fusion",
      legendPlanners: "planificateurs",
      legendModel: "votre modèle",
      legendReviewers: "relecteurs",
      legendFused: "une réponse",
      strip: [
        { label: "Modèles", value: "300+" },
        { label: "Agentic Fusion", value: "dès Pro" },
        { label: "Musique IA", value: "dès Max" },
        { label: "Recherche web", value: "Incluse" },
        { label: "Vidéo IA", value: "dès Max" },
        { label: "Navigateur cloud", value: "Inclus" },
      ],
    },

    fusion: {
      eyebrow: "le fleuron · dès l'offre pro",
      h2Lead: "Agentic Fusion —",
      h2Italic: "plusieurs modèles, une seule interprétation.",
      lede:
        "Lancez /fusion et mettez tout un ensemble sur une seule tâche. Les planificateurs proposent des routes, votre modèle principal fait le vrai travail, avec tous les outils et à découvert, des relecteurs indépendants critiquent le brouillon, et une boucle de verdict révise jusqu'à leur accord. La qualité vient de la synthèse — des modèles ouverts bon marché se combinent en quelque chose qui rivalise avec un modèle frontier, pour une fraction du coût.",
      tierPlanners: "1 · planificateurs — lecture seule, en parallèle",
      chipAdvisor: "conseiller",
      chipMore: "+ jusqu'à 5",
      flowRoutes: "routes ↓",
      coreLabel: "votre modèle principal",
      coreSub: "tous les outils · visible",
      flowDraft: "brouillon ↓",
      tierReviewers: "2 · relecteurs — lecture seule, voient les images",
      chipReviewer: "relecteur",
      flowVerdict: "↺ réviser · approuver ↓",
      final: "une réponse fusionnée",
      points: [
        {
          icon: "🛡️",
          title: "Sûr par construction",
          body:
            "Planificateurs et relecteurs sont en lecture seule au niveau du schéma — ils peuvent chercher et critiquer, mais jamais toucher vos fichiers ni exécuter de commandes.",
        },
        {
          icon: "👁️",
          title: "Un travail visible",
          body:
            "Votre modèle principal travaille en direct, pas dans une boîte noire. Les relecteurs ont même la vision et voient les images générées.",
        },
        {
          icon: "✓",
          title: "Relu avant d'arriver",
          body:
            "Une boucle de verdict révise le brouillon jusqu'à l'approbation — la réponse qui vous parvient a déjà passé la relecture.",
        },
        {
          icon: "🧩",
          title: "Toute combinaison de modèles",
          body:
            "Mélangez modèles open-weight, OpenRouter et gérés comme planificateurs, relecteurs et modèle principal. Choisissez-les en un instant dans n'importe quel client.",
        },
      ],
      ctaResearch: "📊 Lire la recherche →",
      ctaHow: "Comment fonctionne Agentic Fusion →",
    },

    music: {
      eyebrow: "générateur de musique ia · dès l'offre max",
      h2Lead: "Un vrai générateur de musique IA,",
      h2Italic: "dans le groupe.",
      lede:
        "Demandez une chanson à Clioloop et il la compose : des titres complets avec voix, vos paroles ou les siennes, dans tous les genres. Chaque génération produit deux prises, et vous pouvez prolonger, reprendre, ajouter des voix ou séparer les pistes — depuis le chat déjà ouvert.",
      caps: [
        "Chansons complètes avec voix — ou instrumental pur",
        "Vos paroles ou des paroles générées, dans toutes les langues",
        "Prompts de style et de genre jusqu'à 1000 caractères",
        "Prolonger, reprendre, ajouter des voix, séparer les stems",
        "Deux prises par génération",
        "Sur toutes les surfaces — terminal, desktop, Telegram, WhatsApp…",
      ],
      playerTitle: "Ouverture — composée par Clioloop",
      playerSub: "Démo générée par IA",
      playerPlay: "Écouter la démo",
      playerPause: "Pause",
      note: "La génération de musique est incluse dès l'offre Max. Chaque morceau ici est une vraie génération, sans retouche.",
    },

    autonomy: {
      eyebrow: "la boucle autonome",
      h2Lead: "Il ne s'arrête pas",
      h2Italic: "avant d'avoir atteint l'objectif.",
      lede:
        "Clioloop est un agent open source qui vit dans votre terminal, sur le bureau, dans le navigateur et vos applis de discussion. Donnez-lui un objectif et il continue — planifier, utiliser des outils, vérifier sa progression — en retenant ce qu'il apprend de vous.",
      cards: [
        {
          icon: "🎯",
          title: "Objectifs permanents",
          body:
            "/goal lance une boucle : après chaque tour, un juge décide si l'objectif est atteint. Sinon, Clioloop enchaîne automatiquement, avec une bannière de progression en direct.",
        },
        {
          icon: "🗂️",
          title: "Kanban multi-agents",
          body:
            "Découpez les gros chantiers en tableau de tâches. Des agents ouvriers les prennent, les exécutent et rendent compte — visibles dans le tableau de bord et l'app de bureau.",
        },
        {
          icon: "🧠",
          title: "Mémoire & auto-apprentissage",
          body:
            "Une mémoire persistante se met à jour automatiquement à mesure qu'il apprend vos préférences et projets — la session suivante vous connaît déjà.",
        },
        {
          icon: "📚",
          title: "Compétences",
          body:
            "Chargez des packs d'expertise pour la tâche en cours — et laissez l'agent améliorer ses propres compétences en travaillant.",
        },
        {
          icon: "⏰",
          title: "Exécutions planifiées",
          body:
            "Mettez l'agent sur un cron : recherches récurrentes, rapports, vérifications — il tourne et vous envoie le résultat.",
        },
        {
          icon: "🔌",
          title: "Outils & MCP",
          body: "Édition de fichiers, shell, exécution de code — plus tout serveur MCP que vous connectez.",
        },
      ],
      ctaDocs: "Lire les docs & tutoriels →",
    },

    tools: {
      eyebrow: "la passerelle d'outils",
      h2Lead: "Chaque instrument,",
      h2Italic: "un seul abonnement.",
      lede:
        "Le portail mesure les outils hébergés sur votre offre — pas de comptes fournisseurs séparés, pas de clés API supplémentaires.",
      cards: [
        {
          icon: "🔎",
          title: "Recherche & extraction web",
          body: "Recherche web en direct, scraping et extraction structurée pour les boucles de recherche.",
        },
        { icon: "🎨", title: "Génération d'images", body: "Génération d'images rapide sur du matériel dédié." },
        {
          icon: "🎬",
          title: "Génération de vidéo",
          body: "Texte-vers-vidéo et image-vers-vidéo jusqu'à 1080p. Dès l'offre Max.",
        },
        {
          icon: "🎙️",
          title: "Synthèse vocale premium",
          body: "Des voix de studio pour la lecture à voix haute et les réponses vocales.",
        },
        {
          icon: "🌐",
          title: "Navigateur cloud",
          body: "Un navigateur hébergé pour les connexions, formulaires et sites qui bloquent les robots.",
        },
        {
          icon: "🧾",
          title: "Une seule facture",
          body:
            "Tout est mesuré sur votre abonnement — le tableau de bord montre l'usage en direct par mois et par outil.",
        },
      ],
    },

    surfaces: {
      eyebrow: "partout où vous êtes",
      h2Lead: "Un agent,",
      h2Italic: "dans chaque pièce.",
      lede:
        "Le même compte, la même session, la même mémoire — du terminal à vos applis de discussion. Clioloop est un assistant IA pour Telegram, WhatsApp, Signal, Slack, iMessage et plus.",
      cards: [
        {
          icon: "⌨️",
          title: "Terminal & TUI",
          body: "Une interface terminal complète avec markdown, coloration syntaxique et images en ligne.",
        },
        {
          icon: "🖥️",
          title: "App de bureau",
          body: "Une app native avec icône de barre système, pour macOS, Linux et Windows.",
        },
        {
          icon: "📊",
          title: "Tableau de bord web",
          body: "Gérez sessions, tableau Kanban et usage depuis le navigateur.",
        },
        {
          icon: "💬",
          title: "Vos applis de chat",
          body:
            "Telegram, WhatsApp, Signal, Slack, iMessage, Matrix, Discord, e-mail, SMS — la passerelle garde une seule session partout.",
        },
        { icon: "🧑‍💻", title: "Éditeurs", body: "L'intégration LSP amène l'agent dans VS Code et d'autres éditeurs." },
        {
          icon: "🔗",
          title: "API passerelle",
          body: "Des API REST et WebSocket pour piloter l'agent depuis vos propres logiciels.",
        },
      ],
    },

    install: {
      eyebrow: "obtenir clioloop",
      h2Lead: "Installez en une ligne —",
      h2Italic: "ou en un clic.",
      lede: "Clioloop tourne sur Linux, macOS et Windows. Entièrement open source — chaque ligne est lisible sur",
      linuxTitle: "Linux & macOS",
      linuxBody: "Une commande installe la CLI, la TUI et l'app de bureau :",
      linuxAfter: "Puis lancez clio setup et choisissez un modèle.",
      windowsTitle: "Windows",
      windowsBody: "Téléchargez l'installateur et lancez-le :",
      windowsCta: "⬇ Télécharger pour Windows",
      windowsPs: "Ou installez depuis PowerShell :",
      windowsWarn:
        "À savoir : l'installateur n'est pas encore signé, Windows SmartScreen peut donc avertir. C'est attendu — cliquez Informations complémentaires → Exécuter quand même. Tout est open source et vérifiable sur GitHub.",
      connectTitle: "Puis connectez",
      connectBody:
        "Lancez l'assistant de configuration et choisissez Omni Loop Portal pour une connexion et 300+ modèles — ou apportez vos propres clés fournisseur.",
      connectAfter: "Lire le guide de configuration complet →",
    },

    how: {
      eyebrow: "comment ça marche",
      h2Lead: "Connecté en",
      h2Italic: "moins d'une minute.",
      lede: "La configuration rapide est le chemin par défaut sur toutes les surfaces Clioloop.",
      steps: [
        {
          title: "Lancez la configuration",
          body: "Installez Clioloop et lancez l'assistant. « Omni Loop Portal » est la première option.",
          code: "clio setup",
        },
        {
          title: "Approuvez dans le navigateur",
          body:
            "Votre navigateur ouvre ce portail avec un code d'appareil (RFC 8628). Connectez-vous, vérifiez le code, approuvez.",
          code: "WXYZ-2345 ✓",
        },
        {
          title: "Choisissez un modèle & bouclez",
          body:
            "Choisissez dans le catalogue en direct et démarrez. Les jetons rotatifs à usage unique se renouvellent seuls — vous ne touchez jamais une clé.",
          code: "clio",
        },
      ],
    },

    commands: {
      eyebrow: "commandes",
      h2Lead: "Tout ce que fait Clioloop,",
      h2Italic: "depuis une CLI.",
      lede:
        "clio seul lance un chat interactif. Ajoutez une sous-commande pour tout le reste — ou des commandes slash en pleine conversation.",
      col1Title: "Configurer & connecter",
      col1: [
        { cmd: "clio setup", desc: "assistant de premier lancement" },
        { cmd: "clio auth", desc: "connexion / ajout de fournisseurs" },
        { cmd: "clio model", desc: "choisir modèle & fournisseur" },
        { cmd: "clio status", desc: "clés, modèle, santé" },
        { cmd: "clio doctor", desc: "diagnostiquer les problèmes" },
        { cmd: "clio update", desc: "mettre à jour Clioloop" },
      ],
      col2Title: "Exécuter & surfaces",
      col2: [
        { cmd: "clio", desc: "chat interactif" },
        { cmd: "clio --tui", desc: "interface terminal complète" },
        { cmd: "clio desktop", desc: "app de bureau" },
        { cmd: "clio dashboard", desc: "tableau de bord web" },
        { cmd: "clio gateway", desc: "Telegram/Slack/WhatsApp…" },
        { cmd: "clio send", desc: "écrire à un canal depuis un script" },
      ],
      col3Title: "Travailler & automatiser",
      col3: [
        { cmd: "clio kanban", desc: "tableau de tâches multi-agents" },
        { cmd: "clio cron", desc: "tâches planifiées" },
        { cmd: "clio skills", desc: "gérer les packs de compétences" },
        { cmd: "clio mcp", desc: "connecter des serveurs MCP" },
        { cmd: "clio memory", desc: "voir/éditer la mémoire" },
        { cmd: "clio sessions", desc: "gérer sessions & profils" },
      ],
      slashEyebrow: "en session",
      slashTitle: "Commandes slash, en pleine conversation",
      slash: [
        { cmd: "/goal", desc: "travailler jusqu'à ce qu'un objectif soit jugé atteint" },
        { cmd: "/music", desc: "générer une chanson — voix, paroles, tout genre (Max)" },
        { cmd: "/model", desc: "changer de modèle ou de fournisseur sans redémarrer" },
        { cmd: "/kanban", desc: "ouvrir le tableau de tâches" },
        { cmd: "/skills", desc: "charger l'expertise pour la tâche en cours" },
        { cmd: "/fusion", desc: "planificateurs + relecteurs + votre modèle → une réponse (Pro)" },
        { cmd: "/help", desc: "lister toutes les commandes de votre version" },
      ],
    },

    pricingTeaser: {
      eyebrow: "tarifs",
      h2Lead: "Quatre places,",
      h2Italic: "même salle.",
      lede: "Commencez gratuitement avec un modèle. Passez au niveau supérieur quand l'orchestre doit grandir.",
      perMonth: "/mois",
      taglines: {
        free: "Essayez Clioloop avec un modèle gratuit",
        pro: "300+ modèles, outils et Agentic Fusion",
        max: "Ajoute musique & vidéo IA, usage 5×",
        max20x: "Usage 10× pour les grandes flottes",
      },
      cta: "Voir tous les tarifs →",
    },

    cta: {
      eyebrow: "∞ lancez la boucle",
      h2Lead: "Donnez à votre agent",
      h2Italic: "l'orchestre entier.",
      body:
        "Commencez gratuitement avec un modèle, ou passez à Pro pour le catalogue complet de 300+ modèles, la passerelle d'outils et Agentic Fusion. Annulable à tout moment.",
      pricing: "Voir les tarifs",
      docs: "Parcourir les docs",
    },
  },

  pricing: {
    eyebrow: "tarifs",
    h2Lead: "Une connexion. Chaque modèle.",
    h2Italic: "Agentic Fusion.",
    lede:
      "Chaque offre inclut l'expérience Clioloop complète : configuration en un clic sur CLI, TUI, bureau et tableau de bord, inférence en streaming, mesure d'usage et jetons d'appareil rotatifs. Aucune clé API — votre abonnement est l'identifiant. Outils hébergés et Agentic Fusion dès Pro ; musique IA dès Max.",
    perMonth: "/mois",
    flags: { pro: "Le plus populaire", max20x: "Pour les flottes" },
    startFree: "Commencer gratuitement",
    choose: "Choisir",
    taglines: {
      free: "Essayez Clioloop avec GLM 5.2 — gratuit",
      pro: "300+ modèles OpenRouter, un abonnement",
      max: "Génération musique & vidéo — usage Pro 5×",
      max20x: "Usage Pro 10× pour flottes et essaims",
    },
    features: {
      free: [
        { text: "1 modèle gratuit pour essayer" },
        { text: "Pas d'outils hébergés — ni web, image, TTS ou navigateur", kind: "off" },
        { text: "Pas d'Agentic Fusion (dès Pro)", kind: "off" },
        { text: "1 appareil connecté" },
        { text: "Vérification de carte requise — jamais débitée" },
      ],
      pro: [
        { text: "Catalogue complet de 300+ modèles OpenRouter" },
        { text: "Agentic Fusion — planificateurs + relecteurs fusionnent une réponse", kind: "fusion" },
        { text: "Passerelle d'outils : recherche web & extraction · images · TTS premium · navigateur cloud" },
        { text: "Appareils illimités" },
        { text: "Tableau de bord d'usage" },
        { text: "Support par e-mail" },
      ],
      max: [
        { text: "300+ modèles frontier — Claude, GPT, Gemini, Grok" },
        { text: "Tout Pro, y compris Agentic Fusion", kind: "fusion" },
        { text: "Génération de musique IA — chansons complètes avec voix & stems", kind: "music" },
        { text: "Génération de vidéo" },
        { text: "Usage mensuel Pro 5×" },
        { text: "Boucles longues · routage prioritaire" },
      ],
      max20x: [
        { text: "Tout Max, y compris musique & vidéo", kind: "music" },
        { text: "Usage mensuel Pro 10×" },
        { text: "Essaims d'agents parallèles" },
        { text: "Priorité de routage maximale" },
        { text: "Canal de support direct" },
      ],
    },
    faqTitle: "Questions sur les tarifs",
    faq: [
      {
        q: "Pourquoi Free demande-t-il une carte ?",
        a: "Une vérification de carte unique tient les robots et les abus à l'écart du modèle gratuit. Vous n'êtes jamais débité sur l'offre Free — la vérification est une autorisation à 0 €.",
      },
      {
        q: "Combien coûte Agentic Fusion ?",
        a: "Fusion est inclus dès Pro sans supplément. Les appels des planificateurs et relecteurs sont mesurés sur votre quota mensuel normal, comme toute autre inférence. Lancez Fusion dans une session neuve, puis réinitialisez après la réponse finale pour que le panel suivant reparte d'un contexte propre.",
      },
      {
        q: "Comment fonctionne la génération de musique IA ?",
        a: "Sur Max et Max 10x, demandez une chanson sur n'importe quelle surface Clioloop : titres complets avec voix, vos paroles ou générées, tout genre — plus prolongation, reprise et séparation de stems. Chaque génération produit deux prises et est mesurée à la génération.",
      },
      {
        q: "Que signifie « usage » ?",
        a: "Chaque requête est mesurée au coût réel du modèle amont. Votre offre inclut un quota mensuel ; le tableau de bord montre la consommation en direct par mois et par modèle.",
      },
      {
        q: "Puis-je changer d'offre à tout moment ?",
        a: "Oui — les upgrades s'appliquent immédiatement et les downgrades au cycle de facturation suivant, via le portail Stripe de votre tableau de bord.",
      },
    ],
  },
};
