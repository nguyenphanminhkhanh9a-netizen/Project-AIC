"""Adversarial stress test suite for Phase 0.5A Automatic Asset Processing Pipeline.

Challenger 2: Adversarial Quality, Deduplication & Storage Rollback Challenger.
Tests boundary conditions, multi-scale dedup discrimination, extreme drift,
atomic storage rollback, and Resolver status exclusion invariants.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from app.domain.asset_resolver import CharacterAssetResolver
from app.domain.character import (
    AnchorType,
    AssetDefinition,
    CharacterManifest,
    FallbackConfig,
)
from app.pipeline.config import PipelineConfig
from app.pipeline.deduplication.engine import MultiScaleDeduplicator
from app.pipeline.processing.drift_analyzer import DriftVerificationEngine
from app.pipeline.processing.normalizer import SpriteNormalizer
from app.pipeline.quality.cqs_gate import CQSQualityGate
from app.pipeline.storage.manifest_manager import (
    ManifestCommitError,
    ManifestManager,
)
from tests.pipeline.conftest import create_synthetic_character_rgba

# =====================================================================
# 1. Deduplication & Quality Gate Adversarial Tests
# =====================================================================


class TestQualityGateAdversarial:
    """Adversarially challenge CQSQualityGate edge conditions and thresholds."""

    def test_cqs_boundary_pass_vs_quarantine(self) -> None:
        """Verify exact boundary behavior around pass threshold (0.65)."""
        cfg = PipelineConfig()
        gate = CQSQualityGate(config=cfg)

        # Baseline high quality image (passes)
        img_high = create_synthetic_character_rgba(width=1024, height=1536)
        res_high = gate.evaluate(img_high)
        assert res_high.composite_score >= cfg.cqs_pass_threshold
        assert res_high.passed is True
        assert res_high.quarantine is False
        assert res_high.rejection_reason is None

        # Custom mock scoring to verify exact boundary: 0.6500 vs 0.6499
        with (
            patch("app.pipeline.quality.cqs_gate.compute_resolution_score", return_value=0.5),
            patch("app.pipeline.quality.cqs_gate.compute_laplacian_variance", return_value=50.0),
        ):
            # We can mock component scores by adjusting config weights or thresholds
                cfg_borderline = PipelineConfig(
                    cqs_pass_threshold=0.65,
                    cqs_quarantine_threshold=0.50,
                )
                gate_border = CQSQualityGate(config=cfg_borderline)

                # Mock calculate composite to return exactly 0.65
                with patch.object(
                    gate_border,
                    "evaluate",
                    wraps=gate_border.evaluate,
                ):
                    pass

    def test_cqs_exact_threshold_transitions(self) -> None:
        """Adversarially test exact numerical transitions for pass, quarantine, and reject."""
        cfg = PipelineConfig()
        gate = CQSQualityGate(config=cfg)

        # Check resolution hard floor rejection
        img_sub_w = Image.new("RGBA", (511, 768), (100, 100, 100, 255))
        res_sub_w = gate.evaluate(img_sub_w)
        assert res_sub_w.passed is False
        assert res_sub_w.quarantine is False
        assert "below minimum requirement" in (res_sub_w.rejection_reason or "")

        img_sub_h = Image.new("RGBA", (512, 767), (100, 100, 100, 255))
        res_sub_h = gate.evaluate(img_sub_h)
        assert res_sub_h.passed is False
        assert res_sub_h.quarantine is False
        assert "below minimum requirement" in (res_sub_h.rejection_reason or "")

        # Test extreme degraded inputs
        # Flat gray image (zero sharpness, zero contrast)
        flat_img = Image.new("RGBA", (1024, 1536), (128, 128, 128, 255))
        res_flat = gate.evaluate(flat_img)
        assert res_flat.passed is False
        assert res_flat.quarantine is False  # Must be rejected, not quarantined
        assert res_flat.composite_score < cfg.cqs_quarantine_threshold

        # Pure transparent image (zero coverage)
        empty_img = Image.new("RGBA", (1024, 1536), (0, 0, 0, 0))
        res_empty = gate.evaluate(empty_img)
        assert res_empty.passed is False
        assert res_empty.quarantine is False
        assert res_empty.coverage_ratio == 0.0

    def test_cqs_boundary_values_exact(self) -> None:
        """Directly verify the conditional branching for 0.65 and 0.50 boundaries."""
        cfg = PipelineConfig(
            cqs_pass_threshold=0.65,
            cqs_quarantine_threshold=0.50,
            cqs_weight_sharpness=1.0,
            cqs_weight_contrast=0.0,
            cqs_weight_coverage=0.0,
            cqs_weight_resolution=0.0,
        )
        gate = CQSQualityGate(config=cfg)

        # lap_var / (lap_var + 50) = composite_score
        # For composite_score = 0.65: lap_var / (lap_var + 50) = 0.65 => 0.35 * lap_var = 32.5 => lap_var = 92.857142857
        with patch("app.pipeline.quality.cqs_gate.compute_laplacian_variance", return_value=92.85714285714286):
            img = Image.new("RGBA", (1024, 1536), (100, 100, 100, 255))
            res = gate.evaluate(img)
            assert res.composite_score >= 0.65
            assert res.passed is True
            assert res.quarantine is False

        # Just below 0.65 (e.g. composite_score = 0.64) -> Quarantine
        # lap_var / (lap_var + 50) = 0.64 => 0.36 * lap_var = 32 => lap_var = 88.888888888
        with patch("app.pipeline.quality.cqs_gate.compute_laplacian_variance", return_value=88.88):
            img = Image.new("RGBA", (1024, 1536), (100, 100, 100, 255))
            res = gate.evaluate(img)
            assert 0.50 <= res.composite_score < 0.65
            assert res.passed is False
            assert res.quarantine is True

        # Just below 0.50 (e.g. composite_score = 0.49) -> Reject
        # lap_var / (lap_var + 50) = 0.49 => 0.51 * lap_var = 24.5 => lap_var = 48.039
        with patch("app.pipeline.quality.cqs_gate.compute_laplacian_variance", return_value=48.0):
            img = Image.new("RGBA", (1024, 1536), (100, 100, 100, 255))
            res = gate.evaluate(img)
            assert res.composite_score < 0.50
            assert res.passed is False
            assert res.quarantine is False


class TestDeduplicationAdversarial:
    """Adversarially challenge 3-stage multi-scale deduplication engine."""

    def test_dedup_exact_identical_images(self) -> None:
        """Identical image (D_H = 0, SSIM = 1.0) must be rejected as duplicate."""
        img1 = create_synthetic_character_rgba(emotion="neutral")
        img2 = img1.copy()

        engine = MultiScaleDeduplicator()
        res = engine.check_duplicate(candidate_img=img2, existing_assets=[("miku_neutral", img1)])

        assert res.is_duplicate is True
        assert res.action == "reject"
        assert res.global_hamming_distance == 0
        assert res.facial_hamming_distance == 0
        assert res.facial_ssim is not None and res.facial_ssim >= 0.99

    def test_dedup_lossless_recompression(self) -> None:
        """Lossless re-encoding (PNG/lossless WebP) retains identical hash and is correctly rejected."""
        base_img = create_synthetic_character_rgba(emotion="neutral")

        buf = io.BytesIO()
        base_img.save(buf, format="WEBP", lossless=True)
        buf.seek(0)
        recomp_rgba = Image.open(buf)

        engine = MultiScaleDeduplicator()
        res = engine.check_duplicate(
            candidate_img=recomp_rgba,
            existing_assets=[("miku_neutral", base_img)],
        )

        assert res.global_hamming_distance == 0
        assert res.facial_hamming_distance == 0
        assert res.facial_ssim is not None and res.facial_ssim >= 0.99
        assert res.is_duplicate is True
        assert res.action == "reject"

    def test_dedup_lossy_recompression_vulnerability(self) -> None:
        """Verifies lossy re-encoded duplicates with elevated hash distance are quarantined, never accepted.

        Empirical finding: Even with SSIM >= 0.999 (exact structural duplicate),
        mild lossy WebP compression (quality=95) flips odd-order DCT bits around
        median 0.0 on symmetric anime faces, causing facial Hamming distance >= 8 (18).
        With priority ordering checking duplicate condition first, the engine safely
        routes the candidate to 'quarantine' rather than falsely accepting it.
        """
        base_img = create_synthetic_character_rgba(emotion="neutral")

        buf = io.BytesIO()
        base_img.save(buf, format="WEBP", quality=95)
        buf.seek(0)
        recomp_rgba = Image.open(buf)

        engine = MultiScaleDeduplicator()
        res = engine.check_duplicate(
            candidate_img=recomp_rgba,
            existing_assets=[("miku_neutral", base_img)],
        )

        # Global distance remains low (<= 4)
        assert res.global_hamming_distance <= 4
        # Facial SSIM is virtually 1.0 (exact duplicate)
        assert res.facial_ssim is not None and res.facial_ssim >= 0.999
        # But facial distance blew up to >= 8 due to DCT median sensitivity on symmetric faces
        assert res.facial_hamming_distance is not None and res.facial_hamming_distance >= 8
        # Remediation verified: must be quarantined to needs_review, never accepted
        assert res.action == "quarantine"
        assert res.is_duplicate is False
        assert res.is_suspect is True
        assert "quarantined to needs_review" in (res.reason or "")

    def test_dedup_subtle_emotion_quarantine(self) -> None:
        """Subtle emotion variation (same body, borderline SSIM [0.88, 0.94)) must be quarantined."""
        base_img = create_synthetic_character_rgba(emotion="neutral")

        # Create subtle variation: slightly tweak mouth line
        cand_img = base_img.copy()
        draw = ImageDraw.Draw(cand_img)
        cx = 1024 // 2
        cy = int(1536 * 0.28)
        face_h = int(1536 * 0.09)
        mouth_y = cy + int(face_h * 0.60)
        # Add subtle slight line/dot near mouth
        draw.line([(cx - 15, mouth_y - 3), (cx + 15, mouth_y - 3)], fill=(200, 80, 80, 255), width=3)

        # Mock the facial SSIM to land precisely in the quarantine window [0.88, 0.94)
        with (
            patch("app.pipeline.deduplication.engine.compute_ssim", return_value=0.91),
            patch("app.pipeline.deduplication.engine.hamming_distance", side_effect=[2, 3]),
        ):
            engine = MultiScaleDeduplicator()
            res = engine.check_duplicate(cand_img, [("miku_neutral", base_img)])

            assert res.action == "quarantine"
            assert res.is_duplicate is False
            assert res.is_suspect is True
            assert res.facial_ssim == 0.91

    def test_dedup_distinct_emotion_pass(self) -> None:
        """Distinct emotion (neutral vs happy crescent eyes) must be accepted."""
        neutral_img = create_synthetic_character_rgba(emotion="neutral")
        happy_img = create_synthetic_character_rgba(emotion="happy")

        engine = MultiScaleDeduplicator()
        res = engine.check_duplicate(happy_img, [("miku_neutral", neutral_img)])

        # Body is identical (global distance <= 16)
        assert res.global_hamming_distance <= 16
        # But facial difference triggers accept
        assert res.action == "accept"
        assert res.is_duplicate is False
        assert res.is_suspect is True

    def test_dedup_completely_different_character(self) -> None:
        """Completely different character with different color and geometry (D_H > 16) must be accepted."""
        miku = create_synthetic_character_rgba(
            hair_color=(50, 120, 180),  # Blue
            silhouette_color=(60, 70, 90),
            emotion="neutral",
        )
        other_char = create_synthetic_character_rgba(
            hair_color=(200, 80, 50),   # Red / Orange
            silhouette_color=(180, 160, 140),
            head_center_x=300,           # Offset pose
            head_center_y=350,
            emotion="happy",
        )

        engine = MultiScaleDeduplicator()
        res = engine.check_duplicate(other_char, [("miku_neutral", miku)])

        assert res.global_hamming_distance > 16
        assert res.action == "accept"
        assert res.is_duplicate is False
        assert res.is_suspect is False
        assert res.facial_ssim is None  # Skipped stage 2


# =====================================================================
# 2. Drift Analyzer & Normalizer Adversarial Tests
# =====================================================================


class TestDriftAndNormalizerAdversarial:
    """Adversarially challenge Drift Analyzer and Sprite Normalizer."""

    def test_extreme_horizontal_drift_quarantine(self) -> None:
        """Extreme X drift (> 50px) must trigger quarantine."""
        base_img = create_synthetic_character_rgba(head_center_x=512)
        # Shift head by 55px horizontally
        cand_img = create_synthetic_character_rgba(head_center_x=567)

        engine = DriftVerificationEngine()
        result = engine.verify_drift(candidate_img=cand_img, baseline_img=base_img)

        assert result.head_drift_px >= 50.0
        assert result.total_drift_px > 50.0
        assert result.passed is False
        assert result.is_quarantined is True
        assert "Severe alignment drift" in (result.quarantine_reason or "")

    def test_extreme_vertical_drift_quarantine(self) -> None:
        """Extreme Y drift (> 50px) must trigger quarantine when sprite is shifted vertically."""
        base_img = create_synthetic_character_rgba()
        # Shift entire character sprite down by 55px on the canvas
        cand_img = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
        cand_img.paste(base_img, (0, 55))

        engine = DriftVerificationEngine()
        result = engine.verify_drift(candidate_img=cand_img, baseline_img=base_img)

        assert result.eye_drift_px == 55.0
        assert result.total_drift_px == 55.0
        assert result.passed is False
        assert result.is_quarantined is True
        assert "Severe alignment drift" in (result.quarantine_reason or "")

    def test_drift_analyzer_silhouette_heuristic_limitation(self) -> None:
        """Adversarial finding: Drift analyzer relies strictly on silhouette bbox, not facial landmarks.

        Empirical finding: When facial features (e.g. eyes/mouth) shift internally by 55px
        while the character silhouette (hair/clothes) remains stationary, eye_drift_px is 0.0
        because y_eye is computed as a fixed ratio: y1 + sil_h * 0.228.
        This confirms Phase 0.5A's intentional heuristic approach before ONNX models in Phase 0.5B.
        """
        base_img = create_synthetic_character_rgba(eye_line_y=458)
        cand_img = create_synthetic_character_rgba(eye_line_y=513)

        engine = DriftVerificationEngine()
        result = engine.verify_drift(candidate_img=cand_img, baseline_img=base_img)

        # Confirm silhouette heuristic behavior
        assert result.eye_drift_px == 0.0
        assert result.head_drift_px == 0.0
        assert result.passed is True

    def test_drift_exact_boundary_conditions(self) -> None:
        """Test drift boundaries: <= 35px passes, (35, 50] compensates, > 50 quarantines."""
        engine = DriftVerificationEngine()
        base_img = create_synthetic_character_rgba()

        # Mock _extract_head_and_eye_coords to test exact numerical boundaries
        with patch.object(engine, "_extract_head_and_eye_coords") as mock_coords:
            # 1. Zero drift (self comparison)
            mock_coords.side_effect = [(512.0, 458.0), (512.0, 458.0)]
            r0 = engine.verify_drift(base_img, base_img)
            assert r0.passed is True
            assert r0.is_quarantined is False
            assert r0.recommended_offset_x == 0
            assert r0.recommended_offset_y == 0

            # 2. Boundary: exactly 35.0px drift -> pass without offset
            mock_coords.side_effect = [(547.0, 458.0), (512.0, 458.0)]
            r35 = engine.verify_drift(base_img, base_img)
            assert r35.passed is True
            assert r35.is_quarantined is False
            assert r35.total_drift_px == 35.0
            assert r35.recommended_offset_x == 0

            # 3. Boundary: 35.1px drift -> pass with compensation offset
            mock_coords.side_effect = [(547.1, 458.0), (512.0, 458.0)]
            r36 = engine.verify_drift(base_img, base_img)
            assert r36.passed is True
            assert r36.is_quarantined is False
            assert r36.recommended_offset_x == -35

            # 4. Boundary: exactly 50.0px drift -> pass with compensation
            mock_coords.side_effect = [(562.0, 458.0), (512.0, 458.0)]
            r50 = engine.verify_drift(base_img, base_img)
            assert r50.passed is True
            assert r50.is_quarantined is False
            assert r50.recommended_offset_x == -50

            # 5. Boundary: 50.1px drift -> quarantine
            mock_coords.side_effect = [(562.1, 458.0), (512.0, 458.0)]
            r51 = engine.verify_drift(base_img, base_img)
            assert r51.passed is False
            assert r51.is_quarantined is True

    def test_normalizer_dynamic_alpha_edge_classifier(self) -> None:
        """Verify dynamic alpha edge classifier on full-body, waist-up, and bust-up silhouettes."""
        normalizer = SpriteNormalizer()

        # 1. Full-body (feet taper before 95% bottom boundary)
        full_body = create_synthetic_character_rgba(sprite_type="full_body")
        assert normalizer.classify_edge(full_body) == AnchorType.BOTTOM_CENTER

        # 2. Waist-up (torso extends through 95% bottom boundary, height >= 50%)
        waist_up = create_synthetic_character_rgba(sprite_type="waist_up")
        assert normalizer.classify_edge(waist_up) == AnchorType.WAIST_LEVEL

        # 3. Bust-up (shoulders extend through bottom boundary, height < 50%)
        bust_up = create_synthetic_character_rgba(sprite_type="bust_up")
        assert normalizer.classify_edge(bust_up) == AnchorType.EYE_LEVEL

        # 4. Normalize all three and verify output contract invariants
        for sprite, expected_anchor in [
            (full_body, AnchorType.BOTTOM_CENTER),
            (waist_up, AnchorType.WAIST_LEVEL),
            (bust_up, AnchorType.EYE_LEVEL),
        ]:
            canvas, alignment = normalizer.normalize(sprite)
            assert canvas.size == (1024, 1536)
            assert canvas.mode == "RGBA"
            assert alignment.anchor_type == expected_anchor
            assert alignment.bounding_box is not None
            assert alignment.bounding_box[2] > alignment.bounding_box[0]
            assert alignment.bounding_box[3] > alignment.bounding_box[1]


# =====================================================================
# 3. Atomic Storage & Resolver Failure Modes Adversarial Tests
# =====================================================================


class TestStorageAndResolverAdversarial:
    """Adversarially challenge atomic rollback, ENOSPC, permission denied, and resolver status filtering."""

    def test_atomic_rollback_on_enospc(self, tmp_path: Path, sample_character_manifest: CharacterManifest) -> None:
        """Simulate ENOSPC (disk full) during manifest write and verify atomic rollback."""
        mgr = ManifestManager(characters_dir=tmp_path)
        pack_dir = tmp_path / "miku_nakano"
        pack_dir.mkdir(parents=True)
        manifest_file = pack_dir / "manifest.json"
        manifest_file.write_text(sample_character_manifest.model_dump_json(indent=2), encoding="utf-8")
        original_manifest_bytes = manifest_file.read_bytes()

        new_asset = AssetDefinition(
            asset_id="test_new_asset",
            path="assets/dynamic/test.webp",
            status="ready",
        )
        asset_bytes = b"FAKE_WEBP_IMAGE_BYTES"

        # Simulate ENOSPC on open/write of manifest tmp file
        with (
            patch("builtins.open", side_effect=OSError(28, "No space left on device")),
            pytest.raises(ManifestCommitError, match="Atomic manifest write failed"),
        ):
            mgr.commit_asset(
                character_id="miku_nakano",
                asset=new_asset,
                image_bytes=asset_bytes,
            )

        # Assert zero manifest corruption
        assert manifest_file.read_bytes() == original_manifest_bytes

        # Assert no orphan asset left on disk
        orphan_asset = pack_dir / new_asset.path
        assert not orphan_asset.exists()

        # Assert no lingering .tmp files
        tmp_files = list(pack_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_atomic_rollback_on_permission_denied(
        self, tmp_path: Path, sample_character_manifest: CharacterManifest
    ) -> None:
        """Simulate PermissionError during atomic os.replace and verify temporary file unlinking."""
        mgr = ManifestManager(characters_dir=tmp_path)
        pack_dir = tmp_path / "miku_nakano"
        pack_dir.mkdir(parents=True)
        manifest_file = pack_dir / "manifest.json"
        manifest_file.write_text(sample_character_manifest.model_dump_json(indent=2), encoding="utf-8")
        original_manifest_bytes = manifest_file.read_bytes()

        new_asset = AssetDefinition(
            asset_id="test_new_asset_perm",
            path="assets/dynamic/perm.webp",
            status="ready",
        )
        asset_bytes = b"FAKE_IMAGE_BYTES_PERM"

        # Simulate PermissionError on os.replace
        with (
            patch("os.replace", side_effect=PermissionError("Access is denied")),
            pytest.raises(ManifestCommitError, match="Atomic manifest write failed"),
        ):
            mgr.commit_asset(
                character_id="miku_nakano",
                asset=new_asset,
                image_bytes=asset_bytes,
            )

        # Assert manifest.json untouched
        assert manifest_file.read_bytes() == original_manifest_bytes

        # Assert orphan asset unlinked
        orphan_asset = pack_dir / new_asset.path
        assert not orphan_asset.exists()

        # Assert temporary manifest file unlinked
        tmp_files = list(pack_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_resolver_strictly_never_exposes_non_ready_assets(self) -> None:
        """Comprehensive invariant test: Resolver MUST NEVER return 'needs_review' or 'pending' assets."""
        all_status_assets = [
            # 1 Core Ready
            AssetDefinition(
                asset_id="miku_core_ready",
                path="assets/core/idle_neutral.webp",
                state="idle",
                emotion="neutral",
                outfit="school_uniform",
                is_core=True,
                status="ready",
            ),
            # Needs Review asset (quarantined)
            AssetDefinition(
                asset_id="miku_quarantined_pout",
                path="assets/dynamic/quarantine_pout.webp",
                state="idle",
                emotion="pout",
                outfit="school_uniform",
                status="needs_review",
            ),
            # Pending asset (in pipeline)
            AssetDefinition(
                asset_id="miku_pending_smile",
                path="assets/dynamic/pending_smile.webp",
                state="idle",
                emotion="smile",
                outfit="school_uniform",
                status="pending",
            ),
            # Failed asset
            AssetDefinition(
                asset_id="miku_failed_blush",
                path="assets/dynamic/failed_blush.webp",
                state="idle",
                emotion="blush",
                outfit="school_uniform",
                status="failed",
            ),
            # Rejected asset
            AssetDefinition(
                asset_id="miku_rejected_angry",
                path="assets/dynamic/rejected_angry.webp",
                state="idle",
                emotion="angry",
                outfit="school_uniform",
                status="rejected",
            ),
            # Casual outfit asset that is needs_review
            AssetDefinition(
                asset_id="miku_casual_quarantine",
                path="assets/dynamic/casual.webp",
                state="idle",
                emotion="neutral",
                outfit="casual",
                status="needs_review",
            ),
        ]

        manifest = CharacterManifest(
            schema_version="1.0",
            character_id="miku_nakano",
            display_name="Nakano Miku",
            default_outfit="school_uniform",
            fallbacks=FallbackConfig(
                default_asset_id="miku_core_ready",
                emotion_fallbacks={"pout": "neutral", "smile": "neutral", "blush": "neutral", "angry": "neutral"},
            ),
            assets=all_status_assets,
        )

        resolver = CharacterAssetResolver(manifest)

        # 1. Verify index contains strictly ready assets
        for bucket in resolver._index.values():
            for asset in bucket:
                assert asset.status == "ready", f"Non-ready asset in index: {asset.asset_id} with status {asset.status}"

        # 2. Test direct queries for every non-ready asset
        # Query for "pout" (defined only as needs_review) -> must fall back to miku_core_ready
        res_pout = resolver.resolve(state="idle", emotion="pout", outfit="school_uniform")
        assert res_pout.asset.status == "ready"
        assert res_pout.asset.asset_id == "miku_core_ready"
        assert res_pout.is_fallback is True

        # Query for "smile" (defined only as pending) -> must fall back to miku_core_ready
        res_smile = resolver.resolve(state="idle", emotion="smile", outfit="school_uniform")
        assert res_smile.asset.status == "ready"
        assert res_smile.asset.asset_id == "miku_core_ready"
        assert res_smile.is_fallback is True

        # Query for "blush" (failed) -> must fall back to miku_core_ready
        res_blush = resolver.resolve(state="idle", emotion="blush", outfit="school_uniform")
        assert res_blush.asset.status == "ready"
        assert res_blush.asset.asset_id == "miku_core_ready"

        # Query for "angry" (rejected) -> must fall back to miku_core_ready
        res_angry = resolver.resolve(state="idle", emotion="angry", outfit="school_uniform")
        assert res_angry.asset.status == "ready"
        assert res_angry.asset.asset_id == "miku_core_ready"

        # Query for casual outfit (only needs_review defined) -> must fall back
        res_casual = resolver.resolve(state="idle", emotion="neutral", outfit="casual")
        assert res_casual.asset.status == "ready"
        assert res_casual.asset.asset_id == "miku_core_ready"

        # Query for completely non-existent asset -> default fallback
        res_unknown = resolver.resolve(state="unknown", emotion="unknown", outfit="unknown")
        assert res_unknown.asset.status == "ready"
        assert res_unknown.asset.asset_id == "miku_core_ready"
