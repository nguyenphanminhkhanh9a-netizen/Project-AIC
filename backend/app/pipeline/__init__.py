"""Project AIC Automatic Asset Processing Pipeline Core package.

Phase 0.5A Pipeline Core, Protocols, Storage & Quality Gates.
"""

from app.pipeline.background.mock_provider import MockBackgroundRemovalProvider
from app.pipeline.config import PipelineConfig, pipeline_config
from app.pipeline.deduplication.engine import MultiScaleDeduplicator
from app.pipeline.processing.drift_analyzer import DriftVerificationEngine
from app.pipeline.processing.normalizer import SpriteNormalizer
from app.pipeline.quality.cqs_gate import CQSQualityGate
from app.pipeline.security.safe_downloader import SafeDownloader
from app.pipeline.security.sanitizer import ImageSanitizer
from app.pipeline.security.ssrf_guard import SSRFGuard
from app.pipeline.storage.manifest_manager import ManifestManager
from app.pipeline.worker import PipelineWorker

__all__ = [
    "CQSQualityGate",
    "DriftVerificationEngine",
    "ImageSanitizer",
    "ManifestManager",
    "MockBackgroundRemovalProvider",
    "MultiScaleDeduplicator",
    "PipelineConfig",
    "PipelineWorker",
    "SSRFGuard",
    "SafeDownloader",
    "SpriteNormalizer",
    "pipeline_config",
]
