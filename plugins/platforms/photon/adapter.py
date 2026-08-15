"""Optional Photon iMessage sidecar foundation."""
from __future__ import annotations
import os
import shutil
from plugins.platforms._portable_bridge import PortableBridgeAdapter


class PhotonAdapter(PortableBridgeAdapter):
    platform_name = "photon"


def _value(cfg, key: str, env: str) -> str:
    return str(os.getenv(env) or (getattr(cfg, "extra", {}) or {}).get(key) or "").strip()


def validate_config(cfg) -> bool:
    return bool(_value(cfg, "project_id", "PHOTON_PROJECT_ID") and _value(cfg, "project_secret", "PHOTON_PROJECT_SECRET"))


def check_requirements() -> bool:
    return bool(os.getenv("PHOTON_PROJECT_ID") and os.getenv("PHOTON_PROJECT_SECRET") and shutil.which(os.getenv("PHOTON_NODE_BIN", "node")))


def _env_enablement():
    if not (os.getenv("PHOTON_PROJECT_ID") and os.getenv("PHOTON_PROJECT_SECRET")):
        return None
    return {"project_id": os.getenv("PHOTON_PROJECT_ID"), "project_secret": os.getenv("PHOTON_PROJECT_SECRET")}


def register(ctx) -> None:
    ctx.register_platform(
        name="photon", label="Photon iMessage", adapter_factory=PhotonAdapter,
        check_fn=check_requirements, validate_config=validate_config,
        is_connected=validate_config, required_env=["PHOTON_PROJECT_ID", "PHOTON_PROJECT_SECRET"],
        install_hint="Node.js 18+ and a spectrum-ts sidecar are required",
        env_enablement_fn=_env_enablement, allowed_users_env="PHOTON_ALLOWED_USERS",
        allow_all_env="PHOTON_ALLOW_ALL_USERS", cron_deliver_env_var="PHOTON_HOME_CHANNEL",
        emoji="💬", pii_safe=False,
    )
