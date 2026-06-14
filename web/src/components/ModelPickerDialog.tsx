import { Button } from "@clioloop-agent/ui/ui/components/button";
import { Checkbox } from "@clioloop-agent/ui/ui/components/checkbox";
import { ListItem } from "@clioloop-agent/ui/ui/components/list-item";
import { Spinner } from "@clioloop-agent/ui/ui/components/spinner";
import { Input } from "@clioloop-agent/ui/ui/components/input";
import { Label } from "@clioloop-agent/ui/ui/components/label";
import type { GatewayClient } from "@/lib/gatewayClient";
import { Check, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn, themedBody } from "@/lib/utils";
import { fuzzyRank } from "@/lib/fuzzy";

type CheckedState = boolean | "indeterminate";

/**
 * Two-stage model picker modal.
 *
 * Mirrors ui-tui/src/components/modelPicker.tsx:
 *   Stage 1: pick provider (authenticated providers only)
 *   Stage 2: pick model within that provider
 *
 * Two invocation modes:
 *
 * 1. Chat-session mode (ChatSidebar) — pass `gw` + `sessionId`. The picker
 *    loads options via `model.options` JSON-RPC and emits the result as a
 *    slash command string (`/model <model> --provider <slug> [--global]`)
 *    through `onSubmit`, which the ChatPage pipes to `slashExec`.
 *
 * 2. Standalone mode (ModelsPage, Config settings) — pass a `loader` and
 *    `onApply`. The picker fetches options via the REST endpoint and calls
 *    `onApply(provider, model, persistGlobal)` instead of emitting a slash
 *    command.  This lets the Models page reuse the same UI without
 *    requiring an open chat PTY.
 */

interface ModelPricing {
  input: string;
  output: string;
  cache: string | null;
  free: boolean;
}

interface ModelOptionProvider {
  name: string;
  slug: string;
  models?: string[];
  total_models?: number;
  is_current?: boolean;
  warning?: string;
  /** Per-model pricing keyed by model id (present when the picker requested pricing). */
  pricing?: Record<string, ModelPricing>;
  /** managed provider only: whether the current account is on the free tier. */
  free_tier?: boolean;
  /** managed provider only: paid models a free-tier user cannot select (shown disabled). */
  unavailable_models?: string[];
}

/** Free signal shared by every picker: explicit pricing flag, else the `:free` id convention. */
function isFreeModelEntry(provider: ModelOptionProvider | null, modelId: string): boolean {
  return provider?.pricing?.[modelId]?.free ?? modelId.endsWith(":free");
}

interface ModelOptionsResponse {
  model?: string;
  provider?: string;
  providers?: ModelOptionProvider[];
}

interface Props {
  /** Chat-mode: when present, picker emits a slash command via onSubmit. */
  gw?: GatewayClient;
  sessionId?: string;
  onSubmit?(slashCommand: string): void;

  /** Standalone-mode: when present (and onSubmit absent), picker calls onApply. */
  loader?(): Promise<ModelOptionsResponse>;
  onApply?(args: {
    provider: string;
    model: string;
    persistGlobal: boolean;
  }): Promise<void> | void;

  onClose(): void;
  title?: string;
  /** If true, hides "Persist globally" checkbox — always saves to config.yaml. */
  alwaysGlobal?: boolean;
}

export function ModelPickerDialog(props: Props) {
  const {
    gw,
    sessionId,
    onSubmit,
    loader,
    onApply,
    onClose,
    title = "Switch Model",
    alwaysGlobal = false,
  } = props;
  const standalone = !!loader && !!onApply;

  const [providers, setProviders] = useState<ModelOptionProvider[]>([]);
  const [currentModel, setCurrentModel] = useState("");
  const [currentProviderSlug, setCurrentProviderSlug] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSlug, setSelectedSlug] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [query, setQuery] = useState("");
  const [persistGlobal, setPersistGlobal] = useState(alwaysGlobal);
  const [applying, setApplying] = useState(false);
  const closedRef = useRef(false);

  // Load providers + models on open.
  useEffect(() => {
    closedRef.current = false;

    const promise = standalone
      ? (loader as () => Promise<ModelOptionsResponse>)()
      : (gw as GatewayClient).request<ModelOptionsResponse>(
          "model.options",
          sessionId ? { session_id: sessionId } : {},
        );

    promise
      .then((r) => {
        if (closedRef.current) return;
        const next = r?.providers ?? [];
        setProviders(next);
        setCurrentModel(String(r?.model ?? ""));
        setCurrentProviderSlug(String(r?.provider ?? ""));
        setSelectedSlug(
          (next.find((p) => p.is_current) ?? next[0])?.slug ?? "",
        );
        setSelectedModel("");
        setLoading(false);
      })
      .catch((e) => {
        if (closedRef.current) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });

    return () => {
      closedRef.current = true;
    };
    // Deliberately omit props from deps — stable for the dialog's lifetime.
  }, []);

  // Esc closes.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const selectedProvider = useMemo(
    () => providers.find((p) => p.slug === selectedSlug) ?? null,
    [providers, selectedSlug],
  );

  const models = useMemo(
    () => selectedProvider?.models ?? [],
    [selectedProvider],
  );

  const trimmedQuery = query.trim();

  // Fuzzy-ranked providers: match on name + slug + the provider's model ids so
  // typing a model name surfaces its provider (preserves the prior behaviour
  // where a model match also revealed its provider).
  const filteredProviders = useMemo(
    () =>
      fuzzyRank(
        providers,
        trimmedQuery,
        (p) => `${p.name} ${p.slug} ${(p.models ?? []).join(" ")}`,
      ).map((r) => r.item),
    [providers, trimmedQuery],
  );

  // Fuzzy-ranked models carrying the matched character positions so the model
  // list can highlight why each entry matched.
  const filteredModels = useMemo(
    () =>
      fuzzyRank(models, trimmedQuery, (m) => m).map((r) => ({
        model: r.item,
        positions: r.positions,
      })),
    [models, trimmedQuery],
  );

  const canConfirm = !!selectedProvider && !!selectedModel && !applying;

  const confirm = async () => {
    if (!canConfirm || !selectedProvider) return;
    if (standalone && onApply) {
      setApplying(true);
      try {
        await onApply({
          provider: selectedProvider.slug,
          model: selectedModel,
          persistGlobal,
        });
        onClose();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setApplying(false);
      }
    } else if (onSubmit) {
      const global = persistGlobal ? " --global" : "";
      onSubmit(
        `/model ${selectedModel} --provider ${selectedProvider.slug}${global}`,
      );
      onClose();
    }
  };

  // Portal to document.body: the main dashboard column in App.tsx is
  // `relative z-2`, which creates a stacking context that traps fixed
  // descendants below the app sidebar (z-50). Without the portal this
  // modal's z-[100] is scoped to z-2 and the sidebar covers its left
  // edge — visible especially in the Large theme variants where the
  // larger root font widens the dialog into the sidebar's column. See
  // Toast.tsx for the same pattern.
  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-background/85 backdrop-blur-sm p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      role="dialog"
      aria-modal="true"
      aria-labelledby="model-picker-title"
    >
      <div className={cn(themedBody, "relative w-full max-w-3xl max-h-[80vh] border border-border bg-card shadow-2xl flex flex-col")}>
        <Button
          ghost
          size="icon"
          onClick={onClose}
          className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
          aria-label="Close"
        >
          <X />
        </Button>

        <header className="p-5 pb-3 border-b border-border">
          <h2
            id="model-picker-title"
            className="font-mondwest text-display text-base tracking-wider"
          >
            {title}
          </h2>
          <p className="text-xs text-muted-foreground mt-1 font-mono">
            current: {currentModel || "(unknown)"}
            {currentProviderSlug && ` · ${currentProviderSlug}`}
          </p>
        </header>

        <div className="px-5 pt-3 pb-2 border-b border-border">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              autoFocus
              placeholder="Filter providers and models…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-7 h-8 text-sm"
            />
          </div>
        </div>

        <div className="flex-1 min-h-0 grid grid-cols-[200px_1fr] overflow-hidden">
          <ProviderColumn
            loading={loading}
            error={error}
            providers={filteredProviders}
            total={providers.length}
            selectedSlug={selectedSlug}
            query={trimmedQuery}
            onSelect={(slug) => {
              setSelectedSlug(slug);
              setSelectedModel("");
            }}
          />

          <ModelColumn
            provider={selectedProvider}
            models={filteredModels}
            allModels={models}
            selectedModel={selectedModel}
            currentModel={currentModel}
            currentProviderSlug={currentProviderSlug}
            onSelect={setSelectedModel}
            onConfirm={(m) => {
              setSelectedModel(m);
              // Confirm on next tick so state settles.
              window.setTimeout(confirm, 0);
            }}
          />
        </div>

        <footer className="border-t border-border p-3 flex items-center justify-between gap-3 flex-wrap">
          {alwaysGlobal ? (
            <span className="text-xs text-muted-foreground">
              Saves to config.yaml — applies to new sessions.
            </span>
          ) : (
            <div className="flex items-center gap-2">
              <Checkbox
                checked={persistGlobal}
                id="model-picker-persist-global"
                onCheckedChange={(checked: CheckedState) =>
                  setPersistGlobal(checked === true)
                }
              />

              <Label
                className="font-mondwest normal-case tracking-normal text-xs text-muted-foreground cursor-pointer"
                htmlFor="model-picker-persist-global"
              >
                Persist globally (otherwise this session only)
              </Label>
            </div>
          )}

          <div className="flex items-center gap-2 ml-auto">
            <Button outlined onClick={onClose} disabled={applying}>
              Cancel
            </Button>
            <Button onClick={confirm} disabled={!canConfirm}>
              {applying ? <Spinner /> : "Switch"}
            </Button>
          </div>
        </footer>
      </div>
    </div>,
    document.body,
  );
}

/* ------------------------------------------------------------------ */
/*  Provider column                                                    */
/* ------------------------------------------------------------------ */

function ProviderColumn({
  loading,
  error,
  providers,
  total,
  selectedSlug,
  query,
  onSelect,
}: {
  loading: boolean;
  error: string | null;
  providers: ModelOptionProvider[];
  total: number;
  selectedSlug: string;
  query: string;
  onSelect(slug: string): void;
}) {
  return (
    <div className="border-r border-border overflow-y-auto">
      {loading && (
        <div className="flex items-center gap-2 p-4 text-xs text-muted-foreground">
          <Spinner className="text-xs" /> loading…
        </div>
      )}

      {error && <div className="p-4 text-xs text-destructive">{error}</div>}

      {!loading && !error && providers.length === 0 && (
        <div className="p-4 text-xs text-muted-foreground italic">
          {query
            ? "no matches"
            : total === 0
              ? "no authenticated providers"
              : "no matches"}
        </div>
      )}

      {providers.map((p) => {
        const active = p.slug === selectedSlug;
        return (
          <ListItem
            key={p.slug}
            active={active}
            onClick={() => onSelect(p.slug)}
            className={`items-start text-xs border-l-2 ${
              active ? "border-l-primary" : "border-l-transparent"
            }`}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="font-medium truncate">{p.name}</span>
                {p.is_current && <CurrentTag />}
                <TierBadge freeTier={p.free_tier} />
              </div>
              <div className="text-xs text-text-secondary font-mono truncate">
                {p.slug} · {p.total_models ?? p.models?.length ?? 0} models
              </div>
            </div>
          </ListItem>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Model column                                                       */
/* ------------------------------------------------------------------ */

function ModelColumn({
  provider,
  models,
  allModels,
  selectedModel,
  currentModel,
  currentProviderSlug,
  onSelect,
  onConfirm,
}: {
  provider: ModelOptionProvider | null;
  models: { model: string; positions: number[] }[];
  allModels: string[];
  selectedModel: string;
  currentModel: string;
  currentProviderSlug: string;
  onSelect(model: string): void;
  onConfirm(model: string): void;
}) {
  if (!provider) {
    return (
      <div className="overflow-y-auto">
        <div className="p-4 text-xs text-muted-foreground italic">
          pick a provider →
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-y-auto">
      {provider.warning && (
        <div className="p-3 text-xs text-destructive border-b border-border">
          {provider.warning}
        </div>
      )}

      {models.length === 0 ? (
        <div className="p-4 text-xs text-muted-foreground italic">
          {allModels.length
            ? "no models match your filter"
            : "no models listed for this provider"}
        </div>
      ) : (
        (() => {
          const unavailable = new Set(provider.unavailable_models ?? []);
          const freeRows = models.filter((m) => isFreeModelEntry(provider, m.model));
          const paidRows = models.filter((m) => !isFreeModelEntry(provider, m.model));

          const renderRow = ({
            model: m,
            positions,
          }: {
            model: string;
            positions: number[];
          }) => {
            const active = m === selectedModel;
            const isCurrent =
              m === currentModel && provider.slug === currentProviderSlug;
            const locked = unavailable.has(m);

            return (
              <ListItem
                key={m}
                active={active}
                disabled={locked}
                title={locked ? "Upgrade your plan to use this model" : undefined}
                onClick={() => !locked && onSelect(m)}
                onDoubleClick={() => !locked && onConfirm(m)}
                className={cn("px-3 py-1.5 text-xs font-mono", locked && "opacity-45")}
              >
                <Check
                  className={`h-3 w-3 shrink-0 ${active ? "text-primary" : "text-transparent"}`}
                />
                <span className="flex-1 truncate">
                  <HighlightedText text={m} positions={positions} />
                </span>
                {isCurrent && <CurrentTag />}
                <ModelPriceTag price={provider.pricing?.[m]} locked={locked} />
              </ListItem>
            );
          };

          return (
            <>
              {freeRows.length > 0 && (
                <>
                  <SectionHeader label="Free models" />
                  {freeRows.map(renderRow)}
                </>
              )}
              {paidRows.length > 0 && (
                <>
                  <SectionHeader
                    label={provider.free_tier ? "Paid · upgrade to use" : "Paid models"}
                  />
                  {paidRows.map(renderRow)}
                </>
              )}
            </>
          );
        })()
      )}
    </div>
  );
}

/** A dim uppercase section divider inside the model list. */
function SectionHeader({ label }: { label: string }) {
  return (
    <div className="px-3 pt-2 pb-1 text-display text-[0.6rem] uppercase tracking-wider text-muted-foreground">
      {label}
    </div>
  );
}

/** Compact price / FREE / 🔒 Upgrade tag for a model row. */
function ModelPriceTag({
  price,
  locked,
}: {
  price?: ModelPricing;
  locked?: boolean;
}) {
  if (locked) {
    return (
      <span className="shrink-0 text-[0.62rem] uppercase tracking-wide text-muted-foreground">
        🔒 Upgrade
      </span>
    );
  }
  if (!price || (!price.input && !price.output)) return null;
  if (price.free) {
    return (
      <span className="shrink-0 rounded-sm bg-emerald-500/15 px-1 py-0.5 text-[0.62rem] font-semibold uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
        Free
      </span>
    );
  }
  return (
    <span
      className="shrink-0 text-[0.66rem] tabular-nums text-muted-foreground"
      title="Input / Output price per million tokens"
    >
      {price.input || "?"} / {price.output || "?"}
    </span>
  );
}

/** managed-provider account tier chip shown beside the provider name. */
function TierBadge({ freeTier }: { freeTier?: boolean }) {
  if (freeTier === true) {
    return (
      <span className="shrink-0 rounded-sm bg-emerald-500/15 px-1 py-0.5 text-[0.55rem] font-semibold uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
        Free tier
      </span>
    );
  }
  if (freeTier === false) {
    return (
      <span className="shrink-0 rounded-sm bg-primary/15 px-1 py-0.5 text-[0.55rem] font-semibold uppercase tracking-wide text-primary">
        Pro
      </span>
    );
  }
  return null;
}

function CurrentTag() {
  return (
    <span className="text-display text-xs tracking-wider text-primary shrink-0">
      current
    </span>
  );
}

/**
 * Render `text` with the characters at `positions` emphasised, so users can
 * see which characters their fuzzy query matched. Positions are indices into
 * `text`; out-of-range indices are ignored.
 */
function HighlightedText({
  text,
  positions,
}: {
  text: string;
  positions: number[];
}) {
  if (!positions.length) {
    return <>{text}</>;
  }

  const hit = new Set(positions);

  return (
    <>
      {Array.from(text).map((ch, i) =>
        hit.has(i) ? (
          <mark
            key={i}
            className="bg-transparent text-primary font-semibold underline underline-offset-2"
          >
            {ch}
          </mark>
        ) : (
          <span key={i}>{ch}</span>
        ),
      )}
    </>
  );
}
