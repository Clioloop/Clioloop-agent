"""Additive state schema and migration registry for :mod:`clio_state`.

The legacy schema through v20 remains in ``clio_state.py`` for import
compatibility.  Phase-1 features are deliberately additive and live here so an
older state.db can be upgraded without rebuilding or rewriting conversation
history.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable, Iterable, Tuple

LEGACY_SCHEMA_VERSION = 14
SCHEMA_VERSION = 20

PHASE1_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS gateway_routing (
    scope TEXT NOT NULL DEFAULT 'default',
    session_key TEXT NOT NULL,
    source_json TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (scope, session_key)
);
CREATE INDEX IF NOT EXISTS idx_gateway_routing_scope_updated
    ON gateway_routing(scope, updated_at);

CREATE TABLE IF NOT EXISTS session_turn_leases (
    session_key TEXT PRIMARY KEY,
    holder TEXT NOT NULL,
    acquired_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_turn_leases_expires
    ON session_turn_leases(expires_at);

CREATE TABLE IF NOT EXISTS session_model_usage (
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    billing_provider TEXT NOT NULL DEFAULT '',
    billing_base_url TEXT NOT NULL DEFAULT '',
    billing_mode TEXT NOT NULL DEFAULT '',
    task TEXT NOT NULL DEFAULT '',
    api_call_count INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    reasoning_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd REAL NOT NULL DEFAULT 0,
    actual_cost_usd REAL NOT NULL DEFAULT 0,
    cost_status TEXT,
    cost_source TEXT,
    first_seen REAL,
    last_seen REAL,
    PRIMARY KEY (
        session_id, model, billing_provider, billing_base_url,
        billing_mode, task
    )
);
CREATE INDEX IF NOT EXISTS idx_session_model_usage_session
    ON session_model_usage(session_id);

CREATE TABLE IF NOT EXISTS system_prompts (
    hash TEXT PRIMARY KEY,
    prompt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS async_delegations (
    delegation_id TEXT PRIMARY KEY,
    origin_session TEXT NOT NULL DEFAULT '',
    origin_ui_session_id TEXT NOT NULL DEFAULT '',
    parent_session_id TEXT,
    origin_session_id TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL,
    dispatched_at REAL NOT NULL,
    completed_at REAL,
    updated_at REAL NOT NULL,
    event_json TEXT,
    result_json TEXT,
    task_json TEXT,
    delivery_state TEXT NOT NULL DEFAULT 'pending',
    delivery_attempts INTEGER NOT NULL DEFAULT 0,
    delivered_at REAL,
    owner_pid INTEGER,
    owner_started_at INTEGER,
    delivery_claim TEXT,
    delivery_claimed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_async_delegations_delivery
    ON async_delegations(delivery_state, updated_at);
CREATE INDEX IF NOT EXISTS idx_async_delegations_origin
    ON async_delegations(origin_session, origin_ui_session_id);
"""


@dataclass(frozen=True)
class StateMigration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


def _ensure_routing_scope(conn: sqlite3.Connection) -> None:
    """Create the profile/tenant-scoped routing index."""
    prefix = PHASE1_SCHEMA_SQL.split(
        "CREATE TABLE IF NOT EXISTS session_turn_leases", 1
    )[0]
    _execute_ddl(conn, prefix)


def _execute_ddl(conn: sqlite3.Connection, sql: str) -> None:
    """Execute simple additive DDL without ``executescript``'s implicit commit."""
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            conn.execute(statement)


def _ensure_turn_leases(conn: sqlite3.Connection) -> None:
    start = PHASE1_SCHEMA_SQL.index("CREATE TABLE IF NOT EXISTS session_turn_leases")
    end = PHASE1_SCHEMA_SQL.index("CREATE TABLE IF NOT EXISTS session_model_usage")
    _execute_ddl(conn, PHASE1_SCHEMA_SQL[start:end])


def _ensure_all_phase1(conn: sqlite3.Connection) -> None:
    _execute_ddl(conn, PHASE1_SCHEMA_SQL)


def _ensure_prompt_column(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
    if "system_prompt_hash" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN system_prompt_hash TEXT")


def _ensure_session_portability(conn: sqlite3.Connection) -> None:
    """Add durable metadata columns without rebuilding conversation rows."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
    for name, declaration in (
        ("pinned", "INTEGER NOT NULL DEFAULT 0"),
        ("hidden", "INTEGER NOT NULL DEFAULT 0"),
        ("last_read_at", "REAL"),
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE sessions ADD COLUMN {name} {declaration}")


# Every callback is safe after the full current schema has already been ensured.
# This is intentional: new databases run CREATE IF NOT EXISTS once, while old
# databases advance one durable version at a time.
MIGRATIONS: Tuple[StateMigration, ...] = (
    StateMigration(15, "scoped-gateway-routing", _ensure_routing_scope),
    StateMigration(16, "session-turn-leases", _ensure_turn_leases),
    StateMigration(17, "per-session-model-usage", _ensure_all_phase1),
    StateMigration(18, "content-addressed-system-prompts", _ensure_prompt_column),
    StateMigration(19, "durable-async-delegations", _ensure_all_phase1),
    StateMigration(20, "session-portability-metadata", _ensure_session_portability),
)


def validate_migrations(migrations: Iterable[StateMigration] = MIGRATIONS) -> None:
    versions = [migration.version for migration in migrations]
    expected = list(range(LEGACY_SCHEMA_VERSION + 1, SCHEMA_VERSION + 1))
    if versions != expected:
        raise ValueError(
            f"state migration registry must cover {expected}, got {versions}"
        )


def apply_additive_migrations(
    conn: sqlite3.Connection,
    current_version: int,
    *,
    target_version: int = SCHEMA_VERSION,
) -> int:
    """Apply and stamp each pending migration in one caller-owned transaction."""
    validate_migrations()
    version = current_version
    for migration in MIGRATIONS:
        if version < migration.version <= target_version:
            migration.apply(conn)
            conn.execute("UPDATE schema_version SET version = ?", (migration.version,))
            version = migration.version
    return version


__all__ = [
    "LEGACY_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "PHASE1_SCHEMA_SQL",
    "MIGRATIONS",
    "StateMigration",
    "apply_additive_migrations",
    "validate_migrations",
]
