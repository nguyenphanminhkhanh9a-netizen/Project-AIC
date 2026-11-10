"""DirectML Execution Provider for IS-Net Anime background removal on Windows GPUs.

Provides GPU-accelerated inference via DirectX 12 DirectML Execution Provider,
enforcing mandatory ORT_SEQUENTIAL execution, disabled memory pattern allocation,
strict concurrency protection, pre-flight hardware/runtime verification,
and leak-free session lifecycle management.
"""

from __future__ import annotations

import asyncio
import gc
import io
import logging
import threading
import time
from pathlib import Path
from typing import Any

import onnxruntime as ort  # type: ignore[import-not-found,import-untyped]
from PIL import Image

from app.domain.pipeline import BackgroundRemovalProvider
from app.pipeline.background.image_ops import (
    letterbox_preprocess,
    postprocess_mask,
)
from app.pipeline.config import PipelineConfig, pipeline_config
from app.pipeline.security.model_verifier import verify_model_file

logger = logging.getLogger(__name__)


class DirectMLError(RuntimeError):
    """Base exception for DirectML execution provider errors."""


class DirectMLNotAvailableError(DirectMLError):
    """Raised when DirectML execution provider is requested but not available in runtime."""


class DirectMLInitializationError(DirectMLError):
    """Raised when DirectML session initialization or device allocation fails."""


class DirectMLConcurrencyError(DirectMLError):
    """Raised when concurrent inference is attempted on a DirectML session."""


class DirectMLTimeoutError(DirectMLError, TimeoutError):
    """Raised when DirectML session release times out waiting for active inference to finish."""


class ISNetDirectMLProvider(BackgroundRemovalProvider):
    """GPU-accelerated DirectML provider for IS-Net Anime matting via ONNX Runtime."""

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config if config is not None else pipeline_config
        self._session: ort.InferenceSession | None = None
        self._async_lock = asyncio.Lock()
        self._inference_lock = threading.Lock()
        self._load_lock = threading.RLock()
        self._is_inferring: bool = False
        self._inferring_thread_id: int | None = None
        self._release_pending: bool = False
        self._active_provider: str = "uninitialized"
        self._input_name: str | None = None
        self._resolved_device_id: int | None = None

    @property
    def model_name(self) -> str:
        return "isnet_anime"

    @property
    def execution_provider(self) -> str:
        return self._active_provider

    @property
    def directml_device_id(self) -> int | None:
        """Returns the resolved DirectML device ID after session initialization."""
        return self._resolved_device_id

    def _resolve_model_path(self) -> Path:
        """Resolves model path using priority hierarchy matching CPU provider."""
        configured_path = Path(self.config.isnet_anime_model_path)
        default_path = Path.home() / ".cache" / "project_aic" / "models" / "isnetis.onnx"

        if configured_path != default_path:
            return configured_path

        if configured_path.is_file():
            return configured_path

        local_candidates = [
            Path("data/models/isnetis.onnx"),
            Path("data/models/isnet-anime.onnx"),
        ]
        for candidate in local_candidates:
            if candidate.is_file():
                return candidate

        return configured_path

    def _load_session_sync(self) -> None:
        """Performs pre-flight checks, verifies model integrity, and creates DirectML session."""
        with self._load_lock:
            if self._session is not None and not self._release_pending:
                return

            # 1. Pre-flight check: Verify DirectML execution provider is available in runtime
            available_providers = ort.get_available_providers()
            if "DmlExecutionProvider" not in available_providers:
                raise DirectMLNotAvailableError(
                    f"DirectML Execution Provider is not available in the current ONNX Runtime installation. "
                    f"Available providers: {available_providers}. "
                    f"Ensure 'onnxruntime-directml' is installed and running on a compatible Windows DirectX 12 environment."
                )

            # 2. Strict streaming model checksum verification before loading
            model_path = self._resolve_model_path()
            expected_sha = (
                self.config.isnet_model_sha256
                if self.config.isnet_model_sha256
                else self.config.isnet_expected_sha256
            )
            verify_model_file(
                model_path=model_path,
                expected_sha256=expected_sha,
                expected_size=self.config.isnet_model_expected_size,
            )

            try:
                # 3. Resolve DirectML target device via unified discovery helper
                from app.pipeline.background.device_discovery import resolve_directml_adapter

                adapter_info = resolve_directml_adapter(self.config.directml_device_id)
                device_id = adapter_info.index
                self._resolved_device_id = device_id

                # 4. Mandatory DirectML Session Options (R3)
                # Note: DirectML requires ORT_SEQUENTIAL and enable_mem_pattern=False.
                dml_opts = ort.SessionOptions()
                dml_opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
                dml_opts.enable_mem_pattern = False
                dml_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                dml_opts.inter_op_num_threads = 1
                dml_opts.intra_op_num_threads = 1  # GPU-bound; avoid spawning unnecessary CPU threads

                providers = ["DmlExecutionProvider"]
                provider_options: list[dict[str, Any]] = [{"device_id": str(device_id)}]

                logger.info(
                    "Initializing IS-Net DirectML InferenceSession on %s from %s (device_id=%d, %d MB VRAM, mem_pattern=False)",
                    adapter_info.description,
                    model_path,
                    device_id,
                    adapter_info.dedicated_vram_mb,
                )

                session = ort.InferenceSession(
                    str(model_path),
                    sess_options=dml_opts,
                    providers=providers,
                    provider_options=provider_options,
                )
                # 5. Verify that session actually bound to DirectML (no silent CPU fallback)
                active = session.get_providers()
                if "DmlExecutionProvider" not in active:
                    raise DirectMLInitializationError(
                        f"DirectML session was requested but DmlExecutionProvider is not active on session. "
                        f"Active providers: {active}. Silent CPU fallback is rejected."
                    )

                self._session = session
                self._input_name = session.get_inputs()[0].name
                self._active_provider = "directml"
            except Exception as exc:
                # Safe resource cleanup on failed initialization
                self.release()
                if isinstance(exc, (DirectMLNotAvailableError, DirectMLInitializationError)):
                    raise
                raise DirectMLInitializationError(
                    f"Failed to initialize DirectML session: {exc}"
                ) from exc

    def _run_inference_sync(
        self,
        image_bytes: bytes,
        **kwargs: Any,
    ) -> tuple[bytes, dict[str, Any]]:
        """Synchronously executes preprocessing, DirectML GPU inference, and postprocessing.

        Enforces strict mutual exclusion across threads to protect the DirectX 12 session.
        """
        if self._session is None or self._input_name is None or self._release_pending:
            raise RuntimeError("IS-Net DirectML session is not loaded")

        # Concurrency guard: reject concurrent execution on the same DirectML session
        if self.config.directml_strict_concurrency:
            acquired = self._inference_lock.acquire(blocking=False)
            if not acquired:
                raise DirectMLConcurrencyError(
                    "Concurrent inference on DirectML session is strictly prohibited. "
                    "Ensure requests are serialized or use worker_concurrency=1."
                )
        else:
            self._inference_lock.acquire(blocking=True)

        try:
            # Re-check session inside lock to prevent race if release() executed before acquisition
            if self._session is None or self._input_name is None or self._release_pending:
                raise RuntimeError("IS-Net DirectML session is not loaded")

            if self._is_inferring:
                raise DirectMLConcurrencyError(
                    "Concurrent inference on DirectML session is strictly prohibited."
                )
            self._is_inferring = True
            self._inferring_thread_id = threading.get_ident()

            start_t = time.perf_counter()
            with Image.open(io.BytesIO(image_bytes)) as raw_img:
                input_tensor, letterbox_meta = letterbox_preprocess(raw_img)

                try:
                    # DirectML GPU inference
                    outputs = self._session.run(None, {self._input_name: input_tensor})
                except Exception as run_exc:
                    logger.error(
                        "DirectML inference execution failed: %s; releasing session",
                        run_exc,
                    )
                    self.release()
                    raise

                raw_mask = outputs[0]

                out_png_bytes, diag_meta = postprocess_mask(
                    raw_mask=raw_mask,
                    orig_img=raw_img,
                    meta=letterbox_meta,
                )

            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            diag_meta.update(
                {
                    "model_name": self.model_name,
                    "execution_provider": self.execution_provider,
                    "latency_ms": elapsed_ms,
                }
            )
            return out_png_bytes, diag_meta
        finally:
            self._inferring_thread_id = None
            self._is_inferring = False
            self._inference_lock.release()

            if self._release_pending:
                self.release()

    async def remove_background(
        self,
        image_bytes: bytes,
        **kwargs: Any,
    ) -> tuple[bytes, dict[str, Any]]:
        """Processes raw image bytes and yields transparent RGBA PNG bytes.

        Enforces sequential asyncio serialization across calls on this DirectML session.
        """
        async with self._async_lock:
            if self._session is None:
                self._load_session_sync()
            return await asyncio.to_thread(self._run_inference_sync, image_bytes, **kwargs)

    def _destroy_session_sync(self) -> None:
        """Internal helper to deallocate session and reset provider state under locks."""
        if self._session is not None:
            logger.info("Releasing IS-Net DirectML InferenceSession and GPU memory")
            del self._session
            self._session = None
        self._input_name = None
        self._active_provider = "released"
        self._is_inferring = False
        self._inferring_thread_id = None
        self._release_pending = False
        gc.collect()

    def release(self, timeout: float = 5.0) -> None:
        """Safely and idempotently deallocates DirectML session and GPU resources.

        Args:
            timeout: Maximum seconds to wait for active inference to finish.

        Raises:
            DirectMLTimeoutError: If active inference does not complete within timeout.
                The session and provider state remain intact so that release may be retried.
        """
        current_thread = threading.get_ident()

        # 1. Self-Release Check (Must be performed BEFORE acquiring _load_lock):
        # If release() is called from within the active inference thread holding _inference_lock,
        # attempting to acquire _load_lock can cause AB-BA deadlock if an external caller
        # already holds _load_lock and is waiting for _inference_lock.
        # Defer session deallocation until after the inference critical section exits.
        if (
            self._inferring_thread_id is not None
            and self._inferring_thread_id == current_thread
        ):
            logger.info(
                "Release requested from active inference thread %d; deferring session cleanup until critical section exits",
                current_thread,
            )
            self._release_pending = True
            return

        with self._load_lock:
            # 2. Idempotency: If already released or uninitialized (and no release pending), no-op
            if self._session is None and not self._release_pending:
                self._active_provider = "released"
                self._input_name = None
                self._is_inferring = False
                self._inferring_thread_id = None
                return

            # 3. External caller: must acquire _inference_lock to ensure no active inference is in flight
            acquired = self._inference_lock.acquire(timeout=timeout)
            if not acquired:
                logger.warning(
                    "DirectML session release timed out after %.2fs waiting for active inference.",
                    timeout,
                )
                raise DirectMLTimeoutError(
                    f"DirectML session release timed out after {timeout:.2f}s "
                    f"waiting for active inference to complete."
                )
            try:
                self._destroy_session_sync()
            finally:
                self._inference_lock.release()
