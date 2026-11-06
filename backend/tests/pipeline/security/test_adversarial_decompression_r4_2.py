"""Empirical adversarial stress test suite for decompression bomb and malformed image handling.

Challenger R4-2: Empirical Challenger.
Validates:
1. Decompression bomb synthesis:
   - 100MP PNG (10,000 x 10,000) with tiny compressed byte size (~97 KB)
   - 225MP PNG (15,000 x 15,000) with tiny compressed byte size (~218 KB)
   - Verification of zero memory spikes (< 5 MB peak) during validation and sanitization
2. Extreme aspect ratio images:
   - 1 x 70,000,000 px and 70,000,000 x 1 px rejected as SecurityViolationError
   - Legitimate extreme ratios (1 x 1000, 1000 x 1) cleanly sanitized
3. Malformed headers and zero/negative dimensions:
   - PNG with IHDR dimensions = 0 rejected cleanly as CorruptedImageError
   - Mock negative and zero dimensions rejected as CorruptedImageError
   - Truncated PNG, corrupted IHDR CRC, corrupted IDAT, truncated JPEG, truncated WebP
   - Invalid magic bytes rejected as InvalidImageHeaderError
4. Valid character sprites baseline:
   - 1024 x 1536 PNG sprite, JPEG, and WebP pass cleanly without false positives
   - Verification that untrusted EXIF/text metadata is completely stripped
5. Pillow global configuration immutability:
   - Image.MAX_IMAGE_PIXELS remains constant (89,478,485) throughout
"""

from __future__ import annotations

import io
import struct
import tracemalloc
import unittest.mock
import zlib

import pytest
from PIL import Image, PngImagePlugin

from app.pipeline.security.sanitizer import (
    CorruptedImageError,
    ImageSanitizer,
    InvalidImageHeaderError,
    SecurityViolationError,
)


def _build_synthetic_png(width: int, height: int, color_type: int = 0, bit_depth: int = 8) -> bytes:
    """Synthesizes a valid, compressed PNG byte stream with arbitrary dimensions."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    ihdr = chunk(b"IHDR", ihdr_data)

    # 1 byte filter per scanline + scanline width in bytes
    row_len = 1 + width
    compressor = zlib.compressobj(level=9)
    # Compress all scanlines of zeros
    idat_data = compressor.compress((b"\x00" * row_len) * height) + compressor.flush()
    idat = chunk(b"IDAT", idat_data)
    iend = chunk(b"IEND", b"")
    return header + ihdr + idat + iend


def test_100mp_decompression_bomb_intercepted_without_memory_spike() -> None:
    """Challenge: Synthesize a 100MP PNG (10,000 x 10,000, ~97 KB) and verify interception with < 5MB peak RAM."""
    initial_global = Image.MAX_IMAGE_PIXELS
    payload_100mp = _build_synthetic_png(10000, 10000)
    assert len(payload_100mp) < 150_000, "Synthetic 100MP bomb should be highly compressed (< 150 KB)"

    sanitizer = ImageSanitizer()

    # 1. Test validate_raw_bytes
    tracemalloc.start()
    try:
        with pytest.raises(SecurityViolationError, match="Decompression bomb detected"):
            sanitizer.validate_raw_bytes(payload_100mp)
        _, peak_bytes = tracemalloc.get_traced_memory()
        # Ensure peak memory during header inspection is under 5 MB (no rasterization)
        assert peak_bytes < 5 * 1024 * 1024, f"Memory spike detected in validate_raw_bytes: {peak_bytes} bytes"
    finally:
        tracemalloc.stop()

    # 2. Test sanitize_image
    tracemalloc.start()
    try:
        with pytest.raises(SecurityViolationError, match="Decompression bomb detected"):
            sanitizer.sanitize_image(payload_100mp)
        _, peak_bytes = tracemalloc.get_traced_memory()
        assert peak_bytes < 5 * 1024 * 1024, f"Memory spike detected in sanitize_image: {peak_bytes} bytes"
    finally:
        tracemalloc.stop()

    assert Image.MAX_IMAGE_PIXELS == initial_global


def test_225mp_decompression_bomb_intercepted_without_memory_spike() -> None:
    """Challenge: Synthesize a 225MP PNG (15,000 x 15,000, ~218 KB) and verify interception with < 5MB peak RAM."""
    initial_global = Image.MAX_IMAGE_PIXELS
    payload_225mp = _build_synthetic_png(15000, 15000)
    assert len(payload_225mp) < 300_000, "Synthetic 225MP bomb should be compressed (< 300 KB)"

    sanitizer = ImageSanitizer()

    tracemalloc.start()
    try:
        with pytest.raises(SecurityViolationError, match="Decompression bomb detected"):
            sanitizer.validate_raw_bytes(payload_225mp)
        with pytest.raises(SecurityViolationError, match="Decompression bomb detected"):
            sanitizer.sanitize_image(payload_225mp)
        _, peak_bytes = tracemalloc.get_traced_memory()
        assert peak_bytes < 5 * 1024 * 1024, f"Memory spike detected for 225MP bomb: {peak_bytes} bytes"
    finally:
        tracemalloc.stop()

    assert Image.MAX_IMAGE_PIXELS == initial_global


def test_extreme_aspect_ratio_images() -> None:
    """Challenge: Verify handling of extreme aspect ratios (tall, wide, legitimate ratios)."""
    initial_global = Image.MAX_IMAGE_PIXELS
    sanitizer = ImageSanitizer()

    # 1. 1 x 70,000,000 px = 70 MP (exceeds default 67.1 MP limit)
    payload_tall = _build_synthetic_png(1, 70_000_000)
    with pytest.raises(SecurityViolationError, match="Decompression bomb detected"):
        sanitizer.validate_raw_bytes(payload_tall)

    # 2. 70,000,000 x 1 px = 70 MP (exceeds default 67.1 MP limit)
    # For wide image, create header + minimal idat
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr_wide = chunk(b"IHDR", struct.pack(">IIBBBBB", 70_000_000, 1, 8, 0, 0, 0, 0))
    payload_wide = b"\x89PNG\r\n\x1a\n" + ihdr_wide + chunk(b"IEND", b"")

    with pytest.raises(SecurityViolationError, match="Decompression bomb detected"):
        sanitizer.validate_raw_bytes(payload_wide)

    # 3. Legitimate extreme aspect ratios (1 x 1000 and 1000 x 1)
    payload_1x1000 = _build_synthetic_png(1, 1000)
    clean_tall = sanitizer.sanitize_image(payload_1x1000)
    assert clean_tall.size == (1, 1000)
    assert clean_tall.mode == "RGBA"

    payload_1000x1 = _build_synthetic_png(1000, 1)
    clean_wide = sanitizer.sanitize_image(payload_1000x1)
    assert clean_wide.size == (1000, 1)
    assert clean_wide.mode == "RGBA"

    assert Image.MAX_IMAGE_PIXELS == initial_global


def test_zero_and_negative_dimensions_rejection() -> None:
    """Challenge: Verify that zero and negative dimensions are rejected cleanly as CorruptedImageError."""
    initial_global = Image.MAX_IMAGE_PIXELS
    sanitizer = ImageSanitizer()

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    # 1. Synthesize PNGs with 0 dimensions in IHDR
    zero_cases = [
        ("zero_width", struct.pack(">IIBBBBB", 0, 100, 8, 0, 0, 0, 0)),
        ("zero_height", struct.pack(">IIBBBBB", 100, 0, 8, 0, 0, 0, 0)),
        ("both_zero", struct.pack(">IIBBBBB", 0, 0, 8, 0, 0, 0, 0)),
    ]

    for name, ihdr_bytes in zero_cases:
        payload = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr_bytes) + chunk(b"IEND", b"")
        with pytest.raises(CorruptedImageError):
            sanitizer.validate_raw_bytes(payload)
        with pytest.raises(CorruptedImageError):
            sanitizer.sanitize_image(payload)

    # 2. Mock dimension checks (width <= 0 or height <= 0) inside validate_raw_bytes and sanitize_image
    dummy_payload = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    mock_cases = [(0, 100), (100, 0), (0, 0), (-1, 100), (100, -50), (-10, -10)]

    for w, h in mock_cases:
        mock_img = unittest.mock.MagicMock()
        mock_img.width = w
        mock_img.height = h
        mock_img.__enter__.return_value = mock_img

        with unittest.mock.patch.object(Image, "open", return_value=mock_img):
            with pytest.raises(CorruptedImageError, match="Image dimensions must be positive"):
                sanitizer.validate_raw_bytes(dummy_payload)
            with pytest.raises(CorruptedImageError, match="Image dimensions must be positive"):
                sanitizer.sanitize_image(dummy_payload)

    assert Image.MAX_IMAGE_PIXELS == initial_global


def test_malformed_headers_and_corrupted_streams() -> None:
    """Challenge: Verify that corrupted headers, truncated data, and invalid signatures are handled cleanly."""
    initial_global = Image.MAX_IMAGE_PIXELS
    sanitizer = ImageSanitizer()

    # 1. Invalid headers -> InvalidImageHeaderError
    invalid_headers = [
        b"",
        b"NOT_AN_IMAGE",
        b"\x89PNG\r\n\x1a",  # Truncated magic
        b"GIF89a\x01\x00\x01\x00",  # Unsupported format
        b"RIFF\x10\x00\x00\x00AVI ",  # RIFF but not WEBP
    ]
    for bad_header in invalid_headers:
        with pytest.raises(InvalidImageHeaderError):
            sanitizer.validate_raw_bytes(bad_header)
        with pytest.raises(InvalidImageHeaderError):
            sanitizer.sanitize_image(bad_header)

    # 2. Corrupted streams -> CorruptedImageError
    corrupted_streams = [
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00",  # Truncated IHDR
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\n\x00\x00\x00\n\x08\x00\x00\x00\x00\xde\xad\xbe\xef",  # Bad CRC
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00",  # Truncated JPEG
        b"RIFF\x14\x00\x00\x00WEBPVP8 \x08\x00\x00\x00\x00\x00\x00\x00",  # Truncated WebP
    ]
    for corrupt_stream in corrupted_streams:
        with pytest.raises(CorruptedImageError):
            sanitizer.validate_raw_bytes(corrupt_stream)
        with pytest.raises(CorruptedImageError):
            sanitizer.sanitize_image(corrupt_stream)

    assert Image.MAX_IMAGE_PIXELS == initial_global


def test_valid_character_sprite_baseline_and_metadata_stripping() -> None:
    """Baseline: Verify legitimate 1024x1536 character sprites pass cleanly and EXIF/metadata is stripped."""
    initial_global = Image.MAX_IMAGE_PIXELS
    sanitizer_default = ImageSanitizer()
    sanitizer_sprite = ImageSanitizer(max_pixels=2_000_000)

    # 1. 1024x1536 PNG with injected text metadata
    raw_img = Image.new("RGBA", (1024, 1536), (0, 200, 255, 128))
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("SensitiveMetadata", "SecretToken12345")
    buf_png = io.BytesIO()
    raw_img.save(buf_png, format="PNG", pnginfo=png_info)
    payload_png = buf_png.getvalue()

    # Pre-check: metadata present
    pre_check = Image.open(io.BytesIO(payload_png))
    assert "SensitiveMetadata" in getattr(pre_check, "text", {})

    # Sanitize
    clean_png = sanitizer_sprite.sanitize_image(payload_png)
    assert clean_png.size == (1024, 1536)
    assert clean_png.mode == "RGBA"

    # Export to PNG and verify metadata is stripped
    clean_png_bytes = sanitizer_sprite.to_png_bytes(clean_png)
    reloaded_png = Image.open(io.BytesIO(clean_png_bytes))
    assert not getattr(reloaded_png, "text", {}), "Metadata was not stripped from sanitized PNG!"

    # 2. 1024x1536 JPEG baseline
    buf_jpg = io.BytesIO()
    raw_jpg = Image.new("RGB", (1024, 1536), (255, 128, 64))
    raw_jpg.save(buf_jpg, format="JPEG")
    payload_jpg = buf_jpg.getvalue()

    fmt_jpg = sanitizer_default.validate_raw_bytes(payload_jpg)
    assert fmt_jpg == "JPEG"
    clean_jpg = sanitizer_sprite.sanitize_image(payload_jpg)
    assert clean_jpg.size == (1024, 1536)
    assert clean_jpg.mode == "RGBA"

    # 3. 1024x1536 WebP baseline
    buf_webp = io.BytesIO()
    raw_webp = Image.new("RGBA", (1024, 1536), (64, 128, 255, 200))
    raw_webp.save(buf_webp, format="WEBP")
    payload_webp = buf_webp.getvalue()

    fmt_webp = sanitizer_default.validate_raw_bytes(payload_webp)
    assert fmt_webp == "WEBP"
    clean_webp = sanitizer_sprite.sanitize_image(payload_webp)
    assert clean_webp.size == (1024, 1536)
    assert clean_webp.mode == "RGBA"

    # Export to WebP bytes
    clean_webp_bytes = sanitizer_sprite.to_webp_bytes(clean_webp)
    assert len(clean_webp_bytes) > 0

    assert Image.MAX_IMAGE_PIXELS == initial_global
