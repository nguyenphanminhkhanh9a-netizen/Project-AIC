"""Shared fixtures and synthetic image generators for pipeline test suites.

Phase 0.5A Automatic Asset Processing Pipeline.
All images are generated purely in memory in < 2ms without external network or disk dependencies.
"""

from __future__ import annotations

import io
import os
import sys
from collections.abc import Generator
from contextlib import ExitStack
from pathlib import Path
from typing import Literal
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw, ImageFilter

from app.domain.character import (
    AnchorType,
    AssetDefinition,
    CharacterManifest,
    FallbackConfig,
    Resolution,
    SpriteAlignment,
)
from app.pipeline.background.device_discovery import (
    DXGI_ADAPTER_FLAG_NONE,
    VENDOR_INTEL,
    VENDOR_NVIDIA,
    DXGIAdapterInfo,
)


def pytest_configure(config: pytest.Config) -> None:
    """Registers custom test markers for pipeline test suites."""
    config.addinivalue_line("markers", "failure_mode: marks tests for Owner failure modes")
    config.addinivalue_line("markers", "security: marks security and SSRF tests")
    config.addinivalue_line("markers", "stress: marks concurrency and stress tests")
    config.addinivalue_line(
        "markers",
        "directml_hardware: marks genuine hardware integration tests requiring real DirectX 12 GPU",
    )


def to_png_bytes(img: Image.Image) -> bytes:
    """Encodes a PIL image to raw PNG bytes in memory."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def to_webp_bytes(img: Image.Image) -> bytes:
    """Encodes a PIL image to raw WebP bytes in memory."""
    buf = io.BytesIO()
    img.save(buf, format="WEBP", lossless=True)
    return buf.getvalue()


def to_jpeg_bytes(img: Image.Image) -> bytes:
    """Encodes a PIL image to raw JPEG bytes in memory (RGB only)."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def make_corrupt_bytes(size: int = 128) -> bytes:
    """Returns random non-image bytes (e.g. /dev/urandom)."""
    return os.urandom(size)


def make_html_disguised_bytes() -> bytes:
    """Returns raw HTML/PHP text payload pretending to be an image."""
    return b"<!DOCTYPE html><html><body><h1>Error 404 Not Found</h1></body></html>"


def make_truncated_png_bytes() -> bytes:
    """Returns valid PNG magic header followed by truncated/corrupt IHDR chunk."""
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00"


def make_decompress_bomb_bytes() -> bytes:
    """Creates a small compressed PNG header declaring an absurd resolution (10000x10000)."""
    img = Image.new("RGBA", (10000, 10000), (0, 0, 0, 0))
    return to_png_bytes(img)


def create_synthetic_character_rgba(
    width: int = 1024,
    height: int = 1536,
    sprite_type: Literal["full_body", "waist_up", "bust_up"] = "full_body",
    emotion: Literal["neutral", "happy", "pout", "blush", "angry"] = "neutral",
    head_center_x: int | None = None,
    head_center_y: int | None = None,
    eye_line_y: int | None = None,
    silhouette_color: tuple[int, int, int] = (60, 70, 90),
    skin_color: tuple[int, int, int] = (255, 220, 200),
    hair_color: tuple[int, int, int] = (50, 120, 180),  # Miku Blue-ish
    blur_radius: float = 0.0,
) -> Image.Image:
    """Creates an authentic anime-style transparent RGBA portrait with true alpha.

    Ensures:
    - Transparent background (alpha = 0).
    - Opaque character body/silhouette (alpha = 255).
    - True alpha channel extrema (min=0, max=255).
    - Mathematical adherence to alpha edge classifier boundaries:
      * full_body: lowest non-zero alpha pixel touches y <= 1450 (y_max / H < 0.95).
      * waist_up: silhouette extends through canvas bottom (y_max == H).
      * bust_up: shoulders cut off at bottom with total bbox_height < 0.50 * H.
    - True emotion differentiation with distinct facial features.
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = width // 2 if head_center_x is None else head_center_x
    if sprite_type == "bust_up":
        cy = int(height * 0.65) if head_center_y is None else head_center_y
    else:
        cy = int(height * 0.28) if head_center_y is None else head_center_y

    face_w = max(10, int(width * 0.12))
    face_h = max(10, int(height * 0.09))
    hair_rx = max(12, int(face_w * 1.35))
    hair_ry = max(12, int(face_h * 1.25))

    # 1. Hair Back
    draw.ellipse(
        [cx - hair_rx, cy - hair_ry, cx + hair_rx, cy + int(hair_ry * 1.5)],
        fill=(*hair_color, 255),
    )

    # 2. Torso / Clothes (Drawn before head so clothes don't cover chin/mouth)
    neck_y = cy + int(face_h * 0.85)

    if sprite_type == "bust_up":
        # Bust-up close up: shoulders extend to canvas bottom, total silhouette height < 0.50 * height
        draw.polygon(
            [
                (cx - int(width * 0.28), height),
                (cx + int(width * 0.28), height),
                (cx + int(width * 0.18), neck_y),
                (cx - int(width * 0.18), neck_y),
            ],
            fill=(*silhouette_color, 255),
        )
    elif sprite_type == "waist_up":
        # Waist-up: torso extends through bottom canvas (y = height)
        draw.polygon(
            [
                (cx - int(width * 0.25), height),
                (cx + int(width * 0.25), height),
                (cx + int(width * 0.20), neck_y),
                (cx - int(width * 0.20), neck_y),
            ],
            fill=(*silhouette_color, 255),
        )
    else:  # "full_body"
        torso_bottom = int(height * 0.68)
        draw.polygon(
            [
                (cx - int(width * 0.22), torso_bottom),
                (cx + int(width * 0.22), torso_bottom),
                (cx + int(width * 0.18), neck_y),
                (cx - int(width * 0.18), neck_y),
            ],
            fill=(*silhouette_color, 255),
        )
        # Skirt / Upper legs
        skirt_bottom = int(height * 0.78)
        draw.polygon(
            [
                (cx - int(width * 0.25), skirt_bottom),
                (cx + int(width * 0.25), skirt_bottom),
                (cx + int(width * 0.20), torso_bottom),
                (cx - int(width * 0.20), torso_bottom),
            ],
            fill=(40, 50, 70, 255),
        )
        # Legs ending before bottom canvas edge
        leg_bottom = max(skirt_bottom + 2, min(height, int(height * 0.944)))
        leg_w = max(2, int(width * 0.08))
        draw.rectangle(
            [cx - int(width * 0.12), skirt_bottom, cx - int(width * 0.12) + leg_w, leg_bottom],
            fill=(30, 30, 40, 255),
        )
        draw.rectangle(
            [cx + int(width * 0.12) - leg_w, skirt_bottom, cx + int(width * 0.12), leg_bottom],
            fill=(30, 30, 40, 255),
        )

    # 3. Head & Face (Drawn on top of clothes)
    draw.ellipse(
        [cx - face_w, cy - face_h, cx + face_w, cy + face_h],
        fill=(*skin_color, 255),
    )

    # 4. Eyes & Facial Features (Distinct expressions)
    actual_eye_y = cy + int(face_h * 0.15) if eye_line_y is None else eye_line_y
    eye_offset = max(10, int(face_w * 0.35))
    eye_radius_x = max(5, int(face_w * 0.18))
    eye_radius_y = max(5, int(face_h * 0.18))
    mouth_y = cy + int(face_h * 0.60)

    if emotion == "neutral":
        # Neutral open circular eyes + straight mouth line
        draw.ellipse(
            [
                cx - eye_offset - eye_radius_x,
                actual_eye_y - eye_radius_y,
                cx - eye_offset + eye_radius_x,
                actual_eye_y + eye_radius_y,
            ],
            fill=(20, 50, 120, 255),
        )
        draw.ellipse(
            [
                cx + eye_offset - eye_radius_x,
                actual_eye_y - eye_radius_y,
                cx + eye_offset + eye_radius_x,
                actual_eye_y + eye_radius_y,
            ],
            fill=(20, 50, 120, 255),
        )
        draw.line(
            [(cx - int(face_w * 0.18), mouth_y), (cx + int(face_w * 0.18), mouth_y)],
            fill=(200, 50, 50, 255),
            width=max(2, int(height * 0.0026)),
        )
    elif emotion == "happy":
        # Happy closed crescent eyes (^ ^) + open smiling mouth
        eye_w = max(8, int(face_w * 0.25))
        draw.arc(
            [cx - eye_offset - eye_w, actual_eye_y - 15, cx - eye_offset + eye_w, actual_eye_y + 15],
            start=180,
            end=360,
            fill=(20, 50, 120, 255),
            width=max(3, int(height * 0.005)),
        )
        draw.arc(
            [cx + eye_offset - eye_w, actual_eye_y - 15, cx + eye_offset + eye_w, actual_eye_y + 15],
            start=180,
            end=360,
            fill=(20, 50, 120, 255),
            width=max(3, int(height * 0.005)),
        )
        draw.pieslice(
            [cx - int(face_w * 0.30), mouth_y - 15, cx + int(face_w * 0.30), mouth_y + 25],
            start=0,
            end=180,
            fill=(200, 40, 40, 255),
        )
    elif emotion == "pout":
        # Pout narrowed eyes + inverted arc mouth + blush circles
        draw.ellipse(
            [
                cx - eye_offset - eye_radius_x,
                actual_eye_y - int(eye_radius_y * 0.5),
                cx - eye_offset + eye_radius_x,
                actual_eye_y + int(eye_radius_y * 0.8),
            ],
            fill=(20, 50, 120, 255),
        )
        draw.ellipse(
            [
                cx + eye_offset - eye_radius_x,
                actual_eye_y - int(eye_radius_y * 0.5),
                cx + eye_offset + eye_radius_x,
                actual_eye_y + int(eye_radius_y * 0.8),
            ],
            fill=(20, 50, 120, 255),
        )
        draw.arc(
            [cx - int(face_w * 0.22), mouth_y - 15, cx + int(face_w * 0.22), mouth_y + 15],
            start=180,
            end=360,
            fill=(220, 50, 50, 255),
            width=max(3, int(height * 0.004)),
        )
        # Pronounced blush circles
        blush_w = max(10, int(face_w * 0.30))
        blush_h = max(6, int(face_h * 0.18))
        draw.ellipse(
            [
                cx - int(face_w * 0.70) - blush_w,
                actual_eye_y + 20,
                cx - int(face_w * 0.70) + blush_w,
                actual_eye_y + 20 + blush_h,
            ],
            fill=(255, 140, 140, 255),
        )
        draw.ellipse(
            [
                cx + int(face_w * 0.70) - blush_w,
                actual_eye_y + 20,
                cx + int(face_w * 0.70) + blush_w,
                actual_eye_y + 20 + blush_h,
            ],
            fill=(255, 140, 140, 255),
        )

    if blur_radius > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    return img


def create_synthetic_character_rgb(
    width: int = 1024,
    height: int = 1536,
    bg_color: tuple[int, int, int] = (255, 255, 255),
    **kwargs: object,
) -> Image.Image:
    """Creates a synthetic RGB image with solid background for background removal input."""
    rgba = create_synthetic_character_rgba(width=width, height=height, **kwargs)  # type: ignore[arg-type]
    rgb = Image.new("RGB", (width, height), bg_color)
    rgb.paste(rgba, mask=rgba.split()[3])
    return rgb


@pytest.fixture
def synthetic_full_body_rgba() -> Image.Image:
    """Fixture providing a standard 1024x1536 full-body RGBA sprite."""
    return create_synthetic_character_rgba(sprite_type="full_body")


@pytest.fixture
def synthetic_waist_up_rgba() -> Image.Image:
    """Fixture providing a waist-up RGBA sprite touching canvas bottom."""
    return create_synthetic_character_rgba(sprite_type="waist_up")


@pytest.fixture
def synthetic_core_baseline() -> Image.Image:
    """Fixture representing the baseline core idle neutral sprite."""
    return create_synthetic_character_rgba(
        sprite_type="full_body",
        head_center_x=512,
        head_center_y=430,
        eye_line_y=458,
        emotion="neutral",
    )


@pytest.fixture
def sample_character_manifest(tmp_path: Path) -> CharacterManifest:
    """Fixture providing an isolated valid CharacterManifest."""
    assets = [
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
        ),
        AssetDefinition(
            asset_id="miku_core_pout",
            path="assets/core/pout.webp",
            format="webp",
            state="idle",
            emotion="pout",
            outfit="school_uniform",
            resolution=Resolution(width=1024, height=1536),
            anchor=SpriteAlignment(anchor_type=AnchorType.BOTTOM_CENTER),
            is_core=True,
            status="ready",
        ),
    ]
    return CharacterManifest(
        schema_version="1.0",
        character_id="miku_nakano",
        display_name="Nakano Miku",
        default_outfit="school_uniform",
        fallbacks=FallbackConfig(
            default_asset_id="miku_core_idle_neutral",
            emotion_fallbacks={"angry": "pout"},
        ),
        assets=assets,
    )


@pytest.fixture
def synthetic_dxgi_adapters() -> list[DXGIAdapterInfo]:
    """Provides standard dual-GPU DXGI adapters (Intel iGPU + NVIDIA RTX 4050 dGPU) for portable testing."""
    return [
        DXGIAdapterInfo(
            index=0,
            description="Intel(R) UHD Graphics",
            dedicated_vram_bytes=128 * 1024 * 1024,
            dedicated_vram_mb=128,
            shared_ram_mb=16384,
            vendor_id=VENDOR_INTEL,
            device_id=0x4680,
            flags=DXGI_ADAPTER_FLAG_NONE,
            luid=0x1000,
        ),
        DXGIAdapterInfo(
            index=1,
            description="NVIDIA GeForce RTX 4050 Laptop GPU",
            dedicated_vram_bytes=6 * 1024 * 1024 * 1024,
            dedicated_vram_mb=6144,
            shared_ram_mb=16384,
            vendor_id=VENDOR_NVIDIA,
            device_id=0x28A0,
            flags=DXGI_ADAPTER_FLAG_NONE,
            luid=0x1001,
        ),
    ]


@pytest.fixture(autouse=True)
def auto_mock_dxgi_for_pipeline_unit_tests(
    request: pytest.FixtureRequest,
    synthetic_dxgi_adapters: list[DXGIAdapterInfo],
) -> Generator[None, None, None]:
    """Automatically provides synthetic DXGI adapters for unit/concurrency tests unless marked directml_hardware."""
    if "directml_hardware" in request.keywords:
        yield
        return

    # If the test is in test_device_discovery.py, let the test manage its own explicit patches
    if "test_device_discovery" in request.node.nodeid:
        yield
        return

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "app.pipeline.background.device_discovery.enumerate_dxgi_adapters",
                return_value=synthetic_dxgi_adapters,
            )
        )
        bench_mod = sys.modules.get("run_tier3_benchmark")
        if bench_mod is not None and hasattr(bench_mod, "enumerate_dxgi_adapters"):
            stack.enter_context(
                patch(
                    "run_tier3_benchmark.enumerate_dxgi_adapters",
                    return_value=synthetic_dxgi_adapters,
                )
            )
        yield

