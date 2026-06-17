"""Console entrypoint for the Clio ACP adapter."""

import clio_bootstrap  # noqa: F401 - configure stdio before any other imports

import argparse
import asyncio
import logging
import sys

import acp
from acp_adapter.server import CLIO_VERSION, ClioACPAgent


class _BenignProbeMethodFilter(logging.Filter):
    """Suppress noisy ACP runtime logs for editor health probes."""

    _BENIGN_METHODS = {"ping", "health", "healthcheck"}

    def filter(self, record: logging.LogRecord) -> bool:
        if record.getMessage() != "Background task failed" or not record.exc_info:
            return True
        exc = record.exc_info[1]
        if exc.__class__.__name__ != "RequestError":
            return True
        if getattr(exc, "code", None) != -32601:
            return True
        method = (getattr(exc, "data", None) or {}).get("method")
        return method not in self._BENIGN_METHODS


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    for handler in logging.getLogger().handlers:
        handler.addFilter(_BenignProbeMethodFilter())


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


def _run_setup_browser(*, assume_yes: bool = False) -> int:
    from clio_cli.dep_ensure import ensure_dependency

    interactive = not assume_yes
    if not ensure_dependency("node", interactive=interactive):
        return 1
    if not ensure_dependency("browser", interactive=interactive):
        return 1
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="clio-acp")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--setup-browser", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    if args.version:
        print(CLIO_VERSION)
        return
    if args.check:
        print("Clio ACP check OK")
        return
    if args.setup:
        import clio_cli.main

        old = sys.argv[:]
        sys.argv = [old[0] if old else "clio", "model"]
        try:
            clio_cli.main.main()
        finally:
            sys.argv = old
        if sys.stdin.isatty():
            answer = input("Set up browser tools too? [y/N] ").strip().lower()
            if answer in {"y", "yes"}:
                code = _run_setup_browser(assume_yes=False)
                if code:
                    raise SystemExit(code)
        return
    if args.setup_browser:
        code = _run_setup_browser(assume_yes=args.yes)
        if code:
            raise SystemExit(code)
        return

    _setup_logging()
    _load_env()
    agent = ClioACPAgent()
    asyncio.run(acp.run_agent(agent, use_unstable_protocol=True))
