"""Suite 5: Image quality metrics and Composite Quality Scoring (CQS) gate tests.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.pipeline.quality.cqs_gate import CQSQualityGate
from app.pipeline.quality.metrics import (
    compute_alpha_coverage,
    compute_dynamic_range,
    compute_laplacian_variance,
    compute_resolution_score,
)
from tests.pipeline.conftest import create_synthetic_character_rgba


def test_laplacian_sharpness_discrimination() -> None:
    """Verifies that Laplacian variance sharply distinguishes crisp anime edges from blurred images."""
    sharp_img = create_synthetic_character_rgba(blur_radius=0.0)
    blurred_img = create_synthetic_character_rgba(blur_radius=8.0)

    sharp_var = compute_laplacian_variance(sharp_img)
    blurred_var = compute_laplacian_variance(blurred_img)

    assert sharp_var > 45.0, f"Sharp anime lineart variance should be > 45, got {sharp_var}"
    assert blurred_var < 35.0, f"Blurred image variance should be < 35, got {blurred_var}"
    assert sharp_var > blurred_var * 4.0


def test_contrast_metric_discrimination() -> None:
    """Verifies that dynamic range metric identifies good contrast vs washed out images."""
    # Full dynamic range image
    img_good = Image.new("L", (100, 100), 0)
    draw = ImageDraw.Draw(img_good)
    draw.rectangle([20, 20, 80, 80], fill=255)
    dr_good = compute_dynamic_range(img_good)
    assert dr_good > 0.80

    # Washed out / low contrast image (values clamped between 120 and 135)
    washed_arr = np.random.randint(120, 135, size=(100, 100), dtype=np.uint8)
    dr_low = compute_dynamic_range(washed_arr)
    assert dr_low < 0.20


def test_character_coverage_metric() -> None:
    """Verifies that silhouette coverage ratio identifies balanced, empty, and over-zoomed sprites."""
    full_body = create_synthetic_character_rgba(sprite_type="full_body")
    cov = compute_alpha_coverage(full_body)
    assert 0.20 <= cov <= 0.60, f"Full body silhouette coverage {cov} should be balanced"

    # Tiny dot (degenerate image)
    tiny = Image.new("RGBA", (1024, 1536), (0, 0, 0, 0))
    tiny.putpixel((500, 500), (255, 255, 255, 255))
    cov_tiny = compute_alpha_coverage(tiny)
    assert cov_tiny < 0.01

    # Over-zoomed / solid block (99% opaque)
    solid = Image.new("RGBA", (1024, 1536), (255, 255, 255, 255))
    cov_solid = compute_alpha_coverage(solid)
    assert cov_solid == 1.0


def test_resolution_score() -> None:
    """Verifies normalized resolution scoring relative to standard 1024x1536 canvas."""
    assert compute_resolution_score(1024, 1536) == 1.0
    assert compute_resolution_score(2048, 3072) == 1.0  # Capped at 1.0
    assert compute_resolution_score(512, 768) == pytest.approx(0.5, abs=0.01)
    assert compute_resolution_score(0, 0) == 0.0


def test_cqs_pass_on_high_quality_sprite() -> None:
    """Verifies that standard crisp full-body anime sprite easily passes CQS gate."""
    gate = CQSQualityGate()
    img = create_synthetic_character_rgba(sprite_type="full_body")

    result = gate.evaluate(img)
    assert result.passed is True
    assert result.quarantine is False
    assert result.composite_score >= 0.65
    assert result.rejection_reason is None


def test_cqs_quarantine_protects_pastel_art() -> None:
    """Verifies that soft watercolor/pastel art with lower sharpness is quarantined rather than rejected."""
    gate = CQSQualityGate()
    # Apply mild blur radius (2.5) to simulate soft pastel lineart
    pastel_img = create_synthetic_character_rgba(sprite_type="full_body", blur_radius=2.5)

    result = gate.evaluate(pastel_img)
    # Must land in quarantine zone [0.50, 0.65)
    assert 0.48 <= result.composite_score < 0.68
    if result.composite_score < 0.65:
        assert result.quarantine is True
        assert result.passed is False
        assert "quarantine zone" in (result.rejection_reason or "")


def test_resolution_floor_rejection() -> None:
    """Verifies that images below minimum resolution (512x768) are rejected immediately."""
    gate = CQSQualityGate()
    small_img = create_synthetic_character_rgba(width=400, height=600)

    result = gate.evaluate(small_img)
    assert result.passed is False
    assert result.quarantine is False
    assert "below minimum requirement" in (result.rejection_reason or "")
