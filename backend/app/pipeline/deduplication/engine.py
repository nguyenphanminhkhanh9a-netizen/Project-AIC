"""3-Stage Multi-Scale Deduplication Engine with facial crop verification and quarantine buffer.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

from PIL import Image

from app.domain.pipeline import DeduplicationAction, DeduplicationResult
from app.pipeline.config import PipelineConfig, pipeline_config
from app.pipeline.deduplication.face_extractor import FaceExtractor
from app.pipeline.deduplication.phash import compute_phash, hamming_distance
from app.pipeline.deduplication.ssim import compute_ssim


class MultiScaleDeduplicator:
    """3-Stage Deduplication Engine: (1) Global pHash -> (2) Facial Crop SSIM -> (3) Quarantine/Action."""

    def __init__(
        self,
        config: PipelineConfig | None = None,
        face_extractor: FaceExtractor | None = None,
    ) -> None:
        self.config = config if config is not None else pipeline_config
        self.face_extractor = (
            face_extractor
            if face_extractor is not None
            else FaceExtractor(crop_ratio_top=self.config.facial_crop_ratio_top)
        )

    def check_duplicate(
        self,
        candidate_img: Image.Image,
        existing_assets: list[tuple[str, Image.Image]],
    ) -> DeduplicationResult:
        """Compares candidate sprite against existing character pack assets."""
        if not existing_assets:
            return DeduplicationResult(
                is_duplicate=False,
                is_suspect=False,
                matched_asset_id=None,
                global_hamming_distance=64,
                facial_hamming_distance=None,
                facial_ssim=None,
                action="accept",
                reason="No existing pack assets to compare against.",
            )

        # Compute candidate global pHash
        cand_global_hash = compute_phash(candidate_img)

        # Stage 1: Global Coarse Filter
        min_global_dist = 65
        closest_asset_id: str | None = None
        closest_img: Image.Image | None = None

        for asset_id, img in existing_assets:
            img_hash = compute_phash(img)
            dist = hamming_distance(cand_global_hash, img_hash)
            if dist < min_global_dist:
                min_global_dist = dist
                closest_asset_id = asset_id
                closest_img = img

        assert closest_asset_id is not None
        assert closest_img is not None

        # If global Hamming distance > suspect threshold (16), accept immediately (distinct pose/outfit)
        if min_global_dist > self.config.global_hamming_suspect_threshold:
            return DeduplicationResult(
                is_duplicate=False,
                is_suspect=False,
                matched_asset_id=closest_asset_id,
                global_hamming_distance=min_global_dist,
                facial_hamming_distance=None,
                facial_ssim=None,
                action="accept",
                reason=(
                    f"Global distance {min_global_dist} > {self.config.global_hamming_suspect_threshold} "
                    f"(distinct pose or outfit)."
                ),
            )

        # Stage 2: Local Facial Crop Verification
        cand_face = self.face_extractor.extract_face(candidate_img)
        matched_face = self.face_extractor.extract_face(closest_img)

        cand_face_hash = compute_phash(cand_face)
        matched_face_hash = compute_phash(matched_face)
        face_dist = hamming_distance(cand_face_hash, matched_face_hash)

        facial_ssim = compute_ssim(cand_face, matched_face)

        # Stage 3: Decision Rules
        action: DeduplicationAction

        # Check duplicate condition first: SSIM >= duplicate threshold (0.94)
        if facial_ssim >= self.config.facial_ssim_duplicate_threshold:
            if face_dist <= self.config.facial_hamming_duplicate_threshold:
                action = "reject"
                is_duplicate = True
                is_suspect = True
                reason = (
                    f"Exact duplicate matching '{closest_asset_id}' (SSIM={facial_ssim:.3f}, "
                    f"face_dist={face_dist})."
                )
            else:
                # Ambiguity: Very high facial SSIM but elevated hash distance -> quarantine for human review
                action = "quarantine"
                is_duplicate = False
                is_suspect = True
                reason = (
                    f"High facial similarity with elevated hash distance (SSIM={facial_ssim:.3f}, "
                    f"face_dist={face_dist}) quarantined to needs_review."
                )
        # Distinct expression confirmed: SSIM < 0.88 AND facial Hamming distance >= 8
        elif (
            facial_ssim < self.config.facial_ssim_quarantine_low
            and face_dist >= self.config.facial_hamming_distinct_threshold
        ):
            action = "accept"
            is_duplicate = False
            is_suspect = True
            reason = (
                f"Distinct facial expression confirmed (SSIM={facial_ssim:.3f}, "
                f"face_dist={face_dist})."
            )
        # Borderline range: SSIM in [0.88, 0.94) or non-distinct hash distance
        else:
            action = "quarantine"
            is_duplicate = False
            is_suspect = True
            reason = (
                f"Borderline facial similarity (SSIM={facial_ssim:.3f}, face_dist={face_dist}) "
                f"quarantined to needs_review."
            )

        return DeduplicationResult(
            is_duplicate=is_duplicate,
            is_suspect=is_suspect,
            matched_asset_id=closest_asset_id,
            global_hamming_distance=min_global_dist,
            facial_hamming_distance=face_dist,
            facial_ssim=facial_ssim,
            action=action,
            reason=reason,
        )
