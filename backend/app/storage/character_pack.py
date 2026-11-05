"""Character pack loader, manifest parser, and security validation.

Section 7.4 of AIC_ARCHITECTURE_v0.5.md and M0 Task 0.4.
Enforces strict path traversal defenses and magic bytes validation for WebP and PNG assets.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.domain.character import CharacterManifest

logger = logging.getLogger(__name__)

# Magic byte signatures
WEBP_RIFF_HEADER = b"RIFF"
WEBP_FORMAT_HEADER = b"WEBP"
PNG_MAGIC_BYTES = b"\x89PNG\r\n\x1a\n"


class CharacterPackLoader:
    """Safely loads and validates character packs from the local filesystem."""

    @staticmethod
    def safe_resolve_path(pack_dir: Path, relative_path: str) -> Path:
        """Resolves a relative path within pack_dir, blocking path traversal attacks.

        Raises:
            ValueError: If relative_path attempts to escape pack_dir.
        """
        pack_dir_resolved = pack_dir.resolve()
        target_path = (pack_dir / relative_path).resolve()

        if not target_path.is_relative_to(pack_dir_resolved):
            raise ValueError(
                f"Path traversal detected: '{relative_path}' escapes character pack root '{pack_dir}'"
            )

        return target_path

    @staticmethod
    def validate_image_file(path: Path) -> bool:
        """Validates that a file exists, is non-empty, and possesses valid WebP/PNG magic bytes.

        Returns:
            True if the file is a valid WebP or PNG image file, False otherwise.
        """
        if not path.is_file():
            return False

        try:
            stat = path.stat()
            if stat.st_size < 12:
                # Minimum size to verify WebP (12 bytes) or PNG (8 bytes)
                return False

            with open(path, "rb") as f:
                header = f.read(12)

            # WebP signature: RIFF....WEBP
            if header.startswith(WEBP_RIFF_HEADER) and header[8:12] == WEBP_FORMAT_HEADER:
                return True

            # PNG signature: 8 bytes
            return bool(header.startswith(PNG_MAGIC_BYTES))
        except OSError as e:
            logger.warning("Error reading file '%s' for validation: %s", path, e)
            return False

    @classmethod
    def load_manifest(cls, pack_dir: Path, verify_files: bool = True) -> CharacterManifest:
        """Loads and parses manifest.json from pack_dir with optional asset integrity check.

        Args:
            pack_dir: Directory containing manifest.json and assets/.
            verify_files: If True, asserts every asset.path safely exists and has valid magic bytes.

        Raises:
            FileNotFoundError: If manifest.json or an asset file does not exist.
            ValueError: If manifest schema is invalid, path traversal occurs, or image is corrupt.
        """
        manifest_path = pack_dir / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"manifest.json not found in character pack directory: '{pack_dir}'")

        try:
            raw_content = manifest_path.read_text(encoding="utf-8")
        except OSError as e:
            raise OSError(f"Failed to read manifest.json at '{manifest_path}': {e}") from e

        manifest = CharacterManifest.model_validate_json(raw_content)

        if verify_files:
            for asset in manifest.assets:
                resolved_path = cls.safe_resolve_path(pack_dir, asset.path)
                if not resolved_path.is_file():
                    raise FileNotFoundError(
                        f"Asset file '{asset.path}' declared for '{asset.asset_id}' does not exist at '{resolved_path}'"
                    )
                if not cls.validate_image_file(resolved_path):
                    raise ValueError(
                        f"Asset file '{asset.path}' declared for '{asset.asset_id}' has invalid magic bytes or is corrupt"
                    )

        return manifest

    @classmethod
    def discover_character_packs(cls, characters_dir: Path) -> dict[str, Path]:
        """Discovers valid character pack directories inside characters_dir.

        Returns:
            Dictionary mapping character_id -> pack directory Path.
        """
        discovered: dict[str, Path] = {}
        if not characters_dir.is_dir():
            return discovered

        for child in characters_dir.iterdir():
            if child.is_dir() and (child / "manifest.json").is_file():
                try:
                    manifest = cls.load_manifest(child, verify_files=False)
                    discovered[manifest.character_id] = child
                except (OSError, ValueError, KeyError) as e:
                    logger.warning("Skipping invalid character pack at '%s': %s", child, e)

        return discovered
