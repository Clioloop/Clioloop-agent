"""Canonical Bot Chat reset/new commands compact instead of forking identity."""

from unittest.mock import Mock

from cli import ClioCLI
from clio_state import SessionDB


def test_new_on_canonical_bot_chat_routes_to_compress(tmp_path):
    db = SessionDB(db_path=tmp_path / "state.db")
    try:
        session = db.get_or_create_canonical_session(
            owner_profile="alpha",
            canonical_key="bot.chat",
            title="Bot Chat",
            source="bot",
            identity_kind="bot",
            hidden=True,
        )
        cli = ClioCLI.__new__(ClioCLI)
        cli._pending_resume_sessions = None
        cli._session_db = db
        cli.session_id = session["id"]
        cli._manual_compress = Mock()
        cli.new_session = Mock()
        cli._confirm_destructive_slash = Mock(side_effect=AssertionError("must not ask destructive confirmation"))

        assert cli.process_command("/new") is True
        cli._manual_compress.assert_called_once_with("/compress")
        cli.new_session.assert_not_called()
    finally:
        db.close()
