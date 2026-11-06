"""Suite 9: Baseline drift verification and viewport offset compensation tests.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import pytest

from app.domain.asset_resolver import CharacterAssetResolver
from app.domain.character import (
    AnchorType,
    AssetDefinition,
    CharacterManifest,
    FallbackConfig,
    Resolution,
    SpriteAlignment,
)
from app.pipeline.processing.drift_analyzer import DriftVerificationEngine
from tests.pipeline.conftest import create_synthetic_character_rgba


def test_drift_within_tolerance_passes() -> None:
    """Verifies that minor drift (<= 35px) passes cleanly without offset compensation."""
    verifier = DriftVerificationEngine()
    baseline = create_synthetic_character_rgba(head_center_x=512, eye_line_y=537)
    # 8px slight eye variation
    candidate = create_synthetic_character_rgba(head_center_x=514, eye_line_y=545)

    result = verifier.verify_drift(candidate, baseline)
    assert result.passed is True
    assert result.is_quarantined is False
    assert result.total_drift_px <= 35.0
    assert result.recommended_offset_x == 0
    assert result.recommended_offset_y == 0
    assert result.quarantine_reason is None


def test_drift_moderate_compensated() -> None:
    """Verifies that moderate drift (35-50px) passes with mathematical offset compensation."""
    verifier = DriftVerificationEngine()
    baseline = create_synthetic_character_rgba(head_center_x=512, eye_line_y=537)
    # Head shifted right by 38px
    candidate = create_synthetic_character_rgba(head_center_x=550, eye_line_y=537)

    result = verifier.verify_drift(candidate, baseline)
    assert result.passed is True
    assert result.is_quarantined is False
    assert 35.0 < result.total_drift_px <= 50.0
    # Compensation should shift candidate left (-38px)
    assert result.recommended_offset_x == pytest.approx(-38, abs=3)
    assert result.quarantine_reason is None


def test_drift_severe_quarantined() -> None:
    """Verifies that severe drift (> 50px) triggers quarantine to needs_review."""
    verifier = DriftVerificationEngine()
    baseline = create_synthetic_character_rgba(head_center_x=512, eye_line_y=537)
    # Severe horizontal displacement by 85px
    candidate = create_synthetic_character_rgba(head_center_x=597, eye_line_y=537)

    result = verifier.verify_drift(candidate, baseline)
    assert result.passed is False
    assert result.is_quarantined is True
    assert result.total_drift_px > 50.0
    assert "Severe alignment drift" in (result.quarantine_reason or "")


def test_quarantined_drift_asset_invisible_to_resolver() -> None:
    """Verifies that a sprite quarantined due to drift is completely excluded from live rendering."""
    manifest = CharacterManifest(
        schema_version="1.0",
        character_id="miku_nakano",
        display_name="Nakano Miku",
        default_outfit="school_uniform",
        fallbacks=FallbackConfig(default_asset_id="miku_core_idle_neutral"),
        assets=[
            AssetDefinition(
                asset_id="miku_core_idle_neutral",
                path="assets/core/idle_neutral.webp",
                state="idle",
                emotion="neutral",
                outfit="school_uniform",
                resolution=Resolution(width=1024, height=1536),
                anchor=SpriteAlignment(anchor_type=AnchorType.BOTTOM_CENTER),
                status="ready",
            ),
            # Severely drifted asset marked as quarantined
            AssetDefinition(
                asset_id="miku_dynamic_drifted_pout",
                path="assets/dynamic/drifted_pout.webp",
                state="idle",
                emotion="pout",
                outfit="school_uniform",
                resolution=Resolution(width=1024, height=1536),
                anchor=SpriteAlignment(anchor_type=AnchorType.BOTTOM_CENTER),
                status="needs_review",
            ),
        ],
    )

    resolver = CharacterAssetResolver(manifest)
    resolved = resolver.resolve(state="idle", emotion="pout", outfit="school_uniform")

    # Quarantined asset MUST NOT be returned; resolver falls back to core neutral
    assert resolved.asset.asset_id == "miku_core_idle_neutral"
    assert resolved.asset.status == "ready"
    assert resolved.is_fallback is True
