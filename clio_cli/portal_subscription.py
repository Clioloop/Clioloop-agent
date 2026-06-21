"""Omni Loop Portal subscription features (managed tool gateway).

Surfaces the portal's bundled tool services — web search (firecrawl),
cloud browser (browser-use), self-hosted image generation (clioloop-image),
video generation (vidu), and text-to-speech (openai-audio) — as managed feature descriptors consumed
by ``clio_cli.tools_config`` and status surfaces.

Entitlements come from the portal's ``/api/account/info`` endpoint via
:mod:`clio_cli.portal_account` (cached ~60s). Everything degrades
gracefully: when the user is not logged into the portal, or the portal
is unreachable, every feature reports unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

#: feature key → label
_FEATURE_DEFS: tuple[tuple[str, str], ...] = (
    ("web", "Web tools"),
    ("browser", "Browser automation"),
    ("image_gen", "Image generation"),
    ("video_gen", "Video generation"),
    ("music_gen", "Music generation"),
    ("tts", "Text-to-speech"),
    ("modal", "Modal execution"),
)

#: Feature → coverage-category label used in entitlement prompts.
MANAGED_FEATURE_COVERAGE_CATEGORY: dict[str, str] = {
    "web": "web search",
    "browser": "cloud browser",
    "image_gen": "image generation",
    "video_gen": "video generation",
    "music_gen": "music generation",
    "tts": "text-to-speech",
    "modal": "sandboxed execution",
}


@dataclass
class ManagedFeatureState:
    """A single managed-tool feature descriptor.

    Accepts positional and keyword arguments for compatibility with
    the legacy constructor used in the test suite.
    """

    key: str = ""
    label: str = ""
    available: bool = False
    active: bool = False
    managed_by_provider: bool = False
    included_by_default: bool = False
    current_provider: str = ""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Positional/keyword construction (legacy tests use both forms).
        field_names = (
            "key", "label", "available", "active",
            "managed_by_provider", "included_by_default", "current_provider",
        )
        defaults = ("", "", False, False, False, False, "")
        for name, default in zip(field_names, defaults):
            setattr(self, name, default)
        for name, value in zip(field_names, args):
            setattr(self, name, value)
        for name, value in kwargs.items():
            setattr(self, name, value)


def _has_agent_browser() -> bool:
    """True when the agent-browser CLI is on PATH (local browser backend)."""
    import shutil

    return shutil.which("agent-browser") is not None


def _env(key: str) -> str:
    """Read a credential from the process env or ~/.clio/.env."""
    import os

    value = os.getenv(key)
    if value:
        return value
    try:
        from clio_cli.config import get_env_value

        return get_env_value(key) or ""
    except Exception:
        return ""


def _detect_local_backends(config: Optional[dict]) -> dict[str, tuple[bool, str]]:
    """(available, backend label) per feature for bring-your-own-key setups.

    Mirrors the runtime gates each tool actually applies, so the setup
    summary never claims a backend the tool would refuse at call time.
    """
    out: dict[str, tuple[bool, str]] = {}

    # Web search & extract — legacy preference order.
    if _env("FIRECRAWL_API_KEY"):
        out["web"] = (True, "Firecrawl")
    elif _env("FIRECRAWL_API_URL"):
        out["web"] = (True, "Firecrawl (self-hosted)")
    elif _env("PARALLEL_API_KEY"):
        out["web"] = (True, "Parallel")
    elif _env("TAVILY_API_KEY"):
        out["web"] = (True, "Tavily")
    elif _env("EXA_API_KEY"):
        out["web"] = (True, "Exa")
    elif _env("SEARXNG_URL"):
        out["web"] = (True, "SearXNG")
    else:
        out["web"] = (False, "")

    # Browser automation — label reflects the configured backend; available
    # only when that backend's full requirements are met.
    browser_cfg = (config or {}).get("browser") if isinstance(config, dict) else None
    cloud = str((browser_cfg or {}).get("cloud_provider") or "local").strip().lower()
    if cloud == "camofox":
        out["browser"] = (bool(_env("CAMOFOX_URL")), "Camofox")
    elif cloud == "browserbase":
        ready = bool(
            _env("BROWSERBASE_API_KEY") and _env("BROWSERBASE_PROJECT_ID")
        ) and _has_agent_browser()
        out["browser"] = (ready, "Browserbase")
    elif cloud == "browser-use":
        out["browser"] = (bool(_env("BROWSER_USE_API_KEY")), "Browser Use")
    elif _env("BROWSERBASE_API_KEY") or _env("BROWSERBASE_PROJECT_ID"):
        # Partially-configured Browserbase: surface the intent, stay red.
        ready = bool(
            _env("BROWSERBASE_API_KEY") and _env("BROWSERBASE_PROJECT_ID")
        ) and _has_agent_browser()
        out["browser"] = (ready, "Browserbase")
    else:
        ready = _has_agent_browser()
        if ready:
            try:
                from tools.browser_tool import check_browser_requirements

                ready = bool(check_browser_requirements())
            except Exception:
                pass
        out["browser"] = (ready, "Local browser")

    # Video generation — Vidu direct key. Image generation is first-party via
    # the Omni Loop Portal or via plugin backends probed separately by the
    # summary itself.
    vidu = bool(_env("VIDU_API_KEY"))
    out["image_gen"] = (False, "")
    out["video_gen"] = (vidu, "Vidu" if vidu else "")
    apiframe = bool(_env("APIFRAME_API_KEY"))
    out["music_gen"] = (apiframe, "Apiframe" if apiframe else "")

    out["tts"] = (True, "")  # Edge TTS is always available, no key needed.
    out["modal"] = (False, "")
    return out


class ManagedSubscriptionFeatures:
    """Bundle of managed-tool feature states for the current portal login.

    Exposes ``.web`` / ``.browser`` / ``.image_gen`` / ``.video_gen`` /
    ``.music_gen`` / ``.tts`` / ``.modal`` as :class:`ManagedFeatureState` instances, plus a
    ``features`` mapping keyed by feature name.
    """

    def __init__(
        self,
        *,
        provider_auth_present: bool = False,
        provider_is_managed: bool = False,
        subscribed: bool | None = None,
        account_info: Any = None,
        features: Optional[dict[str, ManagedFeatureState]] = None,
        feature_flags: Optional[dict[str, bool]] = None,
        config: Optional[dict] = None,
    ) -> None:
        if features is not None:
            self.provider_auth_present = provider_auth_present
            self.account_info = account_info
            self.features = dict(features)
            for key, state in self.features.items():
                setattr(self, key, state)
            return

        flags = dict(feature_flags or {})
        # Older portals (and test doubles) may omit granular feature flags;
        # a paid subscription implies the full bundle in that case.
        if not flags and getattr(account_info, "paid_service_access", False):
            flags = {k: True for k in ("web", "browser", "image_gen", "video_gen", "music_gen", "tts")}
        if not flags and subscribed:
            flags = {k: True for k in ("web", "browser", "image_gen", "video_gen", "music_gen", "tts")}
        self.provider_auth_present = provider_auth_present
        self.account_info = account_info
        try:
            local = _detect_local_backends(config)
        except Exception:
            local = {}
        self.features: dict[str, ManagedFeatureState] = {}
        for key, label in _FEATURE_DEFS:
            managed = bool(flags.get(key, False) or (provider_is_managed and subscribed))
            local_ok, local_label = local.get(key, (False, ""))
            state = ManagedFeatureState(
                key=key,
                label=label,
                available=managed or local_ok,
                active=managed,
                managed_by_provider=managed,
                included_by_default=managed,
                current_provider="Omni Loop Portal Subscription" if managed else local_label,
            )
            self.features[key] = state
            setattr(self, key, state)

    def items(self) -> list[ManagedFeatureState]:
        return [self.features[key] for key, _ in _FEATURE_DEFS]


def get_managed_subscription_features(
    config: Optional[dict] = None,
    *,
    force_fresh: bool = False,
    **_kwargs: Any,
) -> ManagedSubscriptionFeatures:
    """Return the managed feature bundle for the current portal login.

    Never raises — any failure yields the all-unavailable default.
    """
    try:
        try:
            info = get_managed_portal_account_info(force_fresh=force_fresh)
        except TypeError:
            info = get_managed_portal_account_info()
    except Exception:
        return ManagedSubscriptionFeatures(config=config)
    if not getattr(info, "logged_in", False):
        return ManagedSubscriptionFeatures(config=config)
    return ManagedSubscriptionFeatures(
        provider_auth_present=True,
        account_info=info,
        feature_flags=dict(getattr(info, "features", {}) or {}),
        config=config,
    )


def ensure_managed_provider_access(
    *,
    capability: str = "",
    coverage_category: Optional[str] = None,
    force_fresh: bool = True,
    **_kwargs: Any,
) -> bool:
    """Gate a managed-tool selection on portal login + entitlement.

    Prints an actionable hint and returns False when the user is not
    logged into the Omni Loop Portal Subscription or the plan lacks gateway access.
    """
    features = get_managed_subscription_features(force_fresh=force_fresh)
    info = features.account_info
    if info is None or not getattr(info, "logged_in", False):
        try:
            print(
                "  Omni Loop Portal Subscription login required — connect with: clio setup --portal"
            )
        except Exception:
            pass
        return False
    if getattr(info, "paid_service_access", False) or getattr(
        info, "tool_gateway_entitled", False
    ):
        return True
    what = coverage_category or capability or "this service"
    portal_url = str((getattr(info, "raw", {}) or {}).get("portal_url") or "").rstrip("/")
    upgrade = f" — upgrade at {portal_url}/pricing" if portal_url else ""
    try:
        print(f"  Your Omni Loop Portal Subscription plan does not include {what}{upgrade}")
    except Exception:
        pass
    return False


def get_managed_provider_account_info(*args: Any, **kwargs: Any) -> Any:
    """Account info passthrough (see clio_cli.portal_account)."""
    from clio_cli import portal_account

    return portal_account.get_managed_provider_account_info(*args, **kwargs)


def get_managed_portal_account_info(*args: Any, **kwargs: Any) -> Any:
    """Alias for callers that still refer to the managed portal layer."""
    return get_managed_provider_account_info(*args, **kwargs)


def managed_provider_tools_enabled(*args: Any, **kwargs: Any) -> bool:
    """True when the portal login is entitled to any gateway service."""
    try:
        from tools.tool_backend_helpers import managed_tools_enabled as _enabled

        return _enabled(**{k: v for k, v in kwargs.items() if k == "force_fresh"})
    except Exception:
        return False


#: Config sections that apply_managed_defaults may flip to the gateway.
_DEFAULTABLE_FEATURES = ("web", "browser", "image_gen", "video_gen", "tts")


def apply_managed_defaults(
    config: dict,
    *,
    enabled_toolsets: Optional[set] = None,
    force_fresh: bool = False,
    **_kwargs: Any,
) -> set[str]:
    """Default newly-enabled tool sections to the portal gateway.

    For every entitled feature whose config section has no explicit
    backend yet, sets ``use_gateway: true`` so the tool routes through the
    Omni Loop Portal without further setup. Returns the set of feature
    keys that were auto-configured. Pre-configured sections are never
    touched.
    """
    configured: set[str] = set()
    if not isinstance(config, dict):
        return configured
    features = get_managed_subscription_features(config, force_fresh=force_fresh)
    for key in _DEFAULTABLE_FEATURES:
        if enabled_toolsets is not None and key not in enabled_toolsets:
            continue
        state = features.features.get(key)
        if state is None or not state.available:
            continue
        section = config.get(key)
        if section is None:
            section = {}
            config[key] = section
        if not isinstance(section, dict):
            continue
        # For TTS, "edge" (the free default) is also overridable so managed
        # users who start with Edge TTS get auto-upgraded to portal Supertonic.
        current_provider = str(section.get("provider") or "").strip()
        overridable = {"", "fal", "vidu", "clioloop", "omni-loop"}
        if key == "tts":
            overridable.add("edge")
        if current_provider not in overridable:
            continue
        use_gateway_value = section.get("use_gateway")
        use_gateway_set = use_gateway_value is not None
        use_gateway_truthy = (
            str(use_gateway_value).strip().lower() in {"1", "true", "yes", "on"}
            if use_gateway_set
            else False
        )

        # Respect explicit user choices: a configured provider or an
        # explicit use_gateway value (true OR false) wins. Managed video is
        # the exception because old installs may already have
        # ``use_gateway: true`` from the retired FAL gateway and still need to
        # be migrated to Vidu.
        if use_gateway_set and not (
            key == "video_gen"
            and use_gateway_truthy
            and str(section.get("provider") or "").strip() in {"", "fal"}
        ):
            continue
        # Wire the backend the gateway serves, so the tool picks the right
        # vendor route without a separate provider prompt.
        if key == "web" and not section.get("backend"):
            section["backend"] = "firecrawl"
        elif key == "tts" and (
            not section.get("provider")
            or str(section.get("provider") or "").strip() == "edge"
        ):
            section["provider"] = "openai"
        elif key == "browser" and not section.get("cloud_provider"):
            section["cloud_provider"] = "browser-use"
        elif key == "image_gen":
            # Self-hosted image backend (clioloop-image gateway vendor), like
            # the self-hosted Supertonic TTS. Operators who serve FAL instead
            # should pin image_gen.provider: fal explicitly.
            section["provider"] = "omni-loop"
            section["model"] = "clioloop-local"
        elif key == "video_gen" and (
            not section.get("provider")
            or str(section.get("provider") or "").strip() == "fal"
        ):
            section["provider"] = "vidu"
        section["use_gateway"] = True
        configured.add(key)
    return configured


__all__ = [
    "ManagedFeatureState",
    "ManagedSubscriptionFeatures",
    "get_managed_subscription_features",
    "ensure_managed_provider_access",
    "get_managed_provider_account_info",
    "get_managed_portal_account_info",
    "managed_provider_tools_enabled",
    "MANAGED_FEATURE_COVERAGE_CATEGORY",
    "apply_managed_defaults",
]

managed_tools_enabled = managed_provider_tools_enabled
