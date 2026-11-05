"""Baseline drift verification engine comparing candidate sprites against character core baseline.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from app.domain.pipeline import AlignmentDriftResult
from app.pipeline.config import PipelineConfig, pipeline_config


class DriftVerificationEngine:
    """Verifies eye line and head position drift against designated core baseline asset."""

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config if config is not None else pipeline_config

    def _extract_head_and_eye_coords(self, img: Image.Image) -> tuple[float, float]:
        """Extracts horizontal head center X and vertical eye line Y from RGBA sprite."""
        if "A" in img.getbands():
            alpha = img.getchannel("A")
            bbox = alpha.getbbox()
        else:
            bbox = (0, 0, img.width, img.height)

        if bbox is None:
            return float(img.width / 2.0), float(img.height * 0.35)

        x1, y1, x2, y2 = bbox
        sil_h = y2 - y1

        # Upper 20% of silhouette to find head center X
        upper_h = max(1, int(sil_h * 0.20))
        upper_alpha = np.array(img.getchannel("A").crop((x1, y1, x2, y1 + upper_h)))
        non_zero_coords = np.argwhere(upper_alpha > 10)

        if non_zero_coords.size > 0:
            x_head = float(x1 + np.mean(non_zero_coords[:, 1]))
        else:
            x_head = float((x1 + x2) / 2.0)

        # Eye line Y: standard proportion at ~22.8% from silhouette top
        y_eye = float(y1 + sil_h * 0.228)

        return x_head, y_eye

    def verify_drift(
        self, candidate_img: Image.Image, baseline_img: Image.Image
    ) -> AlignmentDriftResult:
        """Compares candidate eye line and head position against baseline asset."""
        cand_x, cand_y = self._extract_head_and_eye_coords(candidate_img)
        base_x, base_y = self._extract_head_and_eye_coords(baseline_img)

        drift_x = abs(cand_x - base_x)
        drift_y = abs(cand_y - base_y)
        total_drift = max(drift_x, drift_y)

        # Threshold evaluation
        if total_drift <= self.config.max_drift_pass_px:
            return AlignmentDriftResult(
                passed=True,
                is_quarantined=False,
                eye_drift_px=drift_y,
                head_drift_px=drift_x,
                total_drift_px=total_drift,
                recommended_offset_x=0,
                recommended_offset_y=0,
                quarantine_reason=None,
            )

        if total_drift <= self.config.max_drift_compensate_px:
            offset_x = round(base_x - cand_x)
            offset_y = round(base_y - cand_y)
            return AlignmentDriftResult(
                passed=True,
                is_quarantined=False,
                eye_drift_px=drift_y,
                head_drift_px=drift_x,
                total_drift_px=total_drift,
                recommended_offset_x=offset_x,
                recommended_offset_y=offset_y,
                quarantine_reason=None,
            )

        return AlignmentDriftResult(
            passed=False,
            is_quarantined=True,
            eye_drift_px=drift_y,
            head_drift_px=drift_x,
            total_drift_px=total_drift,
            recommended_offset_x=round(base_x - cand_x),
            recommended_offset_y=round(base_y - cand_y),
            quarantine_reason=(
                f"Severe alignment drift ({total_drift:.1f}px) exceeds quarantine threshold "
                f"({self.config.max_drift_quarantine_px:.1f}px)."
            ),
        )
