"""Storage package for Project AIC Backend Sidecar.

Implements SQLite async connection manager, versioned schema migrations,
and repositories for characters, conversations, and messages.
"""

from app.storage.database import DatabaseManager, db_manager
from app.storage.migrations import (
    ensure_migrations_table,
    get_current_version,
    run_migrations,
)
from app.storage.repositories import (
    CharacterRecord,
    CharacterRepository,
    ConversationRecord,
    ConversationRepository,
    MessageRecord,
    MessageRepository,
)

__all__ = [
    "CharacterRecord",
    "CharacterRepository",
    "ConversationRecord",
    "ConversationRepository",
    "DatabaseManager",
    "MessageRecord",
    "MessageRepository",
    "db_manager",
    "ensure_migrations_table",
    "get_current_version",
    "run_migrations",
]
