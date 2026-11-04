"""Data access repositories for SQLite storage.

Corresponds to Section 9.1 of docs/AIC_ARCHITECTURE_v0.5.md and Section 3.5 of Milestone M0:
- CharacterRepository: Manages character definition entries.
- ConversationRepository: Manages session metadata, timestamps, and status.
- MessageRepository: Manages turn-by-turn text, role, locale, and subtitle/emotion metadata JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import aiosqlite


@dataclass
class CharacterRecord:
    """Database representation of an installed or bundled character pack."""

    id: str
    display_name: str
    pack_version: str = "1.0"
    config_path: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class ConversationRecord:
    """Database representation of an active or archived conversation session."""

    id: str
    character_id: str
    title: str | None = None
    status: str = "active"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class MessageRecord:
    """Database representation of a turn message (user or assistant)."""

    id: str
    conversation_id: str
    role: str
    text: str
    locale: str = "ja-JP"
    metadata_json: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class CharacterRepository:
    """CRUD repository for characters table."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def create(self, character: CharacterRecord) -> CharacterRecord:
        """Insert a new character record."""
        await self.conn.execute(
            """
            INSERT INTO characters (id, display_name, pack_version, config_path, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (
                character.id,
                character.display_name,
                character.pack_version,
                character.config_path,
                character.created_at,
            ),
        )
        await self.conn.commit()
        return character

    async def get(self, character_id: str) -> CharacterRecord | None:
        """Fetch a character by ID."""
        cursor = await self.conn.execute(
            "SELECT id, display_name, pack_version, config_path, created_at FROM characters WHERE id = ?;",
            (character_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return CharacterRecord(
            id=row["id"],
            display_name=row["display_name"],
            pack_version=row["pack_version"],
            config_path=row["config_path"],
            created_at=row["created_at"],
        )

    async def list_all(self) -> list[CharacterRecord]:
        """List all characters."""
        cursor = await self.conn.execute(
            "SELECT id, display_name, pack_version, config_path, created_at FROM characters ORDER BY created_at ASC;"
        )
        rows = await cursor.fetchall()
        return [
            CharacterRecord(
                id=r["id"],
                display_name=r["display_name"],
                pack_version=r["pack_version"],
                config_path=r["config_path"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    async def delete(self, character_id: str) -> bool:
        """Delete a character by ID (cascades to conversations/messages)."""
        cursor = await self.conn.execute(
            "DELETE FROM characters WHERE id = ?;",
            (character_id,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0


class ConversationRepository:
    """CRUD repository for conversations table."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def create(self, conversation: ConversationRecord) -> ConversationRecord:
        """Insert a new conversation record."""
        await self.conn.execute(
            """
            INSERT INTO conversations (id, character_id, title, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                conversation.id,
                conversation.character_id,
                conversation.title,
                conversation.status,
                conversation.created_at,
                conversation.updated_at,
            ),
        )
        await self.conn.commit()
        return conversation

    async def get(self, conversation_id: str) -> ConversationRecord | None:
        """Fetch a conversation by ID."""
        cursor = await self.conn.execute(
            """
            SELECT id, character_id, title, status, created_at, updated_at
            FROM conversations WHERE id = ?;
            """,
            (conversation_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return ConversationRecord(
            id=row["id"],
            character_id=row["character_id"],
            title=row["title"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def list_conversations(
        self,
        character_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ConversationRecord]:
        """List conversations with optional character filter and pagination."""
        if character_id:
            cursor = await self.conn.execute(
                """
                SELECT id, character_id, title, status, created_at, updated_at
                FROM conversations
                WHERE character_id = ?
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?;
                """,
                (character_id, limit, offset),
            )
        else:
            cursor = await self.conn.execute(
                """
                SELECT id, character_id, title, status, created_at, updated_at
                FROM conversations
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?;
                """,
                (limit, offset),
            )
        rows = await cursor.fetchall()
        return [
            ConversationRecord(
                id=r["id"],
                character_id=r["character_id"],
                title=r["title"],
                status=r["status"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    async def update_status(self, conversation_id: str, status: str) -> ConversationRecord | None:
        """Update conversation status (e.g. 'archived', 'active') and refreshed timestamp."""
        now_iso = datetime.now(UTC).isoformat()
        cursor = await self.conn.execute(
            """
            UPDATE conversations
            SET status = ?, updated_at = ?
            WHERE id = ?;
            """,
            (status, now_iso, conversation_id),
        )
        await self.conn.commit()
        if cursor.rowcount == 0:
            return None
        return await self.get(conversation_id)

    async def update_title(self, conversation_id: str, title: str) -> ConversationRecord | None:
        """Update conversation title."""
        now_iso = datetime.now(UTC).isoformat()
        cursor = await self.conn.execute(
            """
            UPDATE conversations
            SET title = ?, updated_at = ?
            WHERE id = ?;
            """,
            (title, now_iso, conversation_id),
        )
        await self.conn.commit()
        if cursor.rowcount == 0:
            return None
        return await self.get(conversation_id)

    async def delete(self, conversation_id: str) -> bool:
        """Delete a conversation and all cascading child messages."""
        cursor = await self.conn.execute(
            "DELETE FROM conversations WHERE id = ?;",
            (conversation_id,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0


class MessageRepository:
    """CRUD repository for messages table."""

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def create(self, message: MessageRecord) -> MessageRecord:
        """Insert a message record with metadata serialized to JSON."""
        metadata_str = json.dumps(message.metadata_json, ensure_ascii=False)
        await self.conn.execute(
            """
            INSERT INTO messages (id, conversation_id, role, text, locale, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                message.id,
                message.conversation_id,
                message.role,
                message.text,
                message.locale,
                metadata_str,
                message.created_at,
            ),
        )
        # Touch parent conversation's updated_at timestamp
        await self.conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?;",
            (message.created_at, message.conversation_id),
        )
        await self.conn.commit()
        return message

    async def get(self, message_id: str) -> MessageRecord | None:
        """Fetch a single message by ID."""
        cursor = await self.conn.execute(
            """
            SELECT id, conversation_id, role, text, locale, metadata_json, created_at
            FROM messages WHERE id = ?;
            """,
            (message_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        try:
            meta = json.loads(row["metadata_json"])
        except (json.JSONDecodeError, TypeError):
            meta = {}

        return MessageRecord(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            text=row["text"],
            locale=row["locale"],
            metadata_json=meta,
            created_at=row["created_at"],
        )

    async def list_by_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MessageRecord]:
        """Fetch ordered chronological messages in a conversation."""
        cursor = await self.conn.execute(
            """
            SELECT id, conversation_id, role, text, locale, metadata_json, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
            LIMIT ? OFFSET ?;
            """,
            (conversation_id, limit, offset),
        )
        rows = await cursor.fetchall()
        result: list[MessageRecord] = []
        for r in rows:
            try:
                meta = json.loads(r["metadata_json"])
            except (json.JSONDecodeError, TypeError):
                meta = {}
            result.append(
                MessageRecord(
                    id=r["id"],
                    conversation_id=r["conversation_id"],
                    role=r["role"],
                    text=r["text"],
                    locale=r["locale"],
                    metadata_json=meta,
                    created_at=r["created_at"],
                )
            )
        return result

    async def count_by_conversation(self, conversation_id: str) -> int:
        """Count total messages belonging to a conversation."""
        cursor = await self.conn.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id = ?;",
            (conversation_id,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def delete(self, message_id: str) -> bool:
        """Delete an individual message by ID."""
        cursor = await self.conn.execute(
            "DELETE FROM messages WHERE id = ?;",
            (message_id,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0
