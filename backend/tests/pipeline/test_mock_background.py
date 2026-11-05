"""Suite 7: Mock background removal provider and RGBA alpha channel tests.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.domain.pipeline import BackgroundRemovalProvider
from app.pipeline.background.mock_provider import MockBackgroundRemovalProvider
from tests.pipeline.conftest import (
    create_synthetic_character_rgb,
    create_synthetic_character_rgba,
    to_jpeg_bytes,
    to_png_bytes,
)


def test_mock_provider_protocol_conformance() -> None:
    """Verifies that MockBackgroundRemovalProvider satisfies BackgroundRemovalProvider protocol."""
    provider = MockBackgroundRemovalProvider()
    assert isinstance(provider, BackgroundRemovalProvider)
    assert provider.model_name == "mock_heuristic_matting"
    assert provider.execution_provider == "cpu_mock"


@pytest.mark.asyncio
async def test_mock_provider_generates_authentic_rgba_alpha() -> None:
    """Verifies that flat RGB input is transformed into real RGBA with valid non-empty alpha channel."""
    provider = MockBackgroundRemovalProvider()

    # Input: Flat RGB image with solid white background
    rgb_img = create_synthetic_character_rgb(
        width=512,
        height=768,
        bg_color=(255, 255, 255),
        sprite_type="full_body",
    )
    rgb_bytes = to_jpeg_bytes(rgb_img)

    out_bytes, meta = await provider.remove_background(rgb_bytes)

    assert isinstance(out_bytes, bytes)
    assert len(out_bytes) > 0
    assert meta["model_name"] == "mock_heuristic_matting"
    assert meta["execution_provider"] == "cpu_mock"

    with Image.open(io.BytesIO(out_bytes)) as out_img:
        assert out_img.mode == "RGBA"
        assert out_img.format == "PNG"

        alpha = out_img.getchannel("A")
        extrema = alpha.getextrema()

        # Strict Owner requirement: alpha MUST NOT be dummy constant (e.g. all 255 or all 0)
        assert extrema == (0, 255), f"Alpha extrema {extrema} must be (0, 255)"

        # Verify presence of both transparent and opaque regions
        hist = alpha.histogram()
        assert hist[0] > 0, "Must contain transparent pixels"
        assert hist[255] > 0, "Must contain fully opaque pixels"


@pytest.mark.asyncio
async def test_mock_provider_preserves_existing_alpha() -> None:
    """Verifies that if input already possesses an authentic alpha channel, it is preserved."""
    provider = MockBackgroundRemovalProvider()

    rgba_img = create_synthetic_character_rgba(width=256, height=384)
    rgba_bytes = to_png_bytes(rgba_img)

    out_bytes, meta = await provider.remove_background(rgba_bytes)
    assert meta["alpha_source"] == "preserved_existing_alpha"

    with Image.open(io.BytesIO(out_bytes)) as out_img:
        assert out_img.mode == "RGBA"
        assert out_img.getchannel("A").getextrema() == (0, 255)


def test_mock_provider_release_cleanup() -> None:
    """Verifies that provider.release() executes cleanly without exceptions."""
    provider = MockBackgroundRemovalProvider()
    provider.release()  # Must not raise
