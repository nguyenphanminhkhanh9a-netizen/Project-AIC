"""Tier 3 Real Inference Verification Suite on CPU.

Executes genuine IS-Net Anime ONNX inference on 5 real anime test images.
Verifies geometric preservation (0-pixel delta), authentic 4-channel RGBA generation,
extrema reach (0, 255), presence of continuous soft alpha transition pixels (N_soft > 0),
and saves verification artifacts to data/tier3_output/.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from app.domain.pipeline import BackgroundRemovalProvider
from app.pipeline.background.isnet_provider import ISNetONNXProvider
from app.pipeline.config import PipelineConfig

MODEL_DEFAULT_PATH = Path(os.path.expanduser("~/.cache/project_aic/models/isnetis.onnx"))
FIXTURES_DIR = Path("tests/fixtures/real_anime")
OUTPUT_DIR = Path("../data/tier3_output").resolve()

has_real_model = MODEL_DEFAULT_PATH.is_file()
has_fixtures = FIXTURES_DIR.is_dir() and len(list(FIXTURES_DIR.glob("*.png"))) >= 5

pytestmark = pytest.mark.skipif(
    not (has_real_model and has_fixtures),
    reason="Skipping Tier 3 because isnetis.onnx or real anime fixtures are not present",
)

SAMPLE_NAMES = [
    "sample_01_simple_bg",
    "sample_02_complex_bg",
    "sample_03_long_hair",
    "sample_04_small_accessories",
    "sample_05_translucent_costume",
]


from collections.abc import Generator


@pytest.fixture(scope="module")
def isnet_cpu_provider() -> Generator[BackgroundRemovalProvider, None, None]:
    """Initializes a real ISNetONNXProvider for the test module."""
    config = PipelineConfig(
        use_mock_bg_provider=False,
        isnet_anime_model_path=MODEL_DEFAULT_PATH,
        isnet_model_sha256="f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99",
        isnet_model_expected_size=176_069_933,
        onnx_intra_op_threads=4,
    )
    provider = ISNetONNXProvider(config=config)
    yield provider
    provider.release()


@pytest.mark.asyncio
@pytest.mark.parametrize("sample_name", SAMPLE_NAMES)
async def test_real_cpu_inference_on_anime_sample(
    isnet_cpu_provider: BackgroundRemovalProvider,
    sample_name: str,
) -> None:
    """Executes real ONNX CPU inference on an anime image and verifies 6 quantitative criteria."""
    sample_path = FIXTURES_DIR / f"{sample_name}.png"
    assert sample_path.is_file(), f"Test fixture {sample_path} not found"

    input_bytes = sample_path.read_bytes()
    with Image.open(io.BytesIO(input_bytes)) as in_img:
        orig_w, orig_h = in_img.size
        orig_rgb = in_img.convert("RGB")

    # Run genuine IS-Net background removal
    rgba_bytes, meta = await isnet_cpu_provider.remove_background(input_bytes)

    # 1. Byte validity and format
    assert isinstance(rgba_bytes, bytes)
    assert len(rgba_bytes) > 0

    with Image.open(io.BytesIO(rgba_bytes)) as out_img:
        # 2. Geometric Preservation (0-pixel delta)
        assert out_img.size == (orig_w, orig_h), (
            f"Dimension mismatch for {sample_name}: {out_img.size} vs {(orig_w, orig_h)}"
        )
        # 3. 4-channel RGBA mode
        assert out_img.mode == "RGBA"

        # 4. Alpha extrema and coverage
        alpha_chan = out_img.getchannel("A")
        alpha_arr = np.array(alpha_chan, dtype=np.uint8)
        min_alpha = int(alpha_arr.min())
        max_alpha = int(alpha_arr.max())
        assert min_alpha <= 5, f"{sample_name}: minimum alpha {min_alpha} > 5 (background not extracted)"
        assert max_alpha >= 250, f"{sample_name}: maximum alpha {max_alpha} < 250 (subject not solid)"

        # 5. Standardized 3 disjoint alpha pixel groups:
        # Transparent (alpha == 0), Soft (0 < alpha < 255), Solid (alpha == 255)
        total_pixels = alpha_arr.size
        transparent_pixels = int(np.count_nonzero(alpha_arr == 0))
        soft_pixels = int(np.count_nonzero((alpha_arr > 0) & (alpha_arr < 255)))
        solid_pixels = int(np.count_nonzero(alpha_arr == 255))
        assert transparent_pixels + soft_pixels + solid_pixels == total_pixels, (
            f"{sample_name}: alpha partition sum mismatch: "
            f"{transparent_pixels} + {soft_pixels} + {solid_pixels} != {total_pixels}"
        )
        assert soft_pixels > 0, (
            f"{sample_name}: No soft alpha anti-aliasing detected ({soft_pixels} pixels). "
            f"Expected neural gradient."
        )

        # Detailed transitional alpha threshold (10 <= alpha <= 245) for anti-aliasing gradient analysis
        transitional_alpha_pixels = int(np.count_nonzero((alpha_arr >= 10) & (alpha_arr <= 245)))
        assert transitional_alpha_pixels <= soft_pixels, (
            f"{sample_name}: transitional ({transitional_alpha_pixels}) > soft ({soft_pixels})"
        )
        assert transitional_alpha_pixels > 0, (
            f"{sample_name}: No transitional alpha detected in [10, 245] range"
        )

        # 6. Silhouette coverage limits
        solid_ratio = float(solid_pixels / total_pixels)
        transparent_ratio = float(transparent_pixels / total_pixels)
        soft_ratio = float(soft_pixels / total_pixels)
        assert 0.05 <= solid_ratio <= 0.95, (
            f"{sample_name}: solid ratio {solid_ratio:.3f} outside valid [0.05, 0.95] range"
        )
        assert transparent_ratio >= 0.05, (
            f"{sample_name}: transparent ratio {transparent_ratio:.3f} < 0.05"
        )

        # 7. RGB Color Preservation: solid character pixels must keep identical RGB values
        out_rgb = out_img.convert("RGB")
        solid_mask = alpha_arr == 255
        if np.any(solid_mask):
            diff = np.abs(
                np.array(out_rgb, dtype=np.int16) - np.array(orig_rgb, dtype=np.int16)
            )
            max_solid_rgb_diff = int(diff[solid_mask].max())
            assert max_solid_rgb_diff == 0, (
                f"{sample_name}: RGB values altered in solid core (max diff: {max_solid_rgb_diff})"
            )

    # 8. Save Verification Evidence Artifacts into data/tier3_output/
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_input_file = OUTPUT_DIR / f"{sample_name}_input.png"
    out_mask_file = OUTPUT_DIR / f"{sample_name}_mask.png"
    out_rgba_file = OUTPUT_DIR / f"{sample_name}_output.png"
    out_meta_file = OUTPUT_DIR / f"{sample_name}_meta.json"

    # Save input image
    orig_rgb.save(out_input_file, format="PNG")
    # Save grayscale mask
    alpha_chan.save(out_mask_file, format="PNG")
    # Save transparent RGBA output
    out_rgba_file.write_bytes(rgba_bytes)

    # Save standardized diagnostic metadata
    artifact_meta: dict[str, Any] = {
        "sample_name": sample_name,
        "model_name": meta.get("model_name"),
        "execution_provider": meta.get("execution_provider"),
        "latency_ms": meta.get("latency_ms"),
        "dimensions": [orig_w, orig_h],
        "alpha_extrema": [min_alpha, max_alpha],
        "total_pixels": total_pixels,
        "transparent_pixels": transparent_pixels,
        "soft_pixels": soft_pixels,
        "solid_pixels": solid_pixels,
        "transparent_ratio": transparent_ratio,
        "soft_ratio": soft_ratio,
        "solid_ratio": solid_ratio,
        "transitional_alpha_pixels": transitional_alpha_pixels,
        "transitional_alpha_ratio": float(transitional_alpha_pixels / total_pixels),
        # Backward compatibility aliases
        "soft_edge_pixels": soft_pixels,
        "opaque_ratio": solid_ratio,
    }
    out_meta_file.write_text(json.dumps(artifact_meta, indent=2), encoding="utf-8")
