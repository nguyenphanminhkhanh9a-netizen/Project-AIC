"""Reproduction and concurrency tests for ImageSanitizer and Pillow MAX_IMAGE_PIXELS scoping.

Verifies:
1. Concurrent ImageSanitizers with different pixel thresholds (250k vs 2M) running in parallel threads.
2. Concurrent ImageSanitizers executing in async asyncio tasks via asyncio.to_thread.
3. Zero false rejections in permissive sanitizers.
4. Zero false acceptances in strict sanitizers.
5. Pillow global MAX_IMAGE_PIXELS is never polluted or leaked across concurrent runs.
"""

from __future__ import annotations

import asyncio
import io
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Thread

import pytest
from PIL import Image

from app.pipeline.security.sanitizer import (
    ImageSanitizer,
    SecurityViolationError,
    _scoped_max_pixels,
)


def _create_test_png(width: int, height: int) -> bytes:
    """Helper to generate a valid PNG image of specified dimensions in memory."""
    buf = io.BytesIO()
    img = Image.new("RGBA", (width, height), (0, 128, 255, 255))
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_concurrent_sanitizers_varying_limits_threads() -> None:
    """Verifies that multi-threaded sanitization with differing limits does not corrupt global Pillow state."""
    # Record initial global setting
    initial_global = Image.MAX_IMAGE_PIXELS

    # 400x400 = 160,000 pixels (valid for both 250k and 2M)
    small_png = _create_test_png(400, 400)
    # 800x800 = 640,000 pixels (invalid for 250k, valid for 2M)
    medium_png = _create_test_png(800, 800)

    strict_sanitizer = ImageSanitizer(max_pixels=250_000)
    permissive_sanitizer = ImageSanitizer(max_pixels=2_000_000)

    errors: list[str] = []

    def run_strict_worker(worker_id: int) -> None:
        for _ in range(10):
            try:
                # Small should succeed
                strict_sanitizer.validate_raw_bytes(small_png)
            except Exception as e:  # noqa: BLE001
                errors.append(f"Strict worker {worker_id} failed on small image: {e}")

            try:
                # Medium should be rejected
                strict_sanitizer.validate_raw_bytes(medium_png)
                errors.append(f"Strict worker {worker_id} unexpectedly accepted medium image (640k > 250k)")
            except SecurityViolationError:
                pass
            except Exception as e:  # noqa: BLE001
                errors.append(f"Strict worker {worker_id} raised unexpected error on medium image: {e}")

    def run_permissive_worker(worker_id: int) -> None:
        for _ in range(10):
            try:
                # Small should succeed
                permissive_sanitizer.validate_raw_bytes(small_png)
                # Medium should succeed
                permissive_sanitizer.validate_raw_bytes(medium_png)
            except Exception as e:  # noqa: BLE001
                errors.append(f"Permissive worker {worker_id} failed on valid image: {e}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for i in range(5):
            futures.append(executor.submit(run_strict_worker, i))
            futures.append(executor.submit(run_permissive_worker, i))
        for f in futures:
            f.result()

    assert not errors, f"Concurrency errors occurred: {errors}"
    assert (
        Image.MAX_IMAGE_PIXELS == initial_global
    ), f"Global MAX_IMAGE_PIXELS was corrupted! Initial: {initial_global}, Final: {Image.MAX_IMAGE_PIXELS}"


@pytest.mark.asyncio
async def test_concurrent_sanitizers_async_tasks() -> None:
    """Verifies concurrency safety across asynchronous pipeline tasks."""
    initial_global = Image.MAX_IMAGE_PIXELS

    small_png = _create_test_png(400, 400)  # 160k px
    medium_png = _create_test_png(800, 800)  # 640k px

    strict_sanitizer = ImageSanitizer(max_pixels=250_000)
    permissive_sanitizer = ImageSanitizer(max_pixels=2_000_000)

    async def async_strict_task() -> None:
        for _ in range(5):
            await asyncio.to_thread(strict_sanitizer.validate_raw_bytes, small_png)
            with pytest.raises(SecurityViolationError):
                await asyncio.to_thread(strict_sanitizer.validate_raw_bytes, medium_png)

    async def async_permissive_task() -> None:
        for _ in range(5):
            await asyncio.to_thread(permissive_sanitizer.validate_raw_bytes, small_png)
            await asyncio.to_thread(permissive_sanitizer.validate_raw_bytes, medium_png)

    tasks = []
    for _ in range(5):
        tasks.append(asyncio.create_task(async_strict_task()))
        tasks.append(asyncio.create_task(async_permissive_task()))

    await asyncio.gather(*tasks)

    assert (
        Image.MAX_IMAGE_PIXELS == initial_global
    ), f"Global MAX_IMAGE_PIXELS was corrupted! Initial: {initial_global}, Final: {Image.MAX_IMAGE_PIXELS}"


def test_scoped_max_pixels_mutual_exclusion() -> None:
    """Verifies that _scoped_max_pixels synchronizes using _PIL_CONFIG_LOCK."""
    events: list[str] = []

    def task1() -> None:
        with _scoped_max_pixels(100_000):
            events.append("task1_start")
            time.sleep(0.05)
            assert Image.MAX_IMAGE_PIXELS == 100_000
            events.append("task1_end")

    def task2() -> None:
        time.sleep(0.01)
        with _scoped_max_pixels(200_000):
            events.append("task2_start")
            assert Image.MAX_IMAGE_PIXELS == 200_000
            events.append("task2_end")

    t1 = Thread(target=task1)
    t2 = Thread(target=task2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Mutual exclusion guarantees task1 must finish before task2 starts
    assert events == ["task1_start", "task1_end", "task2_start", "task2_end"]
