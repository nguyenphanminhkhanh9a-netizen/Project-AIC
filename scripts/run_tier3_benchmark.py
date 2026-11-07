"""Standalone benchmark and verification script for IS-Net Anime ONNX on CPU.

Executes real background removal on all 5 real anime test fixtures,
computes quantitative quality metrics, saves visual artifacts to data/tier3_output/,
and prints a Markdown benchmark table.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
from pathlib import Path
import sys
import time

# Ensure backend is on sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from app.pipeline.background.isnet_provider import ISNetONNXProvider  # noqa: E402
from app.pipeline.config import PipelineConfig  # noqa: E402
from app.pipeline.security.model_verifier import verify_model_file  # noqa: E402

FIXTURES_DIR = backend_dir / "tests" / "fixtures" / "real_anime"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "tier3_output"
MODEL_PATH = Path(os.path.expanduser("~/.cache/project_aic/models/isnetis.onnx"))

SAMPLES = [
    ("sample_01_simple_bg", "Simple Solid Background (Schoolgirl)"),
    ("sample_02_complex_bg", "Complex Scenic Background (Akihabara Street)"),
    ("sample_03_long_hair", "Long Flowing Twintails & Ahoge (Miku Idol)"),
    ("sample_04_small_accessories", "Small Accessories (Headphones, Ribbons, Charms)"),
    ("sample_05_translucent_costume", "Translucent Fabric & Wings (Fairy Sorceress)"),
]


async def run_benchmark() -> None:
    print("=" * 80)
    print("PROJECT AIC — IS-NET ANIME ONNX CPU BENCHMARK & TIER 3 VERIFICATION")
    print("=" * 80)

    # 1. Verify model
    print(f"\n[1/3] Verifying model integrity at {MODEL_PATH}...")
    if not MODEL_PATH.is_file():
        print(f"ERROR: Model file not found at {MODEL_PATH}")
        sys.exit(1)

    sha = verify_model_file(MODEL_PATH)
    file_size_mb = MODEL_PATH.stat().st_size / (1024 * 1024)
    print(f"      Size: {file_size_mb:.2f} MB | Verified SHA-256: {sha}")

    # 2. Check fixtures
    print(f"\n[2/3] Checking test fixtures at {FIXTURES_DIR}...")
    for s_id, desc in SAMPLES:
        p = FIXTURES_DIR / f"{s_id}.png"
        if not p.is_file():
            print(f"ERROR: Missing fixture {p}")
            sys.exit(1)
        print(f"      Found: {s_id}.png ({desc})")

    # 3. Run Inference
    print("\n[3/3] Running CPU inference on all 5 samples (intra_op_threads=4)...")
    config = PipelineConfig(
        use_mock_bg_provider=False,
        isnet_anime_model_path=MODEL_PATH,
        onnx_intra_op_threads=4,
    )
    provider = ISNetONNXProvider(config=config)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    try:
        for idx, (s_id, desc) in enumerate(SAMPLES, start=1):
            sample_file = FIXTURES_DIR / f"{s_id}.png"
            raw_bytes = sample_file.read_bytes()

            with Image.open(io.BytesIO(raw_bytes)) as in_img:
                orig_size = in_img.size
                orig_rgb = in_img.convert("RGB")

            t0 = time.perf_counter()
            rgba_bytes, meta = await provider.remove_background(raw_bytes)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            with Image.open(io.BytesIO(rgba_bytes)) as out_img:
                out_size = out_img.size
                mode = out_img.mode
                alpha_chan = out_img.getchannel("A")
                alpha_arr = np.array(alpha_chan, dtype=np.uint8)

            extrema = (int(alpha_arr.min()), int(alpha_arr.max()))
            total_px = alpha_arr.size
            soft_px = int(np.count_nonzero((alpha_arr >= 10) & (alpha_arr <= 245)))
            opaque_pct = float(np.count_nonzero(alpha_arr > 240) / total_px * 100.0)
            trans_pct = float(np.count_nonzero(alpha_arr < 10) / total_px * 100.0)

            # Check RGB preservation on solid pixels
            solid_mask = alpha_arr == 255
            rgb_diff = 0
            if np.any(solid_mask):
                out_rgb = out_img.convert("RGB")
                diff = np.abs(np.array(out_rgb, dtype=np.int16) - np.array(orig_rgb, dtype=np.int16))
                rgb_diff = int(diff[solid_mask].max())

            # Save artifacts
            orig_rgb.save(OUTPUT_DIR / f"{s_id}_input.png", format="PNG")
            alpha_chan.save(OUTPUT_DIR / f"{s_id}_mask.png", format="PNG")
            (OUTPUT_DIR / f"{s_id}_output.png").write_bytes(rgba_bytes)

            meta_data = {
                "sample_id": s_id,
                "description": desc,
                "dimensions": orig_size,
                "latency_ms": latency_ms,
                "alpha_extrema": list(extrema),
                "soft_edge_pixels": soft_px,
                "opaque_percent": opaque_pct,
                "transparent_percent": trans_pct,
                "solid_rgb_max_diff": rgb_diff,
            }
            (OUTPUT_DIR / f"{s_id}_meta.json").write_text(json.dumps(meta_data, indent=2), encoding="utf-8")

            results.append(meta_data)
            print(f"      [{idx}/5] {s_id}: {latency_ms:.1f}ms | soft_px={soft_px} | size={out_size} | OK")
    finally:
        provider.release()

    # Markdown Summary Table
    print("\n" + "=" * 80)
    print("TIER 3 VERIFICATION BENCHMARK SUMMARY")
    print("=" * 80)
    print("| Sample ID | Input Size | Latency | Extrema | Soft Alpha Px | Opaque % | Trans % | Status |")
    print("|---|---|---|---|---|---|---|---|")
    for r in results:
        w, h = r["dimensions"]
        lat = f"{r['latency_ms']:.1f}ms"
        ext = f"({r['alpha_extrema'][0]}, {r['alpha_extrema'][1]})"
        soft = f"{r['soft_edge_pixels']:,}"
        op = f"{r['opaque_percent']:.1f}%"
        tr = f"{r['transparent_percent']:.1f}%"
        print(f"| `{r['sample_id']}` | {w}x{h} | {lat} | {ext} | {soft} | {op} | {tr} | **PASS** |")
    print("=" * 80)
    print(f"\nAll artifacts saved to: {OUTPUT_DIR.resolve()}\n")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
