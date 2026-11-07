"""Image operations for IS-Net Anime ONNX background removal.

Provides symmetrical letterbox padding, float32 ImageNet normalization,
slicing unpadding, float32 bilinear resizing, soft alpha ramp, and RGBA composition.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass(frozen=True)
class LetterboxMeta:
    """Stores letterbox transformation parameters for unpadding and geometry restoration."""

    orig_width: int
    orig_height: int
    new_width: int
    new_height: int
    pad_x: int
    pad_y: int
    canvas_size: int = 1024


def letterbox_preprocess(
    image: Image.Image,
    target_size: int = 1024,
) -> tuple[np.ndarray, LetterboxMeta]:
    """Pads image symmetrically onto a black (0, 0, 0) square canvas and normalizes.

    Args:
        image: Source PIL image (any format/mode, converted to RGB).
        target_size: Dimension of the square canvas (default 1024).

    Returns:
        tuple containing:
            - np.ndarray of shape [1, 3, target_size, target_size], float32 NCHW.
            - LetterboxMeta recording exact scaling and padding coordinates.
    """
    orig_w, orig_h = image.size
    scale = min(target_size / orig_w, target_size / orig_h)
    new_w = max(1, round(orig_w * scale))
    new_h = max(1, round(orig_h * scale))

    pad_x = (target_size - new_w) // 2
    pad_y = (target_size - new_h) // 2

    rgb_img = image.convert("RGB")
    resized_img = rgb_img.resize((new_w, new_h), Image.Resampling.BILINEAR)

    canvas = Image.new("RGB", (target_size, target_size), (0, 0, 0))
    canvas.paste(resized_img, (pad_x, pad_y))

    # Float32 ImageNet normalization
    arr = np.array(canvas, dtype=np.float32) / 255.0
    normalized = (arr - IMAGENET_MEAN) / IMAGENET_STD

    # Transpose HWC -> CHW and add batch dimension -> NCHW
    chw = np.transpose(normalized, (2, 0, 1))
    nchw = np.expand_dims(chw, axis=0).astype(np.float32)

    meta = LetterboxMeta(
        orig_width=orig_w,
        orig_height=orig_h,
        new_width=new_w,
        new_height=new_h,
        pad_x=pad_x,
        pad_y=pad_y,
        canvas_size=target_size,
    )
    return nchw, meta


def apply_soft_alpha_ramp(
    prob_arr: np.ndarray,
    t_low: float = 0.05,
    t_high: float = 0.95,
) -> np.ndarray:
    """Maps continuous probability in [0.0, 1.0] to smooth 8-bit alpha [0, 255].

    - p <= t_low -> 0 (clean transparent background, eliminates halos)
    - p >= t_high -> 255 (solid opaque character core)
    - t_low < p < t_high -> smooth linear interpolation preserving fine hair & accessories.

    Args:
        prob_arr: 2D float32 array of foreground probability values.
        t_low: Lower cutoff threshold (default 0.05).
        t_high: Upper cutoff threshold (default 0.95).

    Returns:
        2D np.ndarray of type uint8 in range [0, 255].
    """
    # Linear ramp formula
    scaled = (prob_arr - t_low) / (t_high - t_low) * 255.0
    alpha = np.clip(np.round(scaled), 0.0, 255.0).astype(np.uint8)
    return alpha


def postprocess_mask(
    raw_mask: np.ndarray,
    orig_img: Image.Image,
    meta: LetterboxMeta,
    t_low: float = 0.05,
    t_high: float = 0.95,
) -> tuple[bytes, dict[str, Any]]:
    """Unpads raw model output, resizes to original dimensions, applies soft alpha ramp, and merges.

    Args:
        raw_mask: Output tensor from IS-Net ONNX model (shape [1, 1, 1024, 1024] or [1024, 1024]).
        orig_img: Original input PIL image.
        meta: LetterboxMeta used during preprocessing.
        t_low: Lower soft alpha threshold.
        t_high: Upper soft alpha threshold.

    Returns:
        tuple containing:
            - Transparent 4-channel RGBA PNG bytes.
            - Diagnostic metadata dictionary.
    """
    mask = np.squeeze(raw_mask)
    if mask.ndim != 2:
        raise ValueError(f"Expected 2D squeezed mask tensor, got shape {mask.shape}")

    # Dynamic Sigmoid activation if logits were exported without final activation
    if float(np.min(mask)) < 0.0 or float(np.max(mask)) > 1.0:
        clipped = np.clip(mask, -20.0, 20.0)
        mask = 1.0 / (1.0 + np.exp(-clipped))

    # Slicing unpad (remove symmetrical letterbox black borders)
    cropped_prob = mask[meta.pad_y : meta.pad_y + meta.new_height, meta.pad_x : meta.pad_x + meta.new_width]

    # Float32 Bilinear resize to original image dimensions preserving continuous probability gradients
    prob_f32 = Image.fromarray(cropped_prob.astype(np.float32), mode="F")
    unpadded_f32 = prob_f32.resize(
        (meta.orig_width, meta.orig_height),
        resample=Image.Resampling.BILINEAR,
    )
    prob_arr = np.array(unpadded_f32, dtype=np.float32)

    # Soft alpha ramp
    alpha_arr = apply_soft_alpha_ramp(prob_arr, t_low=t_low, t_high=t_high)

    # Merge with original RGB image without altering color pixels
    rgb_img = orig_img.convert("RGB")
    alpha_img = Image.fromarray(alpha_arr, mode="L")
    rgba_img = rgb_img.copy()
    rgba_img.putalpha(alpha_img)

    out_buf = io.BytesIO()
    rgba_img.save(out_buf, format="PNG")
    png_bytes = out_buf.getvalue()

    alpha_chan = rgba_img.getchannel("A")
    min_a = int(alpha_arr.min())
    max_a = int(alpha_arr.max())
    total_pixels = alpha_arr.size
    transparent_ratio = float(np.count_nonzero(alpha_arr < 10) / total_pixels)
    opaque_ratio = float(np.count_nonzero(alpha_arr > 240) / total_pixels)
    soft_edge_pixels = int(np.count_nonzero((alpha_arr >= 10) & (alpha_arr <= 245)))

    metadata: dict[str, Any] = {
        "dimensions": [meta.orig_width, meta.orig_height],
        "alpha_extrema": [min_a, max_a],
        "transparent_ratio": transparent_ratio,
        "opaque_ratio": opaque_ratio,
        "soft_edge_pixels": soft_edge_pixels,
        "bbox": list(alpha_chan.getbbox() or [0, 0, 0, 0]),
    }
    return png_bytes, metadata
