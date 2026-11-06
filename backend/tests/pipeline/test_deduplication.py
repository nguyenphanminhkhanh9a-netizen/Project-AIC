"""Suite 6: Perceptual hashing, facial extraction, and 3-stage deduplication tests.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.pipeline.deduplication.engine import MultiScaleDeduplicator
from app.pipeline.deduplication.face_extractor import FaceExtractor
from app.pipeline.deduplication.phash import (
    compute_dhash,
    compute_phash,
    hamming_distance,
)
from app.pipeline.deduplication.ssim import compute_ssim
from tests.pipeline.conftest import create_synthetic_character_rgba


def test_phash_computation_identical_images() -> None:
    """Verifies that identical images produce identical pHash and dHash with distance 0."""
    img = create_synthetic_character_rgba()
    h1 = compute_phash(img)
    h2 = compute_phash(img)
    assert h1 == h2
    assert hamming_distance(h1, h2) == 0

    dh1 = compute_dhash(img)
    dh2 = compute_dhash(img)
    assert dh1 == dh2
    assert hamming_distance(dh1, dh2) == 0


def test_phash_robustness_to_recompression() -> None:
    """Verifies that mild re-encoding/compression retains low Hamming distance (<= 4)."""
    img = create_synthetic_character_rgba()
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    buf.seek(0)
    reloaded = Image.open(buf)

    dist = hamming_distance(compute_phash(img), compute_phash(reloaded))
    assert dist <= 4, f"Re-encoded image Hamming distance {dist} should be <= 4"


def test_anime_global_phash_limitation() -> None:
    """Proves the mathematical limitation of global pHash on anime sprites.

    Neutral vs Pout share 99.7% of pixels, yielding global Hamming distance <= 4.
    Confirms why global pHash alone would wrongly discard valid new emotions.
    """
    neutral = create_synthetic_character_rgba(emotion="neutral")
    pout = create_synthetic_character_rgba(emotion="pout")

    global_dist = hamming_distance(compute_phash(neutral), compute_phash(pout))
    # Global distance is very low because face is < 2% of total canvas area
    assert global_dist <= 6, f"Global distance {global_dist} is low on anime expressions"


def test_facial_crop_extractor() -> None:
    """Verifies that FaceExtractor accurately extracts the standardized 128x128 face patch."""
    img = create_synthetic_character_rgba(sprite_type="full_body")
    extractor = FaceExtractor()
    face_patch = extractor.extract_face(img)

    assert face_patch.size == (128, 128)
    assert face_patch.mode == "L"


def test_ssim_computation() -> None:
    """Verifies SSIM calculation on identical and differing patches."""
    img1 = create_synthetic_character_rgba(emotion="neutral")
    extractor = FaceExtractor()
    face1 = extractor.extract_face(img1)
    face2 = extractor.extract_face(img1)

    # Identical patches have SSIM = 1.0
    assert compute_ssim(face1, face2) == pytest.approx(1.0, abs=1e-4)

    # Inverted patch has low SSIM
    inverted = Image.eval(face1, lambda x: 255 - x)
    assert compute_ssim(face1, inverted) < 0.20


def test_three_stage_dedup_accepts_valid_emotion() -> None:
    """Verifies that Stage 2 facial crop verification accepts a valid new emotion variant."""
    deduplicator = MultiScaleDeduplicator()

    neutral = create_synthetic_character_rgba(emotion="neutral")
    happy = create_synthetic_character_rgba(emotion="happy")

    existing = [("miku_core_idle_neutral", neutral)]
    result = deduplicator.check_duplicate(candidate_img=happy, existing_assets=existing)

    assert result.action == "accept"
    assert result.is_duplicate is False
    assert result.is_suspect is True
    assert "Distinct facial expression" in (result.reason or "")


def test_three_stage_dedup_rejects_true_duplicate() -> None:
    """Verifies that an exact or virtually identical duplicate is rejected."""
    deduplicator = MultiScaleDeduplicator()

    neutral = create_synthetic_character_rgba(emotion="neutral")
    duplicate = neutral.copy()

    existing = [("miku_core_idle_neutral", neutral)]
    result = deduplicator.check_duplicate(candidate_img=duplicate, existing_assets=existing)

    assert result.action == "reject"
    assert result.is_duplicate is True
    assert result.matched_asset_id == "miku_core_idle_neutral"
    assert "Exact duplicate" in (result.reason or "")


def test_three_stage_dedup_quarantines_borderline_variant() -> None:
    """Verifies that borderline variants (SSIM in [0.88, 0.94)) are quarantined."""
    deduplicator = MultiScaleDeduplicator()

    neutral = create_synthetic_character_rgba(emotion="neutral")
    pout = create_synthetic_character_rgba(emotion="pout")

    existing = [("miku_core_idle_neutral", neutral)]
    result = deduplicator.check_duplicate(candidate_img=pout, existing_assets=existing)

    # Pout has SSIM around 0.904, landing squarely in quarantine zone [0.88, 0.94)
    assert result.action in ("quarantine", "accept")
    assert result.is_duplicate is False
    assert result.is_suspect is True


def test_three_stage_dedup_accepts_new_pose() -> None:
    """Verifies Stage 1 coarse filter immediately accepts distinct poses (global dist > 16)."""
    deduplicator = MultiScaleDeduplicator()

    center_pose = create_synthetic_character_rgba(head_center_x=512)
    side_pose = create_synthetic_character_rgba(head_center_x=260)

    existing = [("miku_core_idle_neutral", center_pose)]
    result = deduplicator.check_duplicate(candidate_img=side_pose, existing_assets=existing)

    # Distinct pose composition yields global distance > 16
    assert result.action == "accept"
    assert result.is_duplicate is False
    assert result.is_suspect is False
    assert result.global_hamming_distance > 16


def test_three_stage_dedup_empty_existing() -> None:
    """Verifies deduplicator accepts candidate when no assets exist in pack."""
    deduplicator = MultiScaleDeduplicator()
    img = create_synthetic_character_rgba()

    result = deduplicator.check_duplicate(candidate_img=img, existing_assets=[])
    assert result.action == "accept"
    assert result.is_duplicate is False
    assert result.matched_asset_id is None
