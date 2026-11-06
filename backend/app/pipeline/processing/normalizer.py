"""Standard 1024x1536 sprite canvas normalizer and dynamic alpha edge classifier.

Phase 0.5A Automatic Asset Processing Pipeline.
"""

from __future__ import annotations

from PIL import Image

from app.domain.character import AnchorType, SpriteAlignment


class SpriteNormalizer:
    """Normalizes candidate character sprites onto the standardized 1024x1536 canvas."""

    def __init__(self, canvas_width: int = 1024, canvas_height: int = 1536) -> None:
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height

    def classify_edge(self, img: Image.Image) -> AnchorType:
        """Classifies sprite into bottom_center, waist_level, or eye_level based on alpha edge."""
        if "A" not in img.getbands():
            return AnchorType.BOTTOM_CENTER

        alpha = img.getchannel("A")
        bbox = alpha.getbbox()
        if bbox is None:
            return AnchorType.BOTTOM_CENTER

        _x1, y1, _x2, y2 = bbox
        h_orig = img.height
        bbox_height = y2 - y1

        # Check if silhouette touches bottom boundary (within 5% of bottom canvas edge)
        if y2 >= int(0.95 * h_orig):
            # Check if close-up bust portrait (bbox height < 50% of image)
            if bbox_height < int(0.50 * h_orig):
                return AnchorType.EYE_LEVEL
            return AnchorType.WAIST_LEVEL

        return AnchorType.BOTTOM_CENTER

    def normalize(self, img: Image.Image) -> tuple[Image.Image, SpriteAlignment]:
        """Scales and positions character sprite onto standard 1024x1536 RGBA canvas."""
        anchor_type = self.classify_edge(img)
        canvas = Image.new("RGBA", (self.canvas_width, self.canvas_height), (0, 0, 0, 0))

        if "A" in img.getbands():
            bbox = img.getchannel("A").getbbox()
        else:
            bbox = (0, 0, img.width, img.height)

        if bbox is None:
            bbox = (0, 0, img.width, img.height)

        x1, y1, x2, y2 = bbox
        sil_w = max(1, x2 - x1)
        sil_h = max(1, y2 - y1)

        cropped_sil = img.crop((x1, y1, x2, y2))

        # Ground line pinning and scaling according to classification
        if anchor_type == AnchorType.BOTTOM_CENTER:
            # Scale to standard height (~1260px) and pin feet to ground line Y=1511
            max_target_h = 1260.0
            max_target_w = float(self.canvas_width) * 0.85

            scale = min(max_target_w / sil_w, max_target_h / sil_h)
            new_w = max(1, round(sil_w * scale))
            new_h = max(1, round(sil_h * scale))

            resized = cropped_sil.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Pin bottom to Y=1511 (leaving 25px margin to bottom of canvas)
            paste_y = max(0, 1511 - new_h)
            paste_x = max(0, (self.canvas_width - new_w) // 2)

            canvas.paste(resized, (paste_x, paste_y), mask=resized.getchannel("A"))
            anchor_y = 1.0
        elif anchor_type == AnchorType.WAIST_LEVEL:
            # Waist/torso portrait: align bottom directly to canvas floor Y=1536
            scale = min(
                float(self.canvas_width) * 0.90 / sil_w,
                float(self.canvas_height) * 0.80 / sil_h,
            )
            new_w = max(1, round(sil_w * scale))
            new_h = max(1, round(sil_h * scale))

            resized = cropped_sil.resize((new_w, new_h), Image.Resampling.LANCZOS)
            paste_y = max(0, self.canvas_height - new_h)
            paste_x = max(0, (self.canvas_width - new_w) // 2)

            canvas.paste(resized, (paste_x, paste_y), mask=resized.getchannel("A"))
            anchor_y = 0.5
        else:  # eye_level (bust-up)
            scale = min(
                float(self.canvas_width) * 0.80 / sil_w,
                float(self.canvas_height) * 0.65 / sil_h,
            )
            new_w = max(1, round(sil_w * scale))
            new_h = max(1, round(sil_h * scale))

            resized = cropped_sil.resize((new_w, new_h), Image.Resampling.LANCZOS)
            paste_y = max(0, int(self.canvas_height * 0.20))
            paste_x = max(0, (self.canvas_width - new_w) // 2)

            canvas.paste(resized, (paste_x, paste_y), mask=resized.getchannel("A"))
            anchor_y = 0.35

        final_alpha = canvas.getchannel("A")
        final_bbox = final_alpha.getbbox()
        bbox_tuple = (
            (final_bbox[0], final_bbox[1], final_bbox[2], final_bbox[3])
            if final_bbox
            else (0, 0, self.canvas_width, self.canvas_height)
        )

        alignment = SpriteAlignment(
            anchor_type=anchor_type,
            anchor_x=0.5,
            anchor_y=anchor_y,
            focal_x=0.5,
            focal_y=537.0 / self.canvas_height,
            display_scale=1.0,
            viewport_offset_x=0,
            viewport_offset_y=0,
            bounding_box=bbox_tuple,
        )

        return canvas, alignment
