"""Adversarial Concurrency Stress Test Suite for ImageSanitizer and Pillow Scoping.

Challenger R3-2: Adversarial Domain & Concurrency Challenger.
Empirically stress-tests:
1. 60 concurrent threads simultaneously interleaving 6 distinct pixel limits:
   - 1,000 px (micro)
   - 50,000 px (low)
   - 500,000 px (medium)
   - 2,000,000 px (standard sprite: 1024x1536)
   - 10,000,000 px (high-res)
   - 50,000,000 px (ultra-res)
2. Zero false positive DecompressionBombErrors on legitimate Miku sprites (1024x1536 = 1,572,864 px)
   under hostile concurrency.
3. Zero false negative bypass: Strict sanitizers never accept oversized images despite concurrent 50M px runs.
4. Hostile corrupt streams (truncated bytes, noise, empty payloads) concurrently interleaved:
   ensures exception safety and no lock/state leakage.
5. Async task concurrency with 60 tasks via asyncio.to_thread.
6. Baseline restoration: Image.MAX_IMAGE_PIXELS is guaranteed to return to its original baseline.
"""

from __future__ import annotations

import asyncio
import io
import random
from concurrent.futures import ThreadPoolExecutor

import pytest
from PIL import Image

from app.pipeline.security.sanitizer import (
    CorruptedImageError,
    ImageSanitizer,
    InvalidImageHeaderError,
    SecurityViolationError,
)


def _generate_png_bytes(width: int, height: int, color: tuple[int, int, int, int] = (0, 200, 255, 255)) -> bytes:
    """Creates a genuine PNG byte payload with exact dimensions."""
    buf = io.BytesIO()
    img = Image.new("RGBA", (width, height), color)
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def pregenerated_images() -> dict[str, bytes]:
    """Pregenerate test payloads to isolate sanitizer concurrency from image creation overhead."""
    return {
        # Valid for 1k+ (400 px)
        "micro_valid": _generate_png_bytes(20, 20),
        # Exceeds 1k, valid for 50k+ (2,500 px)
        "micro_exceed_low_valid": _generate_png_bytes(50, 50),
        # Exceeds 50k, valid for 500k+ (90,000 px)
        "low_exceed_med_valid": _generate_png_bytes(300, 300),
        # Exceeds 500k, valid for 2M+ (640,000 px)
        "med_exceed_sprite_valid": _generate_png_bytes(800, 800),
        # Legitimate Miku Character Sprite (1024x1536 = 1,572,864 px)
        "miku_sprite_1024x1536": _generate_png_bytes(1024, 1536),
        # Exceeds 2M, valid for 10M+ (2,250,000 px)
        "sprite_exceed_high_valid": _generate_png_bytes(1500, 1500),
        # Exceeds 10M, valid for 50M (12,000,000 px)
        "high_exceed_ultra_valid": _generate_png_bytes(4000, 3000),
    }


def test_60_threads_interleaving_pixel_limits_adversarial_stress(
    pregenerated_images: dict[str, bytes],
) -> None:
    """Stress-test 60 concurrent worker threads executing across 6 tiers of pixel limits (1k to 50M).

    Validates:
    - Zero false positive DecompressionBombErrors on legitimate 1024x1536 sprites.
    - Zero false negative bypasses on strict limiters.
    - Exact restoration of Image.MAX_IMAGE_PIXELS.
    """
    baseline_max_pixels = Image.MAX_IMAGE_PIXELS

    # Tiered Sanitizers
    sanitizer_1k = ImageSanitizer(max_pixels=1_000)
    sanitizer_50k = ImageSanitizer(max_pixels=50_000)
    sanitizer_500k = ImageSanitizer(max_pixels=500_000)
    sanitizer_sprite = ImageSanitizer(max_pixels=2_000_000)  # Standard Miku sprite limit
    sanitizer_10m = ImageSanitizer(max_pixels=10_000_000)
    sanitizer_50m = ImageSanitizer(max_pixels=50_000_000)

    errors: list[str] = []

    def worker_tier_1k(worker_id: int) -> None:
        for _ in range(15):
            # Should pass: 20x20 = 400 px
            try:
                sanitizer_1k.validate_raw_bytes(pregenerated_images["micro_valid"])
            except Exception as e:  # noqa: BLE001
                errors.append(f"Tier 1k worker {worker_id} failed on valid 400px: {e}")

            # Should be rejected: 50x50 = 2,500 px
            try:
                sanitizer_1k.validate_raw_bytes(pregenerated_images["micro_exceed_low_valid"])
                errors.append(f"Tier 1k worker {worker_id} falsely ACCEPTED 2500px image")
            except SecurityViolationError:
                pass
            except Exception as e:  # noqa: BLE001
                errors.append(f"Tier 1k worker {worker_id} unexpected error: {e}")

    def worker_tier_50k(worker_id: int) -> None:
        for _ in range(15):
            # Should pass: 50x50 = 2,500 px
            try:
                sanitizer_50k.validate_raw_bytes(pregenerated_images["micro_exceed_low_valid"])
            except Exception as e:  # noqa: BLE001
                errors.append(f"Tier 50k worker {worker_id} failed on valid 2500px: {e}")

            # Should be rejected: 300x300 = 90,000 px
            try:
                sanitizer_50k.validate_raw_bytes(pregenerated_images["low_exceed_med_valid"])
                errors.append(f"Tier 50k worker {worker_id} falsely ACCEPTED 90k px image")
            except SecurityViolationError:
                pass
            except Exception as e:  # noqa: BLE001
                errors.append(f"Tier 50k worker {worker_id} unexpected error: {e}")

    def worker_tier_500k(worker_id: int) -> None:
        for _ in range(15):
            # Should pass: 300x300 = 90k px
            try:
                sanitizer_500k.validate_raw_bytes(pregenerated_images["low_exceed_med_valid"])
            except Exception as e:  # noqa: BLE001
                errors.append(f"Tier 500k worker {worker_id} failed on valid 90k px: {e}")

            # Should be rejected: 800x800 = 640k px
            try:
                sanitizer_500k.validate_raw_bytes(pregenerated_images["med_exceed_sprite_valid"])
                errors.append(f"Tier 500k worker {worker_id} falsely ACCEPTED 640k px image")
            except SecurityViolationError:
                pass
            except Exception as e:  # noqa: BLE001
                errors.append(f"Tier 500k worker {worker_id} unexpected error: {e}")

    def worker_tier_sprite(worker_id: int) -> None:
        # Crucial check: Legitimate 1024x1536 sprite must NEVER trigger false positive DecompressionBomb
        for _ in range(15):
            try:
                # Both validate and sanitize
                sanitizer_sprite.validate_raw_bytes(pregenerated_images["miku_sprite_1024x1536"])
                clean_img = sanitizer_sprite.sanitize_image(pregenerated_images["miku_sprite_1024x1536"])
                assert clean_img.size == (1024, 1536)
            except Exception as e:  # noqa: BLE001
                errors.append(f"FALSE POSITIVE: Sprite worker {worker_id} rejected legitimate Miku sprite: {e}")

            # Should be rejected: 1500x1500 = 2.25M px
            try:
                sanitizer_sprite.validate_raw_bytes(pregenerated_images["sprite_exceed_high_valid"])
                errors.append(f"Sprite worker {worker_id} falsely ACCEPTED 2.25M px image")
            except SecurityViolationError:
                pass
            except Exception as e:  # noqa: BLE001
                errors.append(f"Sprite worker {worker_id} unexpected error: {e}")

    def worker_tier_10m(worker_id: int) -> None:
        for _ in range(15):
            # Should pass: 1500x1500 = 2.25M px
            try:
                sanitizer_10m.validate_raw_bytes(pregenerated_images["sprite_exceed_high_valid"])
            except Exception as e:  # noqa: BLE001
                errors.append(f"Tier 10M worker {worker_id} failed on valid 2.25M px: {e}")

            # Should be rejected: 4000x3000 = 12M px
            try:
                sanitizer_10m.validate_raw_bytes(pregenerated_images["high_exceed_ultra_valid"])
                errors.append(f"Tier 10M worker {worker_id} falsely ACCEPTED 12M px image")
            except SecurityViolationError:
                pass
            except Exception as e:  # noqa: BLE001
                errors.append(f"Tier 10M worker {worker_id} unexpected error: {e}")

    def worker_tier_50m(worker_id: int) -> None:
        for _ in range(15):
            # Should pass: 4000x3000 = 12M px
            try:
                sanitizer_50m.validate_raw_bytes(pregenerated_images["high_exceed_ultra_valid"])
            except Exception as e:  # noqa: BLE001
                errors.append(f"Tier 50M worker {worker_id} failed on valid 12M px: {e}")

    # Launch 60 concurrent worker threads (10 per tier)
    with ThreadPoolExecutor(max_workers=60) as executor:
        futures = []
        for i in range(10):
            futures.append(executor.submit(worker_tier_1k, i))
            futures.append(executor.submit(worker_tier_50k, i))
            futures.append(executor.submit(worker_tier_500k, i))
            futures.append(executor.submit(worker_tier_sprite, i))
            futures.append(executor.submit(worker_tier_10m, i))
            futures.append(executor.submit(worker_tier_50m, i))

        for f in futures:
            f.result()

    assert not errors, "Concurrency violations detected:\n" + "\n".join(errors[:20])
    assert (
        Image.MAX_IMAGE_PIXELS == baseline_max_pixels
    ), f"Leak detected: MAX_IMAGE_PIXELS changed from {baseline_max_pixels} to {Image.MAX_IMAGE_PIXELS}"


def test_concurrent_hostile_corrupt_payload_injection(
    pregenerated_images: dict[str, bytes],
) -> None:
    """Stress test: 50 threads interleaving corrupt/malicious byte streams with valid sprite sanitization.

    Verifies exception safety: errors during Image.open/verify/load do not leak locks or corrupt Pillow state.
    """
    baseline_max_pixels = Image.MAX_IMAGE_PIXELS
    sanitizer = ImageSanitizer(max_pixels=2_000_000)

    corrupt_payloads = [
        b"",  # Empty
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 20,  # Truncated PNG
        b"\xff\xd8\xff\xe0" + b"\x12\x34" * 10,  # Corrupt JPEG
        b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 10,  # Corrupt WebP
        b"NOT_AN_IMAGE_FILE_AT_ALL_JUST_RANDOM_TEXT_STRING",
        bytes(random.getrandbits(8) for _ in range(500)),  # Pure random noise
    ]

    errors: list[str] = []

    def corrupt_worker(worker_id: int) -> None:
        for _ in range(20):
            payload = random.choice(corrupt_payloads)
            try:
                sanitizer.sanitize_image(payload)
                errors.append(f"Worker {worker_id} unexpectedly sanitized corrupt payload!")
            except (InvalidImageHeaderError, CorruptedImageError):
                # Expected safe rejection
                pass
            except Exception as e:  # noqa: BLE001
                errors.append(f"Worker {worker_id} raised unexpected exception: {type(e).__name__}: {e}")

    def legitimate_sprite_worker(worker_id: int) -> None:
        for _ in range(20):
            try:
                clean = sanitizer.sanitize_image(pregenerated_images["miku_sprite_1024x1536"])
                assert clean.size == (1024, 1536)
            except Exception as e:  # noqa: BLE001
                errors.append(f"Legitimate worker {worker_id} failed during hostile storm: {e}")

    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = []
        for i in range(25):
            futures.append(executor.submit(corrupt_worker, i))
            futures.append(executor.submit(legitimate_sprite_worker, i))
        for f in futures:
            f.result()

    assert not errors, "Corrupt injection concurrency errors:\n" + "\n".join(errors[:20])
    assert Image.MAX_IMAGE_PIXELS == baseline_max_pixels


@pytest.mark.asyncio
async def test_async_interleaved_concurrency_60_tasks(
    pregenerated_images: dict[str, bytes],
) -> None:
    """Stress test: 60 concurrent asyncio tasks interleaving various sanitizers via asyncio.to_thread."""
    baseline_max_pixels = Image.MAX_IMAGE_PIXELS

    strict_sanitizer = ImageSanitizer(max_pixels=100_000)
    sprite_sanitizer = ImageSanitizer(max_pixels=2_000_000)
    huge_sanitizer = ImageSanitizer(max_pixels=20_000_000)

    async def strict_async_task() -> None:
        for _ in range(10):
            # 20x20 = 400 px should pass
            await asyncio.to_thread(strict_sanitizer.validate_raw_bytes, pregenerated_images["micro_valid"])
            # 300x300 = 90k px should pass
            await asyncio.to_thread(strict_sanitizer.validate_raw_bytes, pregenerated_images["low_exceed_med_valid"])
            # 800x800 = 640k px must fail
            with pytest.raises(SecurityViolationError):
                await asyncio.to_thread(
                    strict_sanitizer.validate_raw_bytes, pregenerated_images["med_exceed_sprite_valid"]
                )

    async def sprite_async_task() -> None:
        for _ in range(10):
            # 1024x1536 Miku sprite must pass with zero false positives
            clean = await asyncio.to_thread(
                sprite_sanitizer.sanitize_image, pregenerated_images["miku_sprite_1024x1536"]
            )
            assert clean.size == (1024, 1536)
            # 1500x1500 must fail
            with pytest.raises(SecurityViolationError):
                await asyncio.to_thread(
                    sprite_sanitizer.validate_raw_bytes, pregenerated_images["sprite_exceed_high_valid"]
                )

    async def huge_async_task() -> None:
        for _ in range(10):
            # 1500x1500 = 2.25M px passes
            await asyncio.to_thread(huge_sanitizer.validate_raw_bytes, pregenerated_images["sprite_exceed_high_valid"])

    tasks = []
    for _ in range(20):
        tasks.append(asyncio.create_task(strict_async_task()))
        tasks.append(asyncio.create_task(sprite_async_task()))
        tasks.append(asyncio.create_task(huge_async_task()))

    await asyncio.gather(*tasks)

    assert Image.MAX_IMAGE_PIXELS == baseline_max_pixels
