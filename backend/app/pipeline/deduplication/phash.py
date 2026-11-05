"""Perceptual hashing (64-bit DCT pHash and gradient dHash) using NumPy and Pillow.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image


def compute_dhash(img: Image.Image, size: int = 8) -> int:
    """Computes a 64-bit difference hash (dHash) based on horizontal pixel intensity gradients."""
    # Resize to (size + 1, size) grayscale
    resized = img.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    arr = np.array(resized, dtype=np.int16)

    # Compare adjacent horizontal pixels: (P_{x+1} > P_x)
    diff = arr[:, 1:] > arr[:, :-1]

    hash_val = 0
    for bit in diff.flatten():
        hash_val = (hash_val << 1) | int(bit)

    return hash_val


def _get_dct_matrix(n: int) -> np.ndarray:
    """Computes the NxN Discrete Cosine Transform (DCT-II) orthogonal matrix."""
    matrix = np.zeros((n, n), dtype=np.float64)
    factor0 = math.sqrt(1.0 / n)
    factor_k = math.sqrt(2.0 / n)

    for k in range(n):
        for i in range(n):
            if k == 0:
                matrix[k, i] = factor0
            else:
                matrix[k, i] = factor_k * math.cos((math.pi * (2 * i + 1) * k) / (2.0 * n))

    return matrix


_DCT_32 = _get_dct_matrix(32)


def compute_phash(
    img: Image.Image,
    hash_size: int = 8,
    highfreq_factor: int = 4,
) -> int:
    """Computes a 64-bit Discrete Cosine Transform perceptual hash (pHash).

    Resizes image to 32x32, performs 2D DCT, extracts top-left 8x8 low-frequency
    coefficients, and thresholds against the median.
    """
    dim = hash_size * highfreq_factor  # 32x32
    resized = img.convert("L").resize((dim, dim), Image.Resampling.LANCZOS)
    pixels = np.array(resized, dtype=np.float64)

    # 2D DCT: D @ pixels @ D.T
    dct_matrix = _DCT_32 if dim == 32 else _get_dct_matrix(dim)
    dct_2d = dct_matrix @ pixels @ dct_matrix.T

    # Extract top-left 8x8 coefficients
    dct_low_freq = dct_2d[:hash_size, :hash_size]

    # Exclude DC component (0, 0) when computing median threshold
    med = float(np.median(dct_low_freq.flat[1:]))

    diff = dct_low_freq > med

    hash_val = 0
    for bit in diff.flatten():
        hash_val = (hash_val << 1) | int(bit)

    return hash_val


def hamming_distance(hash1: int, hash2: int) -> int:
    """Calculates the number of differing bits between two 64-bit hashes."""
    return (hash1 ^ hash2).bit_count()
