"""Optional Buzz bridge foundation (Nostr relay identity + transport outbox)."""
from __future__ import annotations
import os
import shutil
from plugins.platforms._portable_bridge import PortableBridgeAdapter


class BuzzAdapter(PortableBridgeAdapter):
    platform_name = "buzz"


def _value(cfg, key: str, env: str) -> str:
    return str(os.getenv(env) or (getattr(cfg, "extra", {}) or {}).get(key) or "").strip()


def validate_config(cfg) -> bool:
    return bool(_value(cfg, "relay_url", "BUZZ_RELAY_URL") and _value(cfg, "private_key", "BUZZ_PRIVATE_KEY"))


def check_requirements() -> bool:
    return bool(os.getenv("BUZZ_RELAY_URL") and os.getenv("BUZZ_PRIVATE_KEY") and shutil.which(os.getenv("BUZZ_CLI_PATH", "buzz")))


def _env_enablement():
    if not (os.getenv("BUZZ_RELAY_URL") and os.getenv("BUZZ_PRIVATE_KEY")):
        return None
    return {"relay_url": os.getenv("BUZZ_RELAY_URL"), "private_key": os.getenv("BUZZ_PRIVATE_KEY")}


def register(ctx) -> None:
    ctx.register_platform(
        name="buzz", label="Buzz", adapter_factory=BuzzAdapter,
        check_fn=check_requirements, validate_config=validate_config,
        is_connected=validate_config, required_env=["BUZZ_RELAY_URL", "BUZZ_PRIVATE_KEY"],
        install_hint="Install the buzz CLI and configure a dedicated Nostr identity",
        env_enablement_fn=_env_enablement, allowed_users_env="BUZZ_ALLOWED_USERS",
        allow_all_env="BUZZ_ALLOW_ALL_USERS", cron_deliver_env_var="BUZZ_HOME_CHANNEL",
        emoji="🐝", platform_hint="You are in a Buzz channel. Keep replies concise and thread-aware.",
    )
