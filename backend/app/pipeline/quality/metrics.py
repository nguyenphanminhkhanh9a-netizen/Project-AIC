"""Image quality metrics: Laplacian sharpness, dynamic range, alpha coverage, and resolution scoring.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from PIL import Image


def compute_laplacian_variance(img: Image.Image | np.ndarray[Any, Any]) -> float:
    """Computes variance of the 2D discrete Laplacian operator on luminance.

    Higher variance indicates sharper edges and anime lineart.
    """
    if isinstance(img, Image.Image):
        gray = np.array(img.convert("L"), dtype=np.float64)
    else:
        arr = np.asarray(img, dtype=np.float64)
        if arr.ndim == 3 and arr.shape[2] >= 3:
            # Vectorized luminance conversion
            gray = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
        elif arr.ndim == 2:
            gray = arr
        else:
            raise ValueError(f"Unsupported image array shape for Laplacian: {arr.shape}")

    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0

    # Vectorized 2D discrete 4-connected Laplacian
    lap = (
        gray[1:-1, 2:]
        + gray[1:-1, :-2]
        + gray[2:, 1:-1]
        + gray[:-2, 1:-1]
        - 4.0 * gray[1:-1, 1:-1]
    )

    return float(np.var(lap))


def compute_dynamic_range(img: Image.Image | np.ndarray[Any, Any]) -> float:
    """Computes contrast dynamic range as the span between 1st and 99th luminance percentiles."""
    if isinstance(img, Image.Image):
        gray = np.array(img.convert("L"), dtype=np.float64)
    else:
        arr = np.asarray(img, dtype=np.float64)
        if arr.ndim == 3 and arr.shape[2] >= 3:
            gray = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
        elif arr.ndim == 2:
            gray = arr
        else:
            raise ValueError(f"Unsupported image array shape for dynamic range: {arr.shape}")

    if gray.size == 0:
        return 0.0

    p1, p99 = np.percentile(gray, [1.0, 99.0])
    dr = float((p99 - p1) / 255.0)
    return max(0.0, min(1.0, dr))


def compute_alpha_coverage(img: Image.Image) -> float:
    """Computes character silhouette coverage as the ratio of non-transparent pixels to canvas area."""
    if "A" not in img.getbands():
        return 1.0

    alpha = img.getchannel("A")
    alpha_arr = np.array(alpha, dtype=np.uint8)
    total_pixels = alpha_arr.size
    if total_pixels == 0:
        return 0.0

    non_transparent = np.count_nonzero(alpha_arr > 10)
    return float(non_transparent / total_pixels)


def compute_resolution_score(
    width: int,
    height: int,
    target_w: int = 1024,
    target_h: int = 1536,
) -> float:
    """Computes normalized resolution score relative to standard canvas dimensions."""
    if width <= 0 or height <= 0:
        return 0.0

    target_area = float(target_w * target_h)
    actual_area = float(width * height)
    score = math.sqrt(actual_area / target_area)
    return max(0.0, min(1.0, score))
