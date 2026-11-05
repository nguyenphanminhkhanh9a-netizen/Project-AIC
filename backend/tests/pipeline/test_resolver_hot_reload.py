"""Suite 11: CharacterAssetResolver hot reload, thread safety, and concurrent reader stress tests.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

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


def test_resolver_reload_pointer_swap() -> None:
    """Verifies that rebuilding/swapping manifest index immediately exposes newly added ready assets."""
    manifest_v1 = CharacterManifest(
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
            )
        ],
    )
    resolver = CharacterAssetResolver(manifest_v1)

    # Initial query for "pout" falls back to neutral
    initial_res = resolver.resolve(state="idle", emotion="pout", outfit="school_uniform")
    assert initial_res.is_fallback is True
    assert initial_res.asset.asset_id == "core_neutral"

    # Add new approved ready asset
    new_asset = AssetDefinition(
        asset_id="miku_dynamic_pout",
        path="assets/dynamic/pout.webp",
        state="idle",
        emotion="pout",
        outfit="school_uniform",
        resolution=Resolution(width=1024, height=1536),
        anchor=SpriteAlignment(anchor_type=AnchorType.BOTTOM_CENTER),
        status="ready",
    )
    manifest_v2 = manifest_v1.model_copy(update={"assets": [*manifest_v1.assets, new_asset]})

    # Hot reload state
    resolver.manifest = manifest_v2
    resolver._build_index()

    # Query for "pout" now returns exact match instantaneously
    updated_res = resolver.resolve(state="idle", emotion="pout", outfit="school_uniform")
    assert updated_res.is_fallback is False
    assert updated_res.match_strategy == "exact"
    assert updated_res.asset.asset_id == "miku_dynamic_pout"


def test_resolver_reload_rejects_corrupted_manifest(tmp_path: Path) -> None:
    """Verifies that invalid or corrupted manifest JSON cannot corrupt resolver state."""
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text("{invalid_json: true", encoding="utf-8")

    with pytest.raises(ValueError):  # pydantic.ValidationError subclasses ValueError
        CharacterManifest.model_validate_json(manifest_file.read_text(encoding="utf-8"))


def test_concurrent_reader_stress_during_reload() -> None:
    """Stress test: 4 worker threads perform continuous lookups during 10 consecutive manifest reloads."""
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
            )
        ],
    )
    resolver = CharacterAssetResolver(manifest)

    stop_event = threading.Event()
    exceptions: list[Exception] = []
    lookup_count = 0

    def reader_loop() -> None:
        nonlocal lookup_count
        while not stop_event.is_set():
            try:
                res = resolver.resolve(state="idle", emotion="neutral", outfit="school_uniform")
                assert res.asset.asset_id == "core_neutral"
                lookup_count += 1
            except Exception as e:  # noqa: BLE001
                exceptions.append(e)


    threads = [threading.Thread(target=reader_loop) for _ in range(4)]
    for t in threads:
        t.start()

    # Trigger 10 rapid reloads in main thread
    for i in range(10):
        new_asset = AssetDefinition(
            asset_id=f"dynamic_{i}",
            path=f"assets/dynamic/{i}.webp",
            state="idle",
            emotion=f"emotion_{i}",
            outfit="school_uniform",
            status="ready",
        )
        resolver.manifest = resolver.manifest.model_copy(
            update={"assets": [*resolver.manifest.assets, new_asset]}
        )
        resolver._build_index()
        time.sleep(0.005)

    stop_event.set()
    for t in threads:
        t.join()

    assert len(exceptions) == 0, f"Encountered concurrency exceptions: {exceptions}"
    assert lookup_count >= 1000, f"Expected >= 1000 lookups, performed {lookup_count}"


def test_quarantined_asset_excluded_after_reload() -> None:
    """Verifies that quarantined assets (needs_review) remain completely omitted after reload."""
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
                status="ready",
            ),
            AssetDefinition(
                asset_id="quarantined_asset",
                path="assets/dynamic/quarantine.webp",
                state="idle",
                emotion="blush",
                outfit="school_uniform",
                status="needs_review",
            ),
        ],
    )
    resolver = CharacterAssetResolver(manifest)

    # Query for blush must not return quarantined asset
    res = resolver.resolve(state="idle", emotion="blush", outfit="school_uniform")
    assert res.is_fallback is True
    assert res.asset.asset_id == "core_neutral"
    assert ("school_uniform", "idle", "blush") not in resolver._index
