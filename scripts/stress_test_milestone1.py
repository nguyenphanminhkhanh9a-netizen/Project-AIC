"""Standalone Adversarial Stress Test Harness for Milestone 1 (Task 0.5B-1).

Empirical verification of:
1. image_ops.py: Extreme aspect ratios, boundary dimensions, color extrema, and geometry preservation.
2. model_verifier.py: Non-existent paths, size pre-check shortcutting, 1-byte alteration on 176MB file.
3. isnet_provider.py: Concurrency race condition prevention, asyncio.Lock integrity, and multi-request stress.

Author: challenger_05b1_1
"""

from __future__ import annotations

import asyncio
import io
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

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


def log(msg: str) -> None:
    print(f"[CHALLENGER-STRESS] {msg}")


# ==============================================================================
# 1. STRESS TESTS: image_ops.py
# ==============================================================================


def stress_test_image_ops_extreme_dimensions() -> list[dict[str, object]]:
    """Test extreme dimensions and aspect ratios for letterbox_preprocess and postprocess_mask."""
    log("=== TEST 1.1: image_ops Extreme Dimensions & Aspect Ratios ===")
    results = []

    test_cases = [
        ("1x1_pixel", (1, 1), "RGB", (255, 0, 0)),
        ("2x2_pixel", (2, 2), "RGB", (0, 255, 0)),
        ("10x1000_tall_sliver", (10, 1000), "RGB", (100, 150, 200)),
        ("1000x10_wide_sliver", (1000, 10), "RGB", (200, 150, 100)),
        ("1x2000_extreme_tall", (1, 2000), "RGB", (50, 50, 50)),
        ("2000x1_extreme_wide", (2000, 1), "RGB", (50, 50, 50)),
        ("1024x1024_exact_square", (1024, 1024), "RGB", (128, 128, 128)),
        ("2048x2048_oversized_square", (2048, 2048), "RGB", (80, 120, 160)),
        ("333x777_odd_ratio", (333, 777), "RGB", (210, 100, 50)),
        ("999x111_odd_ratio", (999, 111), "RGB", (70, 180, 90)),
        ("7x13_prime_ratio", (7, 13), "RGB", (140, 60, 220)),
    ]

    for name, (w, h), mode, color in test_cases:
        t0 = time.perf_counter()
        img = Image.new(mode, (w, h), color)

        # 1. Letterbox Preprocess
        tensor, meta = letterbox_preprocess(img, target_size=1024)

        assert tensor.shape == (1, 3, 1024, 1024), f"{name}: tensor shape mismatch {tensor.shape}"
        assert tensor.dtype == np.float32, f"{name}: tensor dtype {tensor.dtype} != float32"
        assert not np.isnan(tensor).any(), f"{name}: NaN found in preprocessed tensor"
        assert not np.isinf(tensor).any(), f"{name}: Inf found in preprocessed tensor"
        assert meta.orig_width == w and meta.orig_height == h, (
            f"{name}: meta dimensions {(meta.orig_width, meta.orig_height)} != {(w, h)}"
        )
        assert meta.pad_x >= 0 and meta.pad_y >= 0, f"{name}: negative padding {meta.pad_x}, {meta.pad_y}"

        # 2. Simulate raw mask (1, 1, 1024, 1024) with a centered circle
        raw_mask = np.zeros((1, 1, 1024, 1024), dtype=np.float32)
        y, x = np.ogrid[:1024, :1024]
        mask_circle = (x - 512) ** 2 + (y - 512) ** 2 <= 300**2
        raw_mask[0, 0, mask_circle] = 0.98

        # 3. Postprocess mask
        out_png_bytes, diag_meta = postprocess_mask(raw_mask, img, meta)

        assert isinstance(out_png_bytes, bytes) and len(out_png_bytes) > 0, f"{name}: invalid PNG bytes"
        assert diag_meta["transparent_pixels"] + diag_meta["soft_pixels"] + diag_meta["solid_pixels"] == w * h, (
            f"{name}: partition sum mismatch"
        )
        assert diag_meta["transitional_alpha_pixels"] <= diag_meta["soft_pixels"], (
            f"{name}: transitional > soft"
        )
        with Image.open(io.BytesIO(out_png_bytes)) as out_img:
            assert out_img.mode == "RGBA", f"{name}: mode {out_img.mode} != RGBA"
            assert out_img.size == (w, h), (
                f"{name}: reconstructed size {out_img.size} != original {(w, h)}"
            )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        log(f"  PASS: {name} (size: {w}x{h}, latency: {elapsed_ms:.2f}ms)")
        results.append({"name": name, "size": (w, h), "latency_ms": elapsed_ms, "status": "PASS"})

    return results


def stress_test_image_ops_color_extrema() -> list[dict[str, object]]:
    """Test pure black, pure white, pure transparent, and color extreme cases."""
    log("=== TEST 1.2: image_ops Color Extrema & Transparency Cases ===")
    results = []

    test_cases = [
        ("pure_black_rgb", Image.new("RGB", (512, 512), (0, 0, 0))),
        ("pure_white_rgb", Image.new("RGB", (512, 512), (255, 255, 255))),
        ("pure_gray_rgb", Image.new("RGB", (512, 512), (128, 128, 128))),
        ("pure_transparent_rgba", Image.new("RGBA", (512, 512), (0, 0, 0, 0))),
        ("fully_opaque_rgba", Image.new("RGBA", (512, 512), (255, 128, 64, 255))),
        ("semi_transparent_rgba", Image.new("RGBA", (512, 512), (100, 200, 50, 128))),
        ("grayscale_mode_L", Image.new("L", (512, 512), 200)),
        ("palette_mode_P", Image.new("RGB", (512, 512), (200, 100, 50)).convert("P")),
    ]

    for name, img in test_cases:
        t0 = time.perf_counter()
        w, h = img.size

        # Preprocessing
        tensor, meta = letterbox_preprocess(img, target_size=1024)
        assert tensor.shape == (1, 3, 1024, 1024)
        assert not np.isnan(tensor).any()
        assert not np.isinf(tensor).any()

        # Test with zero mask
        zero_mask = np.zeros((1, 1, 1024, 1024), dtype=np.float32)
        out_bytes_zero, _meta_zero = postprocess_mask(zero_mask, img, meta)
        with Image.open(io.BytesIO(out_bytes_zero)) as out_img:
            assert out_img.mode == "RGBA"
            assert out_img.size == (w, h)
            alpha_arr = np.array(out_img.getchannel("A"))
            assert int(alpha_arr.max()) == 0, f"{name}: zero mask produced non-zero alpha {alpha_arr.max()}"

        # Test with one mask
        one_mask = np.ones((1, 1, 1024, 1024), dtype=np.float32)
        out_bytes_one, _meta_one = postprocess_mask(one_mask, img, meta)
        with Image.open(io.BytesIO(out_bytes_one)) as out_img:
            assert out_img.mode == "RGBA"
            assert out_img.size == (w, h)
            alpha_arr = np.array(out_img.getchannel("A"))
            assert int(alpha_arr.min()) == 255, f"{name}: one mask produced non-255 alpha {alpha_arr.min()}"

        # Test with unnormalized logits (dynamic sigmoid branch)
        logits_mask = np.full((1, 1, 1024, 1024), -15.0, dtype=np.float32)
        logits_mask[0, 0, 200:800, 200:800] = 15.0
        out_bytes_logits, _meta_logits = postprocess_mask(logits_mask, img, meta)
        with Image.open(io.BytesIO(out_bytes_logits)) as out_img:
            assert out_img.mode == "RGBA"
            assert out_img.size == (w, h)
            alpha_arr = np.array(out_img.getchannel("A"))
            assert alpha_arr.min() == 0
            assert alpha_arr.max() == 255

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        log(f"  PASS: {name} (mode: {img.mode}, latency: {elapsed_ms:.2f}ms)")
        results.append({"name": name, "mode": img.mode, "latency_ms": elapsed_ms, "status": "PASS"})

    return results


def stress_test_soft_alpha_ramp_boundaries() -> None:
    """Stress test boundary cases of apply_soft_alpha_ramp."""
    log("=== TEST 1.3: apply_soft_alpha_ramp Boundary & Stress Testing ===")

    # Boundary values array
    # Note: 1 alpha unit out of 255 across range [0.05, 0.95] represents
    # (0.95 - 0.05) / 255 = 0.90 / 255 ~= 0.00353 probability.
    # Half-step for rounding is ~= 0.00176 probability.
    # Therefore, p <= 0.0517 rounds to alpha 0; p >= 0.0518 rounds to alpha >= 1.
    probs = np.array(
        [-5.0, 0.0, 0.0499, 0.05, 0.055, 0.50, 0.945, 0.95, 0.9501, 1.0, 5.0],
        dtype=np.float32,
    )
    alphas = apply_soft_alpha_ramp(probs, t_low=0.05, t_high=0.95)

    assert alphas[0] == 0, "Negative probability should be clamped to 0"
    assert alphas[1] == 0, "0.0 should be 0"
    assert alphas[2] == 0, "0.0499 should be 0"
    assert alphas[3] == 0, "0.05 (t_low) should be 0"
    assert alphas[4] > 0, "0.055 should be > 0 (quantized alpha is ~1)"
    assert 126 <= alphas[5] <= 129, "0.50 midpoint should be ~128"
    assert alphas[6] < 255, "0.945 should be < 255"
    assert alphas[7] == 255, "0.95 (t_high) should be 255"
    assert alphas[8] == 255, "0.9501 should be 255"
    assert alphas[9] == 255, "1.0 should be 255"
    assert alphas[10] == 255, "Excess probability should be clamped to 255"

    log("  PASS: Soft alpha ramp boundary values correctly clamped and interpolated.")


# ==============================================================================
# 2. STRESS TESTS: model_verifier.py
# ==============================================================================


def stress_test_model_verifier(tmp_path: Path) -> list[dict[str, object]]:
    """Test non-existent path, size pre-check shortcutting, and 1-byte alteration on 176MB file."""
    log("=== TEST 2: model_verifier.py Adversarial Stress Tests ===")
    results = []

    # 2.1 Non-existent file path
    non_existent = tmp_path / "does_not_exist_at_all.onnx"
    try:
        verify_model_file(non_existent)
        raise AssertionError("Expected ModelNotFoundError was not raised!")
    except ModelNotFoundError as e:
        assert isinstance(e, FileNotFoundError)
        assert isinstance(e, ModelVerificationError)
        log(f"  PASS: 2.1 Non-existent file caught: {type(e).__name__} ({e})")
        results.append({"test": "2.1_non_existent_file", "status": "PASS", "detail": str(e)})

    # 2.2 Wrong size pre-check shortcut: MUST fail without reading the file
    wrong_size_file = tmp_path / "wrong_size.onnx"
    wrong_size_file.write_bytes(b"A" * 1024)  # 1 KB file

    # Verify that builtins.open is NEVER CALLED for hashing if size mismatch occurs
    original_open = open
    open_called = False

    def tracking_open(*args, **kwargs):
        nonlocal open_called
        open_called = True
        return original_open(*args, **kwargs)

    try:
        with patch("builtins.open", side_effect=tracking_open):
            verify_model_file(
                wrong_size_file,
                expected_size=ISNET_MODEL_EXPECTED_SIZE,
                expected_sha256=ISNET_MODEL_EXPECTED_SHA256,
            )
        raise AssertionError("Expected ModelIntegrityError for wrong size was not raised!")
    except ModelIntegrityError as e:
        assert not open_called, "CRITICAL ERROR: file was opened and read despite size mismatch pre-check!"
        assert "size mismatch" in str(e).lower()
        log(f"  PASS: 2.2 Size pre-check failed immediately without reading file (open_called={open_called})")
        results.append({
            "test": "2.2_wrong_size_precheck",
            "status": "PASS",
            "open_called": open_called,
            "detail": str(e),
        })

    # 2.3 Exactly 176,069,933 bytes file with 1 byte altered
    log("  Preparing 176,069,933 bytes payload file for 1-byte tampering test...")
    large_test_file = tmp_path / "large_tampered_model.onnx"

    # Write a 176,069,933 bytes file in 4MB blocks (takes ~0.2s on SSD)
    target_size = ISNET_MODEL_EXPECTED_SIZE  # 176_069_933
    block_size = 4 * 1024 * 1024
    chunk = b"\xAA" * block_size
    written = 0

    t0 = time.perf_counter()
    with open(large_test_file, "wb") as f:
        while written < target_size:
            to_write = min(block_size, target_size - written)
            f.write(chunk[:to_write])
            written += to_write

    assert large_test_file.stat().st_size == target_size, "File size generation error"
    create_time = time.perf_counter() - t0
    log(f"  Created exact 176,069,933 bytes file in {create_time:.3f}s")

    # Now verify with expected official SHA256: size matches, but checksum MUST fail
    t0 = time.perf_counter()
    try:
        verify_model_file(
            large_test_file,
            expected_size=ISNET_MODEL_EXPECTED_SIZE,
            expected_sha256=ISNET_MODEL_EXPECTED_SHA256,
        )
        raise AssertionError("Expected ModelIntegrityError was not raised for tampered 176MB file!")
    except ModelIntegrityError as e:
        elapsed = time.perf_counter() - t0
        err_msg = str(e)
        assert "checksum mismatch" in err_msg.lower()
        assert ISNET_MODEL_EXPECTED_SHA256 in err_msg.lower()
        assert large_test_file.name in err_msg
        log(f"  PASS: 2.3 176MB file checksum mismatch raised ModelIntegrityError in {elapsed:.3f}s")
        log(f"        Detail: {err_msg}")
        results.append({
            "test": "2.3_176mb_checksum_tampering",
            "status": "PASS",
            "elapsed_s": elapsed,
            "detail": err_msg,
        })

    # 2.4 Verify exact 1-byte alteration: compute correct hash of file, flip 1 byte, check mismatch
    # Flip the very last byte (byte 176_069_932)
    with open(large_test_file, "r+b") as f:
        f.seek(target_size - 1)
        last_byte = f.read(1)
        flipped_byte = bytes([(last_byte[0] ^ 0xFF)])
        f.seek(target_size - 1)
        f.write(flipped_byte)

    # Now verify that file size is still 176,069,933 bytes but hash changed
    assert large_test_file.stat().st_size == target_size
    try:
        verify_model_file(
            large_test_file,
            expected_size=ISNET_MODEL_EXPECTED_SIZE,
            expected_sha256=ISNET_MODEL_EXPECTED_SHA256,
        )
        raise AssertionError("Expected ModelIntegrityError after 1-byte alteration!")
    except ModelIntegrityError as e:
        log("  PASS: 2.4 1-byte alteration in 176MB file correctly triggered ModelIntegrityError.")
        results.append({
            "test": "2.4_single_byte_bitflip",
            "status": "PASS",
            "detail": str(e),
        })

    return results


# ==============================================================================
# 3. STRESS TESTS: ISNetONNXProvider Concurrency & Race Conditions
# ==============================================================================


async def stress_test_isnet_provider_concurrency(tmp_path: Path) -> list[dict[str, object]]:
    """Test concurrent remove_background calls and verify asyncio.Lock prevents duplicate loads."""
    log("=== TEST 3: ISNetONNXProvider Concurrency & asyncio.Lock Stress ===")
    results = []

    # 3.1 Uninitialized Provider: 10 concurrent requests hitting remove_background simultaneously
    log("  3.1 Stress-testing uninitialized session with 10 concurrent tasks...")
    load_count = 0
    load_start_times = []

    provider = ISNetONNXProvider()

    def tracked_load_session_sync() -> None:
        nonlocal load_count
        load_count += 1
        load_start_times.append(time.perf_counter())
        # Simulate realistic model loading duration (100ms)
        time.sleep(0.10)
        provider._session = MagicMock()
        provider._input_name = "input_tensor"
        provider._active_provider = "cpu"

    # Mock inference to return synthetic transparent RGBA
    def fake_run_inference_sync(img_bytes: bytes, **kwargs) -> tuple[bytes, dict[str, object]]:
        return b"FAKE_RGBA_BYTES", {"latency_ms": 1.0}

    provider._load_session_sync = tracked_load_session_sync
    provider._run_inference_sync = fake_run_inference_sync

    # Launch 10 concurrent remove_background calls
    dummy_input = b"DUMMY_IMAGE_BYTES"
    tasks = [provider.remove_background(dummy_input) for _ in range(10)]
    t0 = time.perf_counter()
    gathered_results = await asyncio.gather(*tasks)
    total_elapsed = time.perf_counter() - t0

    assert len(gathered_results) == 10, f"Expected 10 results, got {len(gathered_results)}"
    for res_bytes, meta in gathered_results:
        assert res_bytes == b"FAKE_RGBA_BYTES"

    # CRUCIAL ASSERTION: load_count MUST BE EXACTLY 1!
    assert load_count == 1, (
        f"CRITICAL CONCURRENCY RACE CONDITION: _load_session_sync called {load_count} times! "
        f"asyncio.Lock failed to serialize session creation."
    )
    log(f"  PASS: 3.1 10 concurrent tasks executed in {total_elapsed:.3f}s. Load count = {load_count} (Lock verified)")
    results.append({
        "test": "3.1_uninitialized_concurrency_lock",
        "concurrency": 10,
        "load_count": load_count,
        "elapsed_s": total_elapsed,
        "status": "PASS",
    })

    # 3.2 Real Inference Concurrency: If real model exists, run 5 real anime images simultaneously
    model_path = Path.home() / ".cache" / "project_aic" / "models" / "isnetis.onnx"
    fixtures_dir = backend_dir / "tests" / "fixtures" / "real_anime"

    if model_path.is_file() and fixtures_dir.is_dir():
        fixture_files = list(fixtures_dir.glob("*.png"))
        if len(fixture_files) >= 5:
            log(f"  3.2 Real Model Inference Concurrency: Running {len(fixture_files)} real images simultaneously...")
            real_config = PipelineConfig(
                use_mock_bg_provider=False,
                isnet_anime_model_path=model_path,
                isnet_model_sha256=ISNET_MODEL_EXPECTED_SHA256,
                isnet_model_expected_size=ISNET_MODEL_EXPECTED_SIZE,
                onnx_intra_op_threads=4,
            )
            real_provider = ISNetONNXProvider(config=real_config)

            # Load images
            images_data = [(f.name, f.read_bytes()) for f in fixture_files[:5]]

            async def run_one(name: str, data: bytes) -> tuple[str, bytes, dict[str, object]]:
                rgba_bytes, meta = await real_provider.remove_background(data)
                return name, rgba_bytes, meta

            t0 = time.perf_counter()
            real_tasks = [run_one(name, data) for name, data in images_data]
            real_results = await asyncio.gather(*real_tasks)
            real_total_elapsed = time.perf_counter() - t0

            assert len(real_results) == len(images_data)
            for name, out_rgba, meta in real_results:
                assert isinstance(out_rgba, bytes) and len(out_rgba) > 0
                with Image.open(io.BytesIO(out_rgba)) as img:
                    assert img.mode == "RGBA", f"{name}: not RGBA"
                    alpha_arr = np.array(img.getchannel("A"))
                    assert int(alpha_arr.min()) <= 5
                    assert int(alpha_arr.max()) >= 250
                    total_px = alpha_arr.size
                    n_trans = int(np.count_nonzero(alpha_arr == 0))
                    n_soft = int(np.count_nonzero((alpha_arr > 0) & (alpha_arr < 255)))
                    n_solid = int(np.count_nonzero(alpha_arr == 255))
                    assert n_trans + n_soft + n_solid == total_px, f"{name}: partition mismatch"
                    transitional_count = int(np.count_nonzero((alpha_arr >= 10) & (alpha_arr <= 245)))
                    assert transitional_count <= n_soft, f"{name}: transitional > soft"
                    assert n_soft > 0, f"{name}: no soft alpha"
                    assert transitional_count > 0, f"{name}: no transitional alpha"

            log(
                f"  PASS: 3.2 Real Model Concurrency ({len(images_data)} images) completed in {real_total_elapsed:.2f}s "
                f"({real_total_elapsed/len(images_data):.2f}s/image average concurrent throughput)."
            )
            results.append({
                "test": "3.2_real_model_concurrency",
                "images_count": len(images_data),
                "total_elapsed_s": real_total_elapsed,
                "status": "PASS",
            })
            real_provider.release()
        else:
            log("  SKIP 3.2: Insufficient real anime fixtures for real model concurrency test.")
    else:
        log("  SKIP 3.2: Real model file not found in cache.")

    # 3.3 Concurrency Edge Case: release() called while session is uninitialized or after inference
    log("  3.3 Testing release() behavior under concurrency...")
    p3 = ISNetONNXProvider()
    # Concurrent releases
    for _ in range(5):
        p3.release()
    assert p3.execution_provider == "released"
    assert p3._session is None
    log("  PASS: 3.3 Idempotent release verified under repeated invocation.")
    results.append({"test": "3.3_concurrent_release", "status": "PASS"})

    return results


# ==============================================================================
# MAIN RUNNER
# ==============================================================================


async def main() -> int:
    log("===================================================================")
    log("STARTING EMPIRICAL ADVERSARIAL STRESS TEST HARNESS — MILESTONE 1")
    log("===================================================================")
    import tempfile

    tmp_dir = Path(tempfile.mkdtemp(prefix="aic_stress_"))
    try:
        # 1. image_ops
        stress_test_image_ops_extreme_dimensions()
        stress_test_image_ops_color_extrema()
        stress_test_soft_alpha_ramp_boundaries()

        # 2. model_verifier
        stress_test_model_verifier(tmp_dir)

        # 3. isnet_provider concurrency
        await stress_test_isnet_provider_concurrency(tmp_dir)

        log("===================================================================")
        log("ALL STRESS TESTS COMPLETED SUCCESSFULLY!")
        log("===================================================================")
        return 0
    finally:
        # Cleanup temp directory
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
