"""Versioned SQLite schema migrations for Project AIC.

Corresponds to Section 9.1 of docs/AIC_ARCHITECTURE_v0.5.md and Section 3.5 of Milestone M0.
Tracks applied versions in `schema_migrations` and guarantees idempotency.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import aiosqlite

logger = logging.getLogger("project_aic.storage.migrations")

# Migration definition tuple: (version, name, sql_or_callable)
MIGRATION_V1_SQL = """
-- Core character definition table
CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    pack_version TEXT NOT NULL DEFAULT '1.0',
    config_path TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

-- Conversation sessions table
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conversations_character_id ON conversations (character_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations (updated_at);

-- Messages per conversation table
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    locale TEXT NOT NULL DEFAULT 'ja-JP',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages (created_at);
"""


MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "001_initial_schema", MIGRATION_V1_SQL),
]


async def ensure_migrations_table(conn: aiosqlite.Connection) -> None:
    """Ensure the schema_migrations ledger table exists."""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
        """
    )
    await conn.commit()


async def get_applied_versions(conn: aiosqlite.Connection) -> set[int]:
    """Retrieve all migration version numbers that have already been applied."""
    await ensure_migrations_table(conn)
    cursor = await conn.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
    rows = await cursor.fetchall()
    return {int(row[0]) for row in rows}


async def get_current_version(conn: aiosqlite.Connection) -> int:
    """Retrieve the highest migration version applied, or 0 if none."""
    applied = await get_applied_versions(conn)
    return max(applied) if applied else 0


async def run_migrations(conn: aiosqlite.Connection) -> int:
    """Apply all pending migrations in ascending order idempotently.

    Returns the latest applied schema version.
    """
    await ensure_migrations_table(conn)
    applied = await get_applied_versions(conn)

    for version, name, sql in MIGRATIONS:
        if version not in applied:
            logger.info("Applying database migration V%d: %s", version, name)
            # Execute migration DDL statements
            await conn.executescript(sql)

            # Record migration in ledger
            now_iso = datetime.now(UTC).isoformat()
            await conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
                (version, name, now_iso),
            )
            await conn.commit()
            applied.add(version)
            logger.info("Migration V%d applied successfully.", version)
        else:
            logger.debug("Migration V%d (%s) already applied, skipping.", version, name)

    return max(applied) if applied else 0
