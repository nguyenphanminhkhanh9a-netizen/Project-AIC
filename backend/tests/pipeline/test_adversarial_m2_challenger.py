"""Adversarial challenger test suite for Milestone 2 deliverables.

Independently challenges and stress-tests:
1. CLI options, device resolution precedence, and statistical edge cases on scripts/run_tier3_benchmark.py.
2. PipelineWorker lifecycle integration with real background providers (ISNetDirectMLProvider & ISNetONNXProvider),
   verifying PipelineWorker.stop() completely releases ONNX sessions and GPU/CPU resources.
3. Strict enforcement of anti-silent-fallback guardrails on DirectML across runtime, session init, and benchmark reporting.
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

# Ensure project root and scripts directory are in sys.path
project_root = Path(__file__).resolve().parents[3]
scripts_dir = project_root / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from run_tier3_benchmark import (  # type: ignore[import-not-found,import-untyped]
    analyze_alpha_channel,
    compute_stats,
    detect_dxgi_adapters,
    resolve_directml_device,
)

from app.domain.pipeline import PipelineTask
from app.pipeline.background import (
    DirectMLInitializationError,
    DirectMLNotAvailableError,
    ISNetDirectMLProvider,
    ISNetONNXProvider,
)
from app.pipeline.config import PipelineConfig
from app.pipeline.worker import PipelineWorker


def _get_dummy_png_bytes(width: int = 128, height: int = 128) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), (120, 200, 80))
    img.save(buf, format="PNG")
    return buf.getvalue()


# ==============================================================================
# SECTION 1: STRESS-TEST CLI OPTIONS & BENCHMARK HARNESS
# ==============================================================================


class TestBenchmarkCLIOptionsAndStats:
    """Stress-tests execution options, precedence rules, and invariants in scripts/run_tier3_benchmark.py."""

    def test_cli_device_id_precedence_over_env(self) -> None:
        """Verifies CLI argument --device-id strictly overrides AIC_PIPELINE_DIRECTML_DEVICE_ID environment variable."""
        with patch.dict(os.environ, {"AIC_PIPELINE_DIRECTML_DEVICE_ID": "0"}):
            dev, name, _vram = resolve_directml_device(cli_device_id=1)
            assert dev == 1
            assert "RTX 4050" in name

    def test_env_device_id_precedence_over_autodetect(self) -> None:
        """Verifies environment variable overrides auto-detection when CLI argument is not specified."""
        with patch.dict(os.environ, {"AIC_PIPELINE_DIRECTML_DEVICE_ID": "0"}):
            dev, name, _vram = resolve_directml_device(cli_device_id=None)
            assert dev == 0
            assert "Intel" in name

    def test_invalid_env_device_id_fallback_to_discrete_gpu(self) -> None:
        """Verifies non-numeric or malformed environment variables fall back cleanly to discrete GPU detection."""
        with patch.dict(os.environ, {"AIC_PIPELINE_DIRECTML_DEVICE_ID": "invalid_string_999"}):
            dev, name, _vram = resolve_directml_device(cli_device_id=None)
            assert dev == 1
            assert "RTX 4050" in name

    def test_dxgi_adapter_enumeration(self) -> None:
        """Verifies DXGI discovery discovers the dual-GPU layout (Intel + NVIDIA) on Windows."""
        adapters = detect_dxgi_adapters()
        assert len(adapters) >= 2
        adapter_names = [a[1] for a in adapters]
        assert any("Intel" in name for name in adapter_names)
        assert any("NVIDIA" in name or "RTX" in name for name in adapter_names)

    def test_compute_stats_edge_cases(self) -> None:
        """Stress-tests statistical aggregation with empty, singleton, and identical values."""
        # Case 1: Empty list
        empty_res = compute_stats([])
        assert empty_res == {"mean": 0.0, "median": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}

        # Case 2: Singleton list (must not divide by zero on stdev)
        single_res = compute_stats([42.5])
        assert single_res["mean"] == 42.5
        assert single_res["median"] == 42.5
        assert single_res["std"] == 0.0
        assert single_res["min"] == 42.5
        assert single_res["max"] == 42.5

        # Case 3: Identical values
        identical_res = compute_stats([10.0, 10.0, 10.0, 10.0])
        assert identical_res["mean"] == 10.0
        assert identical_res["std"] == 0.0

    def test_analyze_alpha_channel_mathematical_invariants(self) -> None:
        """Stress-tests alpha channel partitioning and mathematical invariant assertions."""
        # 1. Pure transparent array
        all_trans = np.zeros((100, 100), dtype=np.uint8)
        res_trans = analyze_alpha_channel(all_trans, "all_trans", "Test")
        assert res_trans["transparent_pixels"] == 10000
        assert res_trans["soft_pixels"] == 0
        assert res_trans["solid_pixels"] == 0

        # 2. Pure solid array
        all_solid = np.full((100, 100), 255, dtype=np.uint8)
        res_solid = analyze_alpha_channel(all_solid, "all_solid", "Test")
        assert res_solid["solid_pixels"] == 10000
        assert res_solid["soft_pixels"] == 0
        assert res_solid["transparent_pixels"] == 0

        # 3. Soft ramp
        ramp = np.linspace(0, 255, 10000, dtype=np.uint8).reshape(100, 100)
        res_ramp = analyze_alpha_channel(ramp, "ramp", "Test")
        assert (
            res_ramp["transparent_pixels"] + res_ramp["soft_pixels"] + res_ramp["solid_pixels"]
            == res_ramp["total_pixels"]
        )
        assert res_ramp["transitional_alpha_pixels"] <= res_ramp["soft_pixels"]

    def test_analyze_alpha_channel_detects_corrupted_invariants(self) -> None:
        """Verifies that analyze_alpha_channel raises AssertionError if invariants are violated."""
        # Construct non-uint8 array with out-of-range value to simulate corrupt partition
        broken_alpha = np.array([0, 128, 255, 300], dtype=np.int32)
        # 300 is neither 0, (0 < x < 255), nor 255 -> partition sum fails
        with pytest.raises(AssertionError, match="Alpha partition sum mismatch"):
            analyze_alpha_channel(broken_alpha, "broken", "Test")


# ==============================================================================
# SECTION 2: PIPELINE WORKER INTEGRATION & RESOURCE RELEASE ON STOP
# ==============================================================================


class TestPipelineWorkerRealIntegrationAndCleanup:
    """Stress-tests PipelineWorker integration with real providers and verifies PipelineWorker.stop() releases resources."""

    @pytest.mark.asyncio
    async def test_worker_directml_resource_cleanup_on_stop(self) -> None:
        """Empirically verifies that PipelineWorker under real DirectML configuration deallocates session on stop()."""
        model_path = Path.home() / ".cache" / "project_aic" / "models" / "isnetis.onnx"
        if not model_path.is_file():
            pytest.skip("IS-Net model weights not cached on host")

        config = PipelineConfig(
            use_mock_bg_provider=False,
            onnx_execution_provider="directml",
            directml_device_id=1,
            isnet_anime_model_path=model_path,
        )

        worker = PipelineWorker(config=config)
        assert isinstance(worker.bg_provider, ISNetDirectMLProvider)
        assert worker.bg_provider._session is None

        await worker.start()

        # Execute an inference to force lazy ONNX session loading
        dummy_png = _get_dummy_png_bytes(64, 64)
        out_bytes, _meta = await worker.bg_provider.remove_background(dummy_png)
        assert len(out_bytes) > 0
        assert worker.bg_provider._session is not None
        assert worker.bg_provider._active_provider == "directml"

        # Stop worker
        await worker.stop()

        # Verify session is deallocated and active provider marked released
        assert worker.bg_provider._session is None
        assert worker.bg_provider._active_provider == "released"

    @pytest.mark.asyncio
    async def test_worker_cpu_resource_cleanup_on_stop(self) -> None:
        """Empirically verifies that PipelineWorker under real CPU configuration deallocates session on stop()."""
        model_path = Path.home() / ".cache" / "project_aic" / "models" / "isnetis.onnx"
        if not model_path.is_file():
            pytest.skip("IS-Net model weights not cached on host")

        config = PipelineConfig(
            use_mock_bg_provider=False,
            onnx_execution_provider="cpu",
            isnet_anime_model_path=model_path,
        )

        worker = PipelineWorker(config=config)
        assert isinstance(worker.bg_provider, ISNetONNXProvider)
        assert worker.bg_provider._session is None

        await worker.start()

        # Force session initialization
        dummy_png = _get_dummy_png_bytes(64, 64)
        out_bytes, _meta = await worker.bg_provider.remove_background(dummy_png)
        assert len(out_bytes) > 0
        assert worker.bg_provider._session is not None
        assert worker.bg_provider._active_provider == "cpu"

        # Stop worker
        await worker.stop()

        # Verify session is deallocated
        assert worker.bg_provider._session is None
        assert worker.bg_provider._active_provider == "released"

    @pytest.mark.asyncio
    async def test_worker_stop_idempotency(self) -> None:
        """Verifies calling worker.stop() multiple times consecutively does not raise errors."""
        config = PipelineConfig(use_mock_bg_provider=False, onnx_execution_provider="directml")
        worker = PipelineWorker(config=config)
        assert isinstance(worker.bg_provider, ISNetDirectMLProvider)
        await worker.start()
        await worker.stop()
        # Second call
        await worker.stop()
        # Third call
        await worker.stop()
        assert worker._worker_task is None
        assert worker.bg_provider._session is None

    @pytest.mark.asyncio
    async def test_worker_stop_waits_for_active_task_before_release(self) -> None:
        """Verifies worker.stop() completes the currently processed task before releasing resources."""
        config = PipelineConfig(use_mock_bg_provider=True)
        worker = PipelineWorker(config=config)

        task_completed = asyncio.Event()

        async def slow_download(url: str) -> bytes:
            await asyncio.sleep(0.15)
            task_completed.set()
            return _get_dummy_png_bytes(64, 64)

        worker.downloader.download = slow_download  # type: ignore[method-assign]
        await worker.start()

        task = PipelineTask(
            task_id="test_inflight_task",
            character_id="miku",
            target_outfit="default",
            target_state="idle",
            target_emotion="happy",
            source_url="https://example.com/test.png",
            source_provider="test",
        )
        enqueued = await worker.enqueue(task)
        assert enqueued is True

        # Allow worker loop to pick up the task
        await asyncio.sleep(0.05)

        # Trigger worker stop while slow_download is in flight
        await worker.stop()

        # Confirm the task was permitted to finish
        assert task_completed.is_set()


# ==============================================================================
# SECTION 3: ABSENCE OF SILENT CPU FALLBACK ON DIRECTML
# ==============================================================================


class TestDirectMLAntiSilentFallback:
    """Stress-tests runtime anti-silent-fallback guardrails."""

    def test_directml_fails_when_runtime_lacks_dml_ep(self) -> None:
        """Verifies ISNetDirectMLProvider raises DirectMLNotAvailableError if DmlExecutionProvider is not in ORT."""
        provider = ISNetDirectMLProvider()
        with (
            patch("onnxruntime.get_available_providers", return_value=["CPUExecutionProvider"]),
            pytest.raises(DirectMLNotAvailableError, match="DirectML Execution Provider is not available"),
        ):
            provider._load_session_sync()

    def test_directml_rejects_session_with_only_cpu_ep(self) -> None:
        """Verifies that if ONNX Runtime falls back to CPU during session creation, DirectMLInitializationError is raised."""
        provider = ISNetDirectMLProvider()

        # Mock session that only bound CPUExecutionProvider
        mock_session = MagicMock()
        mock_session.get_providers.return_value = ["CPUExecutionProvider"]

        with (
            patch("onnxruntime.get_available_providers", return_value=["DmlExecutionProvider", "CPUExecutionProvider"]),
            patch("app.pipeline.background.isnet_directml_provider.verify_model_file", return_value="fake_sha"),
            patch("onnxruntime.InferenceSession", return_value=mock_session),
            pytest.raises(
                DirectMLInitializationError,
                match="Silent CPU fallback is rejected",
            ),
        ):
            provider._load_session_sync()

    def test_directml_hardware_binding_on_host_rtx4050(self) -> None:
        """Empirically verifies that ISNetDirectMLProvider on this machine binds to DmlExecutionProvider without silent fallback."""
        model_path = Path.home() / ".cache" / "project_aic" / "models" / "isnetis.onnx"
        if not model_path.is_file():
            pytest.skip("IS-Net model weights not cached on host")

        config = PipelineConfig(
            use_mock_bg_provider=False,
            onnx_execution_provider="directml",
            directml_device_id=1,
            isnet_anime_model_path=model_path,
        )
        provider = ISNetDirectMLProvider(config=config)
        provider._load_session_sync()

        assert provider._session is not None
        active_eps = provider._session.get_providers()
        # DmlExecutionProvider must be the primary provider on the session
        assert "DmlExecutionProvider" in active_eps
        assert active_eps[0] == "DmlExecutionProvider"

        # Clean up
        provider.release()
        assert provider._session is None

    def test_directml_invalid_adapter_raises_and_cleans_up(self) -> None:
        """Empirically verifies that requesting an invalid DirectML adapter index (e.g., 99) raises and cleans up."""
        model_path = Path.home() / ".cache" / "project_aic" / "models" / "isnetis.onnx"
        if not model_path.is_file():
            pytest.skip("IS-Net model weights not cached on host")

        config = PipelineConfig(
            use_mock_bg_provider=False,
            onnx_execution_provider="directml",
            directml_device_id=99,
            isnet_anime_model_path=model_path,
        )
        provider = ISNetDirectMLProvider(config=config)
        with pytest.raises(DirectMLInitializationError, match="Silent CPU fallback is rejected"):
            provider._load_session_sync()

        assert provider._session is None
        assert provider._active_provider == "released"
