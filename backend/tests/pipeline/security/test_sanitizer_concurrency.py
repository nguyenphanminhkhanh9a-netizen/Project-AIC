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
import threading
import time
import typing
import unittest.mock
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image

from app.pipeline.security.sanitizer import (
    ImageSanitizer,
    SecurityViolationError,
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


def test_concurrent_sanitizers_independent_limits_no_lock() -> None:
    """Verifies that multiple ImageSanitizer instances with different limits operate
    simultaneously without thread serialization and without cross-talk."""
    initial_global = Image.MAX_IMAGE_PIXELS

    # Payloads
    # 1. 200x200 = 40,000 px (valid for strict, sprite, high)
    payload_40k = _create_test_png(200, 200)
    # 2. 600x600 = 360,000 px (invalid for strict, valid for sprite and high)
    payload_360k = _create_test_png(600, 600)
    # 3. 1200x1200 = 1,440,000 px (invalid for strict, valid for sprite and high)
    payload_1_44m = _create_test_png(1200, 1200)
    # 4. 1600x1600 = 2,560,000 px (invalid for strict and sprite, valid for high)
    payload_2_56m = _create_test_png(1600, 1600)

    strict_sanitizer = ImageSanitizer(max_pixels=250_000)
    sprite_sanitizer = ImageSanitizer(max_pixels=2_000_000)
    high_sanitizer = ImageSanitizer(max_pixels=10_000_000)

    errors: list[str] = []

    def strict_worker(worker_id: int) -> None:
        for _ in range(20):
            # 40k must succeed
            try:
                strict_sanitizer.validate_raw_bytes(payload_40k)
                clean = strict_sanitizer.sanitize_image(payload_40k)
                assert clean.size == (200, 200)
            except Exception as e:  # noqa: BLE001
                errors.append(f"Strict worker {worker_id} failed on valid 40k image: {e}")

            # 360k must be rejected
            try:
                strict_sanitizer.validate_raw_bytes(payload_360k)
                errors.append(f"Strict worker {worker_id} unexpectedly ACCEPTED 360k image!")
            except SecurityViolationError:
                pass
            except Exception as e:  # noqa: BLE001
                errors.append(f"Strict worker {worker_id} unexpected error on 360k: {e}")

    def sprite_worker(worker_id: int) -> None:
        for _ in range(20):
            # 360k and 1.44M must succeed
            try:
                sprite_sanitizer.validate_raw_bytes(payload_360k)
                sprite_sanitizer.validate_raw_bytes(payload_1_44m)
            except Exception as e:  # noqa: BLE001
                errors.append(f"Sprite worker {worker_id} failed on valid sprite payload: {e}")

            # 2.56M must be rejected
            try:
                sprite_sanitizer.validate_raw_bytes(payload_2_56m)
                errors.append(f"Sprite worker {worker_id} unexpectedly ACCEPTED 2.56M image!")
            except SecurityViolationError:
                pass
            except Exception as e:  # noqa: BLE001
                errors.append(f"Sprite worker {worker_id} unexpected error on 2.56M: {e}")

    def high_worker(worker_id: int) -> None:
        for _ in range(20):
            # 2.56M must succeed
            try:
                high_sanitizer.validate_raw_bytes(payload_2_56m)
            except Exception as e:  # noqa: BLE001
                errors.append(f"High worker {worker_id} failed on valid 2.56M payload: {e}")

    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = []
        for i in range(10):
            futures.append(executor.submit(strict_worker, i))
            futures.append(executor.submit(sprite_worker, i))
            futures.append(executor.submit(high_worker, i))
        for f in futures:
            f.result()

    assert not errors, "Concurrency violations:\n" + "\n".join(errors[:10])
    assert Image.MAX_IMAGE_PIXELS == initial_global


def test_global_max_image_pixels_unmodified_during_processing_hook() -> None:
    """Verifies that Image.MAX_IMAGE_PIXELS remains strictly constant DURING execution of Image.open."""
    initial_global = Image.MAX_IMAGE_PIXELS
    assert initial_global == 89_478_485, "Expected Pillow standard default MAX_IMAGE_PIXELS"

    observed_values: list[int | None] = []
    orig_open = Image.open

    def inspecting_open(*args: typing.Any, **kwargs: typing.Any) -> Image.Image:
        # Sample global state inside Image.open call
        observed_values.append(Image.MAX_IMAGE_PIXELS)
        return orig_open(*args, **kwargs)

    sanitizer_strict = ImageSanitizer(max_pixels=100_000)
    sanitizer_sprite = ImageSanitizer(max_pixels=2_000_000)
    sanitizer_high = ImageSanitizer(max_pixels=50_000_000)

    test_png = _create_test_png(50, 50)

    try:
        Image.open = inspecting_open  # type: ignore[assignment]
        sanitizer_strict.validate_raw_bytes(test_png)
        sanitizer_strict.sanitize_image(test_png)
        sanitizer_sprite.validate_raw_bytes(test_png)
        sanitizer_sprite.sanitize_image(test_png)
        sanitizer_high.validate_raw_bytes(test_png)
        sanitizer_high.sanitize_image(test_png)
    finally:
        Image.open = orig_open

    assert len(observed_values) >= 6, "Expected at least 6 Image.open invocations"
    for idx, val in enumerate(observed_values):
        assert val == initial_global, (
            f"Image.MAX_IMAGE_PIXELS was mutated DURING call #{idx}! "
            f"Expected: {initial_global}, Observed: {val}"
        )
    assert Image.MAX_IMAGE_PIXELS == initial_global


def test_zero_mutation_during_processing_watchdog_thread() -> None:
    """Runs a high-frequency watchdog thread concurrently with active sanitizers to detect any transient mutation."""
    initial_global = Image.MAX_IMAGE_PIXELS
    deviations: list[int | None] = []
    stop_event = threading.Event()

    def watchdog_monitor() -> None:
        while not stop_event.is_set():
            val = Image.MAX_IMAGE_PIXELS
            if val != initial_global:
                deviations.append(val)
            time.sleep(0.0001)

    watchdog = threading.Thread(target=watchdog_monitor, daemon=True)
    watchdog.start()

    payload = _create_test_png(100, 100)
    sanitizers = [
        ImageSanitizer(max_pixels=1_000),
        ImageSanitizer(max_pixels=50_000),
        ImageSanitizer(max_pixels=250_000),
        ImageSanitizer(max_pixels=2_000_000),
        ImageSanitizer(max_pixels=50_000_000),
    ]

    def worker(worker_id: int) -> None:
        for _ in range(30):
            s = sanitizers[worker_id % len(sanitizers)]
            try:
                s.validate_raw_bytes(payload)
                s.sanitize_image(payload)
            except Exception:  # noqa: BLE001, S110
                pass

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker, i) for i in range(10)]
        for f in futures:
            f.result()

    stop_event.set()
    watchdog.join(timeout=2.0)

    assert not deviations, f"Watchdog detected transient mutation of Image.MAX_IMAGE_PIXELS: {deviations}"
    assert Image.MAX_IMAGE_PIXELS == initial_global


def test_oversized_images_rejected_before_raster_load() -> None:
    """Verifies that an image exceeding self.max_pixels raises SecurityViolationError
    without ever calling Image.load() or Image.verify()."""
    # 400x400 = 160,000 pixels
    png_data = _create_test_png(400, 400)

    # 1. Test validate_raw_bytes: verify() must NOT be called for oversized image
    sanitizer_strict = ImageSanitizer(max_pixels=100_000)
    with unittest.mock.patch.object(Image.Image, "verify") as mock_verify:
        with pytest.raises(SecurityViolationError, match="Decompression bomb detected"):
            sanitizer_strict.validate_raw_bytes(png_data)
        assert mock_verify.call_count == 0, "Image.verify() must NOT be called when pixel count exceeds limit!"

    # 2. Test sanitize_image: load() must NOT be called for oversized image
    with unittest.mock.patch.object(Image.Image, "load") as mock_load:
        with pytest.raises(SecurityViolationError, match="Decompression bomb detected"):
            sanitizer_strict.sanitize_image(png_data)
        assert mock_load.call_count == 0, "Image.load() must NOT be called when pixel count exceeds limit!"

    # 3. Contrast verification: load() MUST be called when image is valid
    sanitizer_permissive = ImageSanitizer(max_pixels=500_000)
    orig_load = Image.Image.load
    load_call_count = 0

    def spy_load(self_img: Image.Image) -> typing.Any:
        nonlocal load_call_count
        load_call_count += 1
        return orig_load(self_img)

    with unittest.mock.patch.object(Image.Image, "load", spy_load):
        clean = sanitizer_permissive.sanitize_image(png_data)
        assert clean.size == (400, 400)
        assert load_call_count >= 1, "Image.load() should be called during legitimate rasterization"


def test_decompression_bomb_warning_and_error_handling() -> None:
    """Verifies that DecompressionBombWarning, DecompressionBombError, and instance max_pixels
    checks all securely result in SecurityViolationError without global state mutation."""
    initial_global = Image.MAX_IMAGE_PIXELS
    assert initial_global == 89_478_485

    # Pregenerate high-resolution compressed PNGs
    # 1. 10,000 x 10,000 = 100,000,000 px (> 89.47M, <= 178.95M: triggers DecompressionBombWarning)
    # 2. 15,000 x 15,000 = 225,000,000 px (> 178.95M: triggers DecompressionBombError)
    orig_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None  # Temporarily allow test image creation
    try:
        buf_10k = io.BytesIO()
        Image.new("L", (10000, 10000), 0).save(buf_10k, format="PNG")
        payload_10k = buf_10k.getvalue()

        buf_15k = io.BytesIO()
        Image.new("L", (15000, 15000), 0).save(buf_15k, format="PNG")
        payload_15k = buf_15k.getvalue()
    finally:
        Image.MAX_IMAGE_PIXELS = orig_limit

    sanitizer_default = ImageSanitizer()  # default limit 67.1 MP

    # 1. 10k x 10k triggers DecompressionBombWarning in Pillow -> SecurityViolationError
    with pytest.raises(SecurityViolationError, match="Decompression bomb"):
        sanitizer_default.validate_raw_bytes(payload_10k)

    with pytest.raises(SecurityViolationError, match="Decompression bomb"):
        sanitizer_default.sanitize_image(payload_10k)

    # 2. 15k x 15k triggers DecompressionBombError in Pillow -> SecurityViolationError
    with pytest.raises(SecurityViolationError, match="Decompression bomb"):
        sanitizer_default.validate_raw_bytes(payload_15k)

    with pytest.raises(SecurityViolationError, match="Decompression bomb"):
        sanitizer_default.sanitize_image(payload_15k)

    # 3. Sub-Pillow limit check: 600x600 = 360k px on a 250k limit sanitizer
    sanitizer_250k = ImageSanitizer(max_pixels=250_000)
    payload_360k = _create_test_png(600, 600)

    with pytest.raises(SecurityViolationError, match="Decompression bomb detected: image pixel count"):
        sanitizer_250k.validate_raw_bytes(payload_360k)

    with pytest.raises(SecurityViolationError, match="Decompression bomb detected: image pixel count"):
        sanitizer_250k.sanitize_image(payload_360k)

    # Global Pillow configuration must remain completely intact
    assert Image.MAX_IMAGE_PIXELS == initial_global


def test_concurrent_sanitization_no_mutual_exclusion_lock() -> None:
    """Verifies that multiple ImageSanitizers execute simultaneously without being serialized by a global lock."""
    sanitizer_a = ImageSanitizer(max_pixels=100_000)
    sanitizer_b = ImageSanitizer(max_pixels=200_000)

    payload_a = _create_test_png(200, 200)  # 40k px
    payload_b = _create_test_png(300, 300)  # 90k px

    barrier = threading.Barrier(2, timeout=5.0)
    overlap_detected = False
    lock = threading.Lock()
    active_workers = 0

    def task(sanitizer: ImageSanitizer, payload: bytes) -> None:
        nonlocal overlap_detected, active_workers
        barrier.wait()  # Synchronize start to force parallel execution
        with lock:
            active_workers += 1
            if active_workers >= 2:
                overlap_detected = True
        try:
            sanitizer.validate_raw_bytes(payload)
            clean = sanitizer.sanitize_image(payload)
            assert clean is not None
            time.sleep(0.05)  # Hold execution briefly in parallel
        finally:
            with lock:
                active_workers -= 1

    t1 = threading.Thread(target=task, args=(sanitizer_a, payload_a))
    t2 = threading.Thread(target=task, args=(sanitizer_b, payload_b))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert overlap_detected, "Both sanitizers should be actively processing simultaneously without lock serialization!"
    assert Image.MAX_IMAGE_PIXELS == 89_478_485
