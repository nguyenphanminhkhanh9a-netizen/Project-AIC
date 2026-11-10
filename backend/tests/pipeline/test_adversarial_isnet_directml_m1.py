"""Adversarial stress test suite for ISNetDirectMLProvider lifecycle & concurrency.

Designed by Empirical Challenger to rigorously stress-test:
1. Timeout accuracy and state preservation under load.
2. Thread race conditions between release(), load_session_sync(), and _run_inference_sync().
3. Absence of deadlock during exception handling in active inference while release is waiting.
4. Multithreaded hammering and fuzzing of provider lifecycle methods.
5. Re-entrancy and lock release invariants.
"""

from __future__ import annotations

import io
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from app.pipeline.background import (
    DirectMLConcurrencyError,
    ISNetDirectMLProvider,
)
from app.pipeline.background.isnet_directml_provider import DirectMLTimeoutError
from app.pipeline.config import PipelineConfig


def _create_dummy_png(width: int = 64, height: int = 64) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), (255, 128, 0))
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestTimeoutAccuracyAndStatePreservation:
    """Stress-tests timeout precision and state preservation invariants."""

    @pytest.mark.parametrize("timeout_sec", [0.05, 0.1, 0.2, 0.3])
    def test_release_timeout_duration_accuracy(self, timeout_sec: float) -> None:
        """Verifies that release(timeout) blocks for approximately the requested timeout."""
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"

        inf_running = threading.Event()
        inf_allow_exit = threading.Event()

        def slow_run(*args: Any, **kwargs: Any) -> list[np.ndarray]:
            inf_running.set()
            inf_allow_exit.wait(timeout=3.0)
            return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

        mock_session.run = slow_run
        img_bytes = _create_dummy_png()

        t_inf = threading.Thread(target=lambda: provider._run_inference_sync(img_bytes))
        t_inf.start()
        assert inf_running.wait(timeout=2.0)

        t_start = time.perf_counter()
        with pytest.raises(DirectMLTimeoutError):
            provider.release(timeout=timeout_sec)
        elapsed = time.perf_counter() - t_start

        # Windows scheduling timer granularity is ~15ms, allow reasonable upper tolerance
        assert elapsed >= timeout_sec * 0.9, f"Timeout returned too early: {elapsed}s < {timeout_sec}s"
        assert elapsed <= timeout_sec + 0.15, f"Timeout took too long: {elapsed}s > {timeout_sec + 0.15}s"

        # Check state preservation
        assert provider._session is mock_session
        assert provider._input_name == "input_tensor"
        assert provider.execution_provider == "directml"
        assert provider._is_inferring is True

        inf_allow_exit.set()
        t_inf.join(timeout=2.0)
        assert not t_inf.is_alive()
        assert provider._is_inferring is False

    def test_session_remains_usable_after_release_timeout(self) -> None:
        """Verifies that after release times out, subsequent inference can still succeed on the session."""
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"

        inf1_started = threading.Event()
        inf1_allow_finish = threading.Event()

        def mock_run_1(*args: Any, **kwargs: Any) -> list[np.ndarray]:
            inf1_started.set()
            inf1_allow_finish.wait(timeout=2.0)
            return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

        mock_session.run = mock_run_1
        img_bytes = _create_dummy_png()

        # 1. Run inference 1
        t_inf1 = threading.Thread(target=lambda: provider._run_inference_sync(img_bytes))
        t_inf1.start()
        assert inf1_started.wait(timeout=2.0)

        # 2. release() times out
        with pytest.raises(DirectMLTimeoutError):
            provider.release(timeout=0.05)

        # 3. Allow inference 1 to finish
        inf1_allow_finish.set()
        t_inf1.join(timeout=2.0)

        # 4. Now run inference 2 on the exact same session
        mock_session.run = MagicMock(return_value=[np.zeros((1, 1, 1024, 1024), dtype=np.float32)])
        out_bytes, meta = provider._run_inference_sync(img_bytes)
        assert isinstance(out_bytes, bytes)
        assert meta["execution_provider"] == "directml"

        # 5. Now release succeeds
        provider.release(timeout=1.0)
        assert provider._session is None
        assert provider.execution_provider == "released"


class TestInferenceErrorDuringExternalRelease:
    """Stress-tests the potential lock inversion scenario:

    Thread 1 is inferring and encounters an ONNX exception.
    Thread 2 is simultaneously calling release(timeout=...).
    """

    def test_inference_exception_while_release_waiting_unblocks(self) -> None:
        """Verifies that if inference fails while release() is waiting on _inference_lock,

        the system unblocks without indefinite deadlock.
        """
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"

        inf_started = threading.Event()
        rel_waiting = threading.Event()

        def failing_run(*args: Any, **kwargs: Any) -> list[np.ndarray]:
            inf_started.set()
            # Wait until release thread is actively waiting on lock
            rel_waiting.wait(timeout=2.0)
            raise RuntimeError("DirectX 12 Device Hung / TDR")

        mock_session.run = failing_run
        img_bytes = _create_dummy_png()

        inf_error: list[Exception] = []
        rel_error: list[Exception] = []

        def inf_worker() -> None:
            try:
                provider._run_inference_sync(img_bytes)
            except (RuntimeError, DirectMLConcurrencyError) as e:
                inf_error.append(e)

        def rel_worker() -> None:
            rel_waiting.set()
            try:
                # Bounded timeout of 100ms
                provider.release(timeout=0.1)
            except DirectMLTimeoutError as e:
                rel_error.append(e)

        t_inf = threading.Thread(target=inf_worker)
        t_inf.start()
        assert inf_started.wait(timeout=2.0)

        t_rel = threading.Thread(target=rel_worker)
        t_rel.start()

        # Both threads MUST terminate within bounded time (e.g. 3s max)
        t_rel.join(timeout=3.0)
        t_inf.join(timeout=3.0)

        assert not t_rel.is_alive(), "Release thread deadlocked!"
        assert not t_inf.is_alive(), "Inference thread deadlocked!"

        # Invariant: Provider should end in released state
        assert provider._session is None
        assert provider.execution_provider == "released"
        assert not provider._inference_lock.locked()


class TestMultithreadedHammering:
    """Hammer provider methods concurrently to detect race conditions and crashes."""

    def test_concurrent_hammering_inference_and_release(self) -> None:
        """Spawns multiple threads concurrently running inference, release, and session loading."""
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        mock_session.run.return_value = [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"

        img_bytes = _create_dummy_png(32, 32)
        stop_event = threading.Event()
        unexpected_errors: list[tuple[str, Exception]] = []

        def infer_loop() -> None:
            while not stop_event.is_set():
                try:
                    provider._run_inference_sync(img_bytes)
                except (DirectMLConcurrencyError, RuntimeError) as e:
                    # Permitted exceptions: concurrency rejection or session not loaded
                    msg = str(e)
                    if "not loaded" not in msg and "strictly prohibited" not in msg:
                        unexpected_errors.append(("infer_loop", e))
                except Exception as e:  # noqa: BLE001
                    unexpected_errors.append(("infer_loop", e))
                time.sleep(0.005)

        def release_loop() -> None:
            while not stop_event.is_set():
                try:
                    provider.release(timeout=0.02)
                except DirectMLTimeoutError:
                    pass  # Permitted on timeout
                except Exception as e:  # noqa: BLE001
                    unexpected_errors.append(("release_loop", e))
                time.sleep(0.008)

        def reload_loop() -> None:
            while not stop_event.is_set():
                try:
                    with provider._load_lock:
                        if provider._session is None:
                            provider._session = mock_session
                            provider._input_name = "input_tensor"
                            provider._active_provider = "directml"
                except Exception as e:  # noqa: BLE001
                    unexpected_errors.append(("reload_loop", e))
                time.sleep(0.01)

        threads = [
            threading.Thread(target=infer_loop) for _ in range(4)
        ] + [
            threading.Thread(target=release_loop) for _ in range(3)
        ] + [
            threading.Thread(target=reload_loop) for _ in range(2)
        ]

        for t in threads:
            t.start()

        # Let the stress harness hammer for 0.8 seconds
        time.sleep(0.8)
        stop_event.set()

        for t in threads:
            t.join(timeout=3.0)
            assert not t.is_alive(), "A thread in the stress harness hung!"

        assert len(unexpected_errors) == 0, f"Unexpected errors detected: {unexpected_errors}"

    def test_rapid_load_release_cycle(self) -> None:
        """Rapidly loads and releases provider 50 times to detect leaks or corruption."""
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]

        for i in range(50):
            with provider._load_lock:
                provider._session = mock_session
                provider._input_name = "input_tensor"
                provider._active_provider = "directml"

            assert provider.execution_provider == "directml"
            provider.release(timeout=1.0)
            assert provider._session is None
            assert provider.execution_provider == "released"
            assert provider._input_name is None


class TestReentrantAndDoubleCheckedLocking:
    """Tests re-entrancy and double-checked session guard."""

    def test_reentrant_release_during_inference_cleans_up(self) -> None:
        """Verifies that calling release() directly from the inferring thread works without deadlocking."""
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"

        def self_releasing_run(*args: Any, **kwargs: Any) -> list[np.ndarray]:
            # Inferring thread calls release directly
            provider.release()
            return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

        mock_session.run = self_releasing_run
        img_bytes = _create_dummy_png()

        out_bytes, _meta = provider._run_inference_sync(img_bytes)
        assert isinstance(out_bytes, bytes)
        assert provider._session is None
        assert provider.execution_provider == "released"
        assert not provider._inference_lock.locked()

    def test_double_checked_session_guard_prevents_none_session_run(self) -> None:
        """Verifies that if session becomes None right before acquiring _inference_lock,

        the double-check inside the lock raises RuntimeError instead of AttributeError.
        """
        provider = ISNetDirectMLProvider()
        provider._session = MagicMock()
        provider._input_name = "input"
        provider._active_provider = "directml"

        real_lock = provider._inference_lock

        class SabotagedLock:
            def acquire(self, *args: Any, **kwargs: Any) -> bool:
                provider._session = None  # Simulate race condition where session was destroyed right before lock acquired
                return real_lock.acquire(*args, **kwargs)

            def release(self) -> None:
                real_lock.release()

            def locked(self) -> bool:
                return real_lock.locked()

        provider._inference_lock = SabotagedLock()  # type: ignore[assignment]
        with pytest.raises(RuntimeError) as exc_info:
            provider._run_inference_sync(_create_dummy_png())

        assert "IS-Net DirectML session is not loaded" in str(exc_info.value)


class TestAsyncLifecycleAndEdgeTimeouts:
    """Tests async remove_background auto-reloading and zero-timeout boundaries."""

    @pytest.mark.asyncio
    async def test_remove_background_auto_reloads_after_release(self, tmp_path: Path) -> None:
        """Verifies that after release(), a subsequent call to remove_background() automatically re-loads the session."""
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
        mock_session.run.return_value = [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

        with (
            patch("onnxruntime.get_available_providers", return_value=["DmlExecutionProvider"]),
            patch("app.pipeline.background.isnet_directml_provider.verify_model_file", return_value="dummy_sha"),
            patch("onnxruntime.InferenceSession", return_value=mock_session),
        ):
            img_bytes = _create_dummy_png()

            # 1. First call loads session and infers
            out1, _meta1 = await provider.remove_background(img_bytes)
            assert isinstance(out1, bytes)
            assert provider._session is not None
            assert provider.execution_provider == "directml"

            # 2. Call release()
            provider.release(timeout=1.0)
            assert provider._session is None
            assert provider.execution_provider == "released"

            # 3. Second call automatically re-loads session and infers
            out2, _meta2 = await provider.remove_background(img_bytes)
            assert isinstance(out2, bytes)
            assert provider._session is not None
            assert provider.execution_provider == "directml"

            # 4. Final release
            provider.release(timeout=1.0)
            assert provider._session is None
            assert provider.execution_provider == "released"

    def test_release_timeout_zero_raises_immediately_when_busy(self) -> None:
        """Verifies that timeout=0.0 on a busy session raises DirectMLTimeoutError immediately without waiting."""
        provider = ISNetDirectMLProvider()
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input_tensor")]
        provider._session = mock_session
        provider._input_name = "input_tensor"
        provider._active_provider = "directml"

        inf_running = threading.Event()
        inf_allow_exit = threading.Event()

        def slow_run(*args: Any, **kwargs: Any) -> list[np.ndarray]:
            inf_running.set()
            inf_allow_exit.wait(timeout=2.0)
            return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

        mock_session.run = slow_run
        img_bytes = _create_dummy_png()

        t_inf = threading.Thread(target=lambda: provider._run_inference_sync(img_bytes))
        t_inf.start()
        assert inf_running.wait(timeout=2.0)

        t_start = time.perf_counter()
        with pytest.raises(DirectMLTimeoutError):
            provider.release(timeout=0.0)
        elapsed = time.perf_counter() - t_start

        # Should return almost instantly (< 50ms)
        assert elapsed < 0.05, f"timeout=0.0 took too long: {elapsed}s"
        assert provider._session is mock_session
        assert provider.execution_provider == "directml"

        inf_allow_exit.set()
        t_inf.join(timeout=2.0)

