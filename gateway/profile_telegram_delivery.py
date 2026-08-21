"""Profile-scoped one-shot Telegram delivery for Bot Room replies.

This module is intentionally not a general CLI surface. The controller starts
it with an allowlisted environment and an absolute target ``CLIO_HOME``; it
loads only that profile's secrets, sends one finalized reply, and exits without
mirroring anything into ordinary gateway sessions.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

_MAX_REPLY_BYTES = 800_000


def _profile_home(raw: str) -> Path:
    home = Path(str(raw or "")).expanduser().resolve()
    if not home.is_dir():
        raise ValueError("Target profile home does not exist")
    return home


def _load_target_profile_environment(home: Path) -> None:
    """Load only *home* credentials; never use the repository `.env` fallback."""
    for key in list(os.environ):
        if key.upper().startswith("TELEGRAM_"):
            os.environ.pop(key, None)
    os.environ["CLIO_HOME"] = str(home)

    from clio_cli.env_loader import load_clio_dotenv

    load_clio_dotenv(clio_home=home, project_env=None)


def _read_reply() -> str:
    payload = sys.stdin.buffer.read(_MAX_REPLY_BYTES + 1)
    if len(payload) > _MAX_REPLY_BYTES:
        raise ValueError("Reply payload is too large")
    reply = payload.decode("utf-8", errors="strict").strip()
    if not reply or "\x00" in reply:
        raise ValueError("Reply payload is empty or invalid")
    return reply


def _build_bot(token: str, extra: dict[str, Any]):
    from telegram import Bot

    kwargs: dict[str, Any] = {"token": token}
    custom_base_url = str(extra.get("base_url") or "").strip()
    if custom_base_url:
        kwargs["base_url"] = custom_base_url
        kwargs["base_file_url"] = str(
            extra.get("base_file_url") or custom_base_url
        ).strip()

    try:
        from gateway.platforms.base import resolve_proxy_url

        proxy_url = str(extra.get("proxy_url") or "").strip() or resolve_proxy_url(
            "TELEGRAM_PROXY",
            target_hosts=["api.telegram.org"],
        )
    except Exception:
        proxy_url = ""
    if proxy_url:
        from telegram.request import HTTPXRequest

        kwargs["request"] = HTTPXRequest(proxy=proxy_url)
        kwargs["get_updates_request"] = HTTPXRequest(proxy=proxy_url)
    return Bot(**kwargs)


async def _deliver(home: Path, chat_id: str, thread_id: str, reply: str) -> bool:
    _load_target_profile_environment(home)

    from gateway.config import load_gateway_config
    from gateway.platforms.base import Platform
    from gateway.platforms.telegram import TelegramAdapter

    config = load_gateway_config()
    platform_config = config.platforms.get(Platform.TELEGRAM)
    token = str(getattr(platform_config, "token", "") or "").strip()
    if platform_config is None or not token:
        return False

    adapter = TelegramAdapter(platform_config)
    bot = _build_bot(token, platform_config.extra)
    adapter._bot = bot
    initialized = False
    try:
        await bot.initialize()
        initialized = True
        metadata: dict[str, Any] = {"telegram_strict_thread": True}
        if thread_id:
            metadata["message_thread_id"] = thread_id
        result = await adapter.send(chat_id, reply, metadata=metadata)
        return bool(result.success) and not bool(
            (result.raw_response or {}).get("thread_fallback")
        )
    finally:
        if initialized:
            await bot.shutdown()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--clio-home", required=True)
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--thread-id", default="")
    return parser


def main() -> int:
    try:
        args = _parser().parse_args()
        home = _profile_home(args.clio_home)
        chat_id = str(int(str(args.chat_id).strip()))
        thread_id = (
            str(int(str(args.thread_id).strip())) if str(args.thread_id).strip() else ""
        )
        reply = _read_reply()
        return 0 if asyncio.run(_deliver(home, chat_id, thread_id, reply)) else 1
    except (OSError, RuntimeError, TypeError, UnicodeError, ValueError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
