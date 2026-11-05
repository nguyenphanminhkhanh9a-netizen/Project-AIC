"""Suite 2: Task queue, concurrency governor, in-flight deduplication, and DLQ tests.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.character import (
    AnchorType,
    AssetDefinition,
    CharacterManifest,
    FallbackConfig,
    Resolution,
    SpriteAlignment,
)
from app.domain.pipeline import PipelineTask
from app.pipeline.config import PipelineConfig
from app.pipeline.worker import PipelineWorker
from tests.pipeline.conftest import create_synthetic_character_rgba, to_png_bytes


@pytest.mark.asyncio
async def test_queue_fifo_execution_order() -> None:
    """Verifies that the task queue processes tasks in strict FIFO order."""
    config = PipelineConfig(worker_concurrency=1)
    worker = PipelineWorker(config=config)

    processed_ids: list[str] = []

    async def fake_process(task: PipelineTask) -> MagicMock:
        processed_ids.append(task.task_id)
        await asyncio.sleep(0.01)
        res = MagicMock()
        res.success = True
        return res

    worker.process_task = fake_process  # type: ignore[method-assign]

    tasks = [
        PipelineTask(
            task_id=f"task_{i}",
            character_id="miku_nakano",
            target_state="idle",
            target_emotion=f"emotion_{i}",
            target_outfit="school_uniform",
            source_url=f"https://example.com/art_{i}.png",
            source_provider="test",
        )
        for i in range(3)
    ]

    for t in tasks:
        assert await worker.enqueue(t) is True

    await worker.start()
    await asyncio.sleep(0.1)
    await worker.stop()

    assert processed_ids == ["task_0", "task_1", "task_2"]


@pytest.mark.asyncio
async def test_inflight_deduplication_lock() -> None:
    """Verifies that duplicate tasks for the same visual target are dropped."""
    config = PipelineConfig(worker_concurrency=1)
    worker = PipelineWorker(config=config)

    task_a = PipelineTask(
        task_id="task_a",
        character_id="miku_nakano",
        target_state="idle",
        target_emotion="pout",
        target_outfit="school_uniform",
        source_url="https://example.com/miku_pout_1.png",
        source_provider="pinterest",
    )

    task_b = PipelineTask(
        task_id="task_b",
        character_id="miku_nakano",
        target_state="idle",
        target_emotion="pout",
        target_outfit="school_uniform",
        source_url="https://example.com/miku_pout_2.png",
        source_provider="safebooru",
    )

    # First enqueue succeeds
    assert await worker.enqueue(task_a) is True
    # Duplicate enqueue for identical target is dropped
    assert await worker.enqueue(task_b) is False


@pytest.mark.asyncio
async def test_concurrency_governor_sequential() -> None:
    """Verifies that the semaphore clamps active processing tasks to worker_concurrency."""
    config = PipelineConfig(worker_concurrency=1)
    worker = PipelineWorker(config=config)

    active_count = 0
    max_active = 0

    async def monitored_process(task: PipelineTask) -> MagicMock:
        nonlocal active_count, max_active
        active_count += 1
        max_active = max(max_active, active_count)
        await asyncio.sleep(0.02)
        active_count -= 1
        res = MagicMock()
        res.success = True
        return res

    worker.process_task = monitored_process  # type: ignore[method-assign]

    for i in range(4):
        t = PipelineTask(
            task_id=f"task_{i}",
            character_id="miku_nakano",
            target_state="idle",
            target_emotion=f"emotion_{i}",
            target_outfit="school_uniform",
            source_url=f"https://example.com/{i}.png",
            source_provider="test",
        )
        await worker.enqueue(t)

    await worker.start()
    await asyncio.sleep(0.15)
    await worker.stop()

    assert max_active == 1


@pytest.mark.asyncio
async def test_dead_letter_queue_on_fatal_error(tmp_path: Path) -> None:
    """Verifies that an unhandled processing exception logs task to DLQ."""
    dlq_file = tmp_path / "dlq.json"
    config = PipelineConfig(dlq_path=dlq_file, worker_concurrency=1)
    worker = PipelineWorker(config=config)

    # Mock downloader to raise fatal error
    worker.downloader.download = AsyncMock(side_effect=RuntimeError("Corrupt payload stream"))  # type: ignore[method-assign]

    task = PipelineTask(
        task_id="fatal_task_1",
        character_id="miku_nakano",
        target_state="idle",
        target_emotion="cry",
        target_outfit="school_uniform",
        source_url="https://example.com/bad.png",
        source_provider="test",
    )

    result = await worker.process_task(task)
    assert result.success is False
    assert result.status == "failed"

    dlq_entries = worker.get_dlq_tasks()
    assert len(dlq_entries) == 1
    assert dlq_entries[0]["task_id"] == "fatal_task_1"
    assert dlq_entries[0]["error_type"] == "RuntimeError"
    assert "Corrupt payload stream" in dlq_entries[0]["error_message"]
    assert dlq_file.is_file()


@pytest.mark.asyncio
async def test_worker_fault_isolation(tmp_path: Path) -> None:
    """Verifies that a failing task does not prevent subsequent tasks from executing."""
    config = PipelineConfig(dlq_path=tmp_path / "dlq.json", worker_concurrency=1)
    worker = PipelineWorker(config=config)

    processed: list[str] = []

    async def flappy_process(task: PipelineTask) -> MagicMock:
        if task.task_id == "failing_task":
            raise ValueError("Poison pill calculation error")
        processed.append(task.task_id)
        res = MagicMock()
        res.success = True
        return res

    worker.process_task = flappy_process  # type: ignore[method-assign]

    task1 = PipelineTask(
        task_id="failing_task",
        character_id="miku_nakano",
        target_state="idle",
        target_emotion="bad",
        target_outfit="school_uniform",
        source_url="https://example.com/1.png",
        source_provider="test",
    )
    task2 = PipelineTask(
        task_id="succeeding_task",
        character_id="miku_nakano",
        target_state="idle",
        target_emotion="good",
        target_outfit="school_uniform",
        source_url="https://example.com/2.png",
        source_provider="test",
    )

    await worker.enqueue(task1)
    await worker.enqueue(task2)

    await worker.start()
    await asyncio.sleep(0.08)
    await worker.stop()

    assert processed == ["succeeding_task"]


@pytest.mark.asyncio
async def test_worker_end_to_end_success(tmp_path: Path) -> None:
    """Verifies full successful pipeline task execution through PipelineWorker."""
    # Setup test character pack directory
    pack_dir = tmp_path / "characters" / "miku_nakano"
    pack_dir.mkdir(parents=True)
    (pack_dir / "assets" / "core").mkdir(parents=True)
    (pack_dir / "assets" / "dynamic").mkdir(parents=True)

    baseline_rgba = create_synthetic_character_rgba(emotion="neutral")
    baseline_path = pack_dir / "assets" / "core" / "idle_neutral.webp"
    baseline_rgba.save(baseline_path, format="WEBP")

    manifest = CharacterManifest(
        schema_version="1.0",
        character_id="miku_nakano",
        display_name="Nakano Miku",
        default_outfit="school_uniform",
        fallbacks=FallbackConfig(default_asset_id="miku_core_idle_neutral"),
        assets=[
            AssetDefinition(
                asset_id="miku_core_idle_neutral",
                path="assets/core/idle_neutral.webp",
                format="webp",
                state="idle",
                emotion="neutral",
                outfit="school_uniform",
                resolution=Resolution(width=1024, height=1536),
                anchor=SpriteAlignment(anchor_type=AnchorType.BOTTOM_CENTER),
                is_core=True,
                status="ready",
            )
        ],
    )
    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    config = PipelineConfig(
        characters_dir=tmp_path / "characters",
        dlq_path=tmp_path / "dlq.json",
    )
    worker = PipelineWorker(config=config)

    # Mock downloader returning valid character image bytes
    cand_img = create_synthetic_character_rgba(emotion="happy")
    worker.downloader.download = AsyncMock(return_value=to_png_bytes(cand_img))  # type: ignore[method-assign]

    task = PipelineTask(
        character_id="miku_nakano",
        target_state="idle",
        target_emotion="happy",
        target_outfit="school_uniform",
        source_url="https://example.com/happy.png",
        source_provider="safebooru",
    )

    result = await worker.process_task(task)
    assert result.success is True
    assert result.status == "ready"
    assert result.asset_id == "miku_nakano_school_uniform_idle_happy"

    # Verify manifest on disk now contains the new asset
    updated_manifest = CharacterManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    assert len(updated_manifest.assets) == 2
    new_asset = next(a for a in updated_manifest.assets if a.asset_id == result.asset_id)
    assert new_asset.status == "ready"
    assert (pack_dir / new_asset.path).is_file()
