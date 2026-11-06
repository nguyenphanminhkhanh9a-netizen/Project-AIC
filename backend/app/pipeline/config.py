"""Pipeline runtime configuration and threshold settings.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PipelineConfig(BaseSettings):
    """Central configuration for pipeline security, quality gates, and storage."""

    model_config = SettingsConfigDict(
        env_prefix="AIC_PIPELINE_",
        env_file=".env",
        extra="ignore",
    )

    # Storage Paths
    characters_dir: Path = Field(
        default=Path("backend/app/resources/characters"),
        description="Path to root character pack directory",
    )
    storage_dir: Path = Field(
        default=Path("data/pipeline"),
        description="Working directory for temporary downloads and cache",
    )
    dlq_path: Path = Field(
        default=Path("data/pipeline/dead_letter_queue.json"),
        description="Path to Dead Letter Queue persistence file",
    )

    # Security & Guardrails
    max_download_size_bytes: int = Field(
        default=15 * 1024 * 1024, description="15 MB max image download"
    )
    download_timeout_seconds: float = Field(default=10.0, description="Socket read timeout")
    connect_timeout_seconds: float = Field(default=5.0, description="Socket connect timeout")
    max_redirect_hops: int = Field(default=3, description="Maximum allowed 3xx redirect hops")
    max_image_pixels: int = Field(
        default=8192 * 8192, description="67 Megapixels decompress bomb limit"
    )
    allowed_schemes: tuple[str, ...] = ("http", "https")
    max_downloader_cache_entries: int = Field(
        default=64, description="Maximum items cached in SafeDownloader"
    )
    max_downloader_cache_bytes: int = Field(
        default=64 * 1024 * 1024,
        description="64 MB maximum cumulative byte size of SafeDownloader cache",
    )

    # Quality Gate (CQS) Settings
    min_resolution_width: int = Field(default=512)
    min_resolution_height: int = Field(default=768)
    target_canvas_width: int = Field(default=1024)
    target_canvas_height: int = Field(default=1536)
    min_laplacian_variance: float = Field(default=45.0, description="Sharpness floor")
    min_dynamic_range: float = Field(default=0.35, description="Contrast dynamic range floor")
    min_character_coverage: float = Field(
        default=0.20, description="Minimum silhouette area ratio"
    )
    max_character_coverage: float = Field(
        default=0.92, description="Maximum silhouette area ratio"
    )
    cqs_weight_sharpness: float = Field(default=0.35)
    cqs_weight_contrast: float = Field(default=0.25)
    cqs_weight_coverage: float = Field(default=0.25)
    cqs_weight_resolution: float = Field(default=0.15)
    cqs_pass_threshold: float = Field(default=0.65, description=">= 0.65 passes gate")
    cqs_quarantine_threshold: float = Field(
        default=0.50, description="[0.50, 0.65) quarantined to needs_review"
    )

    # Deduplication Thresholds
    global_hamming_reject_threshold: int = Field(
        default=4, description="Global pHash duplicate threshold"
    )
    global_hamming_suspect_threshold: int = Field(
        default=16, description="Global pHash suspect threshold"
    )
    facial_crop_ratio_top: float = Field(
        default=0.25, description="Top 25% of bbox for facial extraction"
    )
    facial_hamming_distinct_threshold: int = Field(
        default=8, description=">= 8 confirms distinct emotion"
    )
    facial_hamming_duplicate_threshold: int = Field(
        default=2, description="<= 2 suspect duplicate"
    )
    facial_ssim_duplicate_threshold: float = Field(
        default=0.94, description=">= 0.94 confirms exact duplicate"
    )
    facial_ssim_quarantine_low: float = Field(
        default=0.88, description="[0.88, 0.94) quarantined"
    )

    # Drift Verification Thresholds
    max_drift_pass_px: float = Field(default=35.0, description="<= 35px passes without compensation")
    max_drift_compensate_px: float = Field(
        default=50.0, description="25-50px compensated via viewport offsets"
    )
    max_drift_quarantine_px: float = Field(
        default=50.0, description="> 50px quarantined to needs_review"
    )
    baseline_asset_id: str = Field(default="miku_core_idle_neutral")

    # Concurrency & Worker
    worker_concurrency: int = Field(default=1, description="Sequential background processing")
    max_queue_size: int = Field(default=100)


pipeline_config = PipelineConfig()
