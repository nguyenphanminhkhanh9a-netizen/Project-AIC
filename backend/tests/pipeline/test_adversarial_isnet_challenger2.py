"""Empirical challenger stress-test suite for ISNetDirectMLProvider concurrency.

Focus areas:
1. Re-entrancy during exception unwinding (including concurrent release race and double unwinding).
2. High-frequency release retries (lock starvation, multi-thread retry churn, retry during exception).
3. Rapid concurrent load and release interleaved cycles (state invariants, lifecycle churn, session leaks).
"""

from __future__ import annotations

import asyncio
import io
import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from app.pipeline.background.isnet_directml_provider import (
    DirectMLConcurrencyError,
    DirectMLTimeoutError,
    ISNetDirectMLProvider,
)
from app.pipeline.config import PipelineConfig


def _create_dummy_png(width: int = 64, height: int = 64) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), (255, 128, 0))
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestReentrancyExceptionUnwinding:
    """Stress tests for re-entrancy during exception unwinding."""

    def test_single_thread_exception_unwinding_releases_session(self) -> None:
        """Verifies that an exception during inference unwinds and re-entrantly releases session."""
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        mock_session.run.side_effect = RuntimeError("DirectX 12 Device Lost")
        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"

        img_bytes = _create_dummy_png()

        with pytest.raises(RuntimeError, match="DirectX 12 Device Lost"):
            provider._run_inference_sync(img_bytes)

        # Session should be released and locks freed
        assert provider._session is None
        assert provider._input_name is None
        assert provider.execution_provider == "released"
        assert not provider._is_inferring
        assert provider._inferring_thread_id is None
        assert not provider._inference_lock.locked()

        # Idempotent re-release
        provider.release()
        assert provider._session is None

    def test_exception_unwinding_during_concurrent_external_release(self) -> None:
        """Tests race where external thread is blocked waiting in release() while inference raises exception.

        Scenario:
        - Thread A (inferring) holds _inference_lock and enters session.run.
        - Thread B calls release(timeout=0.2). It acquires _load_lock and blocks on _inference_lock.
        - While Thread B is waiting, Thread A encounters an exception in session.run.
        - Thread A calls release() in except block, attempting to acquire _load_lock.
        - Tests whether AB-BA lock inversion creates a deadlock or if it cleanly unwinds once timeout elapses.
        """
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"

        inference_running = threading.Event()
        release_started = threading.Event()
        allow_inference_to_fail = threading.Event()

        def failing_run(*args: Any, **kwargs: Any) -> list[np.ndarray]:
            inference_running.set()
            # Wait until external release is in flight
            assert release_started.wait(timeout=2.0)
            # Give release a moment to enter with self._load_lock and block on _inference_lock
            time.sleep(0.05)
            allow_inference_to_fail.wait(timeout=2.0)
            raise RuntimeError("GPU execution faulted during inference")

        mock_session.run = failing_run
        img_bytes = _create_dummy_png()

        thread_a_error: list[Exception] = []
        thread_b_error: list[Exception] = []

        def worker_a() -> None:
            try:
                provider._run_inference_sync(img_bytes)
            except Exception as e:  # noqa: BLE001
                thread_a_error.append(e)

        def worker_b() -> None:
            try:
                # Thread B calls release with short timeout
                provider.release(timeout=0.15)
            except Exception as e:  # noqa: BLE001
                thread_b_error.append(e)

        t_a = threading.Thread(target=worker_a)
        t_b = threading.Thread(target=worker_b)

        t_a.start()
        assert inference_running.wait(timeout=2.0)

        # Start Thread B release
        t_b.start()
        # Wait a tiny moment so Thread B acquires _load_lock and blocks on _inference_lock
        time.sleep(0.05)
        release_started.set()

        # Trigger Thread A failure
        allow_inference_to_fail.set()

        # Bounded join to verify no permanent hang/deadlock
        t_b.join(timeout=3.0)
        t_a.join(timeout=3.0)

        assert not t_a.is_alive(), "Thread A deadlocked during exception unwinding!"
        assert not t_b.is_alive(), "Thread B deadlocked waiting for inference lock!"

        # Thread A must have raised its original inference error
        assert len(thread_a_error) == 1
        assert "GPU execution faulted" in str(thread_a_error[0])

        # Provider must end in clean released state
        assert provider._session is None
        assert provider.execution_provider == "released"
        assert not provider._inference_lock.locked()

    def test_double_release_in_nested_exception_handler(self) -> None:
        """Verifies safety when release() is invoked multiple times within nested exception handlers."""
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]

        def failing_run(*args: Any, **kwargs: Any) -> list[np.ndarray]:
            # Nested exception handling that invokes release twice
            try:
                raise ValueError("Inner failure")
            finally:
                provider.release()

        mock_session.run = failing_run
        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"

        img_bytes = _create_dummy_png()
        with pytest.raises(ValueError, match="Inner failure"):
            provider._run_inference_sync(img_bytes)

        assert provider._session is None
        assert provider.execution_provider == "released"
        assert not provider._inference_lock.locked()


class TestHighFrequencyReleaseRetries:
    """Stress tests for high-frequency release retries during active inference."""

    def test_high_frequency_retries_under_single_inferring_thread(self) -> None:
        """A thread retries release() in a tight loop with small timeout while inference is running."""
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"

        inference_running = threading.Event()
        stop_inference = threading.Event()

        def slow_run(*args: Any, **kwargs: Any) -> list[np.ndarray]:
            inference_running.set()
            stop_inference.wait(timeout=2.0)
            return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

        mock_session.run = slow_run
        img_bytes = _create_dummy_png()

        t_inf = threading.Thread(target=lambda: provider._run_inference_sync(img_bytes))
        t_inf.start()
        assert inference_running.wait(timeout=2.0)

        retry_count = 0
        timeout_errors = 0
        release_succeeded = False

        def retry_loop() -> None:
            nonlocal retry_count, timeout_errors, release_succeeded
            start_time = time.perf_counter()
            while time.perf_counter() - start_time < 2.0:
                retry_count += 1
                try:
                    provider.release(timeout=0.01)
                    release_succeeded = True
                    break
                except DirectMLTimeoutError:
                    timeout_errors += 1

        t_retrier = threading.Thread(target=retry_loop)
        t_retrier.start()

        # Let the retrier pound release() for at least 10 timeouts
        time.sleep(0.15)
        assert timeout_errors >= 5, f"Expected multiple timeouts, got {timeout_errors}"
        assert not release_succeeded, "Release should not have succeeded while inference is running"
        assert provider._session is mock_session, "Session was destroyed prematurely!"

        # Allow inference to finish
        stop_inference.set()
        t_inf.join(timeout=2.0)
        t_retrier.join(timeout=2.0)

        assert release_succeeded, "Release retry did not succeed after inference stopped"
        assert provider._session is None
        assert provider.execution_provider == "released"

    def test_multithreaded_high_frequency_release_retries(self) -> None:
        """8 threads hammering release(timeout=0.01) while inference is in flight."""
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"

        inference_running = threading.Event()
        stop_inference = threading.Event()

        def slow_run(*args: Any, **kwargs: Any) -> list[np.ndarray]:
            inference_running.set()
            stop_inference.wait(timeout=2.0)
            return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

        mock_session.run = slow_run
        img_bytes = _create_dummy_png()

        t_inf = threading.Thread(target=lambda: provider._run_inference_sync(img_bytes))
        t_inf.start()
        assert inference_running.wait(timeout=2.0)

        success_count = 0
        timeout_count = 0
        unexpected_errors: list[Exception] = []
        stop_workers = threading.Event()

        def hammer_worker() -> None:
            nonlocal success_count, timeout_count
            while not stop_workers.is_set():
                try:
                    provider.release(timeout=0.01)
                    success_count += 1
                    break
                except DirectMLTimeoutError:
                    timeout_count += 1
                except Exception as exc:  # noqa: BLE001
                    unexpected_errors.append(exc)
                    break

        threads = [threading.Thread(target=hammer_worker) for _ in range(8)]
        for t in threads:
            t.start()

        # Let all 8 threads retry concurrently
        time.sleep(0.25)
        assert timeout_count >= 8, f"Expected concurrent timeouts, got {timeout_count}"

        # Now finish inference
        stop_inference.set()
        t_inf.join(timeout=2.0)

        # Allow hammer threads to finish
        for t in threads:
            t.join(timeout=2.0)

        stop_workers.set()

        assert len(unexpected_errors) == 0, f"Encountered unexpected errors: {unexpected_errors}"
        assert success_count >= 1, "At least one retrying thread should have succeeded"
        assert provider._session is None
        assert provider.execution_provider == "released"
        assert not provider._inference_lock.locked()


class TestConcurrentLoadAndReleaseInterleavedCycles:
    """Stress tests for rapid interleaved load and release cycles."""

    def test_rapid_concurrent_load_and_release_hammer(self, tmp_path: Any) -> None:
        """Multiple threads concurrently calling _load_session_sync and release repeatedly."""
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
        mock_input = MagicMock()
        mock_input.name = "input_tensor"
        mock_session.get_inputs.return_value = [mock_input]

        stop_hammer = threading.Event()
        errors: list[Exception] = []
        cycle_count = 0
        cycle_lock = threading.Lock()

        def loader_worker() -> None:
            nonlocal cycle_count
            while not stop_hammer.is_set():
                try:
                    provider._load_session_sync()
                    with cycle_lock:
                        cycle_count += 1
                except Exception as e:  # noqa: BLE001
                    errors.append(e)

        def releaser_worker() -> None:
            while not stop_hammer.is_set():
                try:
                    provider.release(timeout=0.05)
                except DirectMLTimeoutError:
                    pass
                except Exception as e:  # noqa: BLE001
                    errors.append(e)

        with (
            patch("onnxruntime.get_available_providers", return_value=["DmlExecutionProvider"]),
            patch("app.pipeline.background.isnet_directml_provider.verify_model_file", return_value="dummy_sha"),
            patch("onnxruntime.InferenceSession", return_value=mock_session),
        ):
            loaders = [threading.Thread(target=loader_worker) for _ in range(4)]
            releasers = [threading.Thread(target=releaser_worker) for _ in range(4)]

            for t in loaders + releasers:
                t.start()

            time.sleep(0.5)  # Hammer for 500ms
            stop_hammer.set()

            for t in loaders + releasers:
                t.join(timeout=2.0)

        assert len(errors) == 0, f"Errors encountered during load/release hammer: {errors}"
        assert cycle_count > 0, "No load cycles executed"

        # Final state check: invariants must hold
        with provider._load_lock:
            if provider._session is not None:
                assert provider.execution_provider == "directml"
                assert provider._input_name == "input_tensor"
            else:
                assert provider.execution_provider in ("released", "uninitialized")
                assert provider._input_name is None
            assert not provider._inference_lock.locked()

    def test_interleaved_load_infer_release_pipeline(self, tmp_path: Any) -> None:
        """Rapid interleaved cycles of load -> infer -> release across multiple threads."""
        dummy_model = tmp_path / "dummy.onnx"
        dummy_model.write_bytes(b"x" * 100)

        config = PipelineConfig(
            isnet_anime_model_path=dummy_model,
            isnet_model_sha256="",
            isnet_model_expected_size=100,
            directml_strict_concurrency=True,
        )
        provider = ISNetDirectMLProvider(config=config)

        mock_session = MagicMock()
        mock_session.get_providers.return_value = ["DmlExecutionProvider"]
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        mock_session.run.return_value = [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

        img_bytes = _create_dummy_png()
        stop_hammer = threading.Event()
        errors: list[Exception] = []
        completed_inferences = 0
        inf_lock = threading.Lock()

        def pipeline_worker() -> None:
            nonlocal completed_inferences
            while not stop_hammer.is_set():
                try:
                    provider._load_session_sync()
                    try:
                        provider._run_inference_sync(img_bytes)
                        with inf_lock:
                            completed_inferences += 1
                    except (DirectMLConcurrencyError, RuntimeError):
                        # Concurrency error is expected when another thread is inferring or just released
                        pass
                    provider.release(timeout=0.05)
                except DirectMLTimeoutError:
                    pass
                except Exception as e:  # noqa: BLE001
                    errors.append(e)

        with (
            patch("onnxruntime.get_available_providers", return_value=["DmlExecutionProvider"]),
            patch("app.pipeline.background.isnet_directml_provider.verify_model_file", return_value="dummy_sha"),
            patch("onnxruntime.InferenceSession", return_value=mock_session),
        ):
            workers = [threading.Thread(target=pipeline_worker) for _ in range(4)]
            for t in workers:
                t.start()

            time.sleep(0.6)
            stop_hammer.set()

            for t in workers:
                t.join(timeout=3.0)

        assert len(errors) == 0, f"Unexpected errors in interleaved pipeline: {errors}"
        assert completed_inferences > 0, "No inferences completed"

        # Final cleanup
        provider.release()
        assert provider._session is None
        assert provider.execution_provider == "released"
        assert not provider._inference_lock.locked()

    def test_massive_16_thread_load_infer_release_churn(self, tmp_path: Any) -> None:
        """16 threads churning concurrently: 4 loaders, 4 inferrers, 8 release retriers."""
        dummy_model = tmp_path / "dummy.onnx"
        dummy_model.write_bytes(b"x" * 100)

        config = PipelineConfig(
            isnet_anime_model_path=dummy_model,
            isnet_model_sha256="",
            isnet_model_expected_size=100,
            directml_strict_concurrency=True,
        )
        provider = ISNetDirectMLProvider(config=config)

        mock_session = MagicMock()
        mock_session.get_providers.return_value = ["DmlExecutionProvider"]
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        mock_session.run.return_value = [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

        img_bytes = _create_dummy_png()
        stop_event = threading.Event()
        unexpected_errors: list[Exception] = []

        def loader() -> None:
            while not stop_event.is_set():
                try:
                    provider._load_session_sync()
                except Exception as exc:  # noqa: BLE001
                    unexpected_errors.append(exc)

        def inferrer() -> None:
            while not stop_event.is_set():
                try:
                    provider._run_inference_sync(img_bytes)
                except (DirectMLConcurrencyError, RuntimeError):
                    # Expected when session is not yet loaded or another thread is inferring
                    pass
                except Exception as exc:  # noqa: BLE001
                    unexpected_errors.append(exc)

        def releaser() -> None:
            while not stop_event.is_set():
                try:
                    provider.release(timeout=0.02)
                except DirectMLTimeoutError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    unexpected_errors.append(exc)

        with (
            patch("onnxruntime.get_available_providers", return_value=["DmlExecutionProvider"]),
            patch("app.pipeline.background.isnet_directml_provider.verify_model_file", return_value="dummy_sha"),
            patch("onnxruntime.InferenceSession", return_value=mock_session),
        ):
            threads = (
                [threading.Thread(target=loader) for _ in range(4)]
                + [threading.Thread(target=inferrer) for _ in range(4)]
                + [threading.Thread(target=releaser) for _ in range(8)]
            )

            for t in threads:
                t.start()

            time.sleep(1.0)  # Sustained churn for 1 second
            stop_event.set()

            for t in threads:
                t.join(timeout=3.0)

        assert len(unexpected_errors) == 0, f"Unexpected errors during 16-thread churn: {unexpected_errors}"

        # Clean teardown
        provider.release(timeout=1.0)
        assert provider._session is None
        assert provider.execution_provider == "released"
        assert not provider._inference_lock.locked()


class TestEdgeCasesAndAsyncCancellation:
    """Edge cases: zero timeout, asyncio cancellation mid-flight."""

    def test_zero_timeout_release_behavior(self) -> None:
        """release(timeout=0.0) behaves as a non-blocking try-release."""
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"

        # 1. When inference lock is free, timeout=0.0 releases immediately
        provider.release(timeout=0.0)
        assert provider._session is None
        assert provider.execution_provider == "released"

        # 2. Reload session and acquire inference lock manually
        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"
        assert provider._inference_lock.acquire(blocking=False)

        try:
            # When inference lock is held, timeout=0.0 raises DirectMLTimeoutError immediately
            with pytest.raises(DirectMLTimeoutError):
                provider.release(timeout=0.0)
            assert provider._session is mock_session
        finally:
            provider._inference_lock.release()

        # Clean up
        provider.release(timeout=0.1)
        assert provider._session is None

    @pytest.mark.asyncio
    async def test_asyncio_remove_background_task_cancellation_safety(self) -> None:
        """Cancelling remove_background coroutine does not crash session or corrupt locks."""
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"

        inference_started = threading.Event()
        allow_inference_to_finish = threading.Event()

        def slow_run(*args: Any, **kwargs: Any) -> list[np.ndarray]:
            inference_started.set()
            allow_inference_to_finish.wait(timeout=2.0)
            return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

        mock_session.run = slow_run
        img_bytes = _create_dummy_png()

        task = asyncio.create_task(provider.remove_background(img_bytes))
        assert await asyncio.to_thread(inference_started.wait, 2.0)

        # Cancel the asyncio task while inference is actively running in background thread
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Allow the background worker thread to finish
        allow_inference_to_finish.set()
        await asyncio.sleep(0.05)

        # Provider must still be in a valid, functional state
        assert not provider._async_lock.locked()
        assert not provider._inference_lock.locked()

        # A subsequent call must succeed
        mock_session.run = lambda *args, **kwargs: [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]
        png_out, meta = await provider.remove_background(img_bytes)
        assert len(png_out) > 0
        assert meta["execution_provider"] == "directml"

        provider.release()

