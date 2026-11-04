"""Unit tests for SQLite database connection, migrations, and repositories.

Verifies acceptance criteria for Milestone M0 / Task 0.3.
"""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import aiosqlite
import pytest

from app.storage.database import DatabaseManager
from app.storage.migrations import (
    ensure_migrations_table,
    get_applied_versions,
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


@pytest.fixture
async def memory_db() -> DatabaseManager:
    """Fixture providing an isolated in-memory DatabaseManager."""
    return DatabaseManager(db_path=":memory:")


@pytest.fixture
async def migrated_db(memory_db: DatabaseManager) -> AsyncIterator[aiosqlite.Connection]:
    """Fixture providing an active in-memory connection with migrations pre-applied."""
    conn = await memory_db.connect()
    await run_migrations(conn)
    yield conn
    await conn.close()


class TestDatabaseManager:
    """Tests for DatabaseManager connection, pragmas, and transaction semantics."""

    async def test_in_memory_connection_pragmas(self, memory_db: DatabaseManager) -> None:
        assert memory_db.is_memory is True
        async with memory_db.get_connection() as conn:
            cursor = await conn.execute("PRAGMA foreign_keys;")
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == 1  # foreign keys must be ON

    async def test_filesystem_path_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "nested" / "test.db")
            db = DatabaseManager(db_path=db_path)
            assert db.is_memory is False

            async with db.get_connection() as conn:
                cursor = await conn.execute("PRAGMA journal_mode;")
                row = await cursor.fetchone()
                assert row is not None
                assert row[0].lower() == "wal"

            assert Path(db_path).exists()

    async def test_transaction_commit(self, memory_db: DatabaseManager) -> None:
        async with memory_db.get_connection() as conn:
            await conn.execute("CREATE TABLE test_tx (id INT PRIMARY KEY, val TEXT);")
            await conn.commit()

            # Insert inside successful transaction
            await conn.execute("INSERT INTO test_tx (id, val) VALUES (?, ?);", (1, "committed"))
            await conn.commit()

            cursor = await conn.execute("SELECT val FROM test_tx WHERE id = 1;")
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "committed"

    async def test_transaction_rollback_on_error(self, memory_db: DatabaseManager) -> None:
        # Pre-create table
        conn = await memory_db.connect()
        await conn.execute("CREATE TABLE test_rollback (id INT PRIMARY KEY, val TEXT);")
        await conn.commit()

        # Attempt to insert, then simulate error inside transaction
        try:
            async with conn:
                await conn.execute("INSERT INTO test_rollback (id, val) VALUES (?, ?);", (1, "temp"))
                raise RuntimeError("Simulated failure to trigger rollback")
        except RuntimeError:
            pass

        cursor = await conn.execute("SELECT COUNT(*) FROM test_rollback;")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 0
        await conn.close()


class TestMigrations:
    """Tests for schema migration execution and idempotency."""

    async def test_migrations_table_created(self, memory_db: DatabaseManager) -> None:
        async with memory_db.get_connection() as conn:
            await ensure_migrations_table(conn)
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations';"
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "schema_migrations"

    async def test_run_migrations_creates_tables(self, memory_db: DatabaseManager) -> None:
        async with memory_db.get_connection() as conn:
            version = await run_migrations(conn)
            assert version == 1
            assert await get_current_version(conn) == 1

            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('characters', 'conversations', 'messages');"
            )
            rows = await cursor.fetchall()
            table_names = {r[0] for r in rows}
            assert table_names == {"characters", "conversations", "messages"}

    async def test_run_migrations_is_idempotent(self, memory_db: DatabaseManager) -> None:
        async with memory_db.get_connection() as conn:
            v1 = await run_migrations(conn)
            v2 = await run_migrations(conn)
            v3 = await run_migrations(conn)
            assert v1 == 1
            assert v2 == 1
            assert v3 == 1

            versions = await get_applied_versions(conn)
            assert versions == {1}


class TestRepositoriesCRUD:
    """Tests for Character, Conversation, and Message CRUD operations."""

    async def test_character_crud(self, migrated_db: aiosqlite.Connection) -> None:
        repo = CharacterRepository(migrated_db)

        # Create
        char = CharacterRecord(
            id="char_ayumi",
            display_name="Ayumi",
            pack_version="1.0.0",
            config_path="characters/ayumi/manifest.yaml",
        )
        await repo.create(char)

        # Get
        fetched = await repo.get("char_ayumi")
        assert fetched is not None
        assert fetched.id == "char_ayumi"
        assert fetched.display_name == "Ayumi"
        assert fetched.pack_version == "1.0.0"

        # List
        all_chars = await repo.list_all()
        assert len(all_chars) == 1
        assert all_chars[0].id == "char_ayumi"

        # Delete
        deleted = await repo.delete("char_ayumi")
        assert deleted is True
        assert await repo.get("char_ayumi") is None

    async def test_conversation_crud_and_foreign_key(
        self, migrated_db: aiosqlite.Connection
    ) -> None:
        char_repo = CharacterRepository(migrated_db)
        conv_repo = ConversationRepository(migrated_db)

        # FK violation when character does not exist
        invalid_conv = ConversationRecord(
            id=str(uuid4()),
            character_id="non_existent_char",
            title="Chat without character",
        )
        with pytest.raises(sqlite3.IntegrityError):
            await conv_repo.create(invalid_conv)

        # Create valid character first
        await char_repo.create(CharacterRecord(id="char_01", display_name="Aoi"))

        # Create valid conversation
        conv_id = str(uuid4())
        conv = ConversationRecord(
            id=conv_id,
            character_id="char_01",
            title="Evening Chat",
            status="active",
        )
        await conv_repo.create(conv)

        # Get conversation
        fetched = await conv_repo.get(conv_id)
        assert fetched is not None
        assert fetched.title == "Evening Chat"
        assert fetched.status == "active"

        # Update status
        updated = await conv_repo.update_status(conv_id, "archived")
        assert updated is not None
        assert updated.status == "archived"

        # Update title
        updated_title = await conv_repo.update_title(conv_id, "Study Session")
        assert updated_title is not None
        assert updated_title.title == "Study Session"

        # List conversations
        convs = await conv_repo.list_conversations(character_id="char_01")
        assert len(convs) == 1
        assert convs[0].id == conv_id

        # Delete conversation
        deleted = await conv_repo.delete(conv_id)
        assert deleted is True
        assert await conv_repo.get(conv_id) is None

    async def test_message_crud_with_json_metadata(
        self, migrated_db: aiosqlite.Connection
    ) -> None:
        char_repo = CharacterRepository(migrated_db)
        conv_repo = ConversationRepository(migrated_db)
        msg_repo = MessageRepository(migrated_db)

        # Setup character & conversation
        await char_repo.create(CharacterRecord(id="char_02", display_name="Sakura"))
        conv_id = str(uuid4())
        await conv_repo.create(ConversationRecord(id=conv_id, character_id="char_02"))

        # User message
        msg1_id = str(uuid4())
        msg1 = MessageRecord(
            id=msg1_id,
            conversation_id=conv_id,
            role="user",
            text="こんにちは！元気？",
            locale="ja-JP",
            metadata_json={"source": "keyboard_input"},
        )
        await msg_repo.create(msg1)

        # Assistant message with rich subtitle & emotion metadata
        msg2_id = str(uuid4())
        msg2 = MessageRecord(
            id=msg2_id,
            conversation_id=conv_id,
            role="assistant",
            text="うん、元気だよ！今日もよろしくね。",
            locale="ja-JP",
            metadata_json={
                "turn_id": "turn_123",
                "subtitles": {"vi-VN": "Ừ, mình khỏe lắm! Hôm nay cùng cố gắng nhé."},
                "emotion": {"label": "happy", "intensity": 0.8},
                "tts": {"voice_profile_id": "sakura_ja", "enabled": True},
            },
        )
        await msg_repo.create(msg2)

        # Fetch single message
        fetched_msg2 = await msg_repo.get(msg2_id)
        assert fetched_msg2 is not None
        assert fetched_msg2.text == "うん、元気だよ！今日もよろしくね。"
        assert fetched_msg2.metadata_json["turn_id"] == "turn_123"
        assert fetched_msg2.metadata_json["subtitles"]["vi-VN"] == (
            "Ừ, mình khỏe lắm! Hôm nay cùng cố gắng nhé."
        )
        assert fetched_msg2.metadata_json["emotion"]["label"] == "happy"

        # List conversation messages in order
        messages = await msg_repo.list_by_conversation(conv_id)
        assert len(messages) == 2
        assert messages[0].id == msg1_id
        assert messages[1].id == msg2_id

        # Total count
        total_count = await msg_repo.count_by_conversation(conv_id)
        assert total_count == 2

        # Delete single message
        deleted = await msg_repo.delete(msg1_id)
        assert deleted is True
        assert await msg_repo.get(msg1_id) is None
        assert await msg_repo.count_by_conversation(conv_id) == 1

    async def test_cascade_delete_conversation_removes_messages(
        self, migrated_db: aiosqlite.Connection
    ) -> None:
        char_repo = CharacterRepository(migrated_db)
        conv_repo = ConversationRepository(migrated_db)
        msg_repo = MessageRepository(migrated_db)

        await char_repo.create(CharacterRecord(id="char_cascade", display_name="Cascade"))
        conv_id = str(uuid4())
        await conv_repo.create(ConversationRecord(id=conv_id, character_id="char_cascade"))

        msg_id = str(uuid4())
        await msg_repo.create(
            MessageRecord(id=msg_id, conversation_id=conv_id, role="user", text="Test")
        )

        # Delete conversation
        await conv_repo.delete(conv_id)

        # Verify child message was automatically deleted via CASCADE
        assert await msg_repo.get(msg_id) is None
        assert await msg_repo.count_by_conversation(conv_id) == 0
