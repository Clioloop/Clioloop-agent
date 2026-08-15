import sqlite3

from clio_cli.config import _expand_env_vars
from clio_cli.config_defaults import ADDITIVE_DEFAULTS, merge_compat_defaults
from clio_cli.config_migrations import run_additive_migrations
from clio_state import SCHEMA_SQL, SCHEMA_VERSION, SessionDB


def test_recursive_interpolation_and_additive_defaults_are_detached(monkeypatch):
    monkeypatch.setenv("CLIO_TEST_INTERPOLATION", "resolved")
    value = {
        "nested": ["${env:CLIO_TEST_INTERPOLATION}", ("${CLIO_TEST_INTERPOLATION}",)],
        "key-${CLIO_TEST_INTERPOLATION}": "${vault:item}",
    }
    expanded = _expand_env_vars(value)
    assert expanded["nested"] == ["resolved", ("resolved",)]
    assert "key-${CLIO_TEST_INTERPOLATION}" in expanded
    assert expanded["key-${CLIO_TEST_INTERPOLATION}"] == "${vault:item}"

    merged = merge_compat_defaults({"state": {"turn_lease_ttl_seconds": 9}})
    assert merged["state"] == {
        "migration_backups": True,
        "turn_lease_ttl_seconds": 9,
    }
    merged["state"]["migration_backups"] = False
    assert ADDITIVE_DEFAULTS["state"]["migration_backups"] is True


def test_config_migration_registry_is_idempotent():
    original = {"_config_version": 26, "custom": {"keep": True}}
    first, first_steps = run_additive_migrations(26, original, target_version=27)
    second, second_steps = run_additive_migrations(27, first, target_version=27)
    assert first == original == second
    assert first_steps == second_steps == ()
    assert first is not original


def test_temporary_state_db_schema_and_apis_are_idempotent(tmp_path):
    path = tmp_path / "state.db"
    db = SessionDB(path)
    assert db._conn.execute("SELECT version FROM schema_version").fetchone()[0] == SCHEMA_VERSION

    expected = {
        "gateway_routing",
        "session_turn_leases",
        "session_model_usage",
        "system_prompts",
        "async_delegations",
    }
    actual = {
        row[0]
        for row in db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert expected <= actual

    db.save_gateway_routing_entry("same", '{"a":1}', scope="profile-a")
    db.save_gateway_routing_entry("same", '{"b":2}', scope="profile-b")
    db.save_gateway_routing_entry("same", '{"a":3}', scope="profile-a")
    assert db.load_gateway_routing_entries(scope="profile-a") == {"same": '{"a":3}'}
    assert db.load_gateway_routing_entries(scope="profile-b") == {"same": '{"b":2}'}

    assert db.try_acquire_turn_lease("lineage", "one", ttl_seconds=30)
    assert not db.try_acquire_turn_lease("lineage", "two", ttl_seconds=30)
    assert not db.release_turn_lease("lineage", "two")
    assert db.release_turn_lease("lineage", "one")

    db.create_session("s1", "cli", model="main", system_prompt="shared prompt")
    db.create_session("s2", "cli", model="main", system_prompt="shared prompt")
    assert db.get_session("s1")["system_prompt"] == "shared prompt"
    assert db._conn.execute("SELECT COUNT(*) FROM system_prompts").fetchone()[0] == 1

    db.record_model_usage("s1", input_tokens=4, output_tokens=2, api_call_count=1)
    db.record_model_usage("s1", input_tokens=3, output_tokens=1, api_call_count=1)
    usage = db.list_model_usage("s1")
    assert usage[0]["input_tokens"] == 7
    assert usage[0]["api_call_count"] == 2

    db.upsert_async_delegation(
        {"delegation_id": "d1", "state": "complete", "result": {"ok": True}}
    )
    db.upsert_async_delegation(
        {"delegation_id": "d1", "state": "complete", "result": {"ok": True}}
    )
    assert db.get_async_delegation("d1")["result"] == {"ok": True}
    assert db.claim_async_delegation_delivery("d1", "claim")
    assert not db.claim_async_delegation_delivery("d1", "other")
    assert db.complete_async_delegation_delivery("d1", "claim")
    db.close()

    reopened = SessionDB(path)
    assert reopened._conn.execute("SELECT version FROM schema_version").fetchone()[0] == SCHEMA_VERSION
    assert reopened.get_async_delegation("d1")["delivery_state"] == "delivered"
    reopened.close()


def test_legacy_temporary_db_migrates_once_and_gets_backup(tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL)
    conn.execute("INSERT INTO schema_version(version) VALUES (14)")
    conn.execute(
        "INSERT INTO sessions(id, source, system_prompt, started_at) VALUES (?, ?, ?, ?)",
        ("legacy", "cli", "inline prompt", 1.0),
    )
    conn.commit()
    conn.close()

    db = SessionDB(path)
    backup = db.migration_backup_path
    assert backup is not None and backup.exists()
    assert db.get_session("legacy")["system_prompt"] == "inline prompt"
    assert db._conn.execute("SELECT version FROM schema_version").fetchone()[0] == SCHEMA_VERSION
    assert db._conn.execute(
        "SELECT system_prompt FROM sessions WHERE id='legacy'"
    ).fetchone()[0] is None
    db.close()

    db = SessionDB(path)
    assert db.migration_backup_path is None
    assert len(list(tmp_path.glob("legacy.db.pre-*.bak"))) == 1
    db.close()
