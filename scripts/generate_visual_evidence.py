"""Generates comprehensive visual evidence for Tier 3 IS-Net Anime background removal.

Produces:
1. Exactly 30 standardized visual evidence files in data/tier3_output/visual_evidence/:
   - 5 grayscale masks (sample_01_mask.png to sample_05_mask.png)
   - 5 checkerboard composites (sample_01_checkerboard.png to sample_05_checkerboard.png)
   - 5 side-by-side comparison panels (sample_01_comparison.png to sample_05_comparison.png)
   - 15 zoomed crops on checkerboard (sample_XX_zoom_YY.png) covering hair, accessories, edges, artifacts
2. Per-sample detailed subdirectories (sample_01_simple_bg/ to sample_05_translucent_costume/)
3. Master comparative summary grid (master_summary_grid.png)
4. Structured manifest.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

# Root directory resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIER3_DIR = PROJECT_ROOT / "data" / "tier3_output"
OUTPUT_DIR = TIER3_DIR / "visual_evidence"

# Sample mapping: ID -> (sample_num_str, full_key, description)
SAMPLE_MAP = [
    ("sample_01", "sample_01_simple_bg", "Simple Solid Background (Schoolgirl)"),
    ("sample_02", "sample_02_complex_bg", "Complex Scenic Background (Akihabara Street)"),
    ("sample_03", "sample_03_long_hair", "Long Flowing Twintails & Ahoge (Miku Idol)"),
    ("sample_04", "sample_04_small_accessories", "Small Accessories (Headphones, Ribbons, Charms)"),
    ("sample_05", "sample_05_translucent_costume", "Translucent Fabric & Wings (Fairy Sorceress)"),
]

# Standard crop configurations [ymin, xmin, ymax, xmax]
SAMPLE_CROPS = {
    "sample_01_simple_bg": [
        ("zoom_01", "05_crop_hair_bangs", "Hair Strands & Bangs", [150, 140, 400, 390]),
        ("zoom_02", "06_crop_collar_bow", "Sailor Collar & Bow", [300, 180, 550, 430]),
        ("zoom_03", "07_crop_skirt_pleats", "Skirt Pleats & Hem", [650, 50, 900, 300]),
    ],
    "sample_02_complex_bg": [
        ("zoom_01", "05_crop_hair_face", "Hair Bangs & Face Contour", [220, 320, 470, 570]),
        ("zoom_02", "06_crop_clothing_jacket", "Jacket & Street Boundary", [550, 200, 800, 450]),
        ("zoom_03", "07_crop_topright_artifact", "Top-Right Neon Leak (Artifact)", [0, 600, 250, 848]),
    ],
    "sample_03_long_hair": [
        ("zoom_01", "05_crop_hair_ahoge", "Crown Ahoge & Bangs", [100, 320, 350, 570]),
        ("zoom_02", "06_crop_left_twintail", "Flowing Left Twintail Strands", [400, 10, 650, 260]),
        ("zoom_03", "07_crop_headset_accessory", "Headset & Hair Tie", [230, 480, 480, 730]),
    ],
    "sample_04_small_accessories": [
        ("zoom_01", "05_crop_headphones_hair", "Headphone Cushion & Hair", [200, 180, 450, 430]),
        ("zoom_02", "06_crop_hair_accessories", "Hair Ribbons & Charms", [250, 520, 500, 770]),
        ("zoom_03", "07_crop_bottom_fade", "Bottom Semi-Transparent Fade", [980, 250, 1230, 500]),
    ],
    "sample_05_translucent_costume": [
        ("zoom_01", "05_crop_hair_tiara", "Sorceress Tiara & Hair", [120, 360, 370, 610]),
        ("zoom_02", "06_crop_fairy_wing", "Translucent Fairy Wing", [300, 580, 550, 830]),
        ("zoom_03", "07_crop_sheer_fabric", "Sheer Chiffon Gown Fabric", [850, 400, 1100, 650]),
    ],
}

CROP_BORDER_COLORS = [
    (230, 50, 50),   # Red
    (50, 180, 50),   # Green
    (50, 100, 230),  # Blue
]


def make_checkerboard(width: int, height: int, square_size: int = 32) -> Image.Image:
    """Creates a clean two-tone checkerboard pattern in RGBA mode."""
    x = np.arange(width) // square_size
    y = np.arange(height) // square_size
    grid = (y[:, None] + x[None, :]) % 2
    arr = np.where(grid[:, :, None] == 0, [255, 255, 255, 255], [204, 204, 204, 255]).astype(np.uint8)
    return Image.fromarray(arr, mode="RGBA")


def composite_on_background(rgba_img: Image.Image, bg_color: tuple[int, int, int]) -> Image.Image:
    """Composites an RGBA image onto a solid RGB background."""
    bg = Image.new("RGBA", rgba_img.size, (*bg_color, 255))
    return Image.alpha_composite(bg, rgba_img).convert("RGB")


def make_zoom_crop_checkerboard(
    rgba_crop: Image.Image,
    title: str,
    bbox: list[int],
    scale: int = 2,
) -> Image.Image:
    """Creates a zoomed crop on checkerboard with header banner."""
    w, h = rgba_crop.size
    sw, sh = w * scale, h * scale

    cb = make_checkerboard(w, h, square_size=16)
    cb_comp = Image.alpha_composite(cb, rgba_crop).convert("RGB")
    img_cb = cb_comp.resize((sw, sh), Image.Resampling.NEAREST)

    header_h = 32
    canvas = Image.new("RGB", (sw, sh + header_h), (30, 33, 40))
    draw = ImageDraw.Draw(canvas)

    draw.text((8, 8), f"{title} | bbox={bbox} ({scale}x zoom)", fill=(225, 230, 240))
    canvas.paste(img_cb, (0, header_h))
    draw.rectangle([0, header_h, sw - 1, header_h + sh - 1], outline=(70, 80, 95), width=2)
    return canvas


def make_crop_comparison_panel(
    orig_crop: Image.Image,
    mask_crop: Image.Image,
    rgba_crop: Image.Image,
    title: str,
    border_color: tuple[int, int, int],
    scale: int = 2,
) -> Image.Image:
    """Builds a 4-column side-by-side zoomed comparison strip for a crop region.

    Columns:
    1. Original RGB (with colored border)
    2. Alpha Mask (Grayscale)
    3. RGBA over 16px Checkerboard
    4. RGBA over Solid High-Contrast Background (Dark Navy #141E2D)
    """
    w, h = orig_crop.size
    sw, sh = w * scale, h * scale

    img_orig = orig_crop.resize((sw, sh), Image.Resampling.NEAREST)
    img_mask = mask_crop.convert("RGB").resize((sw, sh), Image.Resampling.NEAREST)

    cb = make_checkerboard(w, h, square_size=16)
    cb_comp = Image.alpha_composite(cb, rgba_crop).convert("RGB")
    img_cb = cb_comp.resize((sw, sh), Image.Resampling.NEAREST)

    dark_comp = composite_on_background(rgba_crop, (20, 30, 45))
    img_dark = dark_comp.resize((sw, sh), Image.Resampling.NEAREST)

    header_h = 36
    margin = 8
    panel_w = sw * 4 + margin * 5
    panel_h = sh + header_h + margin * 2

    panel = Image.new("RGB", (panel_w, panel_h), (35, 39, 46))
    draw = ImageDraw.Draw(panel)

    cols = [
        (img_orig, f"Original RGB: {title}"),
        (img_mask, "Alpha Mask (Grayscale)"),
        (img_cb, "Checkerboard Composite"),
        (img_dark, "High-Contrast BG (Navy)"),
    ]

    for idx, (im, col_title) in enumerate(cols):
        x_pos = margin + idx * (sw + margin)
        y_pos = header_h + margin
        panel.paste(im, (x_pos, y_pos))
        draw.text((x_pos + 4, 8), col_title, fill=(220, 220, 220))
        frame_col = border_color if idx == 0 else (70, 75, 85)
        draw.rectangle([x_pos - 1, y_pos - 1, x_pos + sw, y_pos + sh], outline=frame_col, width=2)

    return panel


def make_side_by_side_comparison(
    orig_img: Image.Image,
    mask_img: Image.Image,
    cb_comp: Image.Image,
    dark_comp: Image.Image,
    sample_id: str,
    description: str,
) -> Image.Image:
    """Builds a full side-by-side comparison panel for the sample.

    4 columns: Original | Alpha Mask | Checkerboard | High Contrast Dark Navy
    """
    w, h = orig_img.size
    target_h = 632
    target_w = int(w * (target_h / h))  # 424 px

    thumb_orig = orig_img.resize((target_w, target_h), Image.Resampling.BILINEAR)
    thumb_mask = mask_img.convert("RGB").resize((target_w, target_h), Image.Resampling.BILINEAR)
    thumb_cb = cb_comp.resize((target_w, target_h), Image.Resampling.BILINEAR)
    thumb_dark = dark_comp.resize((target_w, target_h), Image.Resampling.BILINEAR)

    header_h = 44
    margin = 8
    panel_w = target_w * 4 + margin * 5
    panel_h = target_h + header_h + margin * 2

    panel = Image.new("RGB", (panel_w, panel_h), (25, 28, 34))
    draw = ImageDraw.Draw(panel)

    draw.text((margin + 4, 6), f"PROJECT AIC TIER 3 COMPARISON: {sample_id} ({description})", fill=(255, 255, 255))
    draw.text((margin + 4, 24), "Resolution: 848x1264 | Mode: RGBA | IS-Net Anime ONNX CPU", fill=(180, 190, 205))

    thumbs = [
        (thumb_orig, "1. Original RGB Input"),
        (thumb_mask, "2. IS-Net Alpha Mask (Grayscale)"),
        (thumb_cb, "3. RGBA on Checkerboard (Transparency)"),
        (thumb_dark, "4. RGBA on Navy BG (Edge Cleanliness)"),
    ]

    for idx, (th, label) in enumerate(thumbs):
        x_pos = margin + idx * (target_w + margin)
        y_pos = header_h + margin
        panel.paste(th, (x_pos, y_pos))
        draw.text((x_pos + 4, header_h - 14), label, fill=(220, 225, 235))
        draw.rectangle([x_pos - 1, y_pos - 1, x_pos + target_w, y_pos + target_h], outline=(60, 68, 80), width=1)

    return panel


def process_sample(sample_code: str, full_key: str, description: str) -> dict:
    """Processes a single sample, generating both flat and structured outputs."""
    sample_subdir = OUTPUT_DIR / full_key
    sample_subdir.mkdir(parents=True, exist_ok=True)

    input_path = TIER3_DIR / f"{full_key}_input.png"
    mask_path = TIER3_DIR / f"{full_key}_mask.png"
    output_path = TIER3_DIR / f"{full_key}_output.png"
    meta_path = TIER3_DIR / f"{full_key}_meta.json"

    orig_img = Image.open(input_path).convert("RGB")
    mask_img = Image.open(mask_path).convert("L")
    rgba_img = Image.open(output_path).convert("RGBA")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    w, h = orig_img.size

    # --- 1. Grayscale Mask ---
    # Flat requirement: sample_XX_mask.png
    flat_mask_path = OUTPUT_DIR / f"{sample_code}_mask.png"
    mask_img.save(flat_mask_path)
    mask_img.save(sample_subdir / "02_alpha_mask_grayscale.png")

    # --- 2. Checkerboard Composite ---
    cb_full = make_checkerboard(w, h, square_size=32)
    cb_comp = Image.alpha_composite(cb_full, rgba_img).convert("RGB")
    flat_cb_path = OUTPUT_DIR / f"{sample_code}_checkerboard.png"
    cb_comp.save(flat_cb_path)
    cb_comp.save(sample_subdir / "03_checkerboard_composite.png")

    # Save original in subdir
    orig_img.save(sample_subdir / "01_original.png")

    # Save high-contrast dark navy in subdir
    dark_comp = composite_on_background(rgba_img, (20, 30, 45))
    dark_comp.save(sample_subdir / "04_high_contrast_composite.png")

    # --- 3. Side-by-Side Comparison Panel ---
    comp_panel = make_side_by_side_comparison(
        orig_img, mask_img, cb_comp, dark_comp, sample_code, description
    )
    flat_comp_path = OUTPUT_DIR / f"{sample_code}_comparison.png"
    comp_panel.save(flat_comp_path)

    # --- 4. 3 Zoomed Crops on Checkerboard ---
    crop_configs = SAMPLE_CROPS[full_key]
    crop_panels = []
    zoom_crop_info = []

    marked_orig = orig_img.copy()
    draw_marked = ImageDraw.Draw(marked_orig)

    for idx, (zoom_suffix, crop_sub_fname, crop_title, bbox) in enumerate(crop_configs, start=1):
        ymin, xmin, ymax, xmax = bbox
        border_col = CROP_BORDER_COLORS[(idx - 1) % len(CROP_BORDER_COLORS)]

        draw_marked.rectangle([xmin, ymin, xmax, ymax], outline=border_col, width=4)
        draw_marked.text((xmin + 6, ymin + 6), f"Zoom {idx}", fill=border_col)

        sub_orig = orig_img.crop((xmin, ymin, xmax, ymax))
        sub_mask = mask_img.crop((xmin, ymin, xmax, ymax))
        sub_rgba = rgba_img.crop((xmin, ymin, xmax, ymax))

        # Flat zoom crop on checkerboard: sample_XX_zoom_0Y.png
        zoom_cb_img = make_zoom_crop_checkerboard(
            sub_rgba, f"{sample_code} Crop {idx}: {crop_title}", bbox, scale=2
        )
        flat_zoom_path = OUTPUT_DIR / f"{sample_code}_{zoom_suffix}.png"
        zoom_cb_img.save(flat_zoom_path)

        # Detailed 4-column crop comparison in subdirectory
        crop_panel = make_crop_comparison_panel(
            sub_orig, sub_mask, sub_rgba, crop_title, border_col, scale=2
        )
        crop_panel.save(sample_subdir / f"{crop_sub_fname}.png")
        crop_panels.append(crop_panel)

        zoom_crop_info.append({
            "zoom_key": f"{sample_code}_{zoom_suffix}.png",
            "title": crop_title,
            "bbox": bbox,
            "flat_path": str(flat_zoom_path.relative_to(PROJECT_ROOT)),
            "strip_path": str((sample_subdir / f"{crop_sub_fname}.png").relative_to(PROJECT_ROOT)),
        })

    # --- 5. Overview Panel in Subdirectory ---
    overview_h = 632
    overview_w = int(w * (overview_h / h))
    thumb_orig = marked_orig.resize((overview_w, overview_h), Image.Resampling.BILINEAR)
    thumb_mask = mask_img.convert("RGB").resize((overview_w, overview_h), Image.Resampling.BILINEAR)
    thumb_cb = cb_comp.resize((overview_w, overview_h), Image.Resampling.BILINEAR)
    thumb_dark = dark_comp.resize((overview_w, overview_h), Image.Resampling.BILINEAR)

    top_row_w = overview_w * 4 + 8 * 5
    top_row = Image.new("RGB", (top_row_w, overview_h + 36), (30, 33, 39))
    top_draw = ImageDraw.Draw(top_row)
    top_thumbs = [
        (thumb_orig, "Original (with crop boxes)"),
        (thumb_mask, "Alpha Mask"),
        (thumb_cb, "Checkerboard Composite"),
        (thumb_dark, "Navy Contrast Composite"),
    ]
    for i, (th, label) in enumerate(top_thumbs):
        px = 8 + i * (overview_w + 8)
        top_row.paste(th, (px, 28))
        top_draw.text((px + 4, 6), label, fill=(230, 230, 230))

    total_overview_w = max(top_row_w, crop_panels[0].width)
    total_overview_h = top_row.height + sum(p.height + 12 for p in crop_panels) + 40

    overview_img = Image.new("RGB", (total_overview_w, total_overview_h), (25, 27, 32))
    overview_draw = ImageDraw.Draw(overview_img)
    overview_draw.text(
        (16, 10),
        f"TIER 3 VISUAL EVIDENCE: {full_key} ({description})",
        fill=(255, 255, 255),
    )

    curr_y = 36
    overview_img.paste(top_row, (0, curr_y))
    curr_y += top_row.height + 16

    for idx, panel in enumerate(crop_panels):
        c_title = crop_configs[idx][2]
        overview_draw.text((16, curr_y), f"Detail View {idx+1}: {c_title}", fill=(200, 210, 225))
        curr_y += 20
        overview_img.paste(panel, (0, curr_y))
        curr_y += panel.height + 12

    overview_img.save(sample_subdir / "overview_panel.png")

    alpha_arr = np.array(mask_img, dtype=np.uint8)
    total_px = alpha_arr.size
    n_trans = int(np.count_nonzero(alpha_arr == 0))
    n_soft = int(np.count_nonzero((alpha_arr > 0) & (alpha_arr < 255)))
    n_solid = int(np.count_nonzero(alpha_arr == 255))
    transitional_px = int(np.count_nonzero((alpha_arr >= 10) & (alpha_arr <= 245)))
    assert n_trans + n_soft + n_solid == total_px, f"Partition mismatch: {n_trans} + {n_soft} + {n_solid} != {total_px}"

    return {
        "sample_code": sample_code,
        "full_key": full_key,
        "description": description,
        "dimensions": [w, h],
        "latency_ms": meta.get("latency_ms"),
        "total_pixels": total_px,
        "transparent_pixels": n_trans,
        "soft_pixels": n_soft,
        "solid_pixels": n_solid,
        "transitional_alpha_pixels": transitional_px,
        "transparent_percent": round(n_trans / total_px * 100.0, 2),
        "soft_percent": round(n_soft / total_px * 100.0, 2),
        "solid_percent": round(n_solid / total_px * 100.0, 2),
        "transitional_alpha_percent": round(transitional_px / total_px * 100.0, 2),
        # Backward compatibility alias
        "soft_edge_pixels": n_soft,
        "flat_files": {
            "mask": f"{sample_code}_mask.png",
            "checkerboard": f"{sample_code}_checkerboard.png",
            "comparison": f"{sample_code}_comparison.png",
            "zoom_crops": [c["zoom_key"] for c in zoom_crop_info],
        },
        "crops": zoom_crop_info,
    }


def build_master_summary_grid(sample_results: list[dict]) -> None:
    """Builds a combined 5-sample comparative grid image."""
    thumb_h = 400
    thumb_w = int(848 * (thumb_h / 1264))  # ~268 px

    margin = 8
    header_h = 40
    col_w = thumb_w * 3 + margin * 4
    grid_w = col_w * len(sample_results) + margin
    grid_h = thumb_h + header_h + margin * 2

    grid = Image.new("RGB", (grid_w, grid_h), (20, 22, 26))
    draw = ImageDraw.Draw(grid)

    for s_idx, res in enumerate(sample_results):
        s_code = res["sample_code"]
        f_key = res["full_key"]
        s_dir = OUTPUT_DIR / f_key

        im_orig = Image.open(s_dir / "01_original.png").resize((thumb_w, thumb_h), Image.Resampling.BILINEAR)
        im_mask = Image.open(s_dir / "02_alpha_mask_grayscale.png").convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.BILINEAR)
        im_cb = Image.open(s_dir / "03_checkerboard_composite.png").resize((thumb_w, thumb_h), Image.Resampling.BILINEAR)

        x_start = margin + s_idx * col_w
        draw.text((x_start + 4, 8), f"{s_code}: {res['description']}", fill=(240, 240, 240))

        grid.paste(im_orig, (x_start, header_h))
        grid.paste(im_mask, (x_start + thumb_w + margin, header_h))
        grid.paste(im_cb, (x_start + (thumb_w + margin) * 2, header_h))

    grid.save(OUTPUT_DIR / "master_summary_grid.png")


def main() -> None:
    print("=" * 80)
    print("PROJECT AIC — TIER 3 VISUAL EVIDENCE GENERATOR (TASK 0.5B-1)")
    print("=" * 80)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for idx, (sample_code, full_key, desc) in enumerate(SAMPLE_MAP, start=1):
        print(f"[{idx}/{len(SAMPLE_MAP)}] Processing {sample_code} ({full_key})...")
        res = process_sample(sample_code, full_key, desc)
        results.append(res)
        print(f"      Generated flat: {sample_code}_mask.png, {sample_code}_checkerboard.png,")
        print(f"                      {sample_code}_comparison.png, 3x {sample_code}_zoom_*.png")
        print(f"      Generated subdir: {full_key}/ (overview + detailed crops)")

    # Master summary grid
    print("\nBuilding master comparative summary grid...")
    build_master_summary_grid(results)
    print(f"Master summary grid saved: {OUTPUT_DIR / 'master_summary_grid.png'}")

    # Write manifest.json
    manifest = {
        "version": "1.0",
        "description": "Visual evidence artifact manifest for Tier 3 IS-Net Anime ONNX background removal",
        "alpha_metrics_specification": {
            "transparent": "alpha == 0",
            "soft": "0 < alpha < 255",
            "solid": "alpha == 255",
            "disjoint_sum_invariant": "transparent_pixels + soft_pixels + solid_pixels == total_pixels",
            "transitional_alpha_note": "transitional_alpha_pixels (10 <= alpha <= 245) is a diagnostic subset of soft_pixels",
        },
        "target_flat_count": 30,
        "samples": results,
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Manifest written: {manifest_path}")

    # Verify the 30 required flat files exist
    flat_files = [
        f"sample_0{i}_{suffix}.png"
        for i in range(1, 6)
        for suffix in ["mask", "checkerboard", "comparison", "zoom_01", "zoom_02", "zoom_03"]
    ]
    missing = [f for f in flat_files if not (OUTPUT_DIR / f).exists()]

    print("\n" + "=" * 80)
    print("VERIFICATION OF 30 FLAT OUTPUT FILES:")
    if not missing:
        print(f"SUCCESS: All {len(flat_files)} flat visual evidence files exist in:")
        print(f"         {OUTPUT_DIR}")
    else:
        print(f"WARNING: Missing {len(missing)} files: {missing}")
        sys.exit(1)
    print("=" * 80)


if __name__ == "__main__":
    main()
