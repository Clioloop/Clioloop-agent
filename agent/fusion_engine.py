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
# these timeouts cover only the server-side panel calls).
_FUSION_HTTP_TIMEOUT = 300.0
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# The one managed model that is free for every tier (mirrors
# portal/src/lib/model-policy.ts::FREE_OPENROUTER_MODEL). It is an OpenRouter
# ":free" id, so the ``:free`` suffix check also tags it free.
FREE_MANAGED_MODEL = "openai/gpt-oss-120b:free"


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

def _managed_access_token() -> Optional[str]:
    """The managed-provider OAuth access token used to authenticate fusion calls."""
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

    token = _managed_access_token()
    base = _portal_base_url()
    if not token or not base:
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

    headers = {"Authorization": f"Bearer {token}"}
    timeout = httpx.Timeout(_FUSION_HTTP_TIMEOUT, connect=_FUSION_CONNECT_TIMEOUT)
    last_draft = ""
    last_meta: Optional[dict] = None

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{base}/api/v1/fusion/start",
                headers=headers,
                json={
                    "user_message": user_message,
                    "fusion_config": cfg.to_dict(),
                    "conversation_history": conversation_history or [],
                    "tools_summary": _summarize_agent_tools(agent),
                    "main_model": str(getattr(agent, "model", "") or ""),
                },
            )
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
                resp = client.post(
                    f"{base}/api/v1/fusion/step",
                    headers=headers,
                    json={"session_id": session_id, "draft": last_draft},
                )
                if resp.status_code != 200:
                    # We already did the work locally — deliver that draft.
                    return {
                        "final_response": last_draft,
                        "messages": list(conversation_history or []),
                        "api_calls": 0,
                        "completed": True,
                        "failed": False,
                    }
                data = resp.json()
                _forward(data.get("events"))
                action = str(data.get("action") or "")
                session_id = data.get("session_id") or session_id
                last_meta = data.get("fusion") if isinstance(data.get("fusion"), dict) else last_meta

            if action == "deliver":
                result: Dict[str, Any] = {
                    "final_response": str(data.get("final_response") or last_draft),
                    "messages": list(conversation_history or []),
                    "api_calls": 0,
                    "completed": True,
                    "failed": False,
                }
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
                if isinstance(result, dict) and isinstance(last_meta, dict):
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
]
