"""Storage package for Project AIC Backend Sidecar.

Implements SQLite async connection manager, versioned schema migrations,
repositories for characters, conversations, and messages, and character pack loader.
"""

from app.storage.character_pack import CharacterPackLoader
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
    "CharacterPackLoader",
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
