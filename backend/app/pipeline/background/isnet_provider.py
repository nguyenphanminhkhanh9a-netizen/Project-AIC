"""Real IS-Net Anime ONNX background removal provider for CPU execution.

Provides lazy-loading InferenceSession with OpenMP thread clamping,
asyncio.to_thread non-blocking execution, streaming SHA-256 verification,
and genuine 4-channel RGBA matting.
"""

from __future__ import annotations

import asyncio
import gc
import io
import logging
import os
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


class ISNetONNXProvider(BackgroundRemovalProvider):
    """Production CPU provider for IS-Net Anime matting via ONNX Runtime."""

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config if config is not None else pipeline_config
        self._session: ort.InferenceSession | None = None
        self._lock = asyncio.Lock()
        self._active_provider: str = "uninitialized"
        self._input_name: str | None = None

    @property
    def model_name(self) -> str:
        return "isnet_anime"

    @property
    def execution_provider(self) -> str:
        return self._active_provider

    def _resolve_model_path(self) -> Path:
        """Resolves model path using priority hierarchy."""
        configured_path = Path(self.config.isnet_anime_model_path)
        default_path = Path.home() / ".cache" / "project_aic" / "models" / "isnetis.onnx"

        # If user explicitly configured a custom path (e.g. in test or env), honor it directly
        if configured_path != default_path:
            return configured_path

        if configured_path.is_file():
            return configured_path

        # Local repo fallbacks
        local_candidates = [
            Path("data/models/isnetis.onnx"),
            Path("data/models/isnet-anime.onnx"),
        ]
        for candidate in local_candidates:
            if candidate.is_file():
                return candidate

        return configured_path

    def _load_session_sync(self) -> None:
        """Verifies model checksum and instantiates ONNX Runtime InferenceSession."""
        model_path = self._resolve_model_path()
        expected_sha = (
            self.config.isnet_model_sha256
            if self.config.isnet_model_sha256
            else self.config.isnet_expected_sha256
        )

        # Strict streaming verification before loading into memory
        verify_model_file(
            model_path=model_path,
            expected_sha256=expected_sha,
            expected_size=self.config.isnet_model_expected_size,
        )

        cpu_opts = ort.SessionOptions()
        cpu_opts.enable_mem_pattern = True
        cpu_threads = min(self.config.onnx_intra_op_threads, os.cpu_count() or 4)
        cpu_opts.intra_op_num_threads = cpu_threads
        cpu_opts.inter_op_num_threads = 1
        cpu_opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        cpu_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        logger.info(
            "Initializing IS-Net ONNX InferenceSession from %s with %d threads",
            model_path,
            cpu_threads,
        )
        self._session = ort.InferenceSession(
            str(model_path),
            sess_options=cpu_opts,
            providers=["CPUExecutionProvider"],
        )
        self._input_name = self._session.get_inputs()[0].name
        self._active_provider = "cpu"

    def _run_inference_sync(
        self,
        image_bytes: bytes,
        **kwargs: Any,
    ) -> tuple[bytes, dict[str, Any]]:
        """Synchronously executes the full preprocessing, inference, and postprocessing pipeline."""
        if self._session is None or self._input_name is None:
            raise RuntimeError("IS-Net session is not loaded")

        start_t = time.perf_counter()
        with Image.open(io.BytesIO(image_bytes)) as raw_img:
            # Symmetrical letterboxing and float32 ImageNet normalization
            input_tensor, letterbox_meta = letterbox_preprocess(raw_img)

            # ONNX CPU inference
            outputs = self._session.run(None, {self._input_name: input_tensor})
            raw_mask = outputs[0]

            # Float32 unpadding, soft alpha ramp, and RGBA composition
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

    async def remove_background(
        self,
        image_bytes: bytes,
        **kwargs: Any,
    ) -> tuple[bytes, dict[str, Any]]:
        """Processes raw image bytes and yields genuine RGBA PNG bytes with alpha transparency.

        Thread-safe and non-blocking to the FastAPI event loop.
        """
        async with self._lock:
            if self._session is None:
                await asyncio.to_thread(self._load_session_sync)

        return await asyncio.to_thread(self._run_inference_sync, image_bytes, **kwargs)

    def release(self) -> None:
        """Idempotently deallocates ONNX Runtime session and invokes garbage collection."""
        if self._session is not None:
            logger.info("Releasing IS-Net ONNX InferenceSession")
            del self._session
            self._session = None
        self._active_provider = "released"
        gc.collect()
