"""Comprehensive unit, integration, and security tests for Character Pack and Asset Resolver.

Covers M0 Task 0.4 requirements:
1. Manifest parsing and Pydantic validation.
2. Physical verification of Nakano Miku Core Pack RGBA WebP assets.
3. Path traversal attack defenses.
4. Magic bytes verification for WebP & PNG.
5. In-memory dynamic fallback resolution hierarchy (zero hardcoded rules).
6. Decoupled missing asset notification with fault tolerance.
7. High-performance lookup benchmark.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PIL import Image

from app.domain.asset_resolver import (
    CharacterAssetResolver,
    MissingAssetRequest,
)
from app.domain.character import AnchorType
from app.storage.character_pack import CharacterPackLoader

CHARACTERS_DIR = (
    Path(__file__).parent.parent / "app" / "resources" / "characters"
)
MIKU_PACK_DIR = CHARACTERS_DIR / "miku_nakano"


# ==============================================================================
# 1. Manifest Loading and Schema Validation
# ==============================================================================


def test_load_manifest_miku_core() -> None:
    """Verifies that the Nakano Miku manifest loads and validates all 5 core assets."""
    manifest = CharacterPackLoader.load_manifest(MIKU_PACK_DIR, verify_files=True)

    assert manifest.schema_version == "1.0"
    assert manifest.character_id == "miku_nakano"
    assert manifest.display_name == "Nakano Miku"
    assert manifest.default_outfit == "school_uniform"
    assert manifest.fallbacks.default_asset_id == "miku_core_idle_neutral"

    assert len(manifest.assets) == 5
    asset_ids = {a.asset_id for a in manifest.assets}
    expected_ids = {
        "miku_core_idle_neutral",
        "miku_core_happy",
        "miku_core_pout",
        "miku_core_blush_shy",
        "miku_core_comforting",
    }
    assert asset_ids == expected_ids

    for asset in manifest.assets:
        assert asset.is_core is True
        assert asset.status == "ready"
        assert asset.format == "webp"
        assert asset.resolution.width == 1024
        assert asset.resolution.height == 1536
        assert asset.anchor.anchor_type == AnchorType.BOTTOM_CENTER
        assert asset.anchor.anchor_y == 1.0
        assert asset.anchor.focal_y == 0.35


def test_discover_character_packs() -> None:
    """Verifies discovery of character packs in characters directory."""
    packs = CharacterPackLoader.discover_character_packs(CHARACTERS_DIR)
    assert "miku_nakano" in packs
    assert packs["miku_nakano"] == MIKU_PACK_DIR


# ==============================================================================
# 2. Physical File Integrity & Alpha Transparency Verification
# ==============================================================================


def test_physical_webp_integrity_and_alpha() -> None:
    """Confirms all 5 core assets exist physically and possess true alpha transparency."""
    core_assets_dir = MIKU_PACK_DIR / "assets" / "core"
    expected_files = [
        "idle_neutral.webp",
        "happy.webp",
        "pout.webp",
        "blush_shy.webp",
        "comforting.webp",
    ]

    for filename in expected_files:
        file_path = core_assets_dir / filename
        assert file_path.is_file(), f"Asset {filename} is missing on disk"
        assert file_path.stat().st_size > 0, f"Asset {filename} is empty"

        # Check magic bytes
        assert CharacterPackLoader.validate_image_file(file_path) is True

        # Check image structure and alpha transparency
        with Image.open(file_path) as img:
            assert img.format == "WEBP"
            assert img.mode == "RGBA", f"{filename} must be RGBA for transparent overlay"
            assert img.size == (1024, 1536)

            # Check alpha channel distribution
            alpha = img.getchannel("A")
            extrema = alpha.getextrema()
            assert extrema is not None
            assert isinstance(extrema, tuple)
            min_val = extrema[0]
            max_val = extrema[1]
            assert isinstance(min_val, (int, float)) and min_val == 0
            assert isinstance(max_val, (int, float)) and max_val > 0


# ==============================================================================
# 3. Security & Validation Defenses
# ==============================================================================


def test_path_traversal_guard() -> None:
    """Verifies strict blocking of directory traversal attempts."""
    with pytest.raises(ValueError, match="Path traversal detected"):
        CharacterPackLoader.safe_resolve_path(MIKU_PACK_DIR, "../../secret.txt")

    with pytest.raises(ValueError, match="Path traversal detected"):
        CharacterPackLoader.safe_resolve_path(MIKU_PACK_DIR, "../miku_nakano/../../outside.webp")

    # Safe subpath inside pack dir must succeed
    safe_path = CharacterPackLoader.safe_resolve_path(
        MIKU_PACK_DIR, "assets/core/idle_neutral.webp"
    )
    assert safe_path.is_file()


def test_magic_bytes_detection(tmp_path: Path) -> None:
    """Verifies magic bytes validator rejects non-image, corrupt, or truncated files."""
    # Text file masquerading as webp
    fake_webp = tmp_path / "fake.webp"
    fake_webp.write_text("NOT A REAL WEBP HEADER", encoding="utf-8")
    assert CharacterPackLoader.validate_image_file(fake_webp) is False

    # Empty file
    empty_webp = tmp_path / "empty.webp"
    empty_webp.write_bytes(b"")
    assert CharacterPackLoader.validate_image_file(empty_webp) is False

    # Short file < 12 bytes
    short_file = tmp_path / "short.webp"
    short_file.write_bytes(b"RIFFshort")
    assert CharacterPackLoader.validate_image_file(short_file) is False

    # Non-existent file
    assert CharacterPackLoader.validate_image_file(tmp_path / "non_existent.webp") is False


# ==============================================================================
# 4. In-Memory Dynamic Asset Resolver Hierarchy
# ==============================================================================


@pytest.fixture
def miku_resolver() -> CharacterAssetResolver:
    manifest = CharacterPackLoader.load_manifest(MIKU_PACK_DIR, verify_files=True)
    return CharacterAssetResolver(manifest)


def test_resolver_exact_match(miku_resolver: CharacterAssetResolver) -> None:
    """Test Level 1: Exact match on (outfit, state, emotion)."""
    # idle / neutral
    res1 = miku_resolver.resolve(state="idle", emotion="neutral")
    assert res1.match_strategy == "exact"
    assert res1.is_fallback is False
    assert res1.asset.asset_id == "miku_core_idle_neutral"

    # speaking / happy
    res2 = miku_resolver.resolve(state="speaking", emotion="happy")
    assert res2.match_strategy == "exact"
    assert res2.is_fallback is False
    assert res2.asset.asset_id == "miku_core_happy"

    # idle / pout
    res3 = miku_resolver.resolve(state="idle", emotion="pout")
    assert res3.match_strategy == "exact"
    assert res3.is_fallback is False
    assert res3.asset.asset_id == "miku_core_pout"


def test_resolver_emotion_fallback(miku_resolver: CharacterAssetResolver) -> None:
    """Test Level 2: Emotion fallback defined in manifest ('angry' -> 'pout')."""
    # 'angry' is not in core pack, but manifest maps angry -> pout
    res = miku_resolver.resolve(state="idle", emotion="angry")
    assert res.match_strategy == "emotion_fallback"
    assert res.is_fallback is True
    assert res.asset.asset_id == "miku_core_pout"
    assert res.requested_emotion == "angry"


def test_resolver_state_fallback(miku_resolver: CharacterAssetResolver) -> None:
    """Test Level 3: State fallback defined in manifest ('listening' -> 'idle')."""
    # (listening, pout) -> state fallback to (idle, pout)
    res = miku_resolver.resolve(state="listening", emotion="pout")
    assert res.match_strategy == "state_fallback"
    assert res.is_fallback is True
    assert res.asset.asset_id == "miku_core_pout"


def test_resolver_outfit_fallback(miku_resolver: CharacterAssetResolver) -> None:
    """Test Level 4: Outfit fallback chain ('casual' -> 'school_uniform')."""
    # 'casual' outfit currently has no assets, should fallback to school_uniform
    res = miku_resolver.resolve(state="idle", emotion="neutral", outfit="casual")
    assert res.match_strategy == "outfit_fallback"
    assert res.is_fallback is True
    assert res.asset.asset_id == "miku_core_idle_neutral"
    assert res.requested_outfit == "casual"


def test_resolver_default_fallback(miku_resolver: CharacterAssetResolver) -> None:
    """Test Level 5: Default asset fallback when completely unmatched."""
    res = miku_resolver.resolve(state="dancing", emotion="ecstatic")
    assert res.match_strategy == "default_fallback"
    assert res.is_fallback is True
    assert res.asset.asset_id == "miku_core_idle_neutral"


# ==============================================================================
# 5. Decoupled Missing Asset Callback & Fault Tolerance
# ==============================================================================


def test_resolver_missing_asset_callback() -> None:
    """Verifies callback is notified on fallbacks and errors do not block resolver."""
    captured: list[MissingAssetRequest] = []

    def on_missing(req: MissingAssetRequest) -> None:
        captured.append(req)

    manifest = CharacterPackLoader.load_manifest(MIKU_PACK_DIR, verify_files=True)
    resolver = CharacterAssetResolver(manifest, on_missing_asset=on_missing)

    # Exact match: NO missing asset notification
    resolver.resolve(state="idle", emotion="neutral")
    assert len(captured) == 0

    # Fallback match: Missing asset callback triggered
    resolver.resolve(state="idle", emotion="angry")
    assert len(captured) == 1
    assert captured[0].character_id == "miku_nakano"
    assert captured[0].emotion == "angry"
    assert captured[0].state == "idle"

    # Callback throwing exception should NOT cause resolve() to fail
    def failing_callback(req: MissingAssetRequest) -> None:
        raise RuntimeError("Telemetry / background queue service unavailable!")

    resolver_failing = CharacterAssetResolver(manifest, on_missing_asset=failing_callback)
    res = resolver_failing.resolve(state="idle", emotion="angry")
    assert res.match_strategy == "emotion_fallback"
    assert res.asset.asset_id == "miku_core_pout"


# ==============================================================================
# 6. Performance Benchmark Test
# ==============================================================================


def test_resolver_performance_benchmark(miku_resolver: CharacterAssetResolver) -> None:
    """Verifies that in-memory lookup is sub-millisecond (typically < 0.05ms)."""
    iterations = 2000
    start = time.perf_counter()

    for _ in range(iterations):
        miku_resolver.resolve("idle", "neutral")
        miku_resolver.resolve("speaking", "happy")
        miku_resolver.resolve("idle", "angry")  # emotion fallback
        miku_resolver.resolve("dancing", "ecstatic")  # default fallback

    elapsed = time.perf_counter() - start
    total_lookups = iterations * 4
    avg_micros = (elapsed / total_lookups) * 1_000_000

    # Log performance
    print(f"\n[BENCHMARK] {total_lookups} lookups in {elapsed*1000:.2f} ms ({avg_micros:.2f} µs/op)")

    # Assert avg lookup is strictly less than 1 ms (1000 µs)
    assert avg_micros < 1000.0, f"Average lookup time {avg_micros:.2f} µs exceeded 1000 µs limit"
