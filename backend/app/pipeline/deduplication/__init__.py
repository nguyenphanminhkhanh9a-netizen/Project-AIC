"""Perceptual hashing, facial extraction, SSIM, and 3-stage deduplication services."""

from app.pipeline.deduplication.engine import MultiScaleDeduplicator
from app.pipeline.deduplication.face_extractor import FaceExtractor
from app.pipeline.deduplication.phash import compute_dhash, compute_phash, hamming_distance
from app.pipeline.deduplication.ssim import compute_ssim

__all__ = [
    "FaceExtractor",
    "MultiScaleDeduplicator",
    "compute_dhash",
    "compute_phash",
    "compute_ssim",
    "hamming_distance",
]
