"""Suite 8: Canvas normalization and dynamic alpha edge classification tests.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

from app.domain.character import AnchorType
from app.pipeline.processing.normalizer import SpriteNormalizer
from tests.pipeline.conftest import create_synthetic_character_rgba


def test_normalizer_canvas_dimensions() -> None:
    """Verifies that arbitrary input dimensions are standardized onto 1024x1536 canvas."""
    normalizer = SpriteNormalizer(canvas_width=1024, canvas_height=1536)

    for in_w, in_h in [(800, 1200), (600, 900), (1200, 1800)]:
        raw_sprite = create_synthetic_character_rgba(width=in_w, height=in_h)
        norm_img, alignment = normalizer.normalize(raw_sprite)

        assert norm_img.size == (1024, 1536)
        assert norm_img.mode == "RGBA"
        assert alignment.bounding_box is not None
        assert len(alignment.bounding_box) == 4


def test_alpha_edge_classifier_full_body() -> None:
    """Verifies that full-body sprite with visible feet is classified as AnchorType.BOTTOM_CENTER."""
    normalizer = SpriteNormalizer()
    full_body = create_synthetic_character_rgba(sprite_type="full_body")

    anchor_type = normalizer.classify_edge(full_body)
    assert anchor_type == AnchorType.BOTTOM_CENTER


def test_alpha_edge_classifier_waist_up() -> None:
    """Verifies that waist-up sprite touching canvas bottom is classified as AnchorType.WAIST_LEVEL."""
    normalizer = SpriteNormalizer()
    waist_up = create_synthetic_character_rgba(sprite_type="waist_up")

    anchor_type = normalizer.classify_edge(waist_up)
    assert anchor_type == AnchorType.WAIST_LEVEL


def test_alpha_edge_classifier_eye_level() -> None:
    """Verifies that bust-up portrait is classified as AnchorType.EYE_LEVEL."""
    normalizer = SpriteNormalizer()
    bust_up = create_synthetic_character_rgba(sprite_type="bust_up")

    anchor_type = normalizer.classify_edge(bust_up)
    assert anchor_type == AnchorType.EYE_LEVEL


def test_ground_pinning_bottom_center() -> None:
    """Verifies that bottom_center normalization pins character feet to ground line Y=1511."""
    normalizer = SpriteNormalizer(canvas_width=1024, canvas_height=1536)
    full_body = create_synthetic_character_rgba(sprite_type="full_body")

    norm_img, alignment = normalizer.normalize(full_body)
    assert alignment.anchor_type == AnchorType.BOTTOM_CENTER

    alpha = norm_img.getchannel("A")
    bbox = alpha.getbbox()
    assert bbox is not None
    _x1, _y1, _x2, y2 = bbox

    # Feet must be pinned at Y=1511 (with +/- 2px margin)
    assert abs(y2 - 1511) <= 2, f"Feet bottom Y {y2} should be near 1511"


def test_sprite_alignment_metadata_integrity() -> None:
    """Verifies that generated SpriteAlignment contract is valid and fully populated."""
    normalizer = SpriteNormalizer()
    sprite = create_synthetic_character_rgba(sprite_type="full_body")

    _norm_img, alignment = normalizer.normalize(sprite)
    assert alignment.anchor_x == 0.5
    assert alignment.anchor_y == 1.0
    assert alignment.focal_x == 0.5
    assert 0.30 <= alignment.focal_y <= 0.40
    assert alignment.display_scale == 1.0
    assert alignment.viewport_offset_x == 0
    assert alignment.viewport_offset_y == 0
