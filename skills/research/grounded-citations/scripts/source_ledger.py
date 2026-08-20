#!/usr/bin/env python3
"""Create and validate a small claim-level source ledger.

The helper is intentionally offline: callers capture page text with Clio's web
or browser tools, then this script verifies exact evidence without making a
second network request or handling credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = 1
RELATIONS = {"supports", "contradicts", "context"}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def quote_digest(quote: str) -> str:
    return hashlib.sha256(normalize_text(quote).encode("utf-8")).hexdigest()


def empty_ledger() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "sources": []}


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_ledger()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported source ledger schema")
    if not isinstance(data.get("sources"), list):
        raise ValueError("source ledger sources must be a list")
    return data


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def validate_url(url: str) -> str:
    clean = str(url or "").strip()
    parsed = urlparse(clean)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("source URL must not contain credentials")
    return clean


def verify_quote(content: str, quote: str) -> None:
    normalized_quote = normalize_text(quote)
    if not normalized_quote:
        raise ValueError("evidence quote must not be empty")
    if normalized_quote not in normalize_text(content):
        raise ValueError("evidence quote was not found in captured content")


def add_source(
    ledger: dict[str, Any],
    *,
    url: str,
    title: str,
    claim: str,
    quote: str,
    content: str,
    relation: str = "supports",
    publisher: str = "",
    published_at: str = "",
    retrieved_at: str = "",
) -> dict[str, Any]:
    url = validate_url(url)
    title = normalize_text(title)
    claim = normalize_text(claim)
    quote = normalize_text(quote)
    if not title or not claim:
        raise ValueError("source title and atomic claim are required")
    if relation not in RELATIONS:
        raise ValueError(f"relation must be one of: {', '.join(sorted(RELATIONS))}")
    verify_quote(content, quote)

    sources = ledger.setdefault("sources", [])
    source_id = f"S{len(sources) + 1}"
    row = {
        "id": source_id,
        "url": url,
        "title": title,
        "publisher": normalize_text(publisher),
        "published_at": normalize_text(published_at),
        "retrieved_at": retrieved_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "claim": claim,
        "relation": relation,
        "quote": quote,
        "quote_sha256": quote_digest(quote),
    }
    sources.append(row)
    return row


def validate_ledger(ledger: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(ledger.get("sources", []), start=1):
        prefix = f"sources[{index - 1}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} is not an object")
            continue
        expected_id = f"S{index}"
        if row.get("id") != expected_id:
            errors.append(f"{prefix}.id must be {expected_id}")
        if row.get("id") in seen:
            errors.append(f"{prefix}.id is duplicated")
        seen.add(str(row.get("id")))
        try:
            validate_url(str(row.get("url") or ""))
        except ValueError as exc:
            errors.append(f"{prefix}.url: {exc}")
        if row.get("relation") not in RELATIONS:
            errors.append(f"{prefix}.relation is invalid")
        if not normalize_text(row.get("title", "")):
            errors.append(f"{prefix}.title is empty")
        if not normalize_text(row.get("claim", "")):
            errors.append(f"{prefix}.claim is empty")
        quote = normalize_text(row.get("quote", ""))
        if not quote:
            errors.append(f"{prefix}.quote is empty")
        elif row.get("quote_sha256") != quote_digest(quote):
            errors.append(f"{prefix}.quote_sha256 does not match the quote")
    return errors


def render_markdown(ledger: dict[str, Any]) -> str:
    lines = []
    for row in ledger.get("sources", []):
        publisher = f" — {row['publisher']}" if row.get("publisher") else ""
        published = f" ({row['published_at']})" if row.get("published_at") else ""
        lines.append(f"[{row['id']}] {row['title']}{publisher}{published}. {row['url']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create an empty ledger")
    init.add_argument("ledger", type=Path)
    add = sub.add_parser("add", help="verify and add one source/claim")
    add.add_argument("ledger", type=Path)
    add.add_argument("--url", required=True)
    add.add_argument("--title", required=True)
    add.add_argument("--publisher", default="")
    add.add_argument("--published-at", default="")
    add.add_argument("--retrieved-at", default="")
    add.add_argument("--claim", required=True)
    add.add_argument("--quote", required=True)
    add.add_argument("--content-file", required=True, type=Path)
    add.add_argument("--relation", choices=sorted(RELATIONS), default="supports")
    verify = sub.add_parser("verify", help="validate ledger structure and hashes")
    verify.add_argument("ledger", type=Path)
    render = sub.add_parser("render", help="render a Markdown source list")
    render.add_argument("ledger", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        atomic_write(args.ledger, empty_ledger())
        print(args.ledger)
        return 0
    ledger = load_ledger(args.ledger)
    if args.command == "add":
        content = args.content_file.read_text(encoding="utf-8")
        row = add_source(
            ledger,
            url=args.url,
            title=args.title,
            publisher=args.publisher,
            published_at=args.published_at,
            retrieved_at=args.retrieved_at,
            claim=args.claim,
            quote=args.quote,
            content=content,
            relation=args.relation,
        )
        atomic_write(args.ledger, ledger)
        print(row["id"])
        return 0
    errors = validate_ledger(ledger)
    if errors:
        for error in errors:
            print(error)
        return 1
    if args.command == "render":
        print(render_markdown(ledger))
    else:
        print(f"ok: {len(ledger['sources'])} source(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
