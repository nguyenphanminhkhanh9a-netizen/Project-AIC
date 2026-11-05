"""Suite 1: Pipeline protocols, domain DTOs, and AssetStatus extension tests.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.asset_resolver import CharacterAssetResolver
from app.domain.character import (
    AnchorType,
    AssetDefinition,
    CharacterManifest,
    FallbackConfig,
    Resolution,
    SpriteAlignment,
)
from app.domain.pipeline import (
    AlignmentDriftResult,
    BackgroundRemovalProvider,
    DeduplicationResult,
    DiscoveredImage,
    ImageDiscoveryAdapter,
    PipelineResult,
    PipelineTask,
    QualityAssessmentResult,
)


def test_image_discovery_adapter_protocol() -> None:
    """Verifies that ImageDiscoveryAdapter protocol is runtime checkable."""

    class ConformingDiscoveryAdapter:
        @property
        def provider_name(self) -> str:
            return "test_provider"

        @property
        def is_available(self) -> bool:
            return True

        async def search(
            self,
            character_id: str,
            state: str,
            emotion: str,
            outfit: str,
            limit: int = 5,
        ) -> list[DiscoveredImage]:
            return []

    assert isinstance(ConformingDiscoveryAdapter(), ImageDiscoveryAdapter)

    class IncompleteAdapter:
        @property
        def provider_name(self) -> str:
            return "incomplete"

    assert not isinstance(IncompleteAdapter(), ImageDiscoveryAdapter)


def test_background_removal_provider_protocol() -> None:
    """Verifies that BackgroundRemovalProvider protocol is runtime checkable."""

    class ConformingBgProvider:
        @property
        def model_name(self) -> str:
            return "test_model"

        @property
        def execution_provider(self) -> str:
            return "cpu"

        async def remove_background(
            self, image_bytes: bytes, **kwargs: Any
        ) -> tuple[bytes, dict[str, Any]]:
            return image_bytes, {}

        def release(self) -> None:
            pass

    assert isinstance(ConformingBgProvider(), BackgroundRemovalProvider)

    class IncompleteBgProvider:
        @property
        def model_name(self) -> str:
            return "incomplete"

    assert not isinstance(IncompleteBgProvider(), BackgroundRemovalProvider)


def test_discovered_image_model_validation() -> None:
    """Verifies DiscoveredImage schema validation and field constraints."""
    img = DiscoveredImage(
        source_url="https://example.com/art.png",
        source_provider="safebooru",
        character_id="miku_nakano",
        target_state="idle",
        target_emotion="pout",
        target_outfit="school_uniform",
    )
    assert img.source_url == "https://example.com/art.png"
    assert img.priority == 100
    assert img.tags == []

    with pytest.raises(ValidationError):
        DiscoveredImage(  # type: ignore[call-arg]
            source_url="https://example.com/art.png",
            # missing required fields
        )


def test_asset_status_extension_literals() -> None:
    """Verifies AssetStatus supports pending and needs_review in addition to legacy statuses."""
    valid_statuses = [
        "ready",
        "processing",
        "pending",
        "needs_review",
        "failed",
        "rejected",
    ]
    for status_str in valid_statuses:
        asset = AssetDefinition(
            asset_id=f"test_asset_{status_str}",
            path="assets/test.png",
            status=status_str,  # type: ignore[arg-type]
        )
        assert asset.status == status_str

    with pytest.raises(ValidationError):
        AssetDefinition(
            asset_id="invalid_status_asset",
            path="assets/test.png",
            status="quarantined",  # type: ignore[arg-type]
        )


def test_resolver_excludes_quarantined_and_pending_assets() -> None:
    """Verifies that CharacterAssetResolver strictly ignores assets not marked 'ready'."""
    manifest = CharacterManifest(
        schema_version="1.0",
        character_id="miku_nakano",
        display_name="Nakano Miku",
        default_outfit="school_uniform",
        fallbacks=FallbackConfig(default_asset_id="core_neutral"),
        assets=[
            AssetDefinition(
                asset_id="core_neutral",
                path="assets/core/idle_neutral.webp",
                state="idle",
                emotion="neutral",
                outfit="school_uniform",
                resolution=Resolution(width=1024, height=1536),
                anchor=SpriteAlignment(anchor_type=AnchorType.BOTTOM_CENTER),
                status="ready",
            ),
            AssetDefinition(
                asset_id="quarantined_pout",
                path="assets/dynamic/pout_quarantined.webp",
                state="idle",
                emotion="pout",
                outfit="school_uniform",
                resolution=Resolution(width=1024, height=1536),
                anchor=SpriteAlignment(anchor_type=AnchorType.BOTTOM_CENTER),
                status="needs_review",
            ),
            AssetDefinition(
                asset_id="pending_smile",
                path="assets/dynamic/smile_pending.webp",
                state="idle",
                emotion="smile",
                outfit="school_uniform",
                resolution=Resolution(width=1024, height=1536),
                anchor=SpriteAlignment(anchor_type=AnchorType.BOTTOM_CENTER),
                status="pending",
            ),
        ],
    )

    resolver = CharacterAssetResolver(manifest)

    # _index must strictly only contain the "ready" asset
    assert len(resolver._index) == 1
    assert ("school_uniform", "idle", "neutral") in resolver._index
    assert ("school_uniform", "idle", "pout") not in resolver._index
    assert ("school_uniform", "idle", "smile") not in resolver._index

    # Attempting to resolve the quarantined emotion MUST NOT return the quarantined asset
    resolved = resolver.resolve(state="idle", emotion="pout", outfit="school_uniform")
    assert resolved.asset.asset_id == "core_neutral"
    assert resolved.asset.status == "ready"
    assert resolved.is_fallback is True


def test_pipeline_task_and_result_models() -> None:
    """Verifies PipelineTask, PipelineResult, and assessment DTO instantiation."""
    task = PipelineTask(
        character_id="miku_nakano",
        target_state="idle",
        target_emotion="blush",
        target_outfit="school_uniform",
        source_url="https://example.com/miku.png",
        source_provider="test_provider",
    )
    assert task.status == "pending"
    assert task.stage == "discovery"
    assert task.retry_count == 0

    qa = QualityAssessmentResult(
        passed=True,
        sharpness_score=0.85,
        contrast_score=0.92,
        coverage_ratio=0.35,
        composite_score=0.88,
    )
    drift = AlignmentDriftResult(
        passed=True,
        eye_drift_px=5.2,
        head_drift_px=3.1,
        total_drift_px=5.2,
        recommended_offset_x=0,
        recommended_offset_y=0,
    )
    dedup = DeduplicationResult(
        is_duplicate=False,
        is_suspect=False,
        global_hamming_distance=24,
        action="accept",
    )

    result = PipelineResult(
        task_id=task.task_id,
        success=True,
        asset_id="miku_nakano_school_uniform_idle_blush",
        status="ready",
        quality=qa,
        drift=drift,
        dedup=dedup,
    )
    assert result.success is True
    assert result.status == "ready"
    assert result.quality is not None
    assert result.quality.composite_score == 0.88

