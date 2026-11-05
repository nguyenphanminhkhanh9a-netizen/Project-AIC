"""Suite 10: Atomic manifest updates, fsync persistence, and rollback tests.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.domain.character import (
    AnchorType,
    AssetDefinition,
    CharacterManifest,
    FallbackConfig,
    Resolution,
    SpriteAlignment,
)
from app.pipeline.storage.manifest_manager import (
    ManifestCommitError,
    ManifestManager,
)


@pytest.fixture
def test_character_pack(tmp_path: Path) -> tuple[Path, ManifestManager]:
    """Sets up an isolated character pack directory with valid manifest.json."""
    chars_dir = tmp_path / "characters"
    pack_dir = chars_dir / "miku_nakano"
    pack_dir.mkdir(parents=True)
    (pack_dir / "assets" / "core").mkdir(parents=True)
    (pack_dir / "assets" / "dynamic").mkdir(parents=True)

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
                format="webp",
                state="idle",
                emotion="neutral",
                outfit="school_uniform",
                resolution=Resolution(width=1024, height=1536),
                anchor=SpriteAlignment(anchor_type=AnchorType.BOTTOM_CENTER),
                is_core=True,
                status="ready",
            )
        ],
    )
    manifest_path = pack_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    mgr = ManifestManager(characters_dir=chars_dir)
    return pack_dir, mgr


def test_atomic_manifest_commit_success(test_character_pack: tuple[Path, ManifestManager]) -> None:
    """Verifies successful asset file commit and atomic manifest update."""
    pack_dir, mgr = test_character_pack

    new_asset = AssetDefinition(
        asset_id="miku_dynamic_smile",
        path="assets/dynamic/smile.webp",
        format="webp",
        state="idle",
        emotion="smile",
        outfit="school_uniform",
        resolution=Resolution(width=1024, height=1536),
        anchor=SpriteAlignment(anchor_type=AnchorType.BOTTOM_CENTER),
        is_core=False,
        status="ready",
    )
    fake_bytes = b"RIFF....WEBPVP8X" + b"\x00" * 64

    saved_path, updated_manifest = mgr.commit_asset(
        character_id="miku_nakano",
        asset=new_asset,
        image_bytes=fake_bytes,
        format="webp",
    )

    assert saved_path.is_file()
    assert saved_path.read_bytes() == fake_bytes
    assert len(updated_manifest.assets) == 2
    assert any(a.asset_id == "miku_dynamic_smile" for a in updated_manifest.assets)

    # Verify no lingering .tmp files
    tmp_files = list(pack_dir.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_atomic_manifest_commit_permission_rollback(
    test_character_pack: tuple[Path, ManifestManager],
) -> None:
    """Verifies that an error during atomic os.replace rolls back and preserves manifest."""
    pack_dir, mgr = test_character_pack
    manifest_path = pack_dir / "manifest.json"
    original_content = manifest_path.read_text(encoding="utf-8")

    new_asset = AssetDefinition(
        asset_id="miku_fail_asset",
        path="assets/dynamic/fail.webp",
        format="webp",
        state="idle",
        emotion="fail",
        outfit="school_uniform",
        resolution=Resolution(width=1024, height=1536),
        anchor=SpriteAlignment(anchor_type=AnchorType.BOTTOM_CENTER),
        is_core=False,
        status="ready",
    )

    # Injected PermissionError during os.replace
    with (
        patch("os.replace", side_effect=PermissionError("Access Denied")),
        pytest.raises(ManifestCommitError, match="Atomic manifest write failed"),
    ):
        mgr.commit_asset(
            character_id="miku_nakano",
            asset=new_asset,
            image_bytes=b"dummy",
            format="webp",
        )

    # Original manifest must remain completely identical
    assert manifest_path.read_text(encoding="utf-8") == original_content
    # Temporary files must be cleaned up
    assert len(list(pack_dir.glob("*.tmp"))) == 0


def test_orphan_asset_cleanup_on_manifest_error(
    test_character_pack: tuple[Path, ManifestManager],
) -> None:
    """Verifies that if manifest update fails, newly created asset image is unlinked."""
    pack_dir, mgr = test_character_pack
    asset_file = pack_dir / "assets" / "dynamic" / "orphan_test.webp"

    new_asset = AssetDefinition(
        asset_id="miku_orphan",
        path="assets/dynamic/orphan_test.webp",
        format="webp",
        state="idle",
        emotion="orphan",
        outfit="school_uniform",
        resolution=Resolution(width=1024, height=1536),
        anchor=SpriteAlignment(anchor_type=AnchorType.BOTTOM_CENTER),
        is_core=False,
        status="ready",
    )

    with (
        patch("app.pipeline.storage.manifest_manager.save_manifest_atomic", side_effect=RuntimeError("Disk crash")),
        pytest.raises(ManifestCommitError, match="Failed to commit updated manifest"),
    ):
        mgr.commit_asset(
            character_id="miku_nakano",
            asset=new_asset,
            image_bytes=b"ORPHAN_DATA",
            format="webp",
        )

    # Asset file must be cleaned up; no orphan on disk
    assert not asset_file.is_file()

