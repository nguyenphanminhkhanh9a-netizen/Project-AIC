"""Security verifier for IS-Net Anime ONNX model weights.

Validates file existence, exact binary size, and streaming SHA-256 cryptographic checksum
to guard against model supply-chain tampering and truncated downloads.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Official SkyTNT isnetis.onnx weights invariant
ISNET_MODEL_EXPECTED_SIZE: int = 176_069_933
ISNET_MODEL_EXPECTED_SHA256: str = (
    "f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99"
)
DEFAULT_CHUNK_SIZE_BYTES: int = 1024 * 1024  # 1 MB streaming chunks


class ModelVerificationError(Exception):
    """Base exception for model integrity and verification failures."""



class ModelNotFoundError(FileNotFoundError, ModelVerificationError):
    """Raised when model weights file cannot be found at specified path."""



class ModelIntegrityError(ValueError, ModelVerificationError):
    """Raised when model file is corrupted, truncated, or fails SHA-256 verification."""



def verify_model_file(
    model_path: Path,
    expected_sha256: str = ISNET_MODEL_EXPECTED_SHA256,
    expected_size: int | None = ISNET_MODEL_EXPECTED_SIZE,
    chunk_size_bytes: int = DEFAULT_CHUNK_SIZE_BYTES,
) -> str:
    """Verifies that the ONNX model file exists and matches expected size and SHA-256.

    Args:
        model_path: Absolute or relative path to the .onnx file.
        expected_sha256: Expected hexadecimal SHA-256 hash.
        expected_size: Expected exact size in bytes (pre-check), or None to skip size check.
        chunk_size_bytes: Buffer size for streaming SHA-256 hashing.

    Returns:
        The computed lowercase SHA-256 hexadecimal digest string.

    Raises:
        ModelNotFoundError: If the file does not exist.
        ModelIntegrityError: If size pre-check fails or SHA-256 checksum mismatches.
    """
    path = Path(model_path).resolve()

    if not path.is_file():
        raise ModelNotFoundError(
            f"Model weights file not found at: {path}. Please download isnetis.onnx as instructed."
        )

    actual_size = path.stat().st_size
    if expected_size is not None and actual_size != expected_size:
        raise ModelIntegrityError(
            f"Model file size mismatch: expected {expected_size} bytes, got {actual_size} bytes "
            f"(checksum mismatch for {path.name})"
        )

    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size_bytes):
                hasher.update(chunk)
    except OSError as err:
        raise ModelIntegrityError(f"Failed to read model file {path}: {err}") from err

    actual_sha256 = hasher.hexdigest().lower()
    expected_clean = expected_sha256.strip().lower()

    if actual_sha256 != expected_clean:
        logger.critical(
            "IS-Net model SHA-256 checksum mismatch! Expected %s, got %s for %s",
            expected_clean,
            actual_sha256,
            path,
        )
        raise ModelIntegrityError(
            f"Model SHA-256 checksum mismatch: expected {expected_clean}, got {actual_sha256} "
            f"for {path.name}"
        )

    logger.info("Successfully verified model integrity for %s (SHA-256: %s)", path.name, actual_sha256)
    return actual_sha256
