import type { Dictionary } from "./en";

export const de: Dictionary = {
  meta: {
    landingTitle: "Clioloop — der autonome KI-Assistent mit Agentic Fusion & KI-Musikgenerator",
    landingDescription:
      "Clioloop ist ein selbstlernender KI-Assistent: Agentic Fusion dirigiert 300+ Modelle zu einer Antwort, komponiert komplette Songs mit KI, durchsucht das Web, erstellt Bilder und Videos — ein Login, keine API-Keys.",
    pricingTitle: "Preise — 300+ Modelle, Agentic Fusion und KI-Musik, ein Login",
    pricingDescription:
      "Clioloop-Tarife: kostenlos mit einem Modell starten oder mit Pro 300+ Modelle, das Tool-Gateway und Agentic Fusion freischalten. Max ergänzt KI-Musik- und Videogenerierung mit 5–10-facher Nutzung. Keine API-Keys.",
  },

  chrome: {
    features: "Funktionen",
    music: "Musik",
    pricing: "Preise",
    docs: "Doku",
    dashboard: "Dashboard",
    login: "Anmelden",
    getStarted: "Loslegen",
    footerTagline: "Omni Loop Portal · das Abo-Gateway für",
    languages: "Sprachen",
  },

  landing: {
    hero: {
      badge: "ein login · 300+ modelle · agentic fusion",
      h1Lead: "Jedes Modell.",
      h1Italic: "Ein Orchester.",
      lede:
        "Clioloop ist der autonome KI-Assistent, der 300+ Modelle wie ein Orchester dirigiert: Planer schlagen den Weg vor, dein Modell arbeitet sichtbar, unabhängige Reviewer prüfen — und alles verschmilzt zu einer Antwort, der du vertrauen kannst. Ein Login, keine API-Keys. Er schreibt sogar Songs.",
      ctaWindows: "⬇ Für Windows laden",
      ctaMusic: "♪ Anhören",
      ctaInstall: "Auf Linux / macOS installieren",
      terminalTitle: "clioloop installieren",
      ensembleLabel: "das ensemble",
      ensembleSub: "agentic fusion",
      legendPlanners: "planer",
      legendModel: "dein modell",
      legendReviewers: "reviewer",
      legendFused: "eine antwort",
      strip: [
        { label: "Modelle", value: "300+" },
        { label: "Agentic Fusion", value: "ab Pro" },
        { label: "KI-Musik", value: "ab Max" },
        { label: "Websuche", value: "Inklusive" },
        { label: "Video-Gen.", value: "ab Max" },
        { label: "Cloud-Browser", value: "Inklusive" },
      ],
    },

    fusion: {
      eyebrow: "das flaggschiff · ab pro-tarif",
      h2Lead: "Agentic Fusion —",
      h2Italic: "viele Modelle, eine Aufführung.",
      lede:
        "Starte /fusion und setze ein ganzes Ensemble auf eine Aufgabe an. Planer schlagen Wege vor, dein Hauptmodell erledigt die echte Arbeit mit allen Tools und sichtbar, unabhängige Reviewer kritisieren den Entwurf, und eine Urteilsschleife überarbeitet, bis sie zustimmen. Die Qualität entsteht durch die Synthese — günstige offene Modelle verbinden sich zu etwas, das mit einem Frontier-Modell mithält, zu einem Bruchteil der Kosten.",
      tierPlanners: "1 · planer — nur lesend, parallel",
      chipAdvisor: "berater",
      chipMore: "+ bis zu 5",
      flowRoutes: "wege ↓",
      coreLabel: "dein hauptmodell",
      coreSub: "volle tools · sichtbar",
      flowDraft: "entwurf ↓",
      tierReviewers: "2 · reviewer — nur lesend, sehen bilder",
      chipReviewer: "reviewer",
      flowVerdict: "↺ überarbeiten · freigeben ↓",
      final: "eine fusionierte antwort",
      points: [
        {
          icon: "🛡️",
          title: "Sicher per Konstruktion",
          body:
            "Planer und Reviewer sind auf Schema-Ebene nur lesend — sie können recherchieren und kritisieren, aber nie deine Dateien anfassen oder Befehle ausführen.",
        },
        {
          icon: "👁️",
          title: "Arbeit zum Zusehen",
          body:
            "Dein Hauptmodell arbeitet live, nicht in einer Blackbox. Reviewer haben sogar Vision und sehen die erzeugten Bilder.",
        },
        {
          icon: "✓",
          title: "Geprüft, bevor du es siehst",
          body:
            "Eine Urteilsschleife überarbeitet den Entwurf, bis die Reviewer zustimmen — die Antwort, die dich erreicht, hat die Prüfung schon bestanden.",
        },
        {
          icon: "🧩",
          title: "Jede Modell-Kombination",
          body:
            "Kombiniere Open-Weight-, OpenRouter- und verwaltete Modelle als Planer, Reviewer und Hauptmodell. Auswahl per Schnellwahl in jedem Client.",
        },
      ],
      ctaResearch: "📊 Forschung lesen →",
      ctaHow: "So funktioniert Agentic Fusion →",
    },

    music: {
      eyebrow: "ki-musikgenerator · ab max-tarif",
      h2Lead: "Ein kompletter KI-Musikgenerator,",
      h2Italic: "in der Band.",
      lede:
        "Bitte Clioloop um einen Song und er komponiert ihn: komplette Tracks mit Gesang, deinen oder generierten Texten, in jedem Genre. Jede Generierung liefert zwei Versionen, und du kannst Tracks verlängern, covern, Gesang hinzufügen oder Stems trennen — direkt aus dem Chat, den du ohnehin offen hast.",
      caps: [
        "Komplette Songs mit Gesang — oder rein instrumental",
        "Deine Texte oder generierte Texte, in jeder Sprache",
        "Stil- und Genre-Prompts bis 1000 Zeichen",
        "Verlängern, Covern, Gesang hinzufügen, Stems trennen",
        "Zwei Versionen pro Generierung",
        "In jeder Oberfläche — Terminal, Desktop, Telegram, WhatsApp…",
      ],
      playerTitle: "Ouvertüre — komponiert von Clioloop",
      playerSub: "KI-generierter Demo-Track",
      playerPlay: "Demo abspielen",
      playerPause: "Pause",
      note: "Musikgenerierung ist ab dem Max-Tarif enthalten. Jeder Song hier ist eine echte, unbearbeitete Generierung.",
    },

    autonomy: {
      eyebrow: "die autonome schleife",
      h2Lead: "Er hört nicht auf,",
      h2Italic: "bis das Ziel erreicht ist.",
      lede:
        "Clioloop ist ein Open-Source-Agent in deinem Terminal, auf dem Desktop, im Browser und in deinen Chat-Apps. Gib ihm ein Ziel und er arbeitet weiter — plant, nutzt Tools, prüft den eigenen Fortschritt — und merkt sich, was er über dich lernt.",
      cards: [
        {
          icon: "🎯",
          title: "Stehende Ziele",
          body:
            "/goal startet eine Schleife: Nach jedem Zug entscheidet ein Richter, ob das Ziel erreicht ist. Wenn nicht, macht Clioloop automatisch den nächsten Schritt — mit Live-Fortschrittsanzeige.",
        },
        {
          icon: "🗂️",
          title: "Multi-Agent-Kanban",
          body:
            "Zerlege große Arbeit in ein Aufgaben-Board. Worker-Agenten übernehmen Aufgaben, führen sie aus und berichten — sichtbar im Dashboard und in der Desktop-App.",
        },
        {
          icon: "🧠",
          title: "Gedächtnis & Selbstlernen",
          body:
            "Ein persistentes Gedächtnis aktualisiert sich automatisch, während er deine Vorlieben und Projekte lernt — die nächste Sitzung kennt dich schon.",
        },
        {
          icon: "📚",
          title: "Skills",
          body:
            "Lade Expertise-Pakete für die anstehende Aufgabe — und lass den Agenten seine eigenen Skills beim Arbeiten verbessern.",
        },
        {
          icon: "⏰",
          title: "Geplante Läufe",
          body:
            "Setze den Agenten auf einen Cron: wiederkehrende Recherchen, Berichte, Checks — er läuft und schickt dir das Ergebnis.",
        },
        {
          icon: "🔌",
          title: "Tools & MCP",
          body: "Dateien bearbeiten, Shell, Code-Ausführung — plus jeder MCP-Server, den du verbindest.",
        },
      ],
      ctaDocs: "Doku & Tutorials lesen →",
    },

    tools: {
      eyebrow: "das tool-gateway",
      h2Lead: "Jedes Instrument,",
      h2Italic: "ein Abo.",
      lede:
        "Das Portal rechnet gehostete Tools über deinen Tarif ab — keine separaten Anbieter-Konten, keine zusätzlichen API-Keys.",
      cards: [
        {
          icon: "🔎",
          title: "Websuche & Extraktion",
          body: "Live-Websuche, Scraping und strukturierte Extraktion für Recherche-Schleifen.",
        },
        { icon: "🎨", title: "Bildgenerierung", body: "Schnelle Bildgenerierung auf dedizierter Hardware." },
        {
          icon: "🎬",
          title: "Videogenerierung",
          body: "Text-zu-Video und Bild-zu-Video bis 1080p. Ab Max-Tarif.",
        },
        {
          icon: "🎙️",
          title: "Premium Text-to-Speech",
          body: "Studio-Stimmen für Vorlesen und Sprachantworten.",
        },
        {
          icon: "🌐",
          title: "Cloud-Browser",
          body: "Ein gehosteter Browser für Logins, Formulare und Seiten, die Bots blockieren.",
        },
        {
          icon: "🧾",
          title: "Eine Rechnung",
          body:
            "Alles wird über dein Abo abgerechnet — das Dashboard zeigt die Nutzung live pro Monat und pro Tool.",
        },
      ],
    },

    surfaces: {
      eyebrow: "überall, wo du bist",
      h2Lead: "Ein Agent,",
      h2Italic: "in jedem Raum.",
      lede:
        "Dasselbe Konto, dieselbe Sitzung, dasselbe Gedächtnis — vom Terminal bis in deine Chat-Apps. Clioloop ist ein KI-Assistent für Telegram, WhatsApp, Signal, Slack, iMessage und mehr.",
      cards: [
        {
          icon: "⌨️",
          title: "Terminal & TUI",
          body: "Eine vollwertige Terminal-Oberfläche mit Markdown, Syntax-Highlighting und Inline-Bildern.",
        },
        {
          icon: "🖥️",
          title: "Desktop-App",
          body: "Eine native Desktop-App mit System-Tray, für macOS, Linux und Windows.",
        },
        {
          icon: "📊",
          title: "Web-Dashboard",
          body: "Sitzungen, Kanban-Board und Nutzung im Browser verwalten.",
        },
        {
          icon: "💬",
          title: "Deine Chat-Apps",
          body:
            "Telegram, WhatsApp, Signal, Slack, iMessage, Matrix, Discord, E-Mail, SMS — das Gateway hält eine Sitzung über alle hinweg.",
        },
        { icon: "🧑‍💻", title: "Editoren", body: "LSP-Integration bringt den Agenten in VS Code und andere Editoren." },
        {
          icon: "🔗",
          title: "Gateway-API",
          body: "REST- und WebSocket-APIs, um den Agenten aus eigener Software zu steuern.",
        },
      ],
    },

    install: {
      eyebrow: "clioloop holen",
      h2Lead: "In einer Zeile installieren —",
      h2Italic: "oder mit einem Klick.",
      lede: "Clioloop läuft auf Linux, macOS und Windows. Vollständig Open Source — jede Zeile lesbar auf",
      linuxTitle: "Linux & macOS",
      linuxBody: "Ein Befehl installiert CLI, TUI und Desktop-App:",
      linuxAfter: "Danach clio setup ausführen und ein Modell wählen.",
      windowsTitle: "Windows",
      windowsBody: "Installer herunterladen und ausführen:",
      windowsCta: "⬇ Für Windows laden",
      windowsPs: "Oder per PowerShell installieren:",
      windowsWarn:
        "Hinweis: Der Installer ist noch nicht signiert, daher kann Windows SmartScreen warnen. Das ist erwartbar — klicke Weitere Informationen → Trotzdem ausführen. Alles ist Open Source und auf GitHub prüfbar.",
      connectTitle: "Dann verbinden",
      connectBody:
        "Starte den Einrichtungsassistenten und wähle Omni Loop Portal für ein Login und 300+ Modelle — oder bring eigene Provider-Keys mit.",
      connectAfter: "Zur vollständigen Einrichtungsanleitung →",
    },

    how: {
      eyebrow: "so funktioniert's",
      h2Lead: "Verbunden in",
      h2Italic: "unter einer Minute.",
      lede: "Die Schnelleinrichtung ist der Standardweg in jeder Clioloop-Oberfläche.",
      steps: [
        {
          title: "Setup starten",
          body: 'Clioloop installieren und den Assistenten starten. "Omni Loop Portal" ist die erste Option.',
          code: "clio setup",
        },
        {
          title: "Im Browser bestätigen",
          body:
            "Dein Browser öffnet dieses Portal mit einem Gerätecode (RFC 8628). Anmelden, Code prüfen, bestätigen.",
          code: "WXYZ-2345 ✓",
        },
        {
          title: "Modell wählen & loslegen",
          body:
            "Aus dem Live-Katalog wählen und starten. Rotierende Einmal-Tokens erneuern sich automatisch — du fasst nie einen Key an.",
          code: "clio",
        },
      ],
    },

    commands: {
      eyebrow: "befehle",
      h2Lead: "Alles, was Clioloop kann,",
      h2Italic: "aus einer CLI.",
      lede:
        "clio allein startet einen interaktiven Chat. Für alles andere gibt es Unterbefehle — oder Slash-Befehle mitten im Gespräch.",
      col1Title: "Einrichten & verbinden",
      col1: [
        { cmd: "clio setup", desc: "Erst-Einrichtung" },
        { cmd: "clio auth", desc: "anmelden / Provider hinzufügen" },
        { cmd: "clio model", desc: "Modell & Provider wählen" },
        { cmd: "clio status", desc: "Keys, Modell, Gesundheit" },
        { cmd: "clio doctor", desc: "Probleme diagnostizieren" },
        { cmd: "clio update", desc: "Clioloop aktualisieren" },
      ],
      col2Title: "Ausführen & Oberflächen",
      col2: [
        { cmd: "clio", desc: "interaktiver Chat" },
        { cmd: "clio --tui", desc: "volle Terminal-UI" },
        { cmd: "clio desktop", desc: "Desktop-App" },
        { cmd: "clio dashboard", desc: "Web-Dashboard" },
        { cmd: "clio gateway", desc: "Telegram/Slack/WhatsApp…" },
        { cmd: "clio send", desc: "Kanal aus Skripten benachrichtigen" },
      ],
      col3Title: "Arbeiten & automatisieren",
      col3: [
        { cmd: "clio kanban", desc: "Multi-Agent-Aufgabenboard" },
        { cmd: "clio cron", desc: "geplante Jobs" },
        { cmd: "clio skills", desc: "Skill-Pakete verwalten" },
        { cmd: "clio mcp", desc: "MCP-Server verbinden" },
        { cmd: "clio memory", desc: "Gedächtnis ansehen/bearbeiten" },
        { cmd: "clio sessions", desc: "Sitzungen & Profile verwalten" },
      ],
      slashEyebrow: "in der sitzung",
      slashTitle: "Slash-Befehle, mitten im Gespräch",
      slash: [
        { cmd: "/goal", desc: "weiterarbeiten, bis ein Ziel als erreicht gilt" },
        { cmd: "/music", desc: "einen Song generieren — Gesang, Texte, jedes Genre (Max)" },
        { cmd: "/model", desc: "Modell oder Provider ohne Neustart wechseln" },
        { cmd: "/kanban", desc: "das Aufgabenboard öffnen" },
        { cmd: "/skills", desc: "Expertise für die Aufgabe laden" },
        { cmd: "/fusion", desc: "Planer + Reviewer + dein Modell → eine Antwort (Pro)" },
        { cmd: "/help", desc: "alle Befehle deiner Version auflisten" },
      ],
    },

    pricingTeaser: {
      eyebrow: "preise",
      h2Lead: "Vier Plätze,",
      h2Italic: "derselbe Saal.",
      lede: "Kostenlos mit einem Modell starten. Upgraden, wenn das Orchester wachsen soll.",
      perMonth: "/Monat",
      taglines: {
        free: "Clioloop mit einem freien Modell testen",
        pro: "300+ Modelle, Tools und Agentic Fusion",
        max: "Plus KI-Musik & Video, 5-fache Nutzung",
        max20x: "10-fache Nutzung für große Flotten",
      },
      cta: "Alle Preise ansehen →",
    },

    cta: {
      eyebrow: "∞ jetzt loslegen",
      h2Lead: "Gib deinem Agenten",
      h2Italic: "das ganze Orchester.",
      body:
        "Kostenlos mit einem Modell starten oder mit Pro den vollen 300+-Katalog, das Tool-Gateway und Agentic Fusion freischalten. Jederzeit kündbar.",
      pricing: "Preise ansehen",
      docs: "Doku durchstöbern",
    },
  },

  pricing: {
    eyebrow: "preise",
    h2Lead: "Ein Login. Jedes Modell.",
    h2Italic: "Agentic Fusion.",
    lede:
      "Jeder Tarif enthält das volle Clioloop-Erlebnis: Ein-Klick-Einrichtung auf CLI, TUI, Desktop und Dashboard, Streaming-Inferenz, Nutzungsmessung und rotierende Geräte-Tokens. Keine API-Keys — dein Abo ist der Zugang. Gehostete Tools und Agentic Fusion ab Pro; KI-Musikgenerierung ab Max.",
    perMonth: "/Monat",
    flags: { pro: "Am beliebtesten", max20x: "Für Flotten" },
    startFree: "Kostenlos starten",
    choose: "Wähle",
    taglines: {
      free: "Clioloop mit GLM 5.2 testen — kostenlos",
      pro: "300+ OpenRouter-Modelle, ein Abo",
      max: "Musik- & Videogenerierung — 5-fache Pro-Nutzung",
      max20x: "10-fache Pro-Nutzung für Flotten und Schwärme",
    },
    features: {
      free: [
        { text: "1 freies Modell zum Testen" },
        { text: "Keine gehosteten Tools — kein Web, Bild, TTS oder Browser", kind: "off" },
        { text: "Kein Agentic Fusion (ab Pro)", kind: "off" },
        { text: "1 verbundenes Gerät" },
        { text: "Kartenverifizierung nötig — nie belastet" },
      ],
      pro: [
        { text: "Voller Katalog mit 300+ OpenRouter-Modellen" },
        { text: "Agentic Fusion — Planer + Reviewer fusionieren eine Antwort", kind: "fusion" },
        { text: "Tool-Gateway: Websuche & Extraktion · Bild-Gen. · Premium-TTS · Cloud-Browser" },
        { text: "Unbegrenzte Geräte" },
        { text: "Nutzungs-Dashboard" },
        { text: "E-Mail-Support" },
      ],
      max: [
        { text: "300+ Frontier-Modelle — Claude, GPT, Gemini, Grok" },
        { text: "Alles aus Pro, inkl. Agentic Fusion", kind: "fusion" },
        { text: "KI-Musikgenerierung — komplette Songs mit Gesang & Stems", kind: "music" },
        { text: "Videogenerierung" },
        { text: "5-fache Pro-Monatsnutzung" },
        { text: "Langläufer-Schleifen · bevorzugtes Routing" },
      ],
      max20x: [
        { text: "Alles aus Max, inkl. Musik- & Videogenerierung", kind: "music" },
        { text: "10-fache Pro-Monatsnutzung" },
        { text: "Parallele Agenten-Schwärme" },
        { text: "Höchste Routing-Priorität" },
        { text: "Direkter Support-Kanal" },
      ],
    },
    faqTitle: "Fragen zu den Preisen",
    faq: [
      {
        q: "Warum braucht Free eine Karte?",
        a: "Eine einmalige Kartenverifizierung hält Bots und Missbrauch vom freien Modell fern. Auf dem Free-Tarif wird nie abgebucht — die Verifizierung ist eine 0-€-Autorisierung.",
      },
      {
        q: "Was kostet Agentic Fusion?",
        a: "Fusion ist ab Pro ohne Aufpreis enthalten. Die Planer- und Reviewer-Aufrufe werden wie jede andere Inferenz auf dein normales Monatskontingent angerechnet. Starte Fusion in einer frischen Sitzung und setze nach der finalen Antwort zurück, damit das nächste Panel sauberen Kontext bekommt.",
      },
      {
        q: "Wie funktioniert die KI-Musikgenerierung?",
        a: "Auf Max und Max 10x bittest du in jeder Clioloop-Oberfläche um einen Song: komplette Tracks mit Gesang, deinen oder generierten Texten, jedes Genre — plus Verlängern, Covern und Stems. Jede Generierung liefert zwei Versionen und wird pro Generierung abgerechnet.",
      },
      {
        q: "Was bedeutet „Nutzung“?",
        a: "Jede Anfrage wird zu den echten Kosten des Upstream-Modells gemessen. Dein Tarif enthält ein Monatskontingent; das Dashboard zeigt den Verbrauch live pro Monat und Modell.",
      },
      {
        q: "Kann ich den Tarif jederzeit wechseln?",
        a: "Ja — Upgrades gelten sofort, Downgrades zum nächsten Abrechnungszyklus, alles über das Stripe-Portal in deinem Dashboard.",
      },
    ],
  },
};
