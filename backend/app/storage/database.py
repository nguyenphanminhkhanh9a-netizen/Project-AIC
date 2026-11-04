"""SQLite database connection and session management for Project AIC.

Implements ADR-007 and Section 3.5 of Milestone M0:
- Asynchronous SQLite connections using aiosqlite.
- Enforces PRAGMA foreign_keys = ON and WAL journal mode.
- Resolves safe runtime paths and ensures parent directories exist.
- Supports in-memory databases for fast, isolated unit testing.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from app.core.config import settings

logger = logging.getLogger("project_aic.storage")


class DatabaseManager:
    """Manages asynchronous SQLite connections, pragmas, and transaction lifecycles."""

    def __init__(self, db_path: str | None = None) -> None:
        raw_path = db_path if db_path is not None else settings.database_path
        self._raw_path = raw_path
        self._is_memory = raw_path == ":memory:"

        if self._is_memory:
            self._resolved_path = ":memory:"
        else:
            path = Path(raw_path).resolve()
            # Ensure runtime storage directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            self._resolved_path = str(path)

    @property
    def db_path(self) -> str:
        """Return the resolved database path or ':memory:'."""
        return self._resolved_path

    @property
    def is_memory(self) -> bool:
        """Return True if using an in-memory SQLite database."""
        return self._is_memory

    async def connect(self) -> aiosqlite.Connection:
        """Create and configure a new aiosqlite connection with enforced pragmas."""
        conn = await aiosqlite.connect(self._resolved_path)
        conn.row_factory = aiosqlite.Row

        # Enforce foreign key constraints
        await conn.execute("PRAGMA foreign_keys = ON;")

        # Enable Write-Ahead Logging (WAL) for disk-backed databases for concurrency
        if not self._is_memory:
            await conn.execute("PRAGMA journal_mode = WAL;")
            await conn.execute("PRAGMA synchronous = NORMAL;")

        return conn

    @asynccontextmanager
    async def get_connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """Context manager yielding a managed connection, closed upon exit."""
        conn = await self.connect()
        try:
            yield conn
        finally:
            await conn.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """Context manager executing inside an automatic commit/rollback transaction."""
        async with self.get_connection() as conn:
            try:
                yield conn
                await conn.commit()
            except Exception as exc:
                logger.warning("Transaction rolled back due to error: %s", exc)
                await conn.rollback()
                raise


# Default singleton instance using application settings
db_manager = DatabaseManager()
