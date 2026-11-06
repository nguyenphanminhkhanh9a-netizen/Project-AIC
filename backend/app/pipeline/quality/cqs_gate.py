"""Composite Quality Scoring (CQS) gate evaluating sharpness, contrast, coverage, and resolution.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

from PIL import Image

from app.domain.pipeline import QualityAssessmentResult
from app.pipeline.config import PipelineConfig, pipeline_config
from app.pipeline.quality.metrics import (
    compute_alpha_coverage,
    compute_dynamic_range,
    compute_laplacian_variance,
    compute_resolution_score,
)


class CQSQualityGate:
    """Evaluates candidate anime images using Composite Quality Scoring."""

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config if config is not None else pipeline_config

    def evaluate(self, img: Image.Image) -> QualityAssessmentResult:
        """Evaluates image and returns QualityAssessmentResult with pass/quarantine/reject decision."""
        width, height = img.size

        # Hard resolution floor check
        if (
            width < self.config.min_resolution_width
            or height < self.config.min_resolution_height
        ):
            return QualityAssessmentResult(
                passed=False,
                sharpness_score=0.0,
                contrast_score=0.0,
                coverage_ratio=0.0,
                composite_score=0.0,
                quarantine=False,
                rejection_reason=(
                    f"Image resolution {width}x{height} is below minimum requirement "
                    f"({self.config.min_resolution_width}x{self.config.min_resolution_height})."
                ),
            )

        # 1. Sharpness via Laplacian variance
        lap_var = compute_laplacian_variance(img)
        sharpness_score = min(1.0, lap_var / (lap_var + 50.0))

        # 2. Dynamic range & contrast
        dr = compute_dynamic_range(img)
        contrast_score = min(1.0, dr)

        # 3. Silhouette coverage
        coverage_ratio = compute_alpha_coverage(img)
        if self.config.min_character_coverage <= coverage_ratio <= 0.85:
            coverage_score = 1.0
        elif coverage_ratio < self.config.min_character_coverage:
            coverage_score = max(0.0, coverage_ratio / self.config.min_character_coverage)
        else:  # coverage_ratio > 0.85
            coverage_score = max(0.0, 1.0 - (coverage_ratio - 0.85) / 0.15)

        # 4. Resolution score
        resolution_score = compute_resolution_score(
            width,
            height,
            self.config.target_canvas_width,
            self.config.target_canvas_height,
        )

        # Weighted Composite Quality Score
        composite_score = (
            self.config.cqs_weight_sharpness * sharpness_score
            + self.config.cqs_weight_contrast * contrast_score
            + self.config.cqs_weight_coverage * coverage_score
            + self.config.cqs_weight_resolution * resolution_score
        )

        # Decision rules
        if composite_score >= self.config.cqs_pass_threshold:
            return QualityAssessmentResult(
                passed=True,
                sharpness_score=sharpness_score,
                contrast_score=contrast_score,
                coverage_ratio=coverage_ratio,
                composite_score=composite_score,
                quarantine=False,
                rejection_reason=None,
            )

        if composite_score >= self.config.cqs_quarantine_threshold:
            return QualityAssessmentResult(
                passed=False,
                sharpness_score=sharpness_score,
                contrast_score=contrast_score,
                coverage_ratio=coverage_ratio,
                composite_score=composite_score,
                quarantine=True,
                rejection_reason=(
                    f"Composite quality score {composite_score:.3f} is in quarantine zone "
                    f"[{self.config.cqs_quarantine_threshold:.2f}, {self.config.cqs_pass_threshold:.2f})."
                ),
            )

        return QualityAssessmentResult(
            passed=False,
            sharpness_score=sharpness_score,
            contrast_score=contrast_score,
            coverage_ratio=coverage_ratio,
            composite_score=composite_score,
            quarantine=False,
            rejection_reason=(
                f"Composite quality score {composite_score:.3f} below quarantine floor "
                f"({self.config.cqs_quarantine_threshold:.2f})."
            ),
        )
