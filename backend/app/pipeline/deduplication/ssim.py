"""Pure NumPy vectorized Structural Similarity Index (SSIM) on image patches.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image


def compute_ssim(
    img1: Image.Image | np.ndarray[Any, Any],
    img2: Image.Image | np.ndarray[Any, Any],
) -> float:
    """Computes the Structural Similarity Index (SSIM) between two grayscale images or patches.

    Operates on standardized 128x128 patches in pure NumPy.
    """
    if isinstance(img1, Image.Image):
        arr1 = np.array(img1.convert("L").resize((128, 128)), dtype=np.float64)
    else:
        arr1 = np.asarray(img1, dtype=np.float64)

    if isinstance(img2, Image.Image):
        arr2 = np.array(img2.convert("L").resize((128, 128)), dtype=np.float64)
    else:
        arr2 = np.asarray(img2, dtype=np.float64)

    if arr1.shape != arr2.shape:
        raise ValueError(f"Array shapes must match for SSIM: {arr1.shape} vs {arr2.shape}")

    # Dynamic range constants for uint8 scale [0, 255]
    c1 = (0.01 * 255.0) ** 2  # 6.5025
    c2 = (0.03 * 255.0) ** 2  # 58.5225

    mu1 = float(np.mean(arr1))
    mu2 = float(np.mean(arr2))

    var1 = float(np.var(arr1))
    var2 = float(np.var(arr2))

    cov = float(np.mean((arr1 - mu1) * (arr2 - mu2)))

    numerator = (2.0 * mu1 * mu2 + c1) * (2.0 * cov + c2)
    denominator = (mu1**2 + mu2**2 + c1) * (var1 + var2 + c2)

    if denominator == 0.0:
        return 1.0

    ssim_val = float(numerator / denominator)
    return max(-1.0, min(1.0, ssim_val))
