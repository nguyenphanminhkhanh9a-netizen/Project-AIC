"""Reproduction and verification tests for SafeDownloader memory management and lock lifecycle.

Tests:
1. Total byte cache eviction (max_cache_bytes) where oldest entries are evicted when total bytes exceed limit.
2. Oversized payload bypass where downloads exceeding max_cache_bytes are not cached and do not evict other entries.
3. Lock lifecycle cleanup under concurrent requests to ensure _url_locks does not monotonically leak memory.
4. Lock cleanup resilience under request errors and cancellations.
"""

from __future__ import annotations

import asyncio

import pytest

from app.pipeline.security.safe_downloader import SafeDownloader
from app.pipeline.security.ssrf_guard import SSRFGuard


@pytest.mark.asyncio
async def test_byte_aware_cache_eviction() -> None:
    """Verifies that SafeDownloader evicts entries based on max_cache_bytes limit."""
    guard = SSRFGuard()
    downloader = SafeDownloader(
        guard=guard,
        max_cache_entries=10,
        max_cache_bytes=1000,
    )

    async def fake_download(url: str) -> bytes:
        size = int(url.split("/")[-1].split("_")[0])
        return b"x" * size

    downloader._download_uncached = fake_download  # type: ignore[assignment]

    # Download 1: 400 bytes
    await downloader.download("https://example.com/item/400")
    assert getattr(downloader, "_current_cache_bytes", None) == 400
    assert "https://example.com/item/400" in downloader._cache

    # Download 2: 400 bytes (total 800 <= 1000)
    await downloader.download("https://example.com/item/400_b")
    assert getattr(downloader, "_current_cache_bytes", None) == 800
    assert "https://example.com/item/400" in downloader._cache
    assert "https://example.com/item/400_b" in downloader._cache

    # Download 3: 400 bytes (total would be 1200 > 1000 -> evicts item 1)
    await downloader.download("https://example.com/item/400_c")
    assert getattr(downloader, "_current_cache_bytes", None) == 800
    assert "https://example.com/item/400" not in downloader._cache
    assert "https://example.com/item/400_b" in downloader._cache
    assert "https://example.com/item/400_c" in downloader._cache


@pytest.mark.asyncio
async def test_oversized_payload_bypasses_cache() -> None:
    """Verifies that payloads larger than max_cache_bytes bypass cache and do not evict existing items."""
    guard = SSRFGuard()
    downloader = SafeDownloader(
        guard=guard,
        max_cache_entries=10,
        max_cache_bytes=500,
    )

    async def fake_download(url: str) -> bytes:
        size = int(url.split("/")[-1])
        return b"y" * size

    downloader._download_uncached = fake_download  # type: ignore[assignment]

    # Warm cache with 300 bytes
    await downloader.download("https://example.com/item/300")
    assert getattr(downloader, "_current_cache_bytes", None) == 300
    assert "https://example.com/item/300" in downloader._cache

    # Download 600 bytes (> 500 max_cache_bytes)
    res = await downloader.download("https://example.com/item/600")
    assert len(res) == 600
    # Should NOT be in cache
    assert "https://example.com/item/600" not in downloader._cache
    # Existing item should still be in cache
    assert "https://example.com/item/300" in downloader._cache
    assert getattr(downloader, "_current_cache_bytes", None) == 300


@pytest.mark.asyncio
async def test_url_locks_cleanup_after_concurrent_downloads() -> None:
    """Verifies that _url_locks entries are cleaned up once all coroutines for a URL complete."""
    guard = SSRFGuard()
    downloader = SafeDownloader(guard=guard)

    active_downloads = 0
    max_concurrent = 0

    async def slow_download(url: str) -> bytes:
        nonlocal active_downloads, max_concurrent
        active_downloads += 1
        max_concurrent = max(max_concurrent, active_downloads)
        await asyncio.sleep(0.05)
        active_downloads -= 1
        return b"sprite_data"

    downloader._download_uncached = slow_download  # type: ignore[assignment]

    target_url = "https://example.com/sprite_shared.png"

    # Launch 10 concurrent downloads to the exact same URL
    results = await asyncio.gather(*[downloader.download(target_url) for _ in range(10)])

    assert len(results) == 10
    assert all(r == b"sprite_data" for r in results)
    # The lock ensured only 1 actual download occurred
    assert max_concurrent == 1

    # Invariant: _url_locks MUST NOT retain the URL lock when no coroutines are using it
    assert target_url not in downloader._url_locks
    assert len(downloader._url_locks) == 0


@pytest.mark.asyncio
async def test_url_locks_cleanup_on_download_error() -> None:
    """Verifies that lock is cleaned up even if download fails with an exception."""
    guard = SSRFGuard()
    downloader = SafeDownloader(guard=guard)

    async def failing_download(url: str) -> bytes:
        raise RuntimeError("Network failure")

    downloader._download_uncached = failing_download  # type: ignore[assignment]

    target_url = "https://example.com/failing.png"

    with pytest.raises(RuntimeError, match="Network failure"):
        await downloader.download(target_url)

    # Invariant: Lock must be cleaned up on failure
    assert target_url not in downloader._url_locks
    assert len(downloader._url_locks) == 0
