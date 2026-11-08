"""Offline unit tests for ISNetONNXProvider and associated image operations.

Validates lazy loading invariants, supply chain verification, error handling,
letterboxing geometry, soft alpha ramp interpolation, and resource deallocation.
Runs 100% offline with zero ML model weights dependencies.
"""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from app.domain.pipeline import BackgroundRemovalProvider
from app.pipeline.background import (
    ISNetONNXProvider,
    MockBackgroundRemovalProvider,
    apply_soft_alpha_ramp,
    get_background_removal_provider,
    letterbox_preprocess,
    postprocess_mask,
)
from app.pipeline.config import PipelineConfig
from app.pipeline.security.model_verifier import (
    ModelIntegrityError,
    ModelNotFoundError,
    verify_model_file,
)


def test_isnet_provider_protocol_conformance() -> None:
    """Verifies that ISNetONNXProvider implements BackgroundRemovalProvider Protocol."""
    provider = ISNetONNXProvider()
    assert isinstance(provider, BackgroundRemovalProvider)
    assert provider.model_name == "isnet_anime"
    assert provider.execution_provider == "uninitialized"
    assert provider._session is None


def test_isnet_provider_lazy_loading_invariant() -> None:
    """Verifies that instantiation does NOT load ONNX session or touch disk/network."""
    config = PipelineConfig(
        isnet_anime_model_path=Path("/tmp/nonexistent_dummy_model.onnx"),
    )
    provider = ISNetONNXProvider(config=config)
    assert provider._session is None
    # Calling release on uninitialized provider must be safe and idempotent
    provider.release()
    assert provider._session is None
    assert provider.execution_provider == "released"


@pytest.mark.asyncio
async def test_isnet_provider_missing_model_error_handling(tmp_path: Path) -> None:
    """Verifies clear exception is raised when model file is missing without process crash."""
    missing_path = tmp_path / "missing_isnet.onnx"
    config = PipelineConfig(isnet_anime_model_path=missing_path)
    provider = ISNetONNXProvider(config=config)

    dummy_img = Image.new("RGB", (256, 256), (255, 255, 255))
    buf = io.BytesIO()
    dummy_img.save(buf, format="PNG")

    with pytest.raises((FileNotFoundError, ModelNotFoundError)) as exc_info:
        await provider.remove_background(buf.getvalue())

    assert str(missing_path) in str(exc_info.value)
    assert provider._session is None


@pytest.mark.asyncio
async def test_isnet_provider_checksum_mismatch_error_handling(tmp_path: Path) -> None:
    """Verifies that corrupt or tampered model weights are rejected before loading."""
    corrupt_file = tmp_path / "corrupt_isnet.onnx"
    corrupt_file.write_bytes(b"MALICIOUS_OR_CORRUPT_PAYLOAD_NOT_ISNET")

    config = PipelineConfig(
        isnet_anime_model_path=corrupt_file,
        isnet_model_sha256="f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99",
        isnet_model_expected_size=176_069_933,
    )
    provider = ISNetONNXProvider(config=config)

    dummy_img = Image.new("RGB", (256, 256), (255, 255, 255))
    buf = io.BytesIO()
    dummy_img.save(buf, format="PNG")

    with pytest.raises((ValueError, ModelIntegrityError)) as exc_info:
        await provider.remove_background(buf.getvalue())

    assert "checksum mismatch" in str(exc_info.value).lower()
    assert provider._session is None


def test_model_verifier_direct_unit_tests(tmp_path: Path) -> None:
    """Unit test for verify_model_file function directly."""
    dummy_file = tmp_path / "test_file.bin"
    content = b"TEST_PAYLOAD" * 100
    dummy_file.write_bytes(content)

    # Missing file raises ModelNotFoundError (inherits FileNotFoundError)
    with pytest.raises(FileNotFoundError):
        verify_model_file(tmp_path / "nonexistent.bin")

    # Size mismatch raises ModelIntegrityError
    with pytest.raises(ModelIntegrityError) as exc_info:
        verify_model_file(dummy_file, expected_size=999999)
    assert "size mismatch" in str(exc_info.value).lower()

    # Wrong SHA-256 raises ModelIntegrityError
    with pytest.raises(ModelIntegrityError) as exc_info:
        verify_model_file(
            dummy_file,
            expected_sha256="0000000000000000000000000000000000000000000000000000000000000000",
            expected_size=len(content),
        )
    assert "checksum mismatch" in str(exc_info.value).lower()


def test_isnet_provider_idempotent_release() -> None:
    """Verifies that release() can be called multiple times cleanly without side-effects."""
    provider = ISNetONNXProvider()
    provider.release()
    provider.release()
    assert provider._session is None
    assert provider.execution_provider == "released"


def test_letterbox_preprocessing_aspect_ratios() -> None:
    """Tests symmetrical letterboxing on square, portrait, and landscape aspect ratios."""
    # Portrait 600x900 (typical anime character aspect ratio 2:3)
    portrait = Image.new("RGB", (600, 900), (120, 150, 200))
    tensor, meta = letterbox_preprocess(portrait, target_size=1024)

    assert tensor.shape == (1, 3, 1024, 1024)
    assert tensor.dtype == np.float32
    assert meta.orig_width == 600
    assert meta.orig_height == 900
    assert meta.new_height == 1024
    assert meta.pad_y == 0
    assert meta.pad_x > 0  # Black padding on sides

    # Landscape 1200x800
    landscape = Image.new("RGB", (1200, 800), (200, 100, 50))
    l_tensor, l_meta = letterbox_preprocess(landscape, target_size=1024)
    assert l_tensor.shape == (1, 3, 1024, 1024)
    assert l_meta.new_width == 1024
    assert l_meta.pad_x == 0
    assert l_meta.pad_y > 0  # Black padding top/bottom


def test_soft_alpha_ramp_interpolation() -> None:
    """Verifies that soft alpha ramp eliminates halos while preserving gradients."""
    probs = np.array(
        [
            [0.00, 0.04, 0.05],  # All <= 0.05 must be clamped to pure transparent 0
            [0.20, 0.50, 0.80],  # Soft transition values
            [0.95, 0.98, 1.00],  # All >= 0.95 must be clamped to solid opaque 255
        ],
        dtype=np.float32,
    )
    alpha = apply_soft_alpha_ramp(probs, t_low=0.05, t_high=0.95)

    assert alpha.dtype == np.uint8
    # Clamped background
    assert alpha[0, 0] == 0
    assert alpha[0, 1] == 0
    assert alpha[0, 2] == 0

    # Smooth transition
    assert 30 <= alpha[1, 0] <= 50  # ~42.5 -> 43
    assert 120 <= alpha[1, 1] <= 135  # ~127.5 -> 128
    assert 205 <= alpha[1, 2] <= 220  # ~212.5 -> 213

    # Clamped solid core
    assert alpha[2, 0] == 255
    assert alpha[2, 1] == 255
    assert alpha[2, 2] == 255


def test_postprocess_mask_geometry_and_alpha_merge() -> None:
    """Tests postprocessing unpadding, mode='F' bilinear resize, and putalpha merge."""
    orig_img = Image.new("RGB", (400, 600), (255, 0, 0))
    _, meta = letterbox_preprocess(orig_img, target_size=1024)

    # Synthetic mask with high probability in center
    raw_mask = np.zeros((1, 1, 1024, 1024), dtype=np.float32)
    raw_mask[0, 0, 300:700, 300:700] = 0.98

    png_bytes, diag = postprocess_mask(raw_mask, orig_img, meta)
    assert isinstance(png_bytes, bytes)
    assert len(png_bytes) > 0

    with Image.open(io.BytesIO(png_bytes)) as out_img:
        assert out_img.mode == "RGBA"
        # Verify RGB channels are preserved and alpha is genuine
        r, g, b, a_chan = out_img.split()
        assert r.getextrema() == (255, 255)
        assert g.getextrema() == (0, 0)
        assert b.getextrema() == (0, 0)
        assert a_chan.getextrema() == (0, 255)

    assert diag["dimensions"] == [400, 600]
    assert diag["alpha_extrema"] == [0, 255]
    total_px = 400 * 600
    assert diag["total_pixels"] == total_px
    assert diag["transparent_pixels"] + diag["soft_pixels"] + diag["solid_pixels"] == total_px
    assert diag["transitional_alpha_pixels"] <= diag["soft_pixels"]
    assert pytest.approx(diag["transparent_ratio"] + diag["soft_ratio"] + diag["solid_ratio"]) == 1.0


def test_background_provider_factory() -> None:
    """Verifies factory instantiation based on use_mock_bg_provider setting."""
    mock_cfg = PipelineConfig(use_mock_bg_provider=True)
    provider_mock = get_background_removal_provider(config=mock_cfg)
    assert isinstance(provider_mock, MockBackgroundRemovalProvider)

    onnx_cfg = PipelineConfig(use_mock_bg_provider=False)
    provider_onnx = get_background_removal_provider(config=onnx_cfg)
    assert isinstance(provider_onnx, ISNetONNXProvider)


@pytest.mark.asyncio
async def test_isnet_provider_concurrency_lock() -> None:
    """Verifies that asyncio.Lock protects lazy session loading under concurrency."""
    provider = ISNetONNXProvider()

    load_count = 0

    def mock_load_session() -> None:
        nonlocal load_count
        load_count += 1
        provider._session = MagicMock()
        provider._input_name = "img"
        provider._active_provider = "cpu"

    async def fake_remove_bg(image_bytes: bytes) -> tuple[bytes, dict[str, int]]:
        async with provider._lock:
            if provider._session is None:
                await asyncio.sleep(0.01)  # Simulate session init latency
                mock_load_session()
        return b"PNG_DATA", {"status": 1}

    with patch.object(provider, "remove_background", side_effect=fake_remove_bg):
        # Run 5 concurrent calls
        tasks = [provider.remove_background(b"dummy") for _ in range(5)]
        results = await asyncio.gather(*tasks)

    assert len(results) == 5
    assert load_count == 1  # Only loaded once
