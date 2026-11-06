"""Reproduction and invariant tests for CharacterAssetResolver READY invariant and fallback safety.

Tests:
1. Level 5 fallback with default asset in 'pending' status raises DefaultAssetNotReadyError.
2. Level 5 fallback with default asset in 'processing' status raises DefaultAssetNotReadyError.
3. Level 5 fallback with default asset in 'needs_review' status raises DefaultAssetNotReadyError.
4. Level 5 fallback with default asset in 'failed' status raises DefaultAssetNotReadyError.
5. Level 5 fallback with default asset in 'rejected' status raises DefaultAssetNotReadyError.
6. Level 5 fallback with missing default asset raises DefaultAssetMissingError.
7. Exact match resolves successfully even if default fallback asset is unready.
8. Non-ready assets are strictly NEVER returned by CharacterAssetResolver.resolve().
"""

from __future__ import annotations

import pytest

from app.domain.asset_resolver import (
    AssetResolutionError,
    CharacterAssetResolver,
    DefaultAssetMissingError,
    DefaultAssetNotReadyError,
)
from app.domain.character import (
    AssetDefinition,
    AssetStatus,
    CharacterManifest,
    FallbackConfig,
)


def _make_manifest(
    default_status: AssetStatus,
    default_asset_id: str = "asset_default",
    assets: list[AssetDefinition] | None = None,
) -> CharacterManifest:
    """Helper to create a manifest with a specific default asset status."""
    default_asset = AssetDefinition(
        asset_id=default_asset_id,
        path="sprites/default.webp",
        outfit="school_uniform",
        state="idle",
        emotion="neutral",
        status=default_status,
        priority=100,
    )
    all_assets = [default_asset]
    if assets:
        all_assets.extend(assets)

    return CharacterManifest(
        schema_version="1.0",
        character_id="miku",
        display_name="Hatsune Miku",
        default_outfit="school_uniform",
        fallbacks=FallbackConfig(
            default_asset_id=default_asset_id,
            state_fallbacks={"speaking": "idle"},
            emotion_fallbacks={"joy": "neutral"},
        ),
        assets=all_assets,
    )


@pytest.mark.parametrize(
    "unready_status",
    [
        "pending",
        "processing",
        "needs_review",
        "failed",
        "rejected",
    ],
)
def test_default_fallback_unready_status_raises(unready_status: AssetStatus) -> None:
    """Verifies that if the default asset is not ready, resolving an unmapped query raises DefaultAssetNotReadyError."""
    manifest = _make_manifest(default_status=unready_status)
    resolver = CharacterAssetResolver(manifest)

    # Request an outfit/state/emotion combination with no matches, forcing Level 5 fallback
    with pytest.raises(DefaultAssetNotReadyError) as exc_info:
        resolver.resolve(state="sleeping", emotion="terrified", outfit="gothic")

    assert issubclass(DefaultAssetNotReadyError, AssetResolutionError)
    assert issubclass(AssetResolutionError, ValueError)
    assert "not ready" in str(exc_info.value).lower()
    assert unready_status in str(exc_info.value)


def test_default_fallback_missing_default_asset_raises() -> None:
    """Verifies that if the declared default asset does not exist in assets, DefaultAssetMissingError is raised."""
    manifest = CharacterManifest(
        schema_version="1.0",
        character_id="miku",
        display_name="Hatsune Miku",
        default_outfit="school_uniform",
        fallbacks=FallbackConfig(
            default_asset_id="non_existent_asset",
        ),
        assets=[],
    )
    resolver = CharacterAssetResolver(manifest)

    with pytest.raises(DefaultAssetMissingError) as exc_info:
        resolver.resolve(state="idle", emotion="neutral")

    assert issubclass(DefaultAssetMissingError, AssetResolutionError)
    assert "not found" in str(exc_info.value).lower()


def test_unready_default_does_not_break_valid_exact_match() -> None:
    """Verifies that an unready default asset does not prevent resolving a valid, ready exact match."""
    ready_asset = AssetDefinition(
        asset_id="asset_ready_exact",
        path="sprites/ready.webp",
        outfit="school_uniform",
        state="idle",
        emotion="neutral",
        status="ready",
        priority=100,
    )
    manifest = _make_manifest(default_status="needs_review", assets=[ready_asset])
    resolver = CharacterAssetResolver(manifest)

    resolved = resolver.resolve(state="idle", emotion="neutral", outfit="school_uniform")
    assert resolved.asset.asset_id == "asset_ready_exact"
    assert resolved.asset.status == "ready"
    assert resolved.match_strategy == "exact"


def test_ready_invariant_enforced_strictly() -> None:
    """Verifies that any asset returned by resolve() always satisfies asset.status == 'ready'."""
    manifest = _make_manifest(default_status="ready")
    resolver = CharacterAssetResolver(manifest)

    resolved = resolver.resolve(state="idle", emotion="neutral")
    assert resolved.asset.status == "ready"
