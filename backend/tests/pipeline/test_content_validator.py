"""Suite 4: Content sniffing, verification, and metadata sanitization tests.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.pipeline.security.sanitizer import (
    CorruptedImageError,
    ImageSanitizer,
    InvalidImageHeaderError,
    SecurityViolationError,
)
from tests.pipeline.conftest import (
    create_synthetic_character_rgba,
    make_corrupt_bytes,
    make_html_disguised_bytes,
    make_truncated_png_bytes,
    to_jpeg_bytes,
    to_png_bytes,
    to_webp_bytes,
)


def test_magic_bytes_detection_valid_formats() -> None:
    """Verifies format identification for valid PNG, JPEG, and WebP byte buffers."""
    sanitizer = ImageSanitizer()
    img = create_synthetic_character_rgba(width=64, height=64)

    assert sanitizer.sniff_magic_bytes(to_png_bytes(img)) == "PNG"
    assert sanitizer.sniff_magic_bytes(to_jpeg_bytes(img)) == "JPEG"
    assert sanitizer.sniff_magic_bytes(to_webp_bytes(img)) == "WEBP"


def test_magic_bytes_rejection_of_fakes() -> None:
    """Verifies that non-image payloads (HTML, text, random binary) are rejected."""
    sanitizer = ImageSanitizer()

    with pytest.raises(InvalidImageHeaderError):
        sanitizer.sniff_magic_bytes(make_html_disguised_bytes())

    with pytest.raises(InvalidImageHeaderError):
        sanitizer.sniff_magic_bytes(make_corrupt_bytes(64))

    with pytest.raises(InvalidImageHeaderError):
        sanitizer.sniff_magic_bytes(b"MZ\x90\x00\x03\x00\x00\x00")  # Windows PE header


def test_pil_verify_truncated_image() -> None:
    """Verifies that truncated or damaged image streams fail validation with CorruptedImageError."""
    sanitizer = ImageSanitizer()
    truncated = make_truncated_png_bytes()

    with pytest.raises(CorruptedImageError):
        sanitizer.validate_raw_bytes(truncated)


def test_metadata_stripping_and_sanitization() -> None:
    """Verifies that image transcoding strips EXIF, XMP, and comments, yielding pristine RGBA canvas."""
    sanitizer = ImageSanitizer()

    # Create synthetic image with injected EXIF data
    img = create_synthetic_character_rgba(width=128, height=128)
    exif = img.getexif()
    exif[0x010E] = "Sensitive User Description"
    exif[0x0132] = "2026:11:05 14:00:00"

    buf = io.BytesIO()
    img.save(buf, format="PNG", exif=exif)
    raw_with_exif = buf.getvalue()

    # Pass through sanitizer
    clean_img = sanitizer.sanitize_image(raw_with_exif)

    assert clean_img.mode == "RGBA"
    assert clean_img.size == (128, 128)
    # Sanitized image must have zero EXIF tags
    assert len(clean_img.getexif()) == 0


def test_decompression_bomb_protection() -> None:
    """Verifies that images declaring absurd pixel counts trigger SecurityViolationError."""
    # Configure sanitizer with 1 Megapixel limit for test
    sanitizer = ImageSanitizer(max_pixels=1000 * 1000)

    # Image with 2000x2000 = 4 Megapixels > 1 MP
    huge_img = Image.new("RGBA", (2000, 2000), (0, 0, 0, 0))
    huge_bytes = to_png_bytes(huge_img)

    with pytest.raises(SecurityViolationError, match="Decompression bomb"):
        sanitizer.validate_raw_bytes(huge_bytes)


def test_size_limit_rejection() -> None:
    """Verifies that payloads exceeding max_size_bytes are rejected."""
    sanitizer = ImageSanitizer()
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200

    with pytest.raises(SecurityViolationError, match="exceeds limit"):
        sanitizer.validate_raw_bytes(data, max_size_bytes=100)
