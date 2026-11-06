"""Atomic manifest persistence and character asset storage manager.

Phase 0.5A Automatic Asset Processing Pipeline.
Ensures zero manifest corruption via .tmp -> flush -> fsync -> os.replace atomic swap.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from app.domain.character import AssetDefinition, CharacterManifest
from app.pipeline.config import PipelineConfig, pipeline_config


class ManifestCommitError(Exception):
    """Raised when asset or manifest persistence fails."""


def save_manifest_atomic(manifest: CharacterManifest, manifest_path: Path) -> None:
    """Commits manifest updates atomically using temporary file + fsync + os.replace."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = manifest_path.with_name(f"manifest.json.{uuid.uuid4().hex}.tmp")
    try:
        content = manifest.model_dump_json(indent=2)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, manifest_path)
    except Exception as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise ManifestCommitError(f"Atomic manifest write failed: {e}") from e


class ManifestManager:
    """Manages character pack asset files and atomic manifest updates."""

    def __init__(
        self,
        characters_dir: Path | None = None,
        config: PipelineConfig | None = None,
    ) -> None:
        cfg = config if config is not None else pipeline_config
        self.characters_dir = characters_dir if characters_dir is not None else cfg.characters_dir

    def get_manifest_path(self, character_id: str) -> Path:
        """Returns the absolute or relative path to a character's manifest.json."""
        return self.characters_dir / character_id / "manifest.json"

    def load_manifest(self, character_id: str) -> CharacterManifest:
        """Reads and validates the current character manifest."""
        path = self.get_manifest_path(character_id)
        if not path.is_file():
            raise FileNotFoundError(f"Manifest not found for character '{character_id}' at {path}")
        return CharacterManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def commit_asset(
        self,
        character_id: str,
        asset: AssetDefinition,
        image_bytes: bytes,
        format: str = "webp",
    ) -> tuple[Path, CharacterManifest]:
        """Saves image asset to disk and atomically updates the character's manifest.json."""
        pack_dir = self.characters_dir / character_id
        asset_dest = pack_dir / asset.path
        asset_dest.parent.mkdir(parents=True, exist_ok=True)

        manifest_path = self.get_manifest_path(character_id)
        manifest = self.load_manifest(character_id)

        # 1. Write asset file to disk with integrity check
        created_asset_file = False
        try:
            asset_dest.write_bytes(image_bytes)
            created_asset_file = True
            if asset_dest.stat().st_size != len(image_bytes):
                raise OSError("Written asset file size does not match expected byte count.")
        except Exception as e:
            if created_asset_file and asset_dest.is_file():
                try:
                    asset_dest.unlink()
                except OSError:
                    pass
            raise ManifestCommitError(f"Failed to write asset bytes to {asset_dest}: {e}") from e

        # 2. Update manifest asset list (replace if existing asset_id, else append)
        updated_assets = [a for a in manifest.assets if a.asset_id != asset.asset_id]
        updated_assets.append(asset)
        new_manifest = manifest.model_copy(update={"assets": updated_assets})

        # 3. Commit manifest atomically
        try:
            save_manifest_atomic(new_manifest, manifest_path)
        except Exception as e:
            # Clean up orphan asset file if manifest commit fails
            if created_asset_file and asset_dest.is_file():
                try:
                    asset_dest.unlink()
                except OSError:
                    pass
            raise ManifestCommitError(f"Failed to commit updated manifest: {e}") from e

        return asset_dest, new_manifest
