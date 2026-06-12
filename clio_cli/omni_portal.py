"""Omni Loop Portal device-connect helper.

Shared by every non-CLI surface (web dashboard, TUI gateway, desktop app)
that offers a "Connect Omni Loop Portal" button. Starts the RFC 8628
device-authorization flow, polls for approval on a daemon thread, and
persists the OAuth credentials through the same path as
``clio auth add managed``.

The CLI itself uses the richer interactive flow in clio_cli.auth
(`_login_managed`); this module is the headless, poll-from-a-UI variant.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

_connect_lock = threading.Lock()
_connect_state: Dict[str, Any] = {"status": "idle"}


def resolve_portal_base_url() -> str:
    """Portal base URL with env overrides, matching the auth.py chain."""
    from clio_cli.auth import PROVIDER_REGISTRY

    pconfig = PROVIDER_REGISTRY["managed"]
    return (
        os.getenv("CLIO_PORTAL_BASE_URL", "").strip()
        or os.getenv("MANAGED_PORTAL_BASE_URL", "").strip()
        or pconfig.portal_base_url
    ).rstrip("/")


def _connect_worker(device_data: dict, portal_base_url: str, client_id: str, scope: str) -> None:
    import httpx

    from clio_cli import auth as auth_mod

    global _connect_state
    try:
        with httpx.Client(
            timeout=httpx.Timeout(15.0), headers={"Accept": "application/json"}
        ) as client:
            token_data = auth_mod._poll_for_token(
                client,
                portal_base_url,
                client_id,
                str(device_data["device_code"]),
                int(device_data["expires_in"]),
                int(device_data["interval"]),
            )
        now_dt = datetime.now(timezone.utc)
        ttl = int(token_data.get("expires_in") or 3600)
        inference_url = (
            str(token_data.get("inference_base_url") or "").strip()
            or f"{portal_base_url}/api/v1"
        )
        creds = {
            "portal_base_url": portal_base_url,
            "inference_base_url": inference_url,
            "client_id": client_id,
            "scope": token_data.get("scope") or scope,
            "token_type": token_data.get("token_type", "Bearer"),
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "obtained_at": now_dt.isoformat(),
            "expires_in": ttl,
            "expires_at": datetime.fromtimestamp(
                now_dt.timestamp() + ttl, tz=timezone.utc
            ).isoformat(),
        }
        auth_mod.persist_managed_credentials(creds)
        try:
            auth_mod._write_shared_managed_state(creds)
        except Exception:
            pass
        with _connect_lock:
            _connect_state = {"status": "connected"}
    except Exception as exc:
        logger.debug("portal connect worker failed: %s", exc)
        with _connect_lock:
            _connect_state = {"status": "error", "message": str(exc)}


def start_device_connect() -> Dict[str, Any]:
    """Begin a device login. Returns the verification URL + user code.

    Raises on network failure; the caller surfaces the error to its UI.
    A daemon thread polls the portal and persists credentials on approval —
    track progress with :func:`get_connect_status`.
    """
    import httpx

    from clio_cli import auth as auth_mod

    global _connect_state
    pconfig = auth_mod.PROVIDER_REGISTRY["managed"]
    portal_base_url = resolve_portal_base_url()

    with httpx.Client(
        timeout=httpx.Timeout(15.0), headers={"Accept": "application/json"}
    ) as client:
        device_data = auth_mod._request_device_code(
            client, portal_base_url, pconfig.client_id, pconfig.scope
        )

    with _connect_lock:
        _connect_state = {
            "status": "pending",
            "user_code": device_data["user_code"],
            "verification_uri_complete": device_data["verification_uri_complete"],
        }
    threading.Thread(
        target=_connect_worker,
        args=(device_data, portal_base_url, pconfig.client_id, pconfig.scope),
        daemon=True,
    ).start()

    return {
        "status": "pending",
        "user_code": device_data["user_code"],
        "verification_uri": device_data["verification_uri"],
        "verification_uri_complete": device_data["verification_uri_complete"],
        "expires_in": device_data["expires_in"],
    }


def get_connect_status() -> Dict[str, Any]:
    """Current connect-flow status: idle | pending | connected | error."""
    with _connect_lock:
        return dict(_connect_state)
