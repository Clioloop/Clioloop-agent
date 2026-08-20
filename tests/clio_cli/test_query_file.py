"""Safe one-shot query-file transport used by Bot handoffs."""

from __future__ import annotations

import io

import pytest

from clio_cli._parser import build_top_level_parser
from clio_cli.main import _read_query_file


def test_query_and_query_file_are_mutually_exclusive():
    parser, _subparsers, _chat = build_top_level_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["chat", "-q", "inline", "--query-file", "prompt.txt"])


def test_query_file_preserves_hostile_text_verbatim(tmp_path):
    text = 'line one\n"quoted" `ticks` $(not-shell)\n'
    path = tmp_path / "prompt.txt"
    path.write_text(text, encoding="utf-8")
    assert _read_query_file(str(path)) == text


def test_query_file_stdin_and_validation(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.stdin", io.StringIO("stdin prompt\n"))
    assert _read_query_file("-") == "stdin prompt\n"

    empty = tmp_path / "empty.txt"
    empty.write_text("  \n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        _read_query_file(str(empty))

    nul = tmp_path / "nul.txt"
    nul.write_bytes(b"bad\x00prompt")
    with pytest.raises(ValueError, match="NUL"):
        _read_query_file(str(nul))

    large = tmp_path / "large.txt"
    large.write_text("x" * 200_001, encoding="utf-8")
    with pytest.raises(ValueError, match="exceeds"):
        _read_query_file(str(large))
