"""Silhouette-relative facial crop heuristic for fine-grained emotion verification.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

from PIL import Image


class FaceExtractor:
    """Extracts a standardized 128x128 facial patch relative to character alpha silhouette."""

    def __init__(
        self,
        crop_ratio_top: float = 0.25,
        target_crop_size: tuple[int, int] = (128, 128),
    ) -> None:
        self.crop_ratio_top = crop_ratio_top
        self.target_crop_size = target_crop_size

    def extract_face(self, img: Image.Image) -> Image.Image:
        """Locates character silhouette and extracts face patch containing eyes and mouth."""
        width, height = img.size

        # Find non-zero alpha bounding box
        bbox = None
        if "A" in img.getbands():
            bbox = img.getchannel("A").getbbox()

        if bbox is None:
            # Fallback to entire image if no alpha channel or empty mask
            bbox = (0, 0, width, height)

        x_min, y_min, x_max, y_max = bbox
        sil_w = x_max - x_min
        sil_h = y_max - y_min

        if sil_w <= 0 or sil_h <= 0:
            # Safety fallback for degenerate bounding box
            crop_box = (0, 0, width, height)
        else:
            # Horizontal: centered 50% width of silhouette
            center_x = (x_min + x_max) / 2.0
            face_half_w = sil_w * 0.25

            left = max(0, round(center_x - face_half_w))
            right = min(width, round(center_x + face_half_w))

            # Vertical: skip top hair crown (8%), capture eyes/nose/mouth down to 32%
            top = max(0, round(y_min + sil_h * 0.08))
            bottom = min(height, round(y_min + sil_h * 0.32))

            if right <= left or bottom <= top:
                crop_box = (x_min, y_min, x_max, y_min + max(1, int(sil_h * self.crop_ratio_top)))
            else:
                crop_box = (left, top, right, bottom)

        face_crop = img.crop(crop_box)
        return face_crop.convert("L").resize(
            self.target_crop_size,
            Image.Resampling.LANCZOS,
        )
