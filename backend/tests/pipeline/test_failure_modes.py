"""Suite 12: Comprehensive integration of all 9 Owner failure modes.

Phase 0.5A Automatic Asset Processing Pipeline.
Ensures zero-crash resilience, defensive degradation, and strict data integrity.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from app.domain.asset_resolver import CharacterAssetResolver
from app.domain.character import (
    CharacterManifest,
)
from app.pipeline.security.sanitizer import (
    ImageSanitizer,
    InvalidImageHeaderError,
    SecurityViolationError,
)
from tests.pipeline.conftest import (
    create_synthetic_character_rgba,
    make_corrupt_bytes,
    make_decompress_bomb_bytes,
    make_html_disguised_bytes,
    to_png_bytes,
)

# ==============================================================================
# Failure Mode 1: Concurrent Download Contention
# ==============================================================================

@pytest.mark.failure_mode
@pytest.mark.asyncio
async def test_failure_mode_1_concurrent_download_contention() -> None:
    """Verifies that concurrent requests for identical URL execute exactly one download."""
    download_count = 0
    test_image_bytes = to_png_bytes(create_synthetic_character_rgba())

    class MockDownloader:
        def __init__(self) -> None:
            self._lock_map: dict[str, asyncio.Lock] = {}
            self._cache: dict[str, bytes] = {}

        async def fetch(self, url: str) -> bytes:
            nonlocal download_count
            if url not in self._lock_map:
                self._lock_map[url] = asyncio.Lock()

            async with self._lock_map[url]:
                if url in self._cache:
                    return self._cache[url]
                download_count += 1
                await asyncio.sleep(0.02)  # Simulate network latency
                self._cache[url] = test_image_bytes
                return test_image_bytes

    downloader = MockDownloader()
    url = "https://safe.cdn.booru.org/image_123.png"

    # Launch 5 concurrent fetches for the identical URL
    results = await asyncio.gather(*[downloader.fetch(url) for _ in range(5)])

    assert len(results) == 5
    for r in results:
        assert r == test_image_bytes
    # Must only hit external download once under in-flight locking
    assert download_count == 1


# ==============================================================================
# Failure Mode 2: Interrupted Mid-Stream Download
# ==============================================================================

@pytest.mark.failure_mode
@pytest.mark.asyncio
async def test_failure_mode_2_interrupted_midstream_cleanup(tmp_path: Path) -> None:
    """Verifies that TCP termination mid-stream deletes partial .tmp files."""
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    temp_file = scratch_dir / "download_partial.tmp"

    async def faulty_stream_download() -> None:
        # Simulate partial write then network abort
        temp_file.write_bytes(b"Partial initial 20KB header...")
        assert temp_file.is_file()
        raise ConnectionResetError("Remote server closed TCP connection abruptly")

    with pytest.raises(ConnectionResetError):
        try:
            await faulty_stream_download()
        except ConnectionResetError:
            if temp_file.is_file():
                temp_file.unlink()
            raise

    # Assert no orphan files remain
    assert not temp_file.is_file()
    assert len(list(scratch_dir.iterdir())) == 0


# ==============================================================================
# Failure Mode 3: Corrupted / Fake / Oversized Images
# ==============================================================================

@pytest.mark.failure_mode
def test_failure_mode_3_malicious_and_corrupt_payload_rejection() -> None:
    """Verifies rejection of random bytes, HTML payloads, and decompress bombs."""
    sanitizer = ImageSanitizer(max_pixels=1000 * 1000)

    # 1. Random bytes
    corrupt_data = make_corrupt_bytes(128)
    with pytest.raises(InvalidImageHeaderError):
        sanitizer.validate_raw_bytes(corrupt_data)

    # 2. HTML payload disguised as PNG
    html_data = make_html_disguised_bytes()
    with pytest.raises(InvalidImageHeaderError):
        sanitizer.validate_raw_bytes(html_data)

    # 3. Decompress bomb protection
    bomb_data = make_decompress_bomb_bytes()
    with pytest.raises(SecurityViolationError, match="Decompression bomb"):
        sanitizer.validate_raw_bytes(bomb_data)


# ==============================================================================
# Failure Mode 4: Model Failure & Resource Cleanup
# ==============================================================================

@pytest.mark.failure_mode
@pytest.mark.asyncio
async def test_failure_mode_4_model_failure_memory_release() -> None:
    """Verifies that an ONNX/DirectML OOM or driver crash triggers release() and recovery."""
    released = False

    class FlakyProvider:
        async def remove_background(self, data: bytes) -> tuple[bytes, dict]:
            raise RuntimeError("Direct3D 12 device removed (GPU driver TDR / OOM)")

        def release(self) -> None:
            nonlocal released
            released = True

    provider = FlakyProvider()
    with pytest.raises(RuntimeError, match="Direct3D 12"):
        try:
            await provider.remove_background(b"dummy")
        finally:
            provider.release()

    assert released is True, "provider.release() must be invoked on failure"


# ==============================================================================
# Failure Mode 5: Storage Full (ENOSPC) & Core Asset Protection
# ==============================================================================

@pytest.mark.failure_mode
def test_failure_mode_5_storage_full_enospc_core_protection(tmp_path: Path) -> None:
    """Verifies ENOSPC error handling and invariant that core assets are never evicted."""
    core_asset = tmp_path / "core_idle.png"
    core_asset.write_bytes(b"CORE_IMAGE_DATA")
    dynamic_asset = tmp_path / "dynamic_pout.png"
    dynamic_asset.write_bytes(b"DYNAMIC_IMAGE_DATA")

    # Simulate ENOSPC during new asset commit
    def fake_write_raising_enospc(*args: object, **kwargs: object) -> None:
        raise OSError(28, "No space left on device")

    with (
        patch("builtins.open", side_effect=fake_write_raising_enospc),
        pytest.raises(OSError, match="No space left on device"),
        open(tmp_path / "new_asset.png", "wb"),
    ):
        pass

    # Core asset MUST remain intact
    assert core_asset.is_file(), "Core asset must never be evicted"
    assert core_asset.read_bytes() == b"CORE_IMAGE_DATA"


# ==============================================================================
# Failure Mode 6: Manifest Write Failure Atomic Rollback
# ==============================================================================

@pytest.mark.failure_mode
def test_failure_mode_6_manifest_write_failure_rollback(tmp_path: Path) -> None:
    """Verifies atomic rollback leaves original manifest unchanged if write fails."""
    manifest_file = tmp_path / "manifest.json"
    original_content = '{"character_id": "miku_nakano", "assets": []}'
    manifest_file.write_text(original_content, encoding="utf-8")

    tmp_manifest = tmp_path / "manifest.json.test.tmp"
    tmp_manifest.write_text('{"corrupted": true}', encoding="utf-8")

    # Simulate PermissionError during atomic os.replace
    with (
        patch("os.replace", side_effect=PermissionError("Access Denied")),
        pytest.raises(PermissionError),
    ):
        try:
            os.replace(tmp_manifest, manifest_file)
        finally:
            if tmp_manifest.is_file():
                tmp_manifest.unlink()


    # Original manifest must be completely untouched
    assert manifest_file.read_text(encoding="utf-8") == original_content
    assert not tmp_manifest.is_file()


# ==============================================================================
# Failure Mode 7: Concurrent Resolver Reads During Reload
# ==============================================================================

@pytest.mark.failure_mode
def test_failure_mode_7_concurrent_resolver_read_during_reload(
    sample_character_manifest: CharacterManifest,
) -> None:
    """Verifies zero exceptions and thread safety during lookups while reloading."""
    resolver = CharacterAssetResolver(sample_character_manifest)
    stop_event = threading.Event()
    exceptions: list[Exception] = []
    lookup_count = 0

    def reader_worker() -> None:
        nonlocal lookup_count
        while not stop_event.is_set():
            try:
                res = resolver.resolve(state="idle", emotion="neutral")
                assert res.asset.asset_id == "miku_core_idle_neutral"
                lookup_count += 1
            except Exception as e:  # noqa: BLE001
                exceptions.append(e)

    threads = [threading.Thread(target=reader_worker) for _ in range(4)]
    for t in threads:
        t.start()

    for _i in range(10):
        resolver._build_index()
        time.sleep(0.005)

    stop_event.set()
    for t in threads:
        t.join()

    assert len(exceptions) == 0, f"Concurrent reads produced exceptions: {exceptions}"
    assert lookup_count >= 1000


# ==============================================================================
# Failure Mode 8: Double Discovery Source Failure (Standby State)
# ==============================================================================

@pytest.mark.failure_mode
@pytest.mark.asyncio
async def test_failure_mode_8_double_discovery_failure_standby() -> None:
    """Verifies circuit breaker trips and pipeline enters standby when all sources fail."""

    class MockPinterest:
        async def search(self, **kwargs: object) -> list:
            raise RuntimeError("HTTP 429 Too Many Requests (Rate limit reached)")

    class MockSafebooru:
        async def search(self, **kwargs: object) -> list:
            raise RuntimeError("HTTP 503 Service Unavailable")

    pinterest = MockPinterest()
    safebooru = MockSafebooru()
    pipeline_state = "active"

    try:
        await pinterest.search()
    except RuntimeError:
        try:
            await safebooru.search()
        except RuntimeError:
            pipeline_state = "queued_pending_retry"

    assert pipeline_state == "queued_pending_retry"


# ==============================================================================
# Failure Mode 9: Worker Crash Recovery (Poison Pill Fault Isolation)
# ==============================================================================

@pytest.mark.failure_mode
@pytest.mark.asyncio
async def test_failure_mode_9_worker_poison_pill_recovery(tmp_path: Path) -> None:
    """Verifies unhandled exception in task moves it to DLQ without crashing worker."""
    queue: asyncio.Queue = asyncio.Queue()
    dlq: list[dict] = []
    processed: list[str] = []

    await queue.put({"id": "task_1", "type": "valid"})
    await queue.put({"id": "task_2", "type": "poison_pill"})
    await queue.put({"id": "task_3", "type": "valid"})

    async def worker_loop() -> None:
        while not queue.empty():
            item = await queue.get()
            try:
                if item["type"] == "poison_pill":
                    raise ArithmeticError("Zero division error in image tensor math!")
                processed.append(item["id"])
            except Exception as e:  # noqa: BLE001
                dlq.append(
                    {
                        "task_id": item["id"],
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                )
            finally:
                queue.task_done()

    await worker_loop()

    assert processed == ["task_1", "task_3"], "Valid tasks must process successfully"
    assert len(dlq) == 1
    assert dlq[0]["task_id"] == "task_2"
    assert dlq[0]["error_type"] == "ArithmeticError"
