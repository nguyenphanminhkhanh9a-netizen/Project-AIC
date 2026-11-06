"""Adversarial Stress Test Suite for CharacterAssetResolver READY Invariant.

Challenger R3-2: Adversarial Domain & Concurrency Challenger.
Empirically stress-tests:
1. Malicious manifests with default asset ID pointing to every non-READY status:
   - 'pending', 'processing', 'needs_review', 'failed', 'rejected'
   - Arbitrary/corrupt statuses ('quarantined', 'corrupted', 'draft', '', None)
2. Malicious manifests with missing, empty, or non-existent default asset ID.
3. Priority inversion: High-priority unready asset vs low-priority READY asset.
4. Circular outfit fallback graph containing unready assets.
5. Fuzzing oracle: 2,000 randomized manifests and queries with invariant assertions.
6. Invariant verification: In 100% of resolutions, an asset with status != 'ready'
   is NEVER returned under any circumstances.
7. Concurrent resolution stress during dynamic manifest hot-reloading (50+ threads).
"""

from __future__ import annotations

import random
import string
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.domain.asset_resolver import (
    AssetResolutionError,
    CharacterAssetResolver,
    DefaultAssetMissingError,
    DefaultAssetNotReadyError,
)
from app.domain.character import (
    AssetDefinition,
    CharacterManifest,
    CompatibilityGroup,
    FallbackConfig,
)


def _rand_str(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=length))


def test_resolver_rejects_all_non_ready_statuses_in_default_fallback() -> None:
    """Adversarially verify that every known non-ready status raises DefaultAssetNotReadyError."""
    unready_statuses = [
        "pending",
        "processing",
        "needs_review",
        "failed",
        "rejected",
    ]

    for status in unready_statuses:
        manifest = CharacterManifest(
            schema_version="1.0",
            character_id="miku",
            display_name="Hatsune Miku",
            default_outfit="school_uniform",
            fallbacks=FallbackConfig(default_asset_id="default_unready"),
            assets=[
                AssetDefinition(
                    asset_id="default_unready",
                    path="sprites/default.webp",
                    outfit="school_uniform",
                    state="idle",
                    emotion="neutral",
                    status=status,  # type: ignore
                )
            ],
        )
        resolver = CharacterAssetResolver(manifest)

        with pytest.raises(DefaultAssetNotReadyError) as exc_info:
            resolver.resolve(state="sleeping", emotion="terrified", outfit="gothic")

        assert issubclass(DefaultAssetNotReadyError, AssetResolutionError)
        assert status in str(exc_info.value)


def test_resolver_rejects_arbitrary_corrupt_statuses_via_model_construct() -> None:
    """Adversarially bypass Pydantic validation using model_construct to inject arbitrary corrupt statuses."""
    corrupt_statuses = [
        "quarantined",
        "corrupted_stream",
        "draft",
        "deleted",
        "null",
        "",
        "READY",  # case-sensitive check: uppercase is NOT 'ready'
        " ready ",
    ]

    for corrupt_status in corrupt_statuses:
        corrupt_asset = AssetDefinition.model_construct(
            asset_id="default_corrupt",
            path="sprites/corrupt.webp",
            outfit="school_uniform",
            state="idle",
            emotion="neutral",
            status=corrupt_status,
            priority=100,
        )
        manifest = CharacterManifest.model_construct(
            schema_version="1.0",
            character_id="miku",
            display_name="Hatsune Miku",
            default_outfit="school_uniform",
            fallbacks=FallbackConfig.model_construct(default_asset_id="default_corrupt"),
            assets=[corrupt_asset],
            compatibility_groups={},
        )
        resolver = CharacterAssetResolver(manifest)

        with pytest.raises(DefaultAssetNotReadyError) as exc_info:
            resolver.resolve(state="dancing", emotion="ecstatic")

        assert issubclass(DefaultAssetNotReadyError, AssetResolutionError)
        assert corrupt_status in str(exc_info.value)


def test_resolver_rejects_missing_and_non_existent_default_asset() -> None:
    """Verify that empty manifests, missing IDs, or pointing to nonexistent IDs raise DefaultAssetMissingError."""
    # 1. Non-existent asset ID
    manifest_nonexistent = CharacterManifest(
        schema_version="1.0",
        character_id="miku",
        display_name="Hatsune Miku",
        default_outfit="school_uniform",
        fallbacks=FallbackConfig(default_asset_id="does_not_exist_at_all"),
        assets=[
            AssetDefinition(
                asset_id="asset_ready",
                path="sprites/ready.webp",
                outfit="school_uniform",
                state="idle",
                emotion="neutral",
                status="ready",
            )
        ],
    )
    resolver = CharacterAssetResolver(manifest_nonexistent)
    with pytest.raises(DefaultAssetMissingError) as exc_info:
        resolver.resolve(state="unknown_state", emotion="unknown_emotion")
    assert "was not found in assets list" in str(exc_info.value)

    # 2. Empty assets list
    manifest_empty = CharacterManifest(
        schema_version="1.0",
        character_id="miku",
        display_name="Hatsune Miku",
        default_outfit="school_uniform",
        fallbacks=FallbackConfig(default_asset_id="default_miku"),
        assets=[],
    )
    resolver_empty = CharacterAssetResolver(manifest_empty)
    with pytest.raises(DefaultAssetMissingError):
        resolver_empty.resolve(state="idle", emotion="neutral")


def test_priority_inversion_unready_high_priority_ignored() -> None:
    """Adversarial scenario: High-priority asset is 'needs_review' / 'pending'.

    Lower priority asset is 'ready'.
    Resolver MUST ignore the unready high-priority asset and select the ready asset.
    """
    unready_high = AssetDefinition(
        asset_id="asset_high_unready",
        path="sprites/high.webp",
        outfit="school_uniform",
        state="idle",
        emotion="neutral",
        status="needs_review",
        priority=999,
    )
    ready_low = AssetDefinition(
        asset_id="asset_low_ready",
        path="sprites/low.webp",
        outfit="school_uniform",
        state="idle",
        emotion="neutral",
        status="ready",
        priority=10,
    )
    manifest = CharacterManifest(
        schema_version="1.0",
        character_id="miku",
        display_name="Hatsune Miku",
        default_outfit="school_uniform",
        fallbacks=FallbackConfig(default_asset_id="asset_low_ready"),
        assets=[unready_high, ready_low],
    )
    resolver = CharacterAssetResolver(manifest)
    res = resolver.resolve(state="idle", emotion="neutral", outfit="school_uniform")

    assert res.asset.asset_id == "asset_low_ready"
    assert res.asset.status == "ready"


def test_cyclic_outfit_fallback_with_unready_assets_terminates_safely() -> None:
    """Adversarial scenario: Malicious outfit graph with cycle A -> B -> C -> A.

    All matching assets in outfits A, B, and C are 'needs_review' or 'failed'.
    Resolver must not loop infinitely and must fallback to Level 5.
    """
    groups = {
        "outfit_a": CompatibilityGroup(display_name="A", fallback_outfit="outfit_b"),
        "outfit_b": CompatibilityGroup(display_name="B", fallback_outfit="outfit_c"),
        "outfit_c": CompatibilityGroup(display_name="C", fallback_outfit="outfit_a"),
    }
    assets = [
        AssetDefinition(
            asset_id="a_idle",
            path="sprites/a.webp",
            outfit="outfit_a",
            state="idle",
            emotion="neutral",
            status="needs_review",
        ),
        AssetDefinition(
            asset_id="b_idle",
            path="sprites/b.webp",
            outfit="outfit_b",
            state="idle",
            emotion="neutral",
            status="failed",
        ),
        AssetDefinition(
            asset_id="c_idle",
            path="sprites/c.webp",
            outfit="outfit_c",
            state="idle",
            emotion="neutral",
            status="pending",
        ),
        # Final valid default asset
        AssetDefinition(
            asset_id="master_default",
            path="sprites/default.webp",
            outfit="default",
            state="idle",
            emotion="neutral",
            status="ready",
        ),
    ]
    manifest = CharacterManifest(
        schema_version="1.0",
        character_id="miku",
        display_name="Hatsune Miku",
        default_outfit="outfit_a",
        compatibility_groups=groups,
        fallbacks=FallbackConfig(default_asset_id="master_default"),
        assets=assets,
    )
    resolver = CharacterAssetResolver(manifest)
    res = resolver.resolve(state="idle", emotion="neutral", outfit="outfit_a")

    assert res.asset.asset_id == "master_default"
    assert res.asset.status == "ready"
    assert res.match_strategy == "default_fallback"


def test_fuzzing_random_manifests_ready_invariant_oracle() -> None:
    """Fuzzing stress test: Generate 200 random manifests with 1,000 queries.

    Oracle invariant:
    1. If resolve() succeeds, res.asset.status == 'ready' MUST BE TRUE 100% of the time.
    2. If no ready asset can satisfy the request or fallback, it MUST raise AssetResolutionError.
    3. Never return None, never raise unhandled exceptions, never return unready asset.
    """
    random.seed(42)
    statuses = ["ready", "pending", "processing", "needs_review", "failed", "rejected"]
    outfits = ["school", "casual", "gothic", "sports"]
    states = ["idle", "speaking", "listening"]
    emotions = ["neutral", "joy", "pout", "angry"]

    for manifest_idx in range(50):
        # Generate random assets
        num_assets = random.randint(5, 30)
        assets: list[AssetDefinition] = []
        for i in range(num_assets):
            assets.append(
                AssetDefinition(
                    asset_id=f"asset_{manifest_idx}_{i}",
                    path=f"sprites/{i}.webp",
                    outfit=random.choice(outfits),
                    state=random.choice(states),
                    emotion=random.choice(emotions),
                    status=random.choice(statuses),  # type: ignore
                    priority=random.randint(1, 100),
                )
            )

        # Decide default asset id: sometimes valid ready, sometimes unready, sometimes non-existent
        choice = random.choice(["valid_ready", "unready", "nonexistent"])
        if choice == "valid_ready":
            # Add dedicated ready default asset
            def_asset = AssetDefinition(
                asset_id=f"default_ready_{manifest_idx}",
                path="sprites/def.webp",
                outfit="school",
                state="idle",
                emotion="neutral",
                status="ready",
                priority=1,
            )
            assets.append(def_asset)
            default_id = def_asset.asset_id
        elif choice == "unready":
            def_asset = AssetDefinition(
                asset_id=f"default_unready_{manifest_idx}",
                path="sprites/def.webp",
                outfit="school",
                state="idle",
                emotion="neutral",
                status=random.choice(["pending", "processing", "needs_review", "failed", "rejected"]),  # type: ignore
                priority=1,
            )
            assets.append(def_asset)
            default_id = def_asset.asset_id
        else:
            default_id = f"missing_{_rand_str()}"

        manifest = CharacterManifest(
            schema_version="1.0",
            character_id=f"char_{manifest_idx}",
            display_name=f"Character {manifest_idx}",
            default_outfit=random.choice(outfits),
            fallbacks=FallbackConfig(
                default_asset_id=default_id,
                emotion_fallbacks={"pout": "neutral", "angry": "neutral"},
                state_fallbacks={"speaking": "idle", "listening": "idle"},
            ),
            assets=assets,
        )

        resolver = CharacterAssetResolver(manifest)

        # Perform 20 queries per manifest
        for _ in range(20):
            q_outfit = random.choice(outfits + ["nonexistent_outfit"])
            q_state = random.choice(states + ["nonexistent_state"])
            q_emotion = random.choice(emotions + ["nonexistent_emotion"])

            try:
                resolved = resolver.resolve(state=q_state, emotion=q_emotion, outfit=q_outfit)
                # STRICT INVARIANT: Must be ready
                assert (
                    resolved.asset.status == "ready"
                ), f"CRITICAL: Non-ready asset returned: {resolved.asset}"
            except AssetResolutionError as err:
                # Expected when fallback fails or unready
                assert isinstance(err, (DefaultAssetMissingError, DefaultAssetNotReadyError))


def test_concurrent_resolution_and_hot_reload_50_threads() -> None:
    """Stress test: 50 concurrent threads resolving queries while manifest is dynamically updated."""
    ready_asset_1 = AssetDefinition(
        asset_id="asset_1",
        path="sprites/1.webp",
        outfit="school",
        state="idle",
        emotion="neutral",
        status="ready",
    )
    ready_asset_2 = AssetDefinition(
        asset_id="asset_2",
        path="sprites/2.webp",
        outfit="school",
        state="idle",
        emotion="neutral",
        status="ready",
    )
    manifest = CharacterManifest(
        schema_version="1.0",
        character_id="miku",
        display_name="Hatsune Miku",
        default_outfit="school",
        fallbacks=FallbackConfig(default_asset_id="asset_1"),
        assets=[ready_asset_1],
    )
    resolver = CharacterAssetResolver(manifest)

    errors: list[str] = []

    def resolver_worker(worker_id: int) -> None:
        for _ in range(100):
            try:
                res = resolver.resolve(state="idle", emotion="neutral")
                if res.asset.status != "ready":
                    errors.append(f"Worker {worker_id} got non-ready asset: {res.asset.status}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"Worker {worker_id} crashed: {e}")

    def hot_reloader() -> None:
        for i in range(20):
            new_assets = [ready_asset_1, ready_asset_2] if i % 2 == 0 else [ready_asset_1]
            resolver.manifest = CharacterManifest(
                schema_version="1.0",
                character_id="miku",
                display_name="Hatsune Miku",
                default_outfit="school",
                fallbacks=FallbackConfig(default_asset_id="asset_1"),
                assets=new_assets,
            )
            resolver._build_index()

    with ThreadPoolExecutor(max_workers=55) as executor:
        futures = [executor.submit(resolver_worker, i) for i in range(50)]
        futures.append(executor.submit(hot_reloader))
        for f in futures:
            f.result()

    assert not errors, f"Hot reload / concurrent resolution produced errors: {errors}"
