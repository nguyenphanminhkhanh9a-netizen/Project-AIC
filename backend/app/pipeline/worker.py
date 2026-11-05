"""Asynchronous pipeline worker, FIFO task queue, in-flight deduplication, and Dead Letter Queue.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from PIL import Image

from app.domain.character import AssetDefinition, AssetStatus, Resolution
from app.domain.pipeline import (
    AlignmentDriftResult,
    BackgroundRemovalProvider,
    PipelineResult,
    PipelineStage,
    PipelineTask,
)
from app.pipeline.background.mock_provider import MockBackgroundRemovalProvider
from app.pipeline.config import PipelineConfig, pipeline_config
from app.pipeline.deduplication.engine import MultiScaleDeduplicator
from app.pipeline.processing.drift_analyzer import DriftVerificationEngine
from app.pipeline.processing.normalizer import SpriteNormalizer
from app.pipeline.quality.cqs_gate import CQSQualityGate
from app.pipeline.security.safe_downloader import SafeDownloader
from app.pipeline.security.sanitizer import ImageSanitizer
from app.pipeline.storage.manifest_manager import ManifestManager

logger = logging.getLogger(__name__)


class PipelineWorker:
    """Asynchronous background worker executing pipeline tasks with sequential concurrency."""

    def __init__(
        self,
        config: PipelineConfig | None = None,
        downloader: SafeDownloader | None = None,
        sanitizer: ImageSanitizer | None = None,
        quality_gate: CQSQualityGate | None = None,
        bg_provider: BackgroundRemovalProvider | None = None,
        normalizer: SpriteNormalizer | None = None,
        drift_verifier: DriftVerificationEngine | None = None,
        deduplicator: MultiScaleDeduplicator | None = None,
        manifest_manager: ManifestManager | None = None,
    ) -> None:
        self.config = config if config is not None else pipeline_config
        self.downloader = downloader if downloader is not None else SafeDownloader()
        self.sanitizer = sanitizer if sanitizer is not None else ImageSanitizer(
            max_pixels=self.config.max_image_pixels
        )
        self.quality_gate = quality_gate if quality_gate is not None else CQSQualityGate(self.config)
        self.bg_provider = (
            bg_provider if bg_provider is not None else MockBackgroundRemovalProvider()
        )
        self.normalizer = normalizer if normalizer is not None else SpriteNormalizer(
            canvas_width=self.config.target_canvas_width,
            canvas_height=self.config.target_canvas_height,
        )
        self.drift_verifier = (
            drift_verifier if drift_verifier is not None else DriftVerificationEngine(self.config)
        )
        self.deduplicator = (
            deduplicator if deduplicator is not None else MultiScaleDeduplicator(self.config)
        )
        self.manifest_manager = (
            manifest_manager
            if manifest_manager is not None
            else ManifestManager(characters_dir=self.config.characters_dir, config=self.config)
        )

        self._queue: asyncio.Queue[PipelineTask] = asyncio.Queue(maxsize=self.config.max_queue_size)
        self._inflight: set[str] = set()
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(self.config.worker_concurrency)
        self._dlq: list[dict[str, Any]] = []
        self._worker_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    def _task_key(self, task: PipelineTask) -> str:
        return f"{task.character_id}:{task.target_outfit}:{task.target_state}:{task.target_emotion}"

    async def enqueue(self, task: PipelineTask) -> bool:
        """Enqueues a pipeline task if an identical task is not currently in-flight."""
        key = self._task_key(task)
        async with self._lock:
            if key in self._inflight:
                logger.info("Task %s already in-flight; skipping duplicate enqueue.", key)
                return False
            self._inflight.add(key)

        try:
            self._queue.put_nowait(task)
            logger.info("Enqueued task %s (%s).", task.task_id, key)
            return True
        except asyncio.QueueFull:
            async with self._lock:
                self._inflight.remove(key)
            logger.warning("Pipeline queue is full; rejected task %s.", task.task_id)
            return False

    def _record_dlq(self, task: PipelineTask, error: Exception, stage: PipelineStage) -> None:
        """Appends failed task to Dead Letter Queue (DLQ) and persists to disk."""
        entry: dict[str, Any] = {
            "task_id": task.task_id,
            "character_id": task.character_id,
            "target": f"{task.target_outfit}:{task.target_state}:{task.target_emotion}",
            "source_url": task.source_url,
            "stage": stage,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": time.time(),
        }
        self._dlq.append(entry)

        try:
            self.config.dlq_path.parent.mkdir(parents=True, exist_ok=True)
            self.config.dlq_path.write_text(json.dumps(self._dlq, indent=2), encoding="utf-8")
        except OSError as e:
            logger.warning("Failed to persist DLQ to disk: %s", e)

    def get_dlq_tasks(self) -> list[dict[str, Any]]:
        """Returns recorded dead letter queue entries."""
        return list(self._dlq)

    async def process_task(self, task: PipelineTask) -> PipelineResult:
        """Executes full pipeline processing stages on a single task under concurrency governor."""
        current_stage: PipelineStage = "download"
        task.status = "processing"
        task.stage = current_stage
        task.updated_at = time.time()

        async with self._semaphore:
            try:
                # 1. Download
                current_stage = "download"
                task.stage = current_stage
                raw_bytes = await self.downloader.download(task.source_url)

                # 2. Sanitize
                current_stage = "sanitize"
                task.stage = current_stage
                sanitized_input = self.sanitizer.sanitize_image(raw_bytes)

                # 3. Pre-Matting Quality Assessment (CQS)
                current_stage = "quality_pre"
                task.stage = current_stage
                pre_cqs = self.quality_gate.evaluate(sanitized_input)
                if not pre_cqs.passed and not pre_cqs.quarantine:
                    return PipelineResult(
                        task_id=task.task_id,
                        success=False,
                        status="rejected",
                        quality=pre_cqs,
                        error=pre_cqs.rejection_reason,
                    )

                # 4. Background Removal
                current_stage = "bg_removal"
                task.stage = current_stage
                rgba_png_bytes, _bg_meta = await self.bg_provider.remove_background(raw_bytes)
                bg_cutout = self.sanitizer.sanitize_image(rgba_png_bytes)

                # 5. Canvas Normalization & Anchor Placement
                current_stage = "alignment"
                task.stage = current_stage
                normalized_img, alignment_meta = self.normalizer.normalize(bg_cutout)

                # 6. Baseline Drift Verification
                current_stage = "drift_check"
                task.stage = current_stage
                drift_res: AlignmentDriftResult | None = None
                baseline_img = self._load_baseline_image(task.character_id)
                if baseline_img is not None:
                    drift_res = self.drift_verifier.verify_drift(normalized_img, baseline_img)
                    if drift_res.recommended_offset_x != 0 or drift_res.recommended_offset_y != 0:
                        alignment_meta.viewport_offset_x = drift_res.recommended_offset_x
                        alignment_meta.viewport_offset_y = drift_res.recommended_offset_y

                # 7. Post-Matting Quality Assessment
                current_stage = "quality_post"
                task.stage = current_stage
                post_cqs = self.quality_gate.evaluate(normalized_img)

                # 8. Multi-Scale Deduplication
                current_stage = "dedup"
                task.stage = current_stage
                existing_assets = self._load_existing_pack_assets(task.character_id)
                dedup_res = self.deduplicator.check_duplicate(normalized_img, existing_assets)

                if dedup_res.action == "reject":
                    return PipelineResult(
                        task_id=task.task_id,
                        success=False,
                        status="rejected",
                        quality=post_cqs,
                        drift=drift_res,
                        dedup=dedup_res,
                        error=dedup_res.reason,
                    )

                # 9. Determine Status (Quarantine vs Ready)
                final_status: AssetStatus
                if (
                    (drift_res is not None and drift_res.is_quarantined)
                    or pre_cqs.quarantine
                    or post_cqs.quarantine
                    or dedup_res.action == "quarantine"
                ):
                    final_status = "needs_review"
                else:
                    final_status = "ready"

                # 10. Atomic Storage & Manifest Update
                current_stage = "storage"
                task.stage = current_stage
                asset_id = (
                    f"{task.character_id}_{task.target_outfit}_"
                    f"{task.target_state}_{task.target_emotion}"
                )
                relative_path = f"assets/dynamic/{asset_id}.webp"
                webp_bytes = self.sanitizer.to_webp_bytes(normalized_img)

                asset_def = AssetDefinition(
                    asset_id=asset_id,
                    path=relative_path,
                    format="webp",
                    state=task.target_state,
                    emotion=task.target_emotion,
                    outfit=task.target_outfit,
                    resolution=Resolution(
                        width=self.config.target_canvas_width,
                        height=self.config.target_canvas_height,
                    ),
                    anchor=alignment_meta,
                    is_core=False,
                    status=final_status,
                )

                current_stage = "manifest_update"
                task.stage = current_stage
                self.manifest_manager.commit_asset(
                    character_id=task.character_id,
                    asset=asset_def,
                    image_bytes=webp_bytes,
                    format="webp",
                )

                task.status = final_status
                return PipelineResult(
                    task_id=task.task_id,
                    success=True,
                    asset_id=asset_id,
                    status=final_status,
                    quality=post_cqs,
                    drift=drift_res,
                    dedup=dedup_res,
                    error=None,
                )

            except Exception as e:
                logger.exception(
                    "Pipeline task %s failed at stage %s",
                    task.task_id,
                    current_stage,
                )
                self._record_dlq(task, e, current_stage)
                task.status = "failed"
                task.error_message = str(e)
                return PipelineResult(
                    task_id=task.task_id,
                    success=False,
                    status="failed",
                    error=str(e),
                )
            finally:
                async with self._lock:
                    key = self._task_key(task)
                    self._inflight.discard(key)

    def _load_baseline_image(self, character_id: str) -> Image.Image | None:
        """Loads baseline image asset for drift verification if present."""
        try:
            manifest = self.manifest_manager.load_manifest(character_id)
            baseline_id = self.config.baseline_asset_id
            for asset in manifest.assets:
                if asset.asset_id == baseline_id:
                    path = self.manifest_manager.characters_dir / character_id / asset.path
                    if path.is_file():
                        with Image.open(path) as img:
                            return img.convert("RGBA")
        except (OSError, ValueError) as e:
            logger.debug("Baseline asset not loaded: %s", e)
        return None

    def _load_existing_pack_assets(
        self, character_id: str
    ) -> list[tuple[str, Image.Image]]:
        """Loads existing ready pack assets into memory for deduplication comparisons."""
        results: list[tuple[str, Image.Image]] = []
        try:
            manifest = self.manifest_manager.load_manifest(character_id)
            for asset in manifest.assets:
                if asset.status == "ready":
                    path = self.manifest_manager.characters_dir / character_id / asset.path
                    if path.is_file():
                        with Image.open(path) as img:
                            results.append((asset.asset_id, img.convert("RGBA")))
        except (OSError, ValueError) as e:
            logger.debug("Existing pack assets not loaded: %s", e)
        return results

    async def _worker_loop(self) -> None:
        """Background FIFO queue consumer loop."""
        while not self._stop_event.is_set():
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=0.2)
            except TimeoutError:
                continue

            try:
                await self.process_task(task)
            except Exception:
                logger.exception("Unhandled worker boundary exception on task %s", task.task_id)
            finally:
                self._queue.task_done()

    async def start(self) -> None:
        """Starts worker loop background task."""
        if self._worker_task is None or self._worker_task.done():
            self._stop_event.clear()
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("PipelineWorker started.")

    async def stop(self) -> None:
        """Stops worker loop gracefully after current tasks complete."""
        self._stop_event.set()
        if self._worker_task is not None:
            await self._worker_task
            self._worker_task = None
            logger.info("PipelineWorker stopped.")
