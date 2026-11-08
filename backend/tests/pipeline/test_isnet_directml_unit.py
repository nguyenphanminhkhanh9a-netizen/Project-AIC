"""Offline unit tests for ISNetDirectMLProvider and DirectML session constraints.

Validates:
1. Protocol conformance (BackgroundRemovalProvider).
2. Lazy-loading invariant (instantiation does not load weights or initialize GPU).
3. Pre-flight check and explicit error when DirectML is unavailable.
4. Mandatory session options (ORT_SEQUENTIAL, enable_mem_pattern=False).
5. Provider verification (rejection of silent CPU fallback).
6. Resource cleanup on initialization failure.
7. Idempotent resource release (session cleanup and garbage collection).
8. Async sequential execution and multithreaded concurrency rejection.
9. Configuration-driven provider selection in factory.

Runs 100% offline with zero ML model weights dependencies.
"""

from __future__ import annotations

import asyncio
import io
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import onnxruntime as ort  # type: ignore[import-not-found,import-untyped]
import pytest
from PIL import Image

from app.domain.pipeline import BackgroundRemovalProvider
from app.pipeline.background import (
    DirectMLConcurrencyError,
    DirectMLInitializationError,
    DirectMLNotAvailableError,
    ISNetDirectMLProvider,
    ISNetONNXProvider,
    MockBackgroundRemovalProvider,
    get_background_removal_provider,
)
from app.pipeline.config import PipelineConfig


def _create_dummy_png(width: int = 128, height: int = 128) -> bytes:
    """Creates a simple test PNG in bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), (255, 128, 0))
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_directml_provider_protocol_conformance() -> None:
    """Verifies that ISNetDirectMLProvider implements BackgroundRemovalProvider Protocol."""
    provider = ISNetDirectMLProvider()
    assert isinstance(provider, BackgroundRemovalProvider)
    assert provider.model_name == "isnet_anime"
    assert provider.execution_provider == "uninitialized"
    assert provider._session is None


def test_directml_provider_lazy_loading_invariant() -> None:
    """Verifies that instantiation does NOT load ONNX session or allocate GPU memory."""
    config = PipelineConfig(
        isnet_anime_model_path=Path("/tmp/nonexistent_dummy_model.onnx"),
    )
    provider = ISNetDirectMLProvider(config=config)
    assert provider._session is None
    # Calling release on uninitialized provider must be safe and idempotent
    provider.release()
    assert provider._session is None
    assert provider.execution_provider == "released"


def test_directml_unavailable_error_handling() -> None:
    """Verifies pre-flight check raises DirectMLNotAvailableError when DirectML is not in available providers."""
    config = PipelineConfig()
    provider = ISNetDirectMLProvider(config=config)

    # Mock get_available_providers to simulate an environment lacking DirectML
    with patch("onnxruntime.get_available_providers", return_value=["CPUExecutionProvider"]):
        with pytest.raises(DirectMLNotAvailableError) as exc_info:
            provider._load_session_sync()

        assert "DirectML Execution Provider is not available" in str(exc_info.value)
        assert provider._session is None
        assert provider.execution_provider == "uninitialized"


def test_directml_session_options_mandatory_constraints(tmp_path: Path) -> None:
    """Verifies mandatory ORT_SEQUENTIAL, enable_mem_pattern=False, and provider options."""
    dummy_model = tmp_path / "dummy.onnx"
    dummy_model.write_bytes(b"x" * 100)

    config = PipelineConfig(
        isnet_anime_model_path=dummy_model,
        isnet_model_sha256="",
        isnet_model_expected_size=100,
        directml_device_id=1,
    )
    provider = ISNetDirectMLProvider(config=config)

    mock_session = MagicMock()
    mock_session.get_providers.return_value = ["DmlExecutionProvider", "CPUExecutionProvider"]
    mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]

    captured_sess_options: list[ort.SessionOptions] = []

    def mock_init_session(
        path: str,
        sess_options: ort.SessionOptions,
        providers: list[Any],
        provider_options: list[Any],
    ) -> MagicMock:
        captured_sess_options.append(sess_options)
        assert providers == ["DmlExecutionProvider"]
        assert provider_options == [{"device_id": "1"}]
        return mock_session

    with (
        patch(
            "onnxruntime.get_available_providers",
            return_value=["DmlExecutionProvider", "CPUExecutionProvider"],
        ),
        patch(
            "app.pipeline.background.isnet_directml_provider.verify_model_file",
            return_value="dummy_sha",
        ),
        patch("onnxruntime.InferenceSession", side_effect=mock_init_session),
    ):
        provider._load_session_sync()

    assert len(captured_sess_options) == 1
    opts = captured_sess_options[0]
    assert opts.execution_mode == ort.ExecutionMode.ORT_SEQUENTIAL
    assert opts.enable_mem_pattern is False
    assert opts.inter_op_num_threads == 1
    assert opts.intra_op_num_threads == 1
    assert provider.execution_provider == "directml"


def test_directml_silent_fallback_rejection(tmp_path: Path) -> None:
    """Verifies that if ONNX Runtime silently falls back to CPU without DirectML, it is rejected."""
    dummy_model = tmp_path / "dummy.onnx"
    dummy_model.write_bytes(b"x" * 100)

    config = PipelineConfig(
        isnet_anime_model_path=dummy_model,
        isnet_model_sha256="",
        isnet_model_expected_size=100,
    )
    provider = ISNetDirectMLProvider(config=config)

    mock_session = MagicMock()
    # Session only bound to CPUExecutionProvider despite DML requested
    mock_session.get_providers.return_value = ["CPUExecutionProvider"]

    with (
        patch(
            "onnxruntime.get_available_providers",
            return_value=["DmlExecutionProvider", "CPUExecutionProvider"],
        ),
        patch(
            "app.pipeline.background.isnet_directml_provider.verify_model_file",
            return_value="dummy_sha",
        ),
        patch("onnxruntime.InferenceSession", return_value=mock_session),
        pytest.raises(DirectMLInitializationError) as exc_info,
    ):
        provider._load_session_sync()

    assert "Silent CPU fallback is rejected" in str(exc_info.value)
    assert provider._session is None
    assert provider.execution_provider == "released"


def test_directml_session_init_failure_cleanup(tmp_path: Path) -> None:
    """Verifies that an error during InferenceSession instantiation triggers clean deallocation."""
    dummy_model = tmp_path / "dummy.onnx"
    dummy_model.write_bytes(b"x" * 100)

    config = PipelineConfig(
        isnet_anime_model_path=dummy_model,
        isnet_model_sha256="",
        isnet_model_expected_size=100,
    )
    provider = ISNetDirectMLProvider(config=config)

    with (
        patch("onnxruntime.get_available_providers", return_value=["DmlExecutionProvider"]),
        patch(
            "app.pipeline.background.isnet_directml_provider.verify_model_file",
            return_value="dummy_sha",
        ),
        patch(
            "onnxruntime.InferenceSession", side_effect=RuntimeError("DirectX 12 Out of Memory")
        ),
        pytest.raises(DirectMLInitializationError) as exc_info,
    ):
        provider._load_session_sync()

    assert "Failed to initialize DirectML session" in str(exc_info.value)
    assert provider._session is None
    assert provider.execution_provider == "released"


def test_directml_resource_cleanup_idempotent() -> None:
    """Verifies that release() clears session, resets state, and can be called repeatedly."""
    provider = ISNetDirectMLProvider()
    mock_session = MagicMock()
    provider._session = mock_session
    provider._active_provider = "directml"

    provider.release()
    assert provider._session is None
    assert provider.execution_provider == "released"

    # Repeated calls must not raise
    provider.release()
    assert provider._session is None
    assert provider.execution_provider == "released"


def test_directml_concurrency_guard_rejection() -> None:
    """Verifies that concurrent multithreaded calls to _run_inference_sync raise DirectMLConcurrencyError."""
    provider = ISNetDirectMLProvider()
    provider._session = MagicMock()
    provider._input_name = "test_input"
    provider._active_provider = "directml"

    # Simulate an active inference holding the lock
    block_event = threading.Event()
    thread_started = threading.Event()
    error_caught = threading.Event()
    caught_exceptions: list[Exception] = []

    def mock_blocking_run(*args: Any, **kwargs: Any) -> list[np.ndarray]:
        thread_started.set()
        block_event.wait(timeout=2.0)
        return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

    provider._session.run = mock_blocking_run

    img_bytes = _create_dummy_png(64, 64)

    # Thread 1 starts inference and blocks
    t1 = threading.Thread(target=lambda: provider._run_inference_sync(img_bytes))
    t1.start()

    assert thread_started.wait(timeout=2.0), "Thread 1 did not start in time"

    # Thread 2 attempts inference concurrently while Thread 1 is running
    def thread_2_worker() -> None:
        try:
            provider._run_inference_sync(img_bytes)
        except DirectMLConcurrencyError as e:
            caught_exceptions.append(e)
            error_caught.set()

    t2 = threading.Thread(target=thread_2_worker)
    t2.start()

    t2.join(timeout=2.0)
    block_event.set()
    t1.join(timeout=2.0)

    assert error_caught.is_set(), "Thread 2 should have caught DirectMLConcurrencyError"
    assert len(caught_exceptions) == 1
    assert "Concurrent inference on DirectML session is strictly prohibited" in str(
        caught_exceptions[0]
    )


@pytest.mark.asyncio
async def test_directml_concurrency_guard_async_serialization() -> None:
    """Verifies that concurrent remove_background coroutines are serialized without collision."""
    provider = ISNetDirectMLProvider()
    provider._session = MagicMock()
    provider._input_name = "test_input"
    provider._active_provider = "directml"

    active_inferences = 0
    max_concurrent = 0
    lock = threading.Lock()

    def mock_run(*args: Any, **kwargs: Any) -> list[np.ndarray]:
        nonlocal active_inferences, max_concurrent
        with lock:
            active_inferences += 1
            max_concurrent = max(max_concurrent, active_inferences)
        time.sleep(0.01)
        with lock:
            active_inferences -= 1
        return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

    import time

    provider._session.run = mock_run

    img_bytes = _create_dummy_png(64, 64)

    # Launch 5 concurrent remove_background calls
    tasks = [provider.remove_background(img_bytes) for _ in range(5)]
    results = await asyncio.gather(*tasks)

    assert len(results) == 5
    # The async lock ensures max concurrent inferences on the session was exactly 1
    assert max_concurrent == 1


def test_factory_provider_selection() -> None:
    """Verifies get_background_removal_provider properly honors configuration options."""
    # 1. Default mock provider
    cfg_mock = PipelineConfig(use_mock_bg_provider=True)
    p_mock = get_background_removal_provider(cfg_mock)
    assert isinstance(p_mock, MockBackgroundRemovalProvider)

    # 2. Real CPU provider
    cfg_cpu = PipelineConfig(use_mock_bg_provider=False, onnx_execution_provider="cpu")
    p_cpu = get_background_removal_provider(cfg_cpu)
    assert isinstance(p_cpu, ISNetONNXProvider)

    # 3. DirectML provider
    cfg_dml = PipelineConfig(use_mock_bg_provider=False, onnx_execution_provider="directml")
    p_dml = get_background_removal_provider(cfg_dml)
    assert isinstance(p_dml, ISNetDirectMLProvider)

    # 4. DirectML alias 'dml'
    cfg_dml_alias = PipelineConfig(use_mock_bg_provider=False, onnx_execution_provider="dml")
    p_dml_alias = get_background_removal_provider(cfg_dml_alias)
    assert isinstance(p_dml_alias, ISNetDirectMLProvider)

    # 5. Invalid provider raises ValueError
    cfg_invalid = PipelineConfig(use_mock_bg_provider=False, onnx_execution_provider="tensorrt")
    with pytest.raises(ValueError) as exc_info:
        get_background_removal_provider(cfg_invalid)
    assert "Unsupported execution provider 'tensorrt'" in str(exc_info.value)


def test_directml_run_inference_without_load_raises() -> None:
    """Verifies that calling _run_inference_sync on an unloaded session raises RuntimeError."""
    provider = ISNetDirectMLProvider()
    assert provider._session is None
    with pytest.raises(RuntimeError) as exc_info:
        provider._run_inference_sync(b"dummy")
    assert "IS-Net DirectML session is not loaded" in str(exc_info.value)


def test_directml_invalid_device_id_rejection(tmp_path: Path) -> None:
    """Verifies that an out-of-bounds directml_device_id rejects fallback and raises DirectMLInitializationError."""
    dummy_model = tmp_path / "dummy.onnx"
    dummy_model.write_bytes(b"x" * 100)

    config = PipelineConfig(
        isnet_anime_model_path=dummy_model,
        isnet_model_sha256="",
        isnet_model_expected_size=100,
        directml_device_id=999,
    )
    provider = ISNetDirectMLProvider(config=config)

    # When device_id is invalid, ONNX Runtime falls back to CPUExecutionProvider
    mock_session = MagicMock()
    mock_session.get_providers.return_value = ["CPUExecutionProvider"]

    with (
        patch("onnxruntime.get_available_providers", return_value=["DmlExecutionProvider", "CPUExecutionProvider"]),
        patch("app.pipeline.background.isnet_directml_provider.verify_model_file", return_value="dummy_sha"),
        patch("onnxruntime.InferenceSession", return_value=mock_session),
        pytest.raises(DirectMLInitializationError) as exc_info,
    ):
        provider._load_session_sync()

    assert "Silent CPU fallback is rejected" in str(exc_info.value)
    assert provider._session is None
    assert provider.execution_provider == "released"


@pytest.mark.asyncio
async def test_directml_corrupted_input_releases_locks() -> None:
    """Verifies that corrupted image bytes fail gracefully while releasing all locks for subsequent calls."""
    provider = ISNetDirectMLProvider()
    mock_session = MagicMock()
    mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
    provider._session = mock_session
    provider._input_name = "input_tensor"
    provider._active_provider = "directml"

    from PIL import UnidentifiedImageError

    # Call with corrupted bytes: PIL cannot identify
    with pytest.raises(UnidentifiedImageError):
        await provider.remove_background(b"corrupted bytes not an image")

    # Locks must be completely free
    assert not provider._async_lock.locked()
    assert provider._inference_lock.acquire(blocking=False)
    provider._inference_lock.release()
    assert not provider._is_inferring


def test_directml_model_checksum_failure_cleanup(tmp_path: Path) -> None:
    """Verifies that model integrity or checksum failure leaves provider clean without leaking resources."""
    from app.pipeline.security.model_verifier import ModelIntegrityError

    dummy_model = tmp_path / "tampered.onnx"
    dummy_model.write_bytes(b"x" * 50)

    config = PipelineConfig(
        isnet_anime_model_path=dummy_model,
        isnet_model_sha256="expected_valid_sha",
        isnet_model_expected_size=100,
    )
    provider = ISNetDirectMLProvider(config=config)

    with (
        patch("onnxruntime.get_available_providers", return_value=["DmlExecutionProvider"]),
        patch(
            "app.pipeline.background.isnet_directml_provider.verify_model_file",
            side_effect=ModelIntegrityError("Checksum mismatch"),
        ),
        pytest.raises(ModelIntegrityError) as exc_info,
    ):
        provider._load_session_sync()

    assert "Checksum mismatch" in str(exc_info.value)
    assert provider._session is None
    assert provider.execution_provider == "uninitialized"


def test_directml_load_session_sync_idempotent(tmp_path: Path) -> None:
    """Verifies that calling _load_session_sync when session is already loaded is a no-op."""
    dummy_model = tmp_path / "dummy.onnx"
    dummy_model.write_bytes(b"x" * 100)

    config = PipelineConfig(
        isnet_anime_model_path=dummy_model,
        isnet_model_sha256="",
        isnet_model_expected_size=100,
    )
    provider = ISNetDirectMLProvider(config=config)

    mock_session = MagicMock()
    mock_session.get_providers.return_value = ["DmlExecutionProvider"]
    mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]

    with (
        patch("onnxruntime.get_available_providers", return_value=["DmlExecutionProvider"]),
        patch(
            "app.pipeline.background.isnet_directml_provider.verify_model_file",
            return_value="dummy_sha",
        ),
        patch("onnxruntime.InferenceSession", return_value=mock_session) as mock_init,
    ):
        provider._load_session_sync()
        assert mock_init.call_count == 1

        # Second call must be a no-op and not re-initialize InferenceSession
        provider._load_session_sync()
        assert mock_init.call_count == 1
        assert provider._session is mock_session


def test_directml_runtime_inference_error_releases_session() -> None:
    """Verifies that a GPU or ONNX Runtime crash during session.run deallocates session cleanly."""
    provider = ISNetDirectMLProvider()
    mock_session = MagicMock()
    mock_session.run.side_effect = RuntimeError("DirectX 12 Device Lost: DXGI_ERROR_DEVICE_REMOVED")
    provider._session = mock_session
    provider._input_name = "test_input"
    provider._active_provider = "directml"

    img_bytes = _create_dummy_png(64, 64)

    with pytest.raises(RuntimeError) as exc_info:
        provider._run_inference_sync(img_bytes)

    assert "DXGI_ERROR_DEVICE_REMOVED" in str(exc_info.value)
    # Corrupted session must be cleanly deallocated and marked released
    assert provider._session is None
    assert provider._input_name is None
    assert provider.execution_provider == "released"
    assert not provider._is_inferring
    assert not provider._inference_lock.locked()


def test_directml_release_clears_input_name() -> None:
    """Verifies that calling release() explicitly clears _input_name to prevent stale state."""
    provider = ISNetDirectMLProvider()
    provider._session = MagicMock()
    provider._input_name = "cached_input_tensor"
    provider._active_provider = "directml"

    provider.release()
    assert provider._input_name is None
    assert provider._session is None
    assert provider.execution_provider == "released"


def test_directml_concurrency_blocking_mode() -> None:
    """Verifies that when directml_strict_concurrency=False, threads serialize sequentially without error."""
    config = PipelineConfig(directml_strict_concurrency=False)
    provider = ISNetDirectMLProvider(config=config)
    mock_session = MagicMock()
    provider._session = mock_session
    provider._input_name = "test_input"
    provider._active_provider = "directml"

    execution_order: list[str] = []
    lock = threading.Lock()

    def mock_run(*args: Any, **kwargs: Any) -> list[np.ndarray]:
        import time

        with lock:
            execution_order.append("start")
        time.sleep(0.03)
        with lock:
            execution_order.append("end")
        return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

    mock_session.run = mock_run
    img_bytes = _create_dummy_png(64, 64)

    t1 = threading.Thread(target=lambda: provider._run_inference_sync(img_bytes))
    t2 = threading.Thread(target=lambda: provider._run_inference_sync(img_bytes))

    t1.start()
    t2.start()
    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    # Both threads succeeded sequentially: start -> end -> start -> end
    assert execution_order == ["start", "end", "start", "end"]


def test_pipeline_config_negative_device_id_rejected() -> None:
    """Verifies that setting a negative directml_device_id is rejected by Pydantic validation."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PipelineConfig(directml_device_id=-1)


def test_pipeline_worker_wires_directml_provider() -> None:
    """Verifies that PipelineWorker automatically resolves ISNetDirectMLProvider when configured."""
    from app.pipeline.worker import PipelineWorker

    cfg = PipelineConfig(use_mock_bg_provider=False, onnx_execution_provider="directml")
    worker = PipelineWorker(config=cfg)
    assert isinstance(worker.bg_provider, ISNetDirectMLProvider)

    cfg_cpu = PipelineConfig(use_mock_bg_provider=False, onnx_execution_provider="cpu")
    worker_cpu = PipelineWorker(config=cfg_cpu)
    assert isinstance(worker_cpu.bg_provider, ISNetONNXProvider)


def test_directml_load_session_sync_concurrent_threads(tmp_path: Path) -> None:
    """Verifies that concurrent threads calling _load_session_sync instantiate InferenceSession exactly once."""
    dummy_model = tmp_path / "dummy.onnx"
    dummy_model.write_bytes(b"x" * 100)

    config = PipelineConfig(
        isnet_anime_model_path=dummy_model,
        isnet_model_sha256="",
        isnet_model_expected_size=100,
    )
    provider = ISNetDirectMLProvider(config=config)

    mock_session = MagicMock()
    mock_session.get_providers.return_value = ["DmlExecutionProvider"]
    mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]

    init_count = 0
    init_lock = threading.Lock()

    def slow_init(*args: Any, **kwargs: Any) -> MagicMock:
        nonlocal init_count
        import time

        with init_lock:
            init_count += 1
        time.sleep(0.05)  # Simulate slow session loading & shader compilation
        return mock_session

    with (
        patch("onnxruntime.get_available_providers", return_value=["DmlExecutionProvider"]),
        patch(
            "app.pipeline.background.isnet_directml_provider.verify_model_file",
            return_value="dummy_sha",
        ),
        patch("onnxruntime.InferenceSession", side_effect=slow_init),
    ):
        threads = [
            threading.Thread(target=provider._load_session_sync)
            for _ in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=3.0)

    # Exactly 1 InferenceSession must be instantiated despite 5 concurrent loader threads
    assert init_count == 1
    assert provider._session is mock_session
    assert provider.execution_provider == "directml"


def test_directml_external_release_waits_for_active_inference() -> None:
    """Verifies that an external thread calling release() waits for active inference to finish cleanly."""
    provider = ISNetDirectMLProvider()
    mock_session = MagicMock()
    provider._session = mock_session
    provider._input_name = "input_tensor"
    provider._active_provider = "directml"

    inference_running = threading.Event()
    allow_finish = threading.Event()
    inference_completed = threading.Event()

    def mock_run(*args: Any, **kwargs: Any) -> list[np.ndarray]:
        inference_running.set()
        allow_finish.wait(timeout=2.0)
        inference_completed.set()
        return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

    mock_session.run = mock_run
    img_bytes = _create_dummy_png(64, 64)

    # Thread 1 starts inference
    t_inf = threading.Thread(target=lambda: provider._run_inference_sync(img_bytes))
    t_inf.start()

    assert inference_running.wait(timeout=2.0), "Inference thread did not start"

    # Thread 2 calls release() while Thread 1 is still inferring
    release_finished = threading.Event()

    def release_worker() -> None:
        provider.release()
        release_finished.set()

    t_rel = threading.Thread(target=release_worker)
    t_rel.start()

    # Verify release() has NOT finished yet while inference is running
    import time
    time.sleep(0.05)
    assert not release_finished.is_set(), "release() should wait for active inference"

    # Allow inference to complete
    allow_finish.set()
    t_inf.join(timeout=2.0)
    t_rel.join(timeout=2.0)

    assert inference_completed.is_set()
    assert release_finished.is_set()
    assert provider._session is None
    assert provider.execution_provider == "released"


@pytest.mark.asyncio
async def test_pipeline_worker_stop_releases_bg_provider() -> None:
    """Verifies that PipelineWorker.stop() automatically invokes release() on its bg_provider."""
    from app.pipeline.worker import PipelineWorker

    mock_provider = MagicMock(spec=BackgroundRemovalProvider)
    cfg = PipelineConfig(worker_concurrency=1)
    worker = PipelineWorker(config=cfg, bg_provider=mock_provider)

    await worker.start()
    await worker.stop()

    assert mock_provider.release.call_count == 1



