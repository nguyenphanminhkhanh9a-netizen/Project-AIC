"""Adversarial stress test suite for Task 0.5B-1 Milestone 1 by Challenger 1.

Verifies:
1. image_ops.py: Extreme aspect ratios, boundary dimensions, color extrema, and geometry preservation.
2. model_verifier.py: Non-existent paths, size pre-check shortcutting without reading file,
   and 1-byte alteration detection on 176MB file.
3. isnet_provider.py: Concurrency race condition prevention, asyncio.Lock integrity on lazy loading,
   and concurrent real model inference.
"""

from __future__ import annotations

import asyncio
import io
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from app.pipeline.background.image_ops import (
    apply_soft_alpha_ramp,
    letterbox_preprocess,
    postprocess_mask,
)
from app.pipeline.background.isnet_provider import ISNetONNXProvider
from app.pipeline.config import PipelineConfig
from app.pipeline.security.model_verifier import (
    ISNET_MODEL_EXPECTED_SHA256,
    ISNET_MODEL_EXPECTED_SIZE,
    ModelIntegrityError,
    ModelNotFoundError,
    ModelVerificationError,
    verify_model_file,
)


class TestImageOpsExtremeDimensions:
    """Stress testing image_ops.py with extreme dimensions, aspect ratios, and color distributions."""

    @pytest.mark.parametrize(
        ("w", "h", "desc"),
        [
            (1, 1, "1x1 pixel"),
            (2, 2, "2x2 pixels"),
            (10, 1000, "10x1000 tall sliver"),
            (1000, 10, "1000x10 wide sliver"),
            (1, 2000, "1x2000 extreme vertical"),
            (2000, 1, "2000x1 extreme horizontal"),
            (1024, 1024, "1024x1024 exact canvas square"),
            (2048, 2048, "2048x2048 large square"),
            (333, 777, "333x777 odd portrait ratio"),
            (999, 111, "999x111 odd landscape ratio"),
            (7, 13, "7x13 prime ratio"),
        ],
    )
    def test_extreme_dimensions_geometry_preservation(self, w: int, h: int, desc: str) -> None:
        """Verifies that letterboxing and unpadding never crash or distort dimensions on extreme inputs."""
        img = Image.new("RGB", (w, h), (120, 140, 180))

        # Letterbox preprocess
        tensor, meta = letterbox_preprocess(img, target_size=1024)
        assert tensor.shape == (1, 3, 1024, 1024)
        assert tensor.dtype == np.float32
        assert not np.isnan(tensor).any()
        assert not np.isinf(tensor).any()
        assert meta.orig_width == w and meta.orig_height == h
        assert meta.pad_x >= 0 and meta.pad_y >= 0

        # Simulate synthetic probability mask with circle in center
        raw_mask = np.zeros((1, 1, 1024, 1024), dtype=np.float32)
        y, x = np.ogrid[:1024, :1024]
        mask_circle = (x - 512) ** 2 + (y - 512) ** 2 <= 250**2
        raw_mask[0, 0, mask_circle] = 0.95

        # Postprocess unpad and merge
        out_png_bytes, diag_meta = postprocess_mask(raw_mask, img, meta)
        assert isinstance(out_png_bytes, bytes)
        assert len(out_png_bytes) > 0
        assert diag_meta["transparent_pixels"] + diag_meta["soft_pixels"] + diag_meta["solid_pixels"] == w * h
        assert diag_meta["transitional_alpha_pixels"] <= diag_meta["soft_pixels"]

        with Image.open(io.BytesIO(out_png_bytes)) as out_img:
            assert out_img.mode == "RGBA"
            assert out_img.size == (w, h), f"Failed for {desc}: got {out_img.size}, expected {(w, h)}"

    @pytest.mark.parametrize(
        ("mode", "color", "desc"),
        [
            ("RGB", (0, 0, 0), "pure black RGB"),
            ("RGB", (255, 255, 255), "pure white RGB"),
            ("RGB", (128, 128, 128), "pure gray RGB"),
            ("RGBA", (0, 0, 0, 0), "pure transparent RGBA"),
            ("RGBA", (255, 128, 64, 255), "fully opaque RGBA"),
            ("RGBA", (100, 200, 50, 128), "semi-transparent RGBA"),
            ("L", 200, "grayscale mode L"),
        ],
    )
    def test_extreme_color_modes_and_transparency(self, mode: str, color: object, desc: str) -> None:
        """Verifies color extrema and various Pillow image modes are handled cleanly without NaNs."""
        img = Image.new(mode, (400, 600), color)  # type: ignore[arg-type]

        tensor, meta = letterbox_preprocess(img, target_size=1024)
        assert tensor.shape == (1, 3, 1024, 1024)
        assert not np.isnan(tensor).any()
        assert not np.isinf(tensor).any()

        # Zero mask -> pure transparent output
        zero_mask = np.zeros((1, 1, 1024, 1024), dtype=np.float32)
        out_bytes, _diag = postprocess_mask(zero_mask, img, meta)
        with Image.open(io.BytesIO(out_bytes)) as out_img:
            assert out_img.mode == "RGBA"
            assert out_img.size == (400, 600)
            alpha_arr = np.array(out_img.getchannel("A"))
            assert int(alpha_arr.max()) == 0

    def test_dynamic_sigmoid_activation_on_unnormalized_logits(self) -> None:
        """Verifies that masks with values outside [0.0, 1.0] are safely passed through sigmoid."""
        img = Image.new("RGB", (300, 300), (255, 200, 100))
        _, meta = letterbox_preprocess(img, target_size=1024)

        # Unnormalized logits tensor with range [-15.0, 15.0]
        logits_mask = np.full((1, 1, 1024, 1024), -15.0, dtype=np.float32)
        logits_mask[0, 0, 200:800, 200:800] = 15.0

        out_bytes, _diag = postprocess_mask(logits_mask, img, meta)
        with Image.open(io.BytesIO(out_bytes)) as out_img:
            assert out_img.mode == "RGBA"
            alpha_arr = np.array(out_img.getchannel("A"))
            assert alpha_arr.min() == 0
            assert alpha_arr.max() == 255

    def test_invalid_mask_dimensions_raises_value_error(self) -> None:
        """Verifies that non-2D squeezed masks trigger a clear ValueError."""
        img = Image.new("RGB", (200, 200), (0, 0, 0))
        _, meta = letterbox_preprocess(img, target_size=1024)

        invalid_mask = np.zeros((1, 5, 1024, 1024), dtype=np.float32)
        with pytest.raises(ValueError, match="Expected 2D squeezed mask tensor"):
            postprocess_mask(invalid_mask, img, meta)

    def test_soft_alpha_ramp_exact_quantization_boundaries(self) -> None:
        """Verifies soft alpha ramp threshold clamping and discrete 8-bit quantization steps."""
        probs = np.array(
            [-5.0, 0.0, 0.0499, 0.05, 0.055, 0.50, 0.945, 0.95, 0.9501, 1.0, 5.0],
            dtype=np.float32,
        )
        alphas = apply_soft_alpha_ramp(probs, t_low=0.05, t_high=0.95)

        assert alphas[0] == 0
        assert alphas[1] == 0
        assert alphas[2] == 0
        assert alphas[3] == 0
        assert alphas[4] > 0
        assert 126 <= alphas[5] <= 129
        assert alphas[6] < 255
        assert alphas[7] == 255
        assert alphas[8] == 255
        assert alphas[9] == 255
        assert alphas[10] == 255


class TestModelVerifierAdversarial:
    """Stress testing model_verifier.py with malicious payloads, wrong sizes, and bitflips."""

    def test_non_existent_model_file_raises_not_found(self, tmp_path: Path) -> None:
        """Verifies non-existent path raises ModelNotFoundError inheriting FileNotFoundError."""
        missing = tmp_path / "ghost_model.onnx"
        with pytest.raises(ModelNotFoundError) as exc_info:
            verify_model_file(missing)

        assert isinstance(exc_info.value, FileNotFoundError)
        assert isinstance(exc_info.value, ModelVerificationError)
        assert str(missing) in str(exc_info.value)

    def test_size_precheck_shortcut_prevents_file_read(self, tmp_path: Path) -> None:
        """Verifies that size pre-check fails immediately and DOES NOT read file contents."""
        wrong_size = tmp_path / "truncated_model.onnx"
        wrong_size.write_bytes(b"SHORT_PAYLOAD" * 50)

        open_called = False
        original_open = open

        def tracking_open(*args: Any, **kwargs: Any) -> Any:
            nonlocal open_called
            open_called = True
            return original_open(*args, **kwargs)

        with (
            patch("builtins.open", side_effect=tracking_open),
            pytest.raises(ModelIntegrityError) as exc_info,
        ):
            verify_model_file(
                wrong_size,
                expected_size=ISNET_MODEL_EXPECTED_SIZE,
                expected_sha256=ISNET_MODEL_EXPECTED_SHA256,
            )

        assert not open_called, "Security defect: file was read despite size mismatch pre-check failure!"
        assert "size mismatch" in str(exc_info.value).lower()

    def test_176mb_file_with_checksum_mismatch_and_1byte_alteration(self, tmp_path: Path) -> None:
        """Verifies that exact size (176,069,933 bytes) with 1 altered byte fails checksum validation."""
        tampered_file = tmp_path / "tampered_176mb.onnx"
        target_size = ISNET_MODEL_EXPECTED_SIZE
        block_size = 4 * 1024 * 1024
        chunk = b"\x55" * block_size

        written = 0
        with open(tampered_file, "wb") as f:
            while written < target_size:
                to_write = min(block_size, target_size - written)
                f.write(chunk[:to_write])
                written += to_write

        assert tampered_file.stat().st_size == target_size

        # 1. Size matches, but contents differ -> ModelIntegrityError
        with pytest.raises(ModelIntegrityError) as exc_info:
            verify_model_file(
                tampered_file,
                expected_size=ISNET_MODEL_EXPECTED_SIZE,
                expected_sha256=ISNET_MODEL_EXPECTED_SHA256,
            )

        err_msg = str(exc_info.value)
        assert "checksum mismatch" in err_msg.lower()
        assert ISNET_MODEL_EXPECTED_SHA256 in err_msg.lower()
        assert tampered_file.name in err_msg

        # 2. Alter exactly 1 byte in the 176MB file
        with open(tampered_file, "r+b") as f:
            f.seek(target_size - 1)
            byte_val = f.read(1)
            f.seek(target_size - 1)
            f.write(bytes([(byte_val[0] ^ 0xFF)]))

        assert tampered_file.stat().st_size == target_size
        with pytest.raises(ModelIntegrityError):
            verify_model_file(
                tampered_file,
                expected_size=ISNET_MODEL_EXPECTED_SIZE,
                expected_sha256=ISNET_MODEL_EXPECTED_SHA256,
            )


class TestISNetProviderConcurrency:
    """Stress testing concurrency on ISNetONNXProvider under high asynchronous load."""

    @pytest.mark.asyncio
    async def test_concurrent_uninitialized_calls_serialized_by_lock(self) -> None:
        """Verifies that asyncio.Lock prevents duplicate session initialization under concurrency."""
        provider = ISNetONNXProvider()
        load_count = 0

        def slow_load_session_sync() -> None:
            nonlocal load_count
            load_count += 1
            # Simulate I/O and session initialization delay
            time.sleep(0.05)
            provider._session = MagicMock()
            provider._input_name = "test_input"
            provider._active_provider = "cpu"

        def fake_run_inference_sync(img_bytes: bytes, **kwargs: object) -> tuple[bytes, dict[str, object]]:
            return b"FAKED_PNG", {"latency_ms": 1.0}

        provider._load_session_sync = slow_load_session_sync  # type: ignore[assignment]
        provider._run_inference_sync = fake_run_inference_sync  # type: ignore[assignment]

        # Launch 15 concurrent calls
        tasks = [provider.remove_background(b"INPUT_BYTES") for _ in range(15)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 15
        for png_bytes, meta in results:
            assert png_bytes == b"FAKED_PNG"

        # Concurrency safety invariant: session loaded exactly ONCE
        assert load_count == 1, (
            f"Race condition detected: _load_session_sync was invoked {load_count} times instead of 1!"
        )

    @pytest.mark.asyncio
    async def test_repeated_concurrent_release_is_idempotent(self) -> None:
        """Verifies that calling release() repeatedly or concurrently is completely idempotent."""
        provider = ISNetONNXProvider()
        for _ in range(10):
            provider.release()

        assert provider._session is None
        assert provider.execution_provider == "released"

    @pytest.mark.asyncio
    async def test_real_model_concurrent_inference_stress(self) -> None:
        """Verifies real model inference with 5 concurrent requests if model is installed."""
        model_path = Path.home() / ".cache" / "project_aic" / "models" / "isnetis.onnx"
        fixtures_dir = Path("tests/fixtures/real_anime")

        if not (model_path.is_file() and fixtures_dir.is_dir()):
            pytest.skip("Real model weights or anime fixtures are not available")

        fixture_files = list(fixtures_dir.glob("*.png"))
        if len(fixture_files) < 5:
            pytest.skip("Less than 5 fixture images found")

        config = PipelineConfig(
            use_mock_bg_provider=False,
            isnet_anime_model_path=model_path,
            isnet_model_sha256=ISNET_MODEL_EXPECTED_SHA256,
            isnet_model_expected_size=ISNET_MODEL_EXPECTED_SIZE,
            onnx_intra_op_threads=4,
        )
        provider = ISNetONNXProvider(config=config)

        images_bytes = [f.read_bytes() for f in fixture_files[:5]]
        tasks = [provider.remove_background(b) for b in images_bytes]

        results = await asyncio.gather(*tasks)
        assert len(results) == 5

        for out_png, diag in results:
            with Image.open(io.BytesIO(out_png)) as out_img:
                assert out_img.mode == "RGBA"
                alpha_arr = np.array(out_img.getchannel("A"))
                assert int(alpha_arr.min()) <= 5
                assert int(alpha_arr.max()) >= 250
                total_pixels = alpha_arr.size
                transparent_pixels = int(np.count_nonzero(alpha_arr == 0))
                soft_pixels = int(np.count_nonzero((alpha_arr > 0) & (alpha_arr < 255)))
                solid_pixels = int(np.count_nonzero(alpha_arr == 255))
                assert transparent_pixels + soft_pixels + solid_pixels == total_pixels
                transitional_alpha_pixels = int(np.count_nonzero((alpha_arr >= 10) & (alpha_arr <= 245)))
                assert transitional_alpha_pixels <= soft_pixels
                assert soft_pixels > 0
                assert transitional_alpha_pixels > 0

        provider.release()
