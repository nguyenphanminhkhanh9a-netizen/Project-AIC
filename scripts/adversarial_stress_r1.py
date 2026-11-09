"""Adversarial Concurrency Stress Test Harness for Requirement R1.

Tests ISNetDirectMLProvider under adversarial concurrency scenarios:
- Scenario 1: 10 concurrent threads calling release() while 1 thread triggers continuous inference exceptions.
- Scenario 2: Rapid burst of self-release calls from within inference callbacks/exception handlers;
              verifies session is not deallocated prematurely during C++ execution frame.
- Scenario 3: Worker shutdown simulation while inference and session loading run concurrently.
- Scenario 4: High contention multi-thread release storm (20 threads) with short timeouts and retries.

Author: Challenger 1 (challenger_05b2_1)
"""

from __future__ import annotations

import io
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
from PIL import Image

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.pipeline.background.isnet_directml_provider import (
    DirectMLTimeoutError,
    ISNetDirectMLProvider,
)
from app.pipeline.config import PipelineConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("CHALLENGER_R1")


def create_dummy_png(width: int = 64, height: int = 64) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), (128, 200, 50))
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_mock_provider() -> tuple[ISNetDirectMLProvider, MagicMock]:
    cfg = PipelineConfig(directml_strict_concurrency=False)
    provider = ISNetDirectMLProvider(config=cfg)
    mock_session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "input_tensor"
    mock_session.get_inputs.return_value = [mock_input]
    mock_session.get_providers.return_value = ["DmlExecutionProvider"]
    mock_session.run.return_value = [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]
    provider._session = mock_session
    provider._input_name = "input_tensor"
    provider._active_provider = "directml"
    return provider, mock_session


# ==============================================================================
# SCENARIO 1: 10 CONCURRENT RELEASE THREADS + 1 CONTINUOUS INFERENCE EXCEPTION
# ==============================================================================


def test_scenario_1_concurrent_release_with_continuous_inference_exceptions() -> dict[str, Any]:
    """Kịch bản 1: 10 thread đồng thời gọi release() trong khi 1 thread inference gặp exception liên tục.

    Xác minh:
    - Không có deadlock
    - Không có unhandled exception
    - Mọi thread thoát an toàn trong thời gian timeout giới hạn (< 5.0s)
    - Session và locks ở trạng thái nhất quán sau khi hoàn tất
    """
    logger.info("=== START SCENARIO 1: 10 Concurrent Release Threads + 1 Inference Exception Loop ===")
    provider, mock_session = create_mock_provider()
    dummy_img = create_dummy_png(64, 64)

    stop_inference = threading.Event()
    inference_exceptions: list[Exception] = []
    inference_count = 0

    def failing_run(*_args: Any, **_kwargs: Any) -> list[np.ndarray]:
        nonlocal inference_count
        inference_count += 1
        time.sleep(0.005)  # Simulate brief GPU work before crash
        raise RuntimeError(f"GPU device removed simulation #{inference_count}")

    mock_session.run = failing_run

    def inference_loop() -> None:
        while not stop_inference.is_set():
            # If session was cleared by release, re-inject mock session to keep stress going
            if provider._session is None:
                provider._session = mock_session
                provider._input_name = "input_tensor"
                provider._active_provider = "directml"

            try:
                provider._run_inference_sync(dummy_img)
            except RuntimeError as exc:
                inference_exceptions.append(exc)
            except Exception as unexpected:  # noqa: BLE001
                logger.error("Unexpected exception in inference: %s", unexpected)
                inference_exceptions.append(unexpected)
            time.sleep(0.002)

    t_inf = threading.Thread(target=inference_loop, name="InferenceLoopThread")
    t_inf.daemon = True
    t_inf.start()

    # Launch 10 concurrent release threads
    num_release_threads = 10
    release_errors: list[Exception] = []
    release_durations: list[float] = []
    release_threads: list[threading.Thread] = []

    def release_worker(thread_idx: int) -> None:
        start_t = time.perf_counter()
        try:
            # Each thread calls release multiple times in rapid succession
            for _ in range(5):
                provider.release(timeout=2.0)
                time.sleep(0.005)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Release thread %d encountered exception: %s", thread_idx, exc)
            release_errors.append(exc)
        finally:
            elapsed = time.perf_counter() - start_t
            release_durations.append(elapsed)

    start_all = time.perf_counter()
    for i in range(num_release_threads):
        t = threading.Thread(target=release_worker, args=(i,), name=f"ReleaseThread-{i}")
        release_threads.append(t)
        t.start()

    # Wait for all release threads to finish with timeout
    for t in release_threads:
        t.join(timeout=5.0)

    stop_inference.set()
    t_inf.join(timeout=3.0)

    total_duration = time.perf_counter() - start_all

    deadlocked_threads = [t.name for t in release_threads if t.is_alive()]
    if t_inf.is_alive():
        deadlocked_threads.append(t_inf.name)

    passed = (
        len(deadlocked_threads) == 0
        and len(release_errors) == 0
        and total_duration < 10.0
        and not provider._inference_lock.locked()
    )

    result = {
        "scenario": "Scenario 1 (10 Concurrent Releases vs Continuous Inference Exceptions)",
        "passed": passed,
        "total_duration_s": total_duration,
        "inference_iterations": inference_count,
        "inference_exceptions_handled": len(inference_exceptions),
        "release_errors_count": len(release_errors),
        "release_errors": [str(e) for e in release_errors],
        "deadlocked_threads": deadlocked_threads,
        "inference_lock_locked": provider._inference_lock.locked(),
        "final_session": provider._session,
        "final_execution_provider": provider.execution_provider,
    }
    logger.info("Scenario 1 result: %s", result)
    return result


# ==============================================================================
# SCENARIO 2: RAPID BURST OF SELF-RELEASE CALLS FROM INFERENCE CALLBACK
# ==============================================================================


def test_scenario_2_self_release_storm_and_frame_integrity() -> dict[str, Any]:
    """Kịch bản 2: Bắn chuỗi self-release liên tiếp từ trong callback / exception handler của inference.

    Xác minh:
    - Session không bị deallocate sớm khi C++ frame đang chạy (mock_session.run)
    - Chuỗi 50 self-release liên tiếp trong 1 frame không làm hỏng state
    - Session chỉ bị hủy sau khi frame và critical section kết thúc
    - Locks giải phóng hoàn toàn
    """
    logger.info("=== START SCENARIO 2: Self-Release Burst During Inference Execution ===")
    provider, mock_session = create_mock_provider()
    dummy_img = create_dummy_png(64, 64)

    session_checks_during_cpp_frame: list[bool] = []
    num_self_release_calls = 50

    def mock_run_with_self_release_storm(*_args: Any, **_kwargs: Any) -> list[np.ndarray]:
        # Simulate active C++ frame firing a burst of self-release calls
        for _ in range(num_self_release_calls):
            provider.release(timeout=1.0)
            # Check if session is still alive in memory
            session_checks_during_cpp_frame.append(provider._session is not None)
            time.sleep(0.0001)

        # Still inside C++ frame, simulate computation
        time.sleep(0.01)
        session_checks_during_cpp_frame.append(provider._session is not None)
        return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

    mock_session.run = mock_run_with_self_release_storm

    start_t = time.perf_counter()
    out_png, _meta = provider._run_inference_sync(dummy_img)
    duration = time.perf_counter() - start_t

    # All checks during C++ frame must confirm session was ALIVE
    session_stayed_alive = all(session_checks_during_cpp_frame) and len(session_checks_during_cpp_frame) > 0
    # Session must be DESTROYED after critical section exits
    session_destroyed_after = provider._session is None and provider.execution_provider == "released"
    lock_released = not provider._inference_lock.locked()
    release_pending_cleared = provider._release_pending is False

    passed = (
        session_stayed_alive
        and session_destroyed_after
        and lock_released
        and release_pending_cleared
        and len(out_png) > 0
    )

    result = {
        "scenario": "Scenario 2 (Self-Release Storm During Active Frame)",
        "passed": passed,
        "duration_s": duration,
        "self_release_burst_count": num_self_release_calls,
        "session_checks_count": len(session_checks_during_cpp_frame),
        "session_stayed_alive_during_frame": session_stayed_alive,
        "session_destroyed_after_exit": session_destroyed_after,
        "release_pending_cleared": release_pending_cleared,
        "lock_released": lock_released,
    }
    logger.info("Scenario 2 result: %s", result)
    return result


# ==============================================================================
# SCENARIO 3: ABRUPT WORKER SHUTDOWN DURING CONCURRENT INFERENCE & SESSION LOAD
# ==============================================================================


def _run_single_shutdown_race(
    it: int,
    dummy_img: bytes,
) -> dict[str, Any]:
    """Helper to run a single iteration of concurrent inference, load, and shutdown."""
    provider, mock_session = create_mock_provider()
    inf_barrier = threading.Barrier(3)

    def slow_inference_run(*_args: Any, **_kwargs: Any) -> list[np.ndarray]:
        time.sleep(0.03)  # 30ms inference workload
        return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

    mock_session.run = slow_inference_run

    def mock_load(p: ISNetDirectMLProvider, s: MagicMock) -> None:
        with p._load_lock:
            time.sleep(0.01)
            if p._session is None and not p._release_pending:
                p._session = s
                p._input_name = "input_tensor"
                p._active_provider = "directml"

    inf_errors: list[Exception] = []
    load_errors: list[Exception] = []
    stop_errors: list[Exception] = []

    def worker_inference(p: ISNetDirectMLProvider, b: threading.Barrier, errs: list[Exception]) -> None:
        try:
            b.wait(timeout=2.0)
            p._run_inference_sync(dummy_img)
        except Exception as e:  # noqa: BLE001
            errs.append(e)

    def worker_load(p: ISNetDirectMLProvider, s: MagicMock, b: threading.Barrier, errs: list[Exception]) -> None:
        try:
            b.wait(timeout=2.0)
            mock_load(p, s)
        except Exception as e:  # noqa: BLE001
            errs.append(e)

    def worker_shutdown(p: ISNetDirectMLProvider, b: threading.Barrier, errs: list[Exception]) -> None:
        try:
            b.wait(timeout=2.0)
            time.sleep(0.005)  # Let inference and load get into flight
            p.release(timeout=2.0)
        except Exception as e:  # noqa: BLE001
            errs.append(e)

    t_inf = threading.Thread(
        target=worker_inference,
        args=(provider, inf_barrier, inf_errors),
        name=f"Inf-{it}",
    )
    t_load = threading.Thread(
        target=worker_load,
        args=(provider, mock_session, inf_barrier, load_errors),
        name=f"Load-{it}",
    )
    t_stop = threading.Thread(
        target=worker_shutdown,
        args=(provider, inf_barrier, stop_errors),
        name=f"Stop-{it}",
    )

    iter_start = time.perf_counter()
    t_inf.start()
    t_load.start()
    t_stop.start()

    t_inf.join(timeout=3.0)
    t_load.join(timeout=3.0)
    t_stop.join(timeout=3.0)
    iter_elapsed = time.perf_counter() - iter_start

    alive = [t.name for t in [t_inf, t_load, t_stop] if t.is_alive()]
    return {
        "iteration": it,
        "duration_s": iter_elapsed,
        "alive_threads": alive,
        "inf_errors": [type(e).__name__ for e in inf_errors],
        "load_errors": [type(e).__name__ for e in load_errors],
        "stop_errors": [type(e).__name__ for e in stop_errors],
        "lock_locked": provider._inference_lock.locked(),
    }


def test_scenario_3_abrupt_shutdown_during_concurrent_inference_and_load() -> dict[str, Any]:
    """Kịch bản 3: Mô phỏng worker shutdown đột ngột khi inference đang chạy dở và session load đang chạy đồng thời.

    Chạy race condition 30 iterations liên tục:
    - Thread 1: Chạy inference kéo dài (30ms)
    - Thread 2: Gọi _load_session_sync()
    - Thread 3: Gọi release() mô phỏng worker.stop()
    Xác minh:
    - Không xảy ra deadlock giữa _load_lock và _inference_lock
    - Mọi vòng lặp đều hoàn thành trong timeout giới hạn
    - Trạng thái provider cuối cùng nhất quán
    """
    logger.info("=== START SCENARIO 3: Abrupt Shutdown with Concurrent Inference and Load ===")
    iterations = 30
    iteration_records: list[dict[str, Any]] = []
    dummy_img = create_dummy_png(64, 64)

    total_start = time.perf_counter()

    for it in range(iterations):
        rec = _run_single_shutdown_race(it, dummy_img)
        iteration_records.append(rec)
        if rec["alive_threads"]:
            logger.error("Deadlock detected in iteration %d: %s", it, rec["alive_threads"])
            break

    total_duration = time.perf_counter() - total_start
    deadlocks = [r for r in iteration_records if r["alive_threads"]]
    locked_state = [r for r in iteration_records if r["lock_locked"]]

    passed = len(deadlocks) == 0 and len(locked_state) == 0 and len(iteration_records) == iterations

    result = {
        "scenario": "Scenario 3 (Abrupt Shutdown During Concurrent Inference & Load)",
        "passed": passed,
        "iterations_completed": len(iteration_records),
        "total_duration_s": total_duration,
        "deadlock_count": len(deadlocks),
        "locked_after_count": len(locked_state),
        "avg_iteration_duration_s": total_duration / max(len(iteration_records), 1),
    }
    logger.info("Scenario 3 result: %s", result)
    return result


# ==============================================================================
# SCENARIO 4: HIGH CONTENTION RELEASE STORM (20 THREADS) WITH TIMEOUT RETRY
# ==============================================================================


def test_scenario_4_high_contention_release_storm() -> dict[str, Any]:
    """Kịch bản bổ sung: 20 threads đồng thời gọi release() với timeout ngắn và retry.

    Xác minh:
    - Khi có inference đang chạy, các thread nhận DirectMLTimeoutError không bị crash
    - Khi inference hoàn tất, retry release() thành công giải phóng session
    - Lock release idempotent
    """
    logger.info("=== START SCENARIO 4: 20 Threads Release Storm with Timeout Retry ===")
    provider, mock_session = create_mock_provider()
    dummy_img = create_dummy_png(64, 64)

    inf_running = threading.Event()
    allow_inf_to_finish = threading.Event()

    def long_running_inference(*_args: Any, **_kwargs: Any) -> list[np.ndarray]:
        inf_running.set()
        allow_inf_to_finish.wait(timeout=5.0)
        return [np.zeros((1, 1, 1024, 1024), dtype=np.float32)]

    mock_session.run = long_running_inference

    t_inf = threading.Thread(
        target=lambda: provider._run_inference_sync(dummy_img),
        name="LongInferenceThread",
    )
    t_inf.start()
    assert inf_running.wait(timeout=2.0)

    # 20 threads call release with short timeout (0.05s) - must raise DirectMLTimeoutError
    timeout_errors: list[DirectMLTimeoutError] = []
    other_errors: list[Exception] = []

    def quick_release_worker() -> None:
        try:
            provider.release(timeout=0.05)
        except DirectMLTimeoutError as te:
            timeout_errors.append(te)
        except Exception as oe:  # noqa: BLE001
            other_errors.append(oe)

    threads = [threading.Thread(target=quick_release_worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)

    # Now allow inference to finish
    allow_inf_to_finish.set()
    t_inf.join(timeout=3.0)

    # Now all 20 threads retry release with generous timeout (2.0s)
    retry_success_count = 0
    retry_errors: list[Exception] = []

    def retry_release_worker() -> None:
        nonlocal retry_success_count
        try:
            provider.release(timeout=2.0)
            retry_success_count += 1
        except Exception as e:  # noqa: BLE001
            retry_errors.append(e)

    retry_threads = [threading.Thread(target=retry_release_worker) for _ in range(20)]
    for t in retry_threads:
        t.start()
    for t in retry_threads:
        t.join(timeout=2.0)

    passed = (
        len(timeout_errors) == 20
        and len(other_errors) == 0
        and retry_success_count == 20
        and len(retry_errors) == 0
        and provider._session is None
        and provider.execution_provider == "released"
        and not provider._inference_lock.locked()
    )

    result = {
        "scenario": "Scenario 4 (20 Threads Release Storm with Timeout Retry)",
        "passed": passed,
        "timeout_errors_caught": len(timeout_errors),
        "unexpected_errors": len(other_errors),
        "retry_success_count": retry_success_count,
        "retry_errors": len(retry_errors),
        "final_session": provider._session,
        "final_execution_provider": provider.execution_provider,
        "inference_lock_locked": provider._inference_lock.locked(),
    }
    logger.info("Scenario 4 result: %s", result)
    return result


def main() -> int:
    logger.info("Starting Challenger 1 Adversarial Stress Harness...")
    s1 = test_scenario_1_concurrent_release_with_continuous_inference_exceptions()
    s2 = test_scenario_2_self_release_storm_and_frame_integrity()
    s3 = test_scenario_3_abrupt_shutdown_during_concurrent_inference_and_load()
    s4 = test_scenario_4_high_contention_release_storm()

    all_passed = s1["passed"] and s2["passed"] and s3["passed"] and s4["passed"]
    print("\n" + "=" * 60)
    print("CHALLENGER 1 ADVERSARIAL STRESS TEST SUMMARY")
    print("=" * 60)
    print(f"Scenario 1 (10 Threads Release vs Continuous Inf Err): {'PASS' if s1['passed'] else 'FAIL'}")
    print(f"Scenario 2 (Self-Release Burst / C++ Frame Integrity): {'PASS' if s2['passed'] else 'FAIL'}")
    print(f"Scenario 3 (Abrupt Shutdown Concurrent Inf & Load):    {'PASS' if s3['passed'] else 'FAIL'}")
    print(f"Scenario 4 (20 Threads Storm with Timeout Retry):       {'PASS' if s4['passed'] else 'FAIL'}")
    print("=" * 60)
    print(f"OVERALL VERDICT: {'CONFIRM CORRECTNESS (APPROVE)' if all_passed else 'FIND DEFECT (REQUEST_CHANGES)'}")
    print("=" * 60)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
