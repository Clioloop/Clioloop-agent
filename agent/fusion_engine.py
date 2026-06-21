"""Omni Loop Portal Fusion — the `/fusion` command thin client.

Fusion surrounds a normal foreground turn with a server-side panel: planner
models propose routes, the current chat model does the visible full-tool work,
reviewer models critique the draft, then a judge/synthesizer pass fuses one final
answer. **The panel runs server-side on the Omni Loop Portal** — the prompts and
pipeline are not shipped to user machines. This module is a thin client: it owns
only the session config, the local gating pre-check, UI helpers, and the loop
that drives the portal's ``/api/v1/fusion`` start/step protocol, executing the
full-tool work / revise / finalize turns on the local agent (where the file/tool
side effects belong).

Gating: Fusion is a Pro-plan (and up) capability available only when the agent is
connected to the managed Omni Loop Portal provider. See ``fusion_gate_check``.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Plan ids (portal/src/lib/plans.ts) that unlock the Max tier.
MAX_PLAN_IDS = {"max", "max20x"}
# Plans entitled to Model Fusion (Pro and up). The portal enforces this too.
FUSION_PLAN_IDS = {"pro", "max", "max20x"}

# Shown after a full Fusion run finishes. Keep this shared so Telegram,
# desktop, TUI, and classic CLI all use exactly the same reset guidance.
FUSION_RESET_SESSION_NOTICE = (
    "🔮 Fusion run complete. Start a fresh session before your next Fusion run "
    "(/new or /reset) so advisors and reviewers get a clean context and do not "
    "waste usage."
)

# Upper bound on how many planner (advisor) and reviewer models a user may pick.
FUSION_MAX_MODELS_PER_GROUP = 5

# Toolset hints retained for the picker/UI and back-compat with callers that
# import these names. The actual advisor/reviewer execution now happens
# server-side, so these are informational on the client.
FUSION_ADVISOR_TOOLSETS = ["web", "search", "file"]
FUSION_ADVISOR_TOOL_NAMES = frozenset({"read_file", "web_search"})
FUSION_REVIEWER_TOOLSETS = ["web", "search", "file", "vision"]
FUSION_REVIEWER_TOOL_NAMES = frozenset({"read_file", "web_search", "vision_analyze"})

# Hard cap on local turns the start/step loop will execute (work + one rework
# round = 2; the bound just prevents a misbehaving server from looping forever).
_MAX_LOCAL_TURNS = 6

# How long to wait on the portal fusion endpoints (the work draft runs locally;
# these timeouts cover only the server-side panel calls). The server bounds each
# advisor/reviewer/judge sub-call individually, so the panel completes well
# inside this window; the generous overall ceiling (and its headroom over the
# server's own maxDuration) lets the server return its graceful degraded result
# on a slow run instead of the client aborting and silently dropping the
# reviewers/judge — the failure mode this replaces.
_FUSION_HTTP_TIMEOUT = 600.0
_FUSION_CONNECT_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# Config (session-scoped, held on the agent)
# ---------------------------------------------------------------------------

@dataclass
class FusionEvent:
    """A structured Fusion progress event.

    Lets every surface (Telegram/desktop/TUI/CLI) drive a proper reviewer bubble
    rather than a single opaque status line. ``__str__`` returns ``text`` so any
    caller that still treats progress as a plain string keeps working.

    ``phase`` is one of: ``planning``, ``working``, ``reviewing``, ``critique``,
    ``approved``, ``revising``, ``finalizing`` (plus ``judge``/``gate``/
    ``fallback``). ``detail`` carries the reviewers' notes; ``round`` is the
    review round so a surface can key one bubble per round.
    """

    phase: str
    text: str
    detail: str = ""
    round: int = 0
    kind: str = "fusion"
    run_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:  # graceful fallback for string-only callbacks
        return self.text


@dataclass
class FusionConfig:
    """The models chosen via ``/fusion`` plus the on/off toggle.

    ``advisors`` (1..5 planners) handle the first prompt and plan the task;
    ``reviewers`` (1..5) critique the draft. ``judge`` and ``synthesizer`` are
    optional model overrides for the v2 judge/synthesis stages; empty values use
    the current main chat model.
    """

    advisors: List[str] = field(default_factory=list)
    reviewers: List[str] = field(default_factory=list)
    judge: str = ""
    synthesizer: str = ""
    enabled: bool = False
    version: int = 2
    mode: str = "auto"  # auto | fast | full
    gate: bool = True
    legacy_revision_loop: bool = False
    max_total_tokens: int = 200_000

    def is_complete(self) -> bool:
        return bool(self.advisors and self.reviewers)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> "FusionConfig":
        if not isinstance(data, dict):
            return cls()
        advisors = data.get("advisors")
        reviewers = data.get("reviewers")
        # Back-compat: a legacy {model_1, model_2, judge} config used the same
        # two models for planning and review.
        if advisors is None and reviewers is None and (
            data.get("model_1") or data.get("model_2")
        ):
            legacy = [m for m in (data.get("model_1"), data.get("model_2")) if m]
            advisors = list(legacy)
            reviewers = list(legacy)
        return cls(
            advisors=[str(m) for m in (advisors or []) if m],
            reviewers=[str(m) for m in (reviewers or []) if m],
            judge=str(data.get("judge") or data.get("judge_model") or ""),
            synthesizer=str(data.get("synthesizer") or data.get("synthesizer_model") or ""),
            enabled=bool(data.get("enabled")),
            version=int(data.get("version") or 2),
            mode=str(data.get("mode") or "auto"),
            gate=bool(data.get("gate", True)),
            legacy_revision_loop=bool(data.get("legacy_revision_loop", False)),
            max_total_tokens=int(data.get("max_total_tokens") or 200_000),
        )


def get_fusion_config(agent: Any) -> FusionConfig:
    """Return the agent's FusionConfig, creating an empty one on first use."""
    cfg = getattr(agent, "_fusion_config", None)
    if not isinstance(cfg, FusionConfig):
        try:
            from clio_cli.config import load_config

            cfg = FusionConfig.from_dict((load_config().get("fusion") or {}))
        except Exception:
            cfg = FusionConfig()
        try:
            agent._fusion_config = cfg
        except Exception:
            pass
    return cfg


def set_fusion_config(agent: Any, config: FusionConfig) -> None:
    agent._fusion_config = config


def clear_fusion_config(agent: Any) -> None:
    agent._fusion_config = FusionConfig()


def parse_fusion_args(tokens: List[str]) -> Optional[FusionConfig]:
    """Parse the explicit ``/fusion …`` text form into an enabled FusionConfig.

    Two syntaxes are accepted:
      * extended (any order): ``advisors=a,b,c reviewers=d,e``
        (``planners=`` is accepted as an alias; ``judge=``/``main=`` and
        ``synthesizer=``/``synthesizer_model=`` can override the v2 judge and
        final writer).
      * legacy: ``m1 m2 judge`` — three bare tokens map to advisors=[m1,m2],
        reviewers=[m1,m2], judge.
    Each group is clamped to ``FUSION_MAX_MODELS_PER_GROUP``. Returns ``None``
    when the tokens don't form a complete config (caller then opens the picker).
    """
    if not tokens:
        return None

    mode = "auto"
    if tokens and tokens[0].lower() in {"auto", "fast", "full"}:
        mode = tokens[0].lower()
        tokens = tokens[1:]
        if not tokens:
            return None

    def _clamp(models: List[str]) -> List[str]:
        return models[:FUSION_MAX_MODELS_PER_GROUP]

    if any("=" in t for t in tokens):
        kv: Dict[str, str] = {}
        for t in tokens:
            if "=" in t:
                key, val = t.split("=", 1)
                kv[key.strip().lower()] = val.strip()

        def _split(val: str) -> List[str]:
            return _clamp([m.strip() for m in val.split(",") if m.strip()])

        advisors = _split(kv.get("advisors") or kv.get("planners") or "")
        reviewers = _split(kv.get("reviewers") or "")
        judge = kv.get("judge") or kv.get("judge_model") or kv.get("main") or ""
        synthesizer = kv.get("synthesizer") or kv.get("synthesizer_model") or ""
        max_total_tokens = 200_000
        try:
            max_total_tokens = int(kv.get("max_total_tokens") or max_total_tokens)
        except Exception:
            max_total_tokens = 200_000
        cfg = FusionConfig(
            advisors=advisors, reviewers=reviewers, judge=judge,
            synthesizer=synthesizer, enabled=True, mode=mode,
            max_total_tokens=max_total_tokens,
        )
        return cfg if cfg.is_complete() else None

    if len(tokens) >= 3:
        m1, m2, judge = tokens[0], tokens[1], tokens[2]
        return FusionConfig(
            advisors=[m1, m2], reviewers=[m1, m2], judge=judge,
            enabled=True, mode=mode,
        )
    return None


def fusion_is_active(agent: Any) -> bool:
    """True when the agent has a complete, enabled fusion configuration."""
    cfg = getattr(agent, "_fusion_config", None)
    return bool(isinstance(cfg, FusionConfig) and cfg.enabled and cfg.is_complete())


def main_model_is_managed(agent: Any = None) -> bool:
    """True when the current main model runs on the managed Omni Loop subscription.

    Fusion is only available in this case: the whole pipeline — the server-side
    advisor/reviewer/judge panel *and* the local main-model work/finalize turns —
    must run through the portal so every call is metered at OpenRouter cost. When
    the chat model is from another provider (e.g. a directly-configured Ollama
    Cloud or OpenRouter key), the main-model turns bypass the portal and cannot
    be metered, so fusion must stay off and only a normal chat turn may run.

    The check uses the *runtime* provider (the one actually used for inference),
    not the auth-store active provider — those can diverge (a managed login in
    ``auth.json`` while ``config.yaml`` pins ``model.provider`` to a direct
    provider), which is exactly the gap this guards. When an ``agent`` is given,
    its live ``provider`` is authoritative; otherwise the runtime provider is
    resolved from config (for the ``/fusion`` enable check, before a turn runs).
    """
    prov = (getattr(agent, "provider", "") or "").strip().lower() if agent is not None else ""
    if not prov:
        try:
            from clio_cli.runtime_provider import resolve_runtime_provider
            prov = str((resolve_runtime_provider() or {}).get("provider") or "").strip().lower()
        except Exception:
            prov = ""
    return prov == "managed"


# Shown when a user tries to enable fusion while their main model is from a
# provider other than the managed Omni Loop subscription.
FUSION_NEEDS_MANAGED_NOTICE = (
    "🔮 Fusion needs an Omni Loop Portal model. If you've set one with /model in "
    "Telegram, ask Clio to configure the current model as the main model in the "
    "config, then restart the gateway with /restart."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# The one managed model that is free for every tier (mirrors
# portal/src/lib/model-policy.ts::FREE_OPENROUTER_MODEL). It is a paid model
# whose cost Clioloop absorbs, NOT an OpenRouter ":free" variant — so the
# ``:free`` suffix check does NOT catch it; the explicit constant match does.
FREE_MANAGED_MODEL = "z-ai/glm-5.2"


def _model_is_free(model_id: str, pricing: dict | None) -> bool:
    """Return True when *model_id* is a free managed model.

    Mirrors the portal + ``clio_cli.models._is_model_free`` rules: the one free
    model, any ``:free`` OpenRouter variant, or anything priced 0/0. The id-based
    checks work without a pricing dict; ``pricing`` (when supplied) catches ``$0``
    models that don't advertise ``:free``.
    """
    mid = (model_id or "").strip()
    if not mid:
        return False
    if mid == FREE_MANAGED_MODEL or mid.endswith(":free"):
        return True
    if pricing:
        p = pricing.get(mid)
        if p:
            try:
                return float(p.get("prompt", "1")) == 0 and float(p.get("completion", "1")) == 0
            except (TypeError, ValueError):
                return False
    return False


def model_open_tag(model_id: str, pricing: dict | None = None) -> str:
    """Tag a managed model id as free / open-weight / OpenRouter-routed.

    OpenRouter ids are always ``vendor/model``; open (BYO Ollama Cloud) ids are
    bare. ``free`` takes priority (a ``:free`` OpenRouter model is ``(free)``, not
    ``(openrouter)``). Returns ``"(free)"`` / ``"(open)"`` / ``"(openrouter)"``
    (empty string for a blank id).
    """
    mid = (model_id or "").strip()
    if not mid:
        return ""
    if _model_is_free(mid, pricing):
        return "(free)"
    return "(openrouter)" if "/" in mid else "(open)"


def label_model(model_id: str, pricing: dict | None = None) -> str:
    """Human label: ``id (free)`` / ``id (open)`` / ``id (openrouter)`` for pickers + notices."""
    tag = model_open_tag(model_id, pricing)
    return f"{model_id} {tag}".strip()


# Cap the tool summary so a large toolset cannot blow up the work prompt.
_TOOL_SUMMARY_MAX_TOOLS = 60


def _summarize_agent_tools(agent: Any) -> str:
    """Compact bullet list of the main agent's tools (name + one-line blurb).

    Built from ``agent.tools`` (OpenAI-style ``{"function": {...}}`` dicts), this
    is the toolkit the full-tool work/revise turns inherit. It is sent to the
    server so the panel can plan a route the main agent can actually execute, and
    is injected into the worker prompt. Returns ``""`` when no tools are exposed.
    """
    tools = getattr(agent, "tools", None) or []
    lines: List[str] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function") or {}
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        desc = str(fn.get("description") or "").strip()
        # Keep only the first sentence/line so the summary stays compact.
        first_line = desc.splitlines()[0].strip() if desc else ""
        if len(first_line) > 160:
            first_line = first_line[:157].rstrip() + "…"
        lines.append(f"- {name}: {first_line}" if first_line else f"- {name}")
        if len(lines) >= _TOOL_SUMMARY_MAX_TOOLS:
            lines.append("- … (additional tools available)")
            break
    return "\n".join(lines)


def fusion_gate_check(force_fresh: bool = False) -> Tuple[bool, str]:
    """Return ``(allowed, reason)``.

    Allowed only when the active provider is the managed Omni Loop Portal Subscription AND
    the account is on a Pro plan or higher (``pro`` / ``max`` / ``max20x``).
    ``reason`` is a user-facing message explaining how to qualify when not allowed.
    """
    # 1) Must be on the managed provider.
    try:
        from clio_cli.auth import resolve_provider
        provider = resolve_provider()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("fusion gate: provider resolve failed: %s", exc)
        provider = None
    if provider != "managed":
        return False, (
            "🔮 Fusion runs through the Omni Loop Portal Subscription. Connect "
            "it as your inference provider first:  clio setup --portal"
        )

    # 2) Must be logged in + on a Pro plan or higher.
    try:
        from clio_cli.portal_account import get_managed_provider_account_info
        info = get_managed_provider_account_info(force_fresh=force_fresh)
    except Exception as exc:
        logger.debug("fusion gate: account info failed: %s", exc)
        return False, (
            "🔮 Couldn't reach the Omni Loop Portal Subscription to verify "
            "your plan — check your connection and try again."
        )

    if not getattr(info, "logged_in", False):
        return False, (
            "🔮 Fusion needs an Omni Loop Portal Subscription login:  clio setup --portal"
        )

    raw = getattr(info, "raw", None) or {}
    plan = str(raw.get("plan") or "").lower()
    if plan not in FUSION_PLAN_IDS:
        portal = str(raw.get("portal_url") or "").rstrip("/")
        if not portal:
            try:
                from clio_cli.auth import DEFAULT_MANAGED_PORTAL_URL
                portal = str(DEFAULT_MANAGED_PORTAL_URL).rstrip("/")
            except Exception:
                portal = "https://portal.clioloop.com"
        plan_name = str(raw.get("plan_name") or plan or "Free")
        return False, (
            f"🔮 Fusion is a Pro-plan feature — your Omni Loop Portal Subscription "
            f"account is on the {plan_name} plan. Upgrade at {portal}/pricing"
        )

    return True, ""


def _join_models(models: List[str]) -> str:
    """Human list of model labels, e.g. ``a (open)  +  b (open)``."""
    return "  +  ".join(label_model(m) for m in models) if models else "(none)"


def activation_notice(config: FusionConfig) -> str:
    """The message shown to the user when fusion mode turns on."""
    mode = (config.mode or "auto").lower()
    return (
        "🔮 *Fusion mode is on.*\n"
        f"• Planners ({len(config.advisors)}): {_join_models(config.advisors)}\n"
        f"• Reviewers ({len(config.reviewers)}): {_join_models(config.reviewers)}\n"
        "• Main model: your current chat model (`/model` changes it)\n"
        f"• Fusion v{config.version} mode: {mode}\n"
        "Planners propose routes and reviewers critique the draft on the Omni "
        "Loop Portal; your current main model does the full-tool work here; then "
        "a judge/synthesizer pass merges consensus, contradictions, and gaps into "
        "one final answer. Turn it off any time with  /fusion off"
    )


def status_notice(agent: Any) -> str:
    """A `/fusion status` summary."""
    cfg = get_fusion_config(agent)
    if not cfg.is_complete():
        return "🔮 Fusion is not configured. Run  /fusion  to pick your models."
    state = "ON" if cfg.enabled else "off"
    return (
        f"🔮 Fusion is *{state}*.\n"
        f"• Planners ({len(cfg.advisors)}): {_join_models(cfg.advisors)}\n"
        f"• Reviewers ({len(cfg.reviewers)}): {_join_models(cfg.reviewers)}\n"
        "• Main model: your current chat model (`/model` changes it)\n"
        f"• Fusion v{cfg.version} mode: {(cfg.mode or 'auto').lower()}"
    )


def _hide_tools(agent: Any, tool_names: set[str]) -> Tuple[Any, Any]:
    """Temporarily remove named tools from an agent. Returns original state."""
    original_tools = getattr(agent, "tools", None)
    original_valid = getattr(agent, "valid_tool_names", None)
    try:
        if original_tools is not None:
            agent.tools = [
                tool for tool in original_tools
                if (tool.get("function") or {}).get("name") not in tool_names
            ]
        if original_valid is not None:
            agent.valid_tool_names = set(original_valid) - set(tool_names)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("fusion: failed to hide tools %s: %s", sorted(tool_names), exc)
    return original_tools, original_valid


def _restore_tools(agent: Any, original_tools: Any, original_valid: Any) -> None:
    with contextlib.suppress(Exception):
        if original_tools is not None:
            agent.tools = original_tools
    with contextlib.suppress(Exception):
        if original_valid is not None:
            agent.valid_tool_names = original_valid


# ---------------------------------------------------------------------------
# Portal connection helpers
# ---------------------------------------------------------------------------

def _managed_access_token(force_refresh: bool = False) -> Optional[str]:
    """The managed-provider OAuth access token used to authenticate fusion calls."""
    if force_refresh:
        try:
            from clio_cli.auth import resolve_managed_access_token

            token = resolve_managed_access_token(refresh_skew_seconds=3600)
            if token:
                return str(token).strip()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("fusion: forced access token refresh failed: %s", exc)
    try:
        from tools.managed_tool_gateway import read_managed_access_token
        return read_managed_access_token()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("fusion: access token read failed: %s", exc)
        return None


def _portal_base_url() -> str:
    """Resolve the Omni Loop Portal base URL (env → auth store → default)."""
    base = (
        os.getenv("CLIO_PORTAL_BASE_URL", "").strip()
        or os.getenv("MANAGED_PORTAL_BASE_URL", "").strip()
    )
    if not base:
        try:
            from tools.managed_tool_gateway import _read_managed_provider_state
            state = _read_managed_provider_state() or {}
            base = str(state.get("portal_base_url") or "").strip()
        except Exception:
            base = ""
    if not base:
        try:
            from clio_cli.auth import DEFAULT_MANAGED_PORTAL_URL
            base = str(DEFAULT_MANAGED_PORTAL_URL)
        except Exception:
            base = "https://portal.clioloop.com"
    return base.rstrip("/")


def _error_message(response: Any, default: str) -> str:
    """Pull a human message out of a portal error envelope."""
    try:
        body = response.json()
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if isinstance(err, str) and err:
            return err
    except Exception:
        pass
    return default


# ---------------------------------------------------------------------------
# Tool-trace extraction (sent to the portal so reviewers/judge can see what
# the main agent actually did — searches, scrapes, reads, commands — not just
# the final draft text. Pure utility: no Fusion prompts or pipeline logic.)
# ---------------------------------------------------------------------------

_TOOL_TRACE_MAX_CHARS = 4000


def _compact_args(tool_name: str, args_json: str) -> str:
    """Extract the most relevant args for each tool, compact form."""
    import json as _json

    try:
        args = _json.loads(args_json) if args_json else {}
    except Exception:
        return (args_json or "")[:200]
    if not isinstance(args, dict):
        return str(args)[:200]

    if tool_name == "web_search":
        return f'query="{str(args.get("query", ""))[:120]}", limit={args.get("limit", "")}'
    if tool_name == "web_extract":
        urls = args.get("urls", [])
        urls_str = ", ".join(str(u) for u in urls[:3])
        if len(urls) > 3:
            urls_str += f", …({len(urls) - 3} more)"
        return f"urls=[{urls_str}]"
    if tool_name == "terminal":
        return f'command="{str(args.get("command", ""))[:150]}"'
    if tool_name in ("read_file", "write_file"):
        path = str(args.get("path", ""))[:100]
        if tool_name == "write_file":
            content_len = len(str(args.get("content", "")))
            return f'path="{path}", content={content_len} chars'
        return f'path="{path}"'
    if tool_name == "browser_navigate":
        return f'url="{str(args.get("url", ""))[:150]}"'
    if tool_name == "browser_click":
        return f'ref="{str(args.get("ref", ""))[:60]}"'
    if tool_name == "browser_type":
        ref = str(args.get("ref", ""))[:60]
        text_len = len(str(args.get("text", "")))
        return f'ref="{ref}", text={text_len} chars'
    if tool_name == "search_files":
        return f'pattern="{str(args.get("pattern", ""))[:80]}", target={args.get("target", "")}'

    # Generic: show all keys, truncate values.
    parts: List[str] = []
    for k, v in args.items():
        v_str = str(v)
        if len(v_str) > 100:
            v_str = v_str[:97] + "…"
        parts.append(f"{k}={v_str}")
        if len(parts) >= 5:
            break
    return ", ".join(parts)


def _compact_result(tool_name: str, content: str) -> str:
    """Summarize a tool result to ~500 chars."""
    if not content:
        return "(empty)"
    content = content.strip()
    if len(content) <= 500:
        return content
    # Web search results: keep URL list visible.
    if tool_name == "web_search":
        return f"{len(content)} chars: " + content[:400] + "…"
    # Web extract: summarize what was extracted.
    if tool_name == "web_extract":
        return f"{len(content)} chars of extracted content: " + content[:350] + "…"
    # Terminal: keep first/last to see both command and result.
    if tool_name == "terminal":
        return f"{len(content)} chars: " + content[:200] + "…(middle omitted)…" + content[-200:]
    # Generic.
    return f"{len(content)} chars: " + content[:200] + "…(middle omitted)…" + content[-200:]


def _extract_tool_trace(messages: Any) -> str:
    """Build a compact trace of tool calls + results from a conversation's
    messages list, for the Fusion reviewers/judge to see what the agent did.

    Returns a string like::

        === TOOL WORK TRACE (main agent) ===
        1. web_search(query="weather forecast Varna…", limit=5)
           → 5 results: accuweather.com/…, weather-forecast.com/…, …
        2. web_extract(urls=[https://accuweather.com/…, …])
           → 14,958 chars of extracted content: …
        === END TOOL WORK TRACE ===

    Capped at ``_TOOL_TRACE_MAX_CHARS``.
    """
    if not isinstance(messages, list):
        return ""
    steps: List[str] = []
    step_num = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "")
        if role == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                if not isinstance(tc, dict):
                    continue
                step_num += 1
                fn = tc.get("function") or {}
                name = str(fn.get("name") or "?")
                args_raw = str(fn.get("arguments") or "")
                args_str = _compact_args(name, args_raw)
                steps.append(f"{step_num}. {name}({args_str})")
        elif role == "tool":
            content = str(msg.get("content", ""))
            name = str(msg.get("name", ""))
            result_summary = _compact_result(name, content)
            if steps:
                steps[-1] += f"\n   → {result_summary}"
    if not steps:
        return ""
    trace = "=== TOOL WORK TRACE (main agent) ===\n" + "\n".join(steps)
    trace += "\n=== END TOOL WORK TRACE ==="
    if len(trace) > _TOOL_TRACE_MAX_CHARS:
        trace = trace[: _TOOL_TRACE_MAX_CHARS - 50] + "\n…(truncated)=== END TOOL WORK TRACE ==="
    return trace


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_fusion_turn(
    agent: Any,
    user_message: str,
    config: Optional[FusionConfig] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    task_id: Optional[str] = None,
    stream_callback: Optional[Callable] = None,
    persist_user_message: Optional[str] = None,
    progress: Optional[Callable[["FusionEvent"], None]] = None,
    work_stream_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Run one fused turn via the Omni Loop Portal's server-side Fusion engine.

    Returns a ``run_conversation``-shaped dict (the final turn result), so callers
    can treat a fused turn exactly like a normal turn. The portal runs the
    advisor/reviewer/judge/synthesizer panel; the full-tool work/revise/finalize
    turns run on this local agent (where file/tool side effects belong). Falls
    back to a plain ``run_conversation`` whenever fusion isn't viable.
    """
    cfg = config or get_fusion_config(agent)

    def _emit(phase: str, text: str, **kwargs: Any) -> None:
        if progress is not None:
            with contextlib.suppress(Exception):
                progress(FusionEvent(phase=phase, text=text, **kwargs))

    def _normal_turn() -> Dict[str, Any]:
        return agent.run_conversation(
            user_message,
            conversation_history=conversation_history,
            task_id=task_id,
            stream_callback=stream_callback,
            persist_user_message=persist_user_message,
        )

    # Misconfigured, or the message isn't plain text (e.g. a multimodal
    # content-parts list) — the panel prompts assume a text request.
    if not (isinstance(cfg, FusionConfig) and cfg.is_complete()) \
            or not isinstance(user_message, str):
        return _normal_turn()

    # The main model must run on the managed Omni Loop subscription, otherwise
    # the main-model work/finalize turns bypass the portal and can't be metered.
    # If the current chat model is from another provider, fusion is unavailable —
    # silently run a normal chat turn (no per-turn notice; the /fusion command
    # already explains this when the user tries to enable it on a foreign model).
    if not main_model_is_managed(agent):
        return _normal_turn()

    allowed, reason = fusion_gate_check(force_fresh=False)
    if not allowed:
        return {
            "final_response": reason,
            "messages": list(conversation_history or []),
            "api_calls": 0,
            "completed": False,
            "failed": True,
            "error": reason,
        }

    # Cheap local auto-gate: obvious tiny messages skip the panel entirely (the
    # server mirrors this by resolving auto→full once the call arrives).
    mode = (cfg.mode or "auto").lower()
    if mode == "auto" and cfg.gate:
        words = re.findall(r"\w+", user_message)
        if len(words) <= 5 and not re.search(
            r"\b(fix|build|implement|debug|review|plan|code|test)\b", user_message, re.I
        ):
            _emit("gate", "🔮 Fusion: simple request — answering directly…", data={"decision": "skip"})
            return _normal_turn()

    base = _portal_base_url()
    if not base:
        _emit("fallback", "🔮 Fusion: not connected to the Omni Loop Portal — answering directly…")
        return _normal_turn()

    try:
        import httpx
    except Exception:
        logger.debug("fusion: httpx unavailable; answering directly")
        return _normal_turn()

    def _forward(events: Any) -> None:
        if not progress or not isinstance(events, list):
            return
        for evt in events:
            if not isinstance(evt, dict):
                continue
            with contextlib.suppress(Exception):
                progress(FusionEvent(
                    phase=str(evt.get("phase") or ""),
                    text=str(evt.get("text") or ""),
                    detail=str(evt.get("detail") or ""),
                    round=int(evt.get("round") or 0),
                    kind=str(evt.get("kind") or "fusion"),
                    run_id=str(evt.get("run_id") or ""),
                    data=evt.get("data") if isinstance(evt.get("data"), dict) else {},
                ))

    def _run_local_turn(message: str, *, internal: bool, sc: Optional[Callable]) -> Dict[str, Any]:
        if internal:
            return agent.run_conversation(
                message,
                conversation_history=conversation_history,
                internal_turn=True,
                stream_callback=sc,
            )
        return agent.run_conversation(
            message,
            conversation_history=conversation_history,
            task_id=task_id,
            stream_callback=sc,
            persist_user_message=persist_user_message or user_message,
        )

    def _portal_headers(force_refresh: bool = False) -> Optional[Dict[str, str]]:
        token = _managed_access_token(force_refresh=force_refresh)
        if not token:
            return None
        return {"Authorization": f"Bearer {token}"}

    def _portal_post(client: Any, path: str, payload: Dict[str, Any]) -> Any:
        headers = _portal_headers(force_refresh=False)
        if not headers:
            return None
        resp = client.post(f"{base}{path}", headers=headers, json=payload)
        if getattr(resp, "status_code", None) == 401:
            refreshed = _portal_headers(force_refresh=True)
            if refreshed:
                resp = client.post(f"{base}{path}", headers=refreshed, json=payload)
        return resp

    timeout = httpx.Timeout(_FUSION_HTTP_TIMEOUT, connect=_FUSION_CONNECT_TIMEOUT)
    last_draft = ""
    last_meta: Optional[dict] = None

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = _portal_post(
                client,
                "/api/v1/fusion/start",
                {
                    "user_message": user_message,
                    "fusion_config": cfg.to_dict(),
                    "conversation_history": conversation_history or [],
                    "tools_summary": _summarize_agent_tools(agent),
                    "main_model": str(getattr(agent, "model", "") or ""),
                    # The portal re-checks this server-side and refuses fusion
                    # unless the main model runs on the managed subscription, so
                    # the panel + main turns are all metered through the portal.
                    "main_provider": (getattr(agent, "provider", "") or "").strip().lower(),
                },
            )
            if resp is None:
                _emit("fallback", "🔮 Fusion: not connected to the Omni Loop Portal — answering directly…")
                return _normal_turn()
            if resp.status_code == 403:
                msg = _error_message(resp, "🔮 Fusion is a Pro-plan feature — upgrade in the Omni Loop Portal.")
                _emit("fallback", msg)
                return {
                    "final_response": msg,
                    "messages": list(conversation_history or []),
                    "api_calls": 0,
                    "completed": False,
                    "failed": True,
                    "error": msg,
                }
            if resp.status_code == 404:
                _emit("fallback", "🔮 Fusion isn't available on this portal yet — answering directly…")
                return _normal_turn()
            if resp.status_code != 200:
                _emit("fallback", "🔮 Fusion service error — answering directly…")
                return _normal_turn()

            data = resp.json()
            _forward(data.get("events"))
            action = str(data.get("action") or "")
            session_id = data.get("session_id")
            last_meta = data.get("fusion") if isinstance(data.get("fusion"), dict) else last_meta

            if action == "fallback":
                return _normal_turn()

            # Drive the local work/revise loop, posting each draft back.
            turns = 0
            while action in {"work", "revise"} and turns < _MAX_LOCAL_TURNS:
                turns += 1
                # Hide the main model's *draft* answer + reasoning from the chat
                # for this work/revise turn — the user should see only the
                # tool-call actions and interim commentary. The draft itself is
                # handed to the reviewers, not shown (see
                # run_agent._fusion_hide_draft). Always cleared in finally so the
                # later finalize turn streams the fused answer normally.
                with contextlib.suppress(Exception):
                    agent._fusion_hide_draft = True
                try:
                    draft_result = _run_local_turn(
                        str(data.get("message") or ""),
                        internal=True,
                        sc=(work_stream_callback or stream_callback) if action == "work" else None,
                    )
                finally:
                    with contextlib.suppress(Exception):
                        agent._fusion_hide_draft = False
                last_draft = str((draft_result or {}).get("final_response") or "").strip()
                # Extract a compact trace of the tool calls the agent made
                # (searches, scrapes, reads, commands) so the Fusion
                # reviewers/judge can verify the draft against the actual tool
                # output — not just the final text.
                tool_trace = _extract_tool_trace(
                    (draft_result or {}).get("messages") or []
                )
                resp = _portal_post(
                    client,
                    "/api/v1/fusion/step",
                    {
                        "session_id": session_id,
                        "draft": last_draft,
                        "tool_trace": tool_trace,
                    },
                )
                if resp is None:
                    _emit(
                        "degraded",
                        "⚠️ Fusion review did not complete; delivering the local draft without reviewer/judge approval.",
                        data={"reason": "missing_token"},
                    )
                    return {
                        "final_response": (
                            f"{last_draft}\n\n"
                            "⚠️ Fusion review did not complete; this is the local main-worker draft, "
                            "not a reviewed Fusion final. Start a fresh session and run Fusion again "
                            "for reviewer/judge review."
                        ).strip(),
                        "messages": list(conversation_history or []),
                        "api_calls": 0,
                        "completed": True,
                        "failed": False,
                        "fusion": {"reviewed": False, "degraded": "missing portal token"},
                    }
                if resp.status_code != 200:
                    # We already did the work locally — deliver that draft.
                    reason = _error_message(resp, f"portal step failed with HTTP {resp.status_code}")
                    logger.warning(
                        "fusion: /step failed status=%s reason=%s; delivering unreviewed draft",
                        resp.status_code,
                        reason,
                    )
                    _emit(
                        "degraded",
                        "⚠️ Fusion review did not complete; delivering the local draft without reviewer/judge approval.",
                        data={"status": resp.status_code, "reason": reason},
                    )
                    return {
                        "final_response": (
                            f"{last_draft}\n\n"
                            "⚠️ Fusion review did not complete; this is the local main-worker draft, "
                            "not a reviewed Fusion final. Start a fresh session and run Fusion again "
                            "for reviewer/judge review."
                        ).strip(),
                        "messages": list(conversation_history or []),
                        "api_calls": 0,
                        "completed": True,
                        "failed": False,
                        "fusion": {
                            "reviewed": False,
                            "degraded": "portal step failed",
                            "status": resp.status_code,
                            "reason": reason,
                        },
                    }
                data = resp.json()
                _forward(data.get("events"))
                action = str(data.get("action") or "")
                session_id = data.get("session_id") or session_id
                last_meta = data.get("fusion") if isinstance(data.get("fusion"), dict) else last_meta

            if action == "deliver":
                fusion_reviewed = not (isinstance(last_meta, dict) and last_meta.get("reviewed") is False)
                result: Dict[str, Any] = {
                    "final_response": str(data.get("final_response") or last_draft),
                    "messages": list(conversation_history or []),
                    "api_calls": 0,
                    "completed": True,
                    "failed": False,
                }
                if fusion_reviewed:
                    result["fusion_completed"] = True
                if isinstance(last_meta, dict):
                    result["fusion"] = last_meta
                return result

            if action == "finalize":
                hide_image = bool(data.get("hide_image_tool"))
                orig_tools = orig_valid = None
                try:
                    if hide_image:
                        orig_tools, orig_valid = _hide_tools(agent, {"image_generate"})
                    result = _run_local_turn(
                        str(data.get("message") or ""),
                        internal=False,
                        sc=stream_callback,
                    )
                finally:
                    _restore_tools(agent, orig_tools, orig_valid)
                if isinstance(result, dict):
                    fusion_reviewed = not (isinstance(last_meta, dict) and last_meta.get("reviewed") is False)
                    if (
                        fusion_reviewed
                        and
                        result.get("completed", True) is not False
                        and not result.get("failed")
                        and not result.get("interrupted")
                        and not result.get("error")
                    ):
                        result["fusion_completed"] = True
                    if isinstance(last_meta, dict):
                        result["fusion"] = last_meta
                return result

            # Unknown/exhausted: deliver the local draft if we have one.
            if last_draft:
                return {
                    "final_response": last_draft,
                    "messages": list(conversation_history or []),
                    "api_calls": 0,
                    "completed": True,
                    "failed": False,
                }
            return _normal_turn()
    except Exception as exc:
        logger.warning("fusion: portal call failed (%s); answering directly", exc)
        if last_draft:
            return {
                "final_response": last_draft,
                "messages": list(conversation_history or []),
                "api_calls": 0,
                "completed": True,
                "failed": False,
            }
        return _normal_turn()


__all__ = [
    "FusionConfig",
    "FusionEvent",
    "get_fusion_config",
    "set_fusion_config",
    "clear_fusion_config",
    "parse_fusion_args",
    "fusion_is_active",
    "main_model_is_managed",
    "FUSION_NEEDS_MANAGED_NOTICE",
    "FUSION_RESET_SESSION_NOTICE",
    "fusion_gate_check",
    "model_open_tag",
    "label_model",
    "activation_notice",
    "status_notice",
    "run_fusion_turn",
    "FUSION_ADVISOR_TOOL_NAMES",
    "FUSION_ADVISOR_TOOLSETS",
    "FUSION_REVIEWER_TOOL_NAMES",
    "FUSION_REVIEWER_TOOLSETS",
    "FUSION_MAX_MODELS_PER_GROUP",
    "MAX_PLAN_IDS",
    "FUSION_PLAN_IDS",
    "_extract_tool_trace",
    "_compact_args",
    "_compact_result",
]
