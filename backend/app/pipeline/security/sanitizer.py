"""Image content sniffing, verification, and metadata-stripping transcoding.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import io

from PIL import Image


class ImageSanitizationError(ValueError):
    """Base exception for image content validation and sanitization errors."""


class InvalidImageHeaderError(ImageSanitizationError):
    """Raised when file signature does not match supported image formats."""


class CorruptedImageError(ImageSanitizationError):
    """Raised when image stream is truncated, unparseable, or corrupt."""


class SecurityViolationError(ImageSanitizationError):
    """Raised when image violates security thresholds (e.g. decompression bomb, size limit)."""


class ImageSanitizer:
    """Sniffs file signatures, verifies pixel buffers, and strips untrusted metadata."""

    def __init__(self, max_pixels: int = 8192 * 8192) -> None:
        self.max_pixels = max_pixels

    def sniff_magic_bytes(self, header: bytes) -> str:
        """Verifies initial bytes against supported image format signatures (PNG, JPEG, WebP)."""
        if not header:
            raise InvalidImageHeaderError("Empty byte payload cannot be verified.")

        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "PNG"
        if header.startswith(b"\xff\xd8\xff"):
            return "JPEG"
        if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
            return "WEBP"

        raise InvalidImageHeaderError(
            f"Unrecognized or unsupported image header signature: {header[:16]!r}"
        )

    def validate_raw_bytes(
        self, data: bytes, max_size_bytes: int = 15 * 1024 * 1024
    ) -> str:
        """Validates payload size, magic bytes signature, and structural integrity via PIL.verify()."""
        if not data:
            raise InvalidImageHeaderError("Image payload is empty.")

        if len(data) > max_size_bytes:
            raise SecurityViolationError(
                f"Image payload size ({len(data)} bytes) exceeds limit ({max_size_bytes} bytes)."
            )

        fmt = self.sniff_magic_bytes(data[:32])

        try:
            with Image.open(io.BytesIO(data)) as img:
                if img.width <= 0 or img.height <= 0:
                    raise CorruptedImageError("Image dimensions must be positive.")
                pixels = img.width * img.height
                pillow_limit = Image.MAX_IMAGE_PIXELS if Image.MAX_IMAGE_PIXELS is not None else 89_478_485
                if pixels > self.max_pixels or pixels > pillow_limit:
                    raise SecurityViolationError(
                        f"Decompression bomb detected: image pixel count ({pixels}) "
                        f"exceeds limit (max_pixels: {self.max_pixels}, pillow_limit: {pillow_limit})."
                    )
                img.verify()
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
            raise SecurityViolationError(
                f"Decompression bomb detected: image exceeds pixel limit ({self.max_pixels}): {e}"
            ) from e
        except (SecurityViolationError, CorruptedImageError):
            raise
        except Exception as e:
            raise CorruptedImageError(f"Corrupted or invalid image stream: {e}") from e

        return fmt

    def sanitize_image(self, data: bytes) -> Image.Image:
        """Decodes image into a fresh in-memory RGBA canvas, stripping all metadata and EXIF."""
        self.validate_raw_bytes(data)

        try:
            with Image.open(io.BytesIO(data)) as raw_img:
                if raw_img.width <= 0 or raw_img.height <= 0:
                    raise CorruptedImageError("Image dimensions must be positive.")
                pixels = raw_img.width * raw_img.height
                pillow_limit = Image.MAX_IMAGE_PIXELS if Image.MAX_IMAGE_PIXELS is not None else 89_478_485
                if pixels > self.max_pixels or pixels > pillow_limit:
                    raise SecurityViolationError(
                        f"Decompression bomb detected: image pixel count ({pixels}) "
                        f"exceeds limit (max_pixels: {self.max_pixels}, pillow_limit: {pillow_limit})."
                    )
                raw_img.load()
                # Create a pristine new RGBA canvas without any EXIF/XMP chunks
                clean_canvas = Image.new("RGBA", raw_img.size, (0, 0, 0, 0))
                converted = raw_img.convert("RGBA")
                clean_canvas.paste(converted, (0, 0))
                return clean_canvas
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
            raise SecurityViolationError(
                f"Decompression bomb detected during rasterization: {e}"
            ) from e
        except (SecurityViolationError, CorruptedImageError):
            raise
        except Exception as e:
            raise CorruptedImageError(f"Failed to rasterize and sanitize image: {e}") from e

    def to_png_bytes(self, img: Image.Image) -> bytes:
        """Encodes sanitized PIL Image to PNG bytes with zero EXIF/metadata."""
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def to_webp_bytes(self, img: Image.Image, quality: int = 90) -> bytes:
        """Encodes sanitized PIL Image to WebP bytes."""
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=quality, lossless=True)
        return buf.getvalue()
