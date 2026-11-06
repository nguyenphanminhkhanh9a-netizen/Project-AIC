"""Character pack domain models, manifest schema, and alignment metadata.

Corresponds to Section 7.4 of docs/AIC_ARCHITECTURE_v0.5.md and Milestone M0 / Task 0.4.
Fully dynamic, extensible for any character without hardcoded outfit or emotion values.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class AnchorType(str, Enum):
    """Anchor reference type for sprite positioning on screen."""

    BOTTOM_CENTER = "bottom_center"  # Full body standing, pinned to floor/bottom
    CENTER = "center"                # Symmetric centered anchor
    EYE_LEVEL = "eye_level"          # Close-up/bust-up anchored on eye/facial line
    WAIST_LEVEL = "waist_level"      # Half-body / waist-up anchor
    CUSTOM = "custom"                # Custom coordinate anchor


class SpriteAlignment(BaseModel):
    """Viewport alignment and anchor point metadata for seamless crossfading."""

    anchor_type: AnchorType = Field(
        default=AnchorType.BOTTOM_CENTER,
        description="Semantic anchor category",
    )
    anchor_x: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Normalized horizontal anchor (0.0 = left, 1.0 = right)",
    )
    anchor_y: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Normalized vertical anchor (0.0 = top, 1.0 = bottom)",
    )
    focal_x: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Normalized horizontal focal point (e.g. eye center)",
    )
    focal_y: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Normalized vertical focal point for anti-jittering alignment",
    )
    display_scale: float = Field(
        default=1.0,
        gt=0.0,
        description="Uniform display scale factor for viewport sizing",
    )
    viewport_offset_x: int = Field(
        default=0,
        description="Pixel offset compensation on X axis",
    )
    viewport_offset_y: int = Field(
        default=0,
        description="Pixel offset compensation on Y axis",
    )
    bounding_box: tuple[int, int, int, int] | None = Field(
        default=None,
        description="Tight alpha bounding box (left, top, right, bottom) if computed",
    )


class Resolution(BaseModel):
    """Pixel dimension of asset image."""

    width: int = Field(gt=0, description="Image width in pixels")
    height: int = Field(gt=0, description="Image height in pixels")


AssetStatus = Literal[
    "ready",
    "processing",
    "pending",
    "needs_review",
    "failed",
    "rejected",
]


class AssetDefinition(BaseModel):
    """Specification of a single character visual asset in the manifest."""

    asset_id: str = Field(min_length=1, description="Unique asset identifier in this pack")
    path: str = Field(min_length=1, description="Relative path from pack root to image file")
    format: str = Field(default="webp", description="Image format: webp, png, svg")
    state: str = Field(default="idle", description="Character state: idle, speaking, listening")
    emotion: str = Field(default="neutral", description="Emotion classification label")
    intensity: float = Field(default=0.5, ge=0.0, le=1.0, description="Emotion intensity factor")
    outfit: str = Field(default="default", description="Outfit category identifier")
    pose: str = Field(default="standing", description="Pose identifier: standing, sitting, half_body")
    action: str = Field(default="idle", description="Action gesture: idle, waving, pointing")
    asset_type: str = Field(default="sprite_full", description="Type: sprite_full, sprite_bust, background")
    resolution: Resolution = Field(
        default_factory=lambda: Resolution(width=1024, height=1536),
        description="Native resolution of the asset",
    )
    anchor: SpriteAlignment = Field(
        default_factory=SpriteAlignment,
        description="Alignment anchor and focal point metadata",
    )
    is_core: bool = Field(
        default=False,
        description="Whether this is a core bundled asset (immutable, never evicted)",
    )
    status: AssetStatus = Field(
        default="ready",
        description="Readiness status for resolver consumption",
    )
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    priority: int = Field(default=100, description="Higher priority selected when matching")


class CompatibilityGroup(BaseModel):
    """Defines valid pose and outfit transitions with fallback rules."""

    display_name: str = Field(description="Human readable name of outfit/pose group")
    allowed_poses: list[str] = Field(default_factory=list, description="Poses valid with this outfit")
    fallback_outfit: str | None = Field(
        default=None,
        description="Fallback outfit ID if specific asset is missing in this outfit",
    )


class FallbackConfig(BaseModel):
    """Dynamic fallback rules declared directly in manifest."""

    default_asset_id: str = Field(
        min_length=1,
        description="Absolute final fallback asset ID if no match is found",
    )
    emotion_fallbacks: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping from requested emotion to fallback emotion, e.g. {'pout': 'neutral'}",
    )
    state_fallbacks: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping from state to fallback state, e.g. {'speaking': 'idle'}",
    )


class CharacterManifest(BaseModel):
    """Root configuration contract for a Character Pack.

    Section 7.4 of AIC_ARCHITECTURE_v0.5.md.
    Entirely dynamic and data-driven; supports any character without code modifications.
    """

    schema_version: str = Field(default="1.0", description="Manifest schema version")
    character_id: str = Field(min_length=1, description="Unique character identifier")
    display_name: str = Field(min_length=1, description="Display name of the character")
    default_locale: str = Field(default="ja-JP", description="Default spoken language locale")
    default_outfit: str = Field(default="default", description="Default outfit group ID")
    description: str = Field(default="", description="Character background description")
    compatibility_groups: dict[str, CompatibilityGroup] = Field(
        default_factory=dict,
        description="Outfit and pose compatibility definitions with dynamic fallbacks",
    )
    assets: list[AssetDefinition] = Field(
        default_factory=list,
        description="Complete list of visual assets declared in this pack",
    )
    fallbacks: FallbackConfig = Field(
        description="Dynamic fallback rules for emotions, states, and default asset",
    )
