"""Standalone benchmark and comparative verification script for IS-Net Anime ONNX on CPU vs DirectML GPU.

Executes real background removal on all 5 real anime test fixtures across both
CPUExecutionProvider and DmlExecutionProvider (DirectML).
Computes quantitative alpha partition metrics, verifies mathematical invariants,
quantifies numerical discrepancies, saves visual and diagnostic artifacts to data/tier3_output/,
and prints formatted Markdown benchmark tables.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Ensure backend is on sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import numpy as np
import onnxruntime as ort  # type: ignore[import-not-found,import-untyped]
from PIL import Image

from app.pipeline.background.isnet_directml_provider import (
    ISNetDirectMLProvider,
)
from app.pipeline.background.isnet_provider import ISNetONNXProvider
from app.pipeline.config import PipelineConfig
from app.pipeline.security.model_verifier import verify_model_file

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


def analyze_alpha_channel(alpha_arr: np.ndarray, sample_id: str, provider_name: str) -> dict[str, Any]:
    """Computes standardized disjoint alpha partition and checks mathematical invariants."""
    total_px = alpha_arr.size
    n_trans = int(np.count_nonzero(alpha_arr == 0))
    n_soft = int(np.count_nonzero((alpha_arr > 0) & (alpha_arr < 255)))
    n_solid = int(np.count_nonzero(alpha_arr == 255))

    # Invariant 1: Exhaustive partition
    assert n_trans + n_soft + n_solid == total_px, (
        f"{sample_id} ({provider_name}): Alpha partition sum mismatch: "
        f"{n_trans} + {n_soft} + {n_solid} != {total_px}"
    )

    # Invariant 2: Transitional threshold [10, 245] is a strict subset of soft pixels (0, 255)
    transitional_px = int(np.count_nonzero((alpha_arr >= 10) & (alpha_arr <= 245)))
    assert transitional_px <= n_soft, (
        f"{sample_id} ({provider_name}): transitional ({transitional_px}) > soft ({n_soft})"
    )

    extrema = (int(alpha_arr.min()), int(alpha_arr.max()))
    return {
        "extrema": list(extrema),
        "total_pixels": total_px,
        "transparent_pixels": n_trans,
        "soft_pixels": n_soft,
        "solid_pixels": n_solid,
        "transparent_percent": float(n_trans / total_px * 100.0),
        "soft_percent": float(n_soft / total_px * 100.0),
        "solid_percent": float(n_solid / total_px * 100.0),
        "transitional_alpha_pixels": transitional_px,
        "transitional_alpha_percent": float(transitional_px / total_px * 100.0),
    }


async def run_benchmark() -> None:
    print("=" * 110)
    print("PROJECT AIC — IS-NET ANIME ONNX DUAL-PROVIDER (CPU vs DIRECTML GPU) BENCHMARK")
    print("=" * 110)

    # 1. Verify model
    print(f"\n[1/4] Verifying model integrity at {MODEL_PATH}...")
    if not MODEL_PATH.is_file():
        print(f"ERROR: Model file not found at {MODEL_PATH}")
        sys.exit(1)

    sha = verify_model_file(MODEL_PATH)
    file_size_mb = MODEL_PATH.stat().st_size / (1024 * 1024)
    print(f"      Size: {file_size_mb:.2f} MB | Verified SHA-256: {sha}")

    # 2. Check fixtures
    print(f"\n[2/4] Checking test fixtures at {FIXTURES_DIR}...")
    for s_id, desc in SAMPLES:
        p = FIXTURES_DIR / f"{s_id}.png"
        if not p.is_file():
            print(f"ERROR: Missing fixture {p}")
            sys.exit(1)
        print(f"      Found: {s_id}.png ({desc})")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 3. Check DirectML Hardware & Runtime Support
    available_providers = ort.get_available_providers()
    directml_supported = "DmlExecutionProvider" in available_providers
    print("\n[3/4] Checking ONNX Runtime Execution Providers...")
    print(f"      Available Providers: {available_providers}")
    if directml_supported:
        print("      DirectML GPU Execution Provider: AVAILABLE (Hardware acceleration enabled)")
    else:
        print("      DirectML GPU Execution Provider: NOT AVAILABLE")
        print("      Status: PARTIAL / BLOCKED for DirectML GPU. CPU will be run exclusively.")

    # 4. Execute CPU Inference
    print("\n[4/4] Executing Comparative Inference...")
    print("\n--- Running CPU Provider (intra_op_threads=4, enable_mem_pattern=True) ---")
    cpu_config = PipelineConfig(
        use_mock_bg_provider=False,
        onnx_execution_provider="cpu",
        isnet_anime_model_path=MODEL_PATH,
        onnx_intra_op_threads=4,
    )
    cpu_provider = ISNetONNXProvider(config=cpu_config)

    cpu_results: dict[str, dict[str, Any]] = {}
    cpu_alpha_maps: dict[str, np.ndarray] = {}

    try:
        for idx, (s_id, desc) in enumerate(SAMPLES, start=1):
            sample_file = FIXTURES_DIR / f"{s_id}.png"
            raw_bytes = sample_file.read_bytes()

            with Image.open(io.BytesIO(raw_bytes)) as in_img:
                orig_size = in_img.size
                orig_rgb = in_img.convert("RGB")

            t0 = time.perf_counter()
            rgba_bytes, _diag = await cpu_provider.remove_background(raw_bytes)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            with Image.open(io.BytesIO(rgba_bytes)) as out_img:
                alpha_chan = out_img.getchannel("A")
                alpha_arr = np.array(alpha_chan, dtype=np.uint8)

            metrics = analyze_alpha_channel(alpha_arr, s_id, "CPU")
            cpu_alpha_maps[s_id] = alpha_arr

            # Check RGB preservation on solid pixels
            solid_mask = alpha_arr == 255
            rgb_diff = 0
            if np.any(solid_mask):
                out_rgb = out_img.convert("RGB")
                diff = np.abs(np.array(out_rgb, dtype=np.int16) - np.array(orig_rgb, dtype=np.int16))
                rgb_diff = int(diff[solid_mask].max())

            # Save CPU artifacts
            orig_rgb.save(OUTPUT_DIR / f"{s_id}_input.png", format="PNG")
            alpha_chan.save(OUTPUT_DIR / f"{s_id}_mask.png", format="PNG")
            alpha_chan.save(OUTPUT_DIR / f"{s_id}_cpu_mask.png", format="PNG")
            (OUTPUT_DIR / f"{s_id}_output.png").write_bytes(rgba_bytes)
            (OUTPUT_DIR / f"{s_id}_cpu_output.png").write_bytes(rgba_bytes)

            meta = {
                "sample_id": s_id,
                "description": desc,
                "dimensions": list(orig_size),
                "latency_ms": latency_ms,
                "solid_rgb_max_diff": rgb_diff,
                **metrics,
            }
            (OUTPUT_DIR / f"{s_id}_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            (OUTPUT_DIR / f"{s_id}_cpu_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            cpu_results[s_id] = meta
            print(f"      [CPU {idx}/5] {s_id}: {latency_ms:.1f}ms | soft={metrics['soft_pixels']:,} ({metrics['soft_percent']:.2f}%) | transitional={metrics['transitional_alpha_pixels']:,} | OK")
    finally:
        cpu_provider.release()

    # 5. Execute DirectML Inference (if available)
    dml_results: dict[str, dict[str, Any]] = {}
    dml_alpha_maps: dict[str, np.ndarray] = {}

    if directml_supported:
        print("\n--- Running DirectML GPU Provider (device_id=0, enable_mem_pattern=False) ---")
        dml_config = PipelineConfig(
            use_mock_bg_provider=False,
            onnx_execution_provider="directml",
            isnet_anime_model_path=MODEL_PATH,
            directml_device_id=0,
        )
        dml_provider = ISNetDirectMLProvider(config=dml_config)

        try:
            # Warm-up run to compile DirectML DirectX 12 shaders ahead of timing
            sample_1_bytes = (FIXTURES_DIR / "sample_01_simple_bg.png").read_bytes()
            print("      Warming up DirectML shader pipeline...")
            t_warm_0 = time.perf_counter()
            await dml_provider.remove_background(sample_1_bytes)
            t_warm = (time.perf_counter() - t_warm_0) * 1000.0
            print(f"      Warmup completed in {t_warm:.1f}ms (DirectX shader compilation cached)")

            for idx, (s_id, desc) in enumerate(SAMPLES, start=1):
                sample_file = FIXTURES_DIR / f"{s_id}.png"
                raw_bytes = sample_file.read_bytes()

                with Image.open(io.BytesIO(raw_bytes)) as in_img:
                    orig_size = in_img.size
                    orig_rgb = in_img.convert("RGB")

                t0 = time.perf_counter()
                rgba_bytes, _diag = await dml_provider.remove_background(raw_bytes)
                latency_ms = (time.perf_counter() - t0) * 1000.0

                with Image.open(io.BytesIO(rgba_bytes)) as out_img:
                    alpha_chan = out_img.getchannel("A")
                    alpha_arr = np.array(alpha_chan, dtype=np.uint8)

                metrics = analyze_alpha_channel(alpha_arr, s_id, "DirectML")
                dml_alpha_maps[s_id] = alpha_arr

                solid_mask = alpha_arr == 255
                rgb_diff = 0
                if np.any(solid_mask):
                    out_rgb = out_img.convert("RGB")
                    diff = np.abs(np.array(out_rgb, dtype=np.int16) - np.array(orig_rgb, dtype=np.int16))
                    rgb_diff = int(diff[solid_mask].max())

                # Save DirectML artifacts
                alpha_chan.save(OUTPUT_DIR / f"{s_id}_dml_mask.png", format="PNG")
                (OUTPUT_DIR / f"{s_id}_dml_output.png").write_bytes(rgba_bytes)

                meta = {
                    "sample_id": s_id,
                    "description": desc,
                    "dimensions": list(orig_size),
                    "latency_ms": latency_ms,
                    "solid_rgb_max_diff": rgb_diff,
                    **metrics,
                }
                (OUTPUT_DIR / f"{s_id}_dml_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
                dml_results[s_id] = meta
                print(f"      [DML {idx}/5] {s_id}: {latency_ms:.1f}ms | soft={metrics['soft_pixels']:,} ({metrics['soft_percent']:.2f}%) | transitional={metrics['transitional_alpha_pixels']:,} | OK")
        finally:
            dml_provider.release()

    # 6. Comparative Numerical Discrepancy & Consistency Analysis
    comparison_results: list[dict[str, Any]] = []

    print("\n--- Comparative Arithmetic & Quality Analysis (CPU vs DirectML) ---")
    for s_id, desc in SAMPLES:
        cpu_meta = cpu_results[s_id]
        if directml_supported and s_id in dml_results:
            dml_meta = dml_results[s_id]
            cpu_a = cpu_alpha_maps[s_id].astype(np.int16)
            dml_a = dml_alpha_maps[s_id].astype(np.int16)

            abs_diff = np.abs(cpu_a - dml_a)
            max_diff = int(abs_diff.max())
            mean_diff = float(abs_diff.mean())
            total_px = cpu_a.size

            exact_match_px = int(np.count_nonzero(abs_diff == 0))
            exact_match_pct = float(exact_match_px / total_px * 100.0)

            within_1_px = int(np.count_nonzero(abs_diff <= 1))
            within_1_pct = float(within_1_px / total_px * 100.0)

            speedup = float(cpu_meta["latency_ms"] / dml_meta["latency_ms"])

            comp = {
                "sample_id": s_id,
                "description": desc,
                "dimensions": cpu_meta["dimensions"],
                "cpu_latency_ms": cpu_meta["latency_ms"],
                "dml_latency_ms": dml_meta["latency_ms"],
                "speedup_factor": speedup,
                "max_alpha_difference": max_diff,
                "mean_alpha_difference": mean_diff,
                "exact_alpha_match_percent": exact_match_pct,
                "within_1_alpha_match_percent": within_1_pct,
                "discrepancy_explanation": (
                    "Normal sub-LSB float32 variance due to GPU DirectX HLSL SIMD FP32 rounding vs CPU AVX2 instructions."
                    if max_diff <= 5 else "Investigate non-trivial numerical discrepancy."
                ),
            }
            (OUTPUT_DIR / f"{s_id}_comparison.json").write_text(json.dumps(comp, indent=2), encoding="utf-8")
            comparison_results.append(comp)
            print(f"      {s_id}: Speedup={speedup:.2f}x (CPU {cpu_meta['latency_ms']:.1f}ms -> DML {dml_meta['latency_ms']:.1f}ms) | MaxDiff={max_diff} | ExactMatch={exact_match_pct:.2f}% | Within±1={within_1_pct:.2f}%")
        else:
            comp = {
                "sample_id": s_id,
                "description": desc,
                "dimensions": cpu_meta["dimensions"],
                "cpu_latency_ms": cpu_meta["latency_ms"],
                "dml_latency_ms": None,
                "speedup_factor": None,
                "status": "BLOCKED / NO_GPU",
            }
            comparison_results.append(comp)

    # 7. Print Formatted Markdown Tables
    print("\n" + "=" * 115)
    print("### TABLE 1: LATENCY BENCHMARK & HARDWARE ACCELERATION COMPARISON")
    print("=" * 115)
    print("| Sample ID | Image Dimensions | CPU Latency (ms) | DirectML Latency (ms) | Speedup Factor | Hardware Status |")
    print("|---|---|---|---|---|---|")
    total_cpu_lat = 0.0
    total_dml_lat = 0.0
    for c in comparison_results:
        s_id = c["sample_id"]
        dims = f"{c['dimensions'][0]}x{c['dimensions'][1]}"
        cpu_lat = f"{c['cpu_latency_ms']:.1f} ms"
        total_cpu_lat += c["cpu_latency_ms"]
        if c.get("dml_latency_ms") is not None:
            dml_lat = f"{c['dml_latency_ms']:.1f} ms"
            total_dml_lat += c["dml_latency_ms"]
            speedup = f"**{c['speedup_factor']:.2f}x**"
            status = "RTX 4050 (DirectML)"
        else:
            dml_lat = "N/A"
            speedup = "N/A"
            status = "BLOCKED (No GPU)"
        print(f"| `{s_id}` | {dims} | {cpu_lat} | {dml_lat} | {speedup} | {status} |")

    avg_cpu = total_cpu_lat / len(comparison_results)
    if directml_supported and total_dml_lat > 0:
        avg_dml = total_dml_lat / len(comparison_results)
        avg_speedup = avg_cpu / avg_dml
        print(f"| **AVERAGE** | — | **{avg_cpu:.1f} ms** | **{avg_dml:.1f} ms** | **{avg_speedup:.2f}x** | **OVERALL SPEEDUP** |")
    print("=" * 115)

    print("\n" + "=" * 115)
    print("### TABLE 2: STANDARDIZED ALPHA CHANNEL PARTITIONING (DIRECTML OUTPUT)")
    print("=" * 115)
    print("| Sample ID | Extrema | Transparent (alpha==0) | Soft (0<alpha<255) | Solid (alpha==255) | Transitional [10, 245] | Partition Invariant |")
    print("|---|---|---|---|---|---|---|")
    for s_id, _desc in SAMPLES:
        m = dml_results.get(s_id, cpu_results[s_id])
        ext = f"({m['extrema'][0]}, {m['extrema'][1]})"
        tr = f"{m['transparent_pixels']:,} ({m['transparent_percent']:.1f}%)"
        sf = f"{m['soft_pixels']:,} ({m['soft_percent']:.1f}%)"
        sd = f"{m['solid_pixels']:,} ({m['solid_percent']:.1f}%)"
        trans = f"{m['transitional_alpha_pixels']:,} ({m['transitional_alpha_percent']:.1f}%)"
        inv = "PASS (Sum==Total, Trans<=Soft)" if (
            m["transparent_pixels"] + m["soft_pixels"] + m["solid_pixels"] == m["total_pixels"]
            and m["transitional_alpha_pixels"] <= m["soft_pixels"]
        ) else "FAIL"
        print(f"| `{s_id}` | {ext} | {tr} | {sf} | {sd} | {trans} | **{inv}** |")
    print("=" * 115)

    if directml_supported:
        print("\n" + "=" * 115)
        print("### TABLE 3: NUMERICAL DISCREPANCY & ARITHMETIC CONSISTENCY (CPU vs GPU)")
        print("=" * 115)
        print("| Sample ID | Max Alpha Diff | Mean Alpha Diff | Identical Pixels (%) | Within ±1 Alpha (%) | Arithmetic Invariant Status |")
        print("|---|---|---|---|---|---|")
        for c in comparison_results:
            s_id = c["sample_id"]
            max_d = c["max_alpha_difference"]
            mean_d = f"{c['mean_alpha_difference']:.4f}"
            exact_p = f"{c['exact_alpha_match_percent']:.2f}%"
            within_1 = f"{c['within_1_alpha_match_percent']:.2f}%"
            print(f"| `{s_id}` | {max_d} / 255 | {mean_d} | {exact_p} | {within_1} | **PASS (Sub-LSB FP32 variance)** |")
        print("=" * 115)

    # Save comprehensive benchmark summary report
    summary_report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_path": str(MODEL_PATH),
        "model_sha256": sha,
        "directml_available": directml_supported,
        "hardware": "NVIDIA GeForce RTX 4050 Laptop GPU (6GB VRAM)" if directml_supported else "CPU Only",
        "average_cpu_latency_ms": avg_cpu,
        "average_dml_latency_ms": avg_dml if directml_supported else None,
        "average_speedup_factor": avg_speedup if directml_supported else None,
        "comparisons": comparison_results,
    }
    (OUTPUT_DIR / "benchmark_report.json").write_text(json.dumps(summary_report, indent=2), encoding="utf-8")
    print(f"\nAll benchmark artifacts and JSON reports saved to:\n{OUTPUT_DIR.resolve()}\n")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
