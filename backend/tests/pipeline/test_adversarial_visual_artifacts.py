"""Adversarial Verification Suite for Visual Quality and Output Artifacts.

Task 0.5B-1 Comprehensive Verification:
Challenger 1: Visual Quality & Artifact Challenger

Covers:
1. File Integrity & PNG Format Stress across all 32 items in data/tier3_output/visual_evidence/
   and 40 subdirectory images (71 PNGs total).
2. Script Robustness & Edge Cases for scripts/generate_visual_evidence.py.
3. Empirical Truthfulness:
   - sample_02 top-right artifact leak (exact alpha max = 81).
   - sample_04 soft-edge spatial distribution (exact 250,753 pixels, 90.16% lower half).
   - sample_05 wing and fabric transparency (44,001 soft pixels in gown crop, wing median alpha = 110).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, UnidentifiedImageError

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FIXTURE_TIER3_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "tier3_output"
TIER3_DIR = (
    FIXTURE_TIER3_DIR
    if FIXTURE_TIER3_DIR.is_dir()
    else (PROJECT_ROOT / "data" / "tier3_output")
)
VIS_DIR = TIER3_DIR / "visual_evidence"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

scripts_dir = PROJECT_ROOT / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

import generate_visual_evidence as gve  # type: ignore[import-not-found]


class TestVisualEvidenceArtifactsIntegrity:
    """Objective 1: File Integrity and PNG Format Stress."""

    def test_directory_and_manifest_existence(self) -> None:
        """Verify visual evidence directory and structured manifest exist."""
        assert VIS_DIR.is_dir(), f"Visual evidence directory not found: {VIS_DIR}"
        manifest_path = VIS_DIR / "manifest.json"
        assert manifest_path.is_file(), "manifest.json not found in visual_evidence"

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["version"] == "1.0"
        assert manifest["target_flat_count"] == 30
        assert len(manifest["samples"]) == 5

        # Verify standardized alpha metrics specification in manifest
        alpha_spec = manifest.get("alpha_metrics_specification", {})
        assert alpha_spec.get("transparent") == "alpha == 0"
        assert alpha_spec.get("soft") == "0 < alpha < 255"
        assert alpha_spec.get("solid") == "alpha == 255"

        # Verify all 5 samples satisfy partition invariant and transitional subset constraint
        for sample in manifest["samples"]:
            n_trans = sample["transparent_pixels"]
            n_soft = sample["soft_pixels"]
            n_solid = sample["solid_pixels"]
            n_tot = sample["total_pixels"]
            assert n_trans + n_soft + n_solid == n_tot, f"{sample['sample_code']}: partition mismatch"
            assert sample["transitional_alpha_pixels"] <= n_soft, (
                f"{sample['sample_code']}: transitional ({sample['transitional_alpha_pixels']}) > soft ({n_soft})"
            )

    def test_top_level_files_count_and_naming(self) -> None:
        """Verify exactly 32 top-level files (31 PNGs + 1 JSON) with strict naming conventions."""
        top_files = [f for f in VIS_DIR.iterdir() if f.is_file()]
        assert len(top_files) == 32, f"Expected 32 top-level files, found {len(top_files)}"

        png_files = [f for f in top_files if f.suffix == ".png"]
        assert len(png_files) == 31, f"Expected 31 top-level PNGs, found {len(png_files)}"

        # 5 masks, 5 checkerboards, 5 comparisons, 15 zoom crops, 1 master grid
        for i in range(1, 6):
            s = f"sample_0{i}"
            assert (VIS_DIR / f"{s}_mask.png").exists()
            assert (VIS_DIR / f"{s}_checkerboard.png").exists()
            assert (VIS_DIR / f"{s}_comparison.png").exists()
            assert (VIS_DIR / f"{s}_zoom_01.png").exists()
            assert (VIS_DIR / f"{s}_zoom_02.png").exists()
            assert (VIS_DIR / f"{s}_zoom_03.png").exists()
        assert (VIS_DIR / "master_summary_grid.png").exists()

    def test_all_pngs_have_valid_signature_and_ihdr(self) -> None:
        """Verify every PNG file across visual_evidence has valid 8-byte PNG signature and IHDR."""
        all_pngs = list(VIS_DIR.rglob("*.png"))
        assert len(all_pngs) == 71, f"Expected 71 PNGs total, found {len(all_pngs)}"

        for p in all_pngs:
            raw = p.read_bytes()
            assert len(raw) >= 16, f"File too small: {p}"
            assert raw[:8] == PNG_SIGNATURE, f"Invalid PNG signature in {p}"
            assert raw[12:16] == b"IHDR", f"Missing IHDR chunk in {p}"

            # Verify uncorrupted raster
            with Image.open(p) as im:
                im.verify()
            with Image.open(p) as im:
                im.load()  # Full raster decode

    def test_image_color_modes_and_canvas_dimensions(self) -> None:
        """Verify color modes (L for grayscale masks, RGB for composites) and dimensions."""
        for i in range(1, 6):
            s = f"sample_0{i}"
            # 1. Masks must be mode 'L' and match source dimensions (848, 1264)
            with Image.open(VIS_DIR / f"{s}_mask.png") as m:
                assert m.mode == "L", f"{s}_mask.png mode should be L, got {m.mode}"
                assert m.size == (848, 1264)

            # 2. Checkerboard composites are RGB (flattened on grid) and match source dimensions
            with Image.open(VIS_DIR / f"{s}_checkerboard.png") as cb:
                assert cb.mode == "RGB", f"{s}_checkerboard.png mode should be RGB, got {cb.mode}"
                assert cb.size == (848, 1264)

            # 3. Comparison panels are RGB with 4 columns: size (1736, 692)
            with Image.open(VIS_DIR / f"{s}_comparison.png") as comp:
                assert comp.mode == "RGB", f"{s}_comparison.png mode should be RGB, got {comp.mode}"
                assert comp.size == (1736, 692)

            # 4. Zoom crops: 2x scaled crops + 32px header banner
            # Normal crops: 250x250 -> 500x500 + 32 header = (500, 532)
            # sample_02_zoom_03 is clamped at right border: 248x250 -> 496x500 + 32 header = (496, 532)
            for z in [1, 2, 3]:
                zoom_file = VIS_DIR / f"{s}_zoom_0{z}.png"
                with Image.open(zoom_file) as z_im:
                    assert z_im.mode == "RGB"
                    if s == "sample_02" and z == 3:
                        assert z_im.size == (496, 532)
                    else:
                        assert z_im.size == (500, 532)


class TestScriptRobustnessAndEdgeCases:
    """Objective 2: Robustness against edge cases, corrupted files, and non-existent directories."""

    def test_missing_input_raises_filenotfounderror(self) -> None:
        """Verify process_sample raises FileNotFoundError when input is missing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            old_tier3 = gve.TIER3_DIR
            old_output = gve.OUTPUT_DIR
            try:
                gve.TIER3_DIR = tmp_path
                gve.OUTPUT_DIR = tmp_path / "vis"
                with pytest.raises(FileNotFoundError):
                    gve.process_sample("sample_99", "sample_99_missing", "Missing")
            finally:
                gve.TIER3_DIR = old_tier3
                gve.OUTPUT_DIR = old_output

    def test_corrupted_and_empty_images_raise_unidentifiedimageerror(self) -> None:
        """Verify process_sample raises UnidentifiedImageError on empty or corrupted files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            old_tier3 = gve.TIER3_DIR
            old_output = gve.OUTPUT_DIR
            try:
                gve.TIER3_DIR = tmp_path
                gve.OUTPUT_DIR = tmp_path / "vis"

                (tmp_path / "sample_test_input.png").write_bytes(b"")
                (tmp_path / "sample_test_mask.png").write_bytes(b"")
                (tmp_path / "sample_test_output.png").write_bytes(b"")

                with pytest.raises(UnidentifiedImageError):
                    gve.process_sample("sample_01", "sample_test", "Empty")
            finally:
                gve.TIER3_DIR = old_tier3
                gve.OUTPUT_DIR = old_output

    def test_make_checkerboard_boundary_conditions(self) -> None:
        """Stress-test checkerboard generation with extreme dimensions and square sizes."""
        # square_size larger than width/height
        cb_large = gve.make_checkerboard(8, 8, square_size=64)
        assert cb_large.size == (8, 8)
        assert cb_large.mode == "RGBA"

        # 1x1 canvas
        cb_1x1 = gve.make_checkerboard(1, 1, square_size=1)
        assert cb_1x1.size == (1, 1)

        # Non-square odd dimensions
        cb_odd = gve.make_checkerboard(31, 79, square_size=5)
        assert cb_odd.size == (31, 79)


class TestEmpiricalImageTruthfulness:
    """Objective 3: Verify empirical truthfulness of claimed visual artifacts and metrics."""

    def test_sample_02_neon_leak_artifact(self) -> None:
        """Verify sample_02 has a genuine top-right artifact leak with max alpha of exactly 81."""
        mask_02 = np.array(Image.open(TIER3_DIR / "sample_02_complex_bg_mask.png").convert("L"))
        out_02 = np.array(Image.open(TIER3_DIR / "sample_02_complex_bg_output.png"))
        alpha_02 = out_02[:, :, 3]

        assert np.array_equal(mask_02, alpha_02), "Mask and output alpha do not match"

        # Small box [0:100, 650:848]
        sub = alpha_02[0:100, 650:848]
        nonzero_count = np.sum(sub > 0)
        assert nonzero_count > 0, "Top-right leak should contain non-zero alpha pixels"
        assert int(np.max(sub)) == 81, f"Expected max alpha = 81 in leak, got {np.max(sub)}"

    def test_sample_04_soft_edge_concentration(self) -> None:
        """Verify sample_04 disjoint partition (538k trans, 285k soft, 248k solid) and 250k transitional alpha."""
        alpha_04 = np.array(Image.open(TIER3_DIR / "sample_04_small_accessories_mask.png").convert("L"))
        total_pixels = alpha_04.size
        assert total_pixels == 848 * 1264

        # Standard 3 disjoint groups
        transparent_pixels = int(np.sum(alpha_04 == 0))
        soft_pixels = int(np.sum((alpha_04 > 0) & (alpha_04 < 255)))
        solid_pixels = int(np.sum(alpha_04 == 255))
        assert transparent_pixels == 538089
        assert soft_pixels == 285223
        assert solid_pixels == 248560
        assert transparent_pixels + soft_pixels + solid_pixels == total_pixels

        # Diagnostic transitional alpha range (10 <= alpha <= 245)
        transitional_mask = (alpha_04 >= 10) & (alpha_04 <= 245)
        transitional_pixels = int(np.sum(transitional_mask))
        assert transitional_pixels == 250753
        assert transitional_pixels <= soft_pixels

        # Spatial distribution of transitional gradient (lower half concentration)
        upper_transitional = int(np.sum(transitional_mask[:632, :]))
        lower_transitional = int(np.sum(transitional_mask[632:, :]))
        assert lower_transitional / transitional_pixels > 0.90, (
            f"Lower half transitional ratio {lower_transitional/transitional_pixels} <= 0.90"
        )
        assert upper_transitional == 24673
        assert lower_transitional == 226080

        bottom_264 = int(np.sum(transitional_mask[1000:, :]))
        assert bottom_264 == 166495
        assert bottom_264 / transitional_pixels > 0.66

        # Check Y >= 1200 has 0 opaque pixels (artistic fade)
        bottom_rows = alpha_04[1200:, :]
        assert np.sum(bottom_rows == 255) == 0, "Bottom rows should have 0 opaque pixels (artistic fade)"
        assert np.max(bottom_rows) <= 125

    def test_sample_05_translucent_wings_and_gown(self) -> None:
        """Verify sample_05 disjoint partition (546k trans, 176k soft, 348k solid) and translucent gown."""
        alpha_05 = np.array(Image.open(TIER3_DIR / "sample_05_translucent_costume_mask.png").convert("L"))
        total_pixels = alpha_05.size
        assert total_pixels == 848 * 1264

        # Standard 3 disjoint groups
        transparent_pixels = int(np.sum(alpha_05 == 0))
        soft_pixels = int(np.sum((alpha_05 > 0) & (alpha_05 < 255)))
        solid_pixels = int(np.sum(alpha_05 == 255))
        assert transparent_pixels == 546573
        assert soft_pixels == 176607
        assert solid_pixels == 348692
        assert transparent_pixels + soft_pixels + solid_pixels == total_pixels

        # Gown crop: [850:1100, 400:650]
        gown_crop = alpha_05[850:1100, 400:650]
        soft_gown = np.sum((gown_crop > 0) & (gown_crop < 255))
        assert soft_gown == 44001, f"Expected 44,001 soft gown pixels, got {soft_gown}"
        assert soft_gown / gown_crop.size > 0.70, "Gown should have >70% soft pixels"

        # Wing crop: [300:550, 580:830]
        wing_crop = alpha_05[300:550, 580:830]
        wing_soft = int(np.sum((wing_crop > 0) & (wing_crop < 255)))
        assert wing_soft == 2746, f"Expected 2,746 soft wing pixels, got {wing_soft}"
        wing_soft_vals = wing_crop[(wing_crop > 0) & (wing_crop < 255)]
        wing_p50 = int(np.percentile(wing_soft_vals, 50))
        assert wing_p50 == 110, f"Expected wing median alpha = 110, got {wing_p50}"

        # Diagnostic transitional alpha range (10 <= alpha <= 245)
        transitional_pixels = int(np.sum((alpha_05 >= 10) & (alpha_05 <= 245)))
        assert transitional_pixels == 160824, f"Expected 160,824 transitional pixels, got {transitional_pixels}"
        assert transitional_pixels <= soft_pixels
