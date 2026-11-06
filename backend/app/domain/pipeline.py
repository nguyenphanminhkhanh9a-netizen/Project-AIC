"""Pipeline domain protocols, lifecycle stages, and data transfer objects (DTOs).

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.domain.character import AssetStatus

PipelineStage = Literal[
    "discovery",
    "download",
    "sanitize",
    "quality_pre",
    "bg_removal",
    "alignment",
    "drift_check",
    "quality_post",
    "dedup",
    "storage",
    "manifest_update",
]

DeduplicationAction = Literal["accept", "quarantine", "reject"]


class DiscoveredImage(BaseModel):
    """Candidate image metadata returned by an ImageDiscoveryAdapter."""

    source_url: str = Field(description="Remote image URL")
    source_provider: str = Field(
        description="Name of discovery adapter (e.g. 'pinterest', 'safebooru')",
    )
    preview_url: str | None = Field(default=None, description="Low-res thumbnail URL if available")
    width: int | None = Field(default=None, description="Discovered image width in pixels")
    height: int | None = Field(default=None, description="Discovered image height in pixels")
    tags: list[str] = Field(default_factory=list, description="Associated image tags")
    author: str | None = Field(default=None, description="Artist or source attribution")
    character_id: str = Field(description="Target character ID")
    target_state: str = Field(description="Target character state (e.g. 'idle', 'speaking')")
    target_emotion: str = Field(description="Target character emotion (e.g. 'pout', 'blush')")
    target_outfit: str = Field(description="Target character outfit (e.g. 'school_uniform')")
    priority: int = Field(default=100, description="Processing priority (higher executed first)")


@runtime_checkable
class ImageDiscoveryAdapter(Protocol):
    """Protocol for pluggable image discovery adapters (Phase 0.5C)."""

    @property
    def provider_name(self) -> str:
        """Unique identifier of the discovery source."""
        ...

    @property
    def is_available(self) -> bool:
        """True if the adapter is operational and not throttled/circuit-broken."""
        ...

    async def search(
        self,
        character_id: str,
        state: str,
        emotion: str,
        outfit: str,
        limit: int = 5,
    ) -> list[DiscoveredImage]:
        """Queries source for candidates matching character visual requirements."""
        ...


@runtime_checkable
class BackgroundRemovalProvider(Protocol):
    """Protocol for background removal providers (Mock in 0.5A, ONNX in 0.5B)."""

    @property
    def model_name(self) -> str:
        """Name of the background matting model or provider."""
        ...

    @property
    def execution_provider(self) -> str:
        """Execution backend ('cpu_mock', 'directml', 'cpu')."""
        ...

    async def remove_background(
        self,
        image_bytes: bytes,
        **kwargs: Any,
    ) -> tuple[bytes, dict[str, Any]]:
        """Processes RGB image bytes and returns (transparent_png_bytes, metadata_dict)."""
        ...

    def release(self) -> None:
        """Explicitly releases cached sessions, models, and OS memory."""
        ...


class QualityAssessmentResult(BaseModel):
    """Evaluation result from Composite Quality Scoring (CQS)."""

    passed: bool = Field(description="True if image satisfies quality gates")
    sharpness_score: float = Field(description="Normalized Laplacian variance [0.0, 1.0]")
    contrast_score: float = Field(description="Normalized dynamic range [0.0, 1.0]")
    coverage_ratio: float = Field(description="Character silhouette area / canvas area")
    composite_score: float = Field(description="Weighted CQS score [0.0, 1.0]")
    quarantine: bool = Field(
        default=False, description="True if score is in quarantine zone [0.50, 0.65)"
    )
    rejection_reason: str | None = Field(
        default=None, description="Explanation if rejected or quarantined"
    )


class AlignmentDriftResult(BaseModel):
    """Evaluation result from Baseline Drift Verification against core asset."""

    passed: bool = Field(description="True if drift is within acceptable limits (<= 50px)")
    is_quarantined: bool = Field(
        default=False, description="True if drift exceeds 50px quarantine threshold"
    )
    eye_drift_px: float = Field(description="Vertical eye line deviation in pixels")
    head_drift_px: float = Field(description="Horizontal head center deviation in pixels")
    total_drift_px: float = Field(description="Maximum component drift in pixels")
    recommended_offset_x: int = Field(
        default=0, description="Calculated viewport X offset compensation"
    )
    recommended_offset_y: int = Field(
        default=0, description="Calculated viewport Y offset compensation"
    )
    quarantine_reason: str | None = Field(default=None, description="Explanation if quarantined")


class DeduplicationResult(BaseModel):
    """Evaluation result from the 3-Stage Deduplication Engine."""

    is_duplicate: bool = Field(
        description="True if candidate matches an existing asset exactly"
    )
    is_suspect: bool = Field(description="True if candidate triggered Stage 2 verification")
    matched_asset_id: str | None = Field(
        default=None, description="Existing asset ID that triggered match"
    )
    global_hamming_distance: int = Field(description="Hamming distance on global 64-bit pHash")
    facial_hamming_distance: int | None = Field(
        default=None, description="Hamming distance on facial crop pHash"
    )
    facial_ssim: float | None = Field(
        default=None, description="Structural Similarity on facial crops"
    )
    action: DeduplicationAction = Field(
        description="Recommended action: 'accept', 'quarantine', 'reject'"
    )
    reason: str | None = Field(default=None, description="Explanation of deduplication decision")


class PipelineTask(BaseModel):
    """Work order queued for asynchronous pipeline execution."""

    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    character_id: str
    target_state: str
    target_emotion: str
    target_outfit: str
    source_url: str
    source_provider: str
    stage: PipelineStage = "discovery"
    status: AssetStatus = "pending"
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineResult(BaseModel):
    """Final result of a completed or failed pipeline task."""

    task_id: str
    success: bool
    asset_id: str | None = None
    status: AssetStatus
    quality: QualityAssessmentResult | None = None
    drift: AlignmentDriftResult | None = None
    dedup: DeduplicationResult | None = None
    error: str | None = None
