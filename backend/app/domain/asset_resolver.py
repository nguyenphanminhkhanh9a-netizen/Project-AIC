"""Character asset resolver with in-memory dynamic fallback resolution.

Implements Section 7.4 of AIC_ARCHITECTURE_v0.5.md and M0 Task 0.4.
Provides sub-millisecond in-memory lookup with decoupled notification for missing assets.
Zero hardcoding: all fallback hierarchies and asset groupings are strictly data-driven
from the CharacterManifest.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.character import AssetDefinition, CharacterManifest

logger = logging.getLogger(__name__)

MatchStrategy = Literal[
    "exact",
    "emotion_fallback",
    "state_fallback",
    "outfit_fallback",
    "default_fallback",
]


class MissingAssetRequest(BaseModel):
    """Notification payload when an exact asset match is not present in the pack."""

    character_id: str = Field(description="Target character ID")
    state: str = Field(description="Requested state")
    emotion: str = Field(description="Requested emotion")
    outfit: str = Field(description="Requested outfit")


class ResolvedAsset(BaseModel):
    """Result of an asset resolution lookup including traceability metadata."""

    asset: AssetDefinition = Field(description="Selected asset definition")
    match_strategy: MatchStrategy = Field(description="Strategy that produced this asset")
    is_fallback: bool = Field(description="True if not an exact match on (outfit, state, emotion)")
    requested_state: str = Field(description="Originally requested state")
    requested_emotion: str = Field(description="Originally requested emotion")
    requested_outfit: str = Field(description="Originally requested outfit")


MissingAssetCallback = Callable[[MissingAssetRequest], None]


class CharacterAssetResolver:
    """Fast, in-memory asset resolver for a single character pack.

    Operates purely in memory. Never blocks on disk I/O, network requests,
    or background workers.
    """

    def __init__(
        self,
        manifest: CharacterManifest,
        on_missing_asset: MissingAssetCallback | None = None,
    ) -> None:
        self.manifest = manifest
        self._on_missing_asset = on_missing_asset
        self._assets_by_id: dict[str, AssetDefinition] = {}
        # Key: (outfit, state, emotion) -> list of AssetDefinition sorted by priority desc
        self._index: dict[tuple[str, str, str], list[AssetDefinition]] = defaultdict(list)
        self._build_index()

    def _build_index(self) -> None:
        """Indexes manifest assets in memory for O(1) multi-key lookup."""
        for asset in self.manifest.assets:
            self._assets_by_id[asset.asset_id] = asset
            # Only index assets marked as "ready" for display resolution
            if asset.status == "ready":
                key = (asset.outfit, asset.state, asset.emotion)
                self._index[key].append(asset)

        # Sort each bucket by descending priority so the highest priority is first
        for key in self._index:
            self._index[key].sort(key=lambda a: a.priority, reverse=True)

    def _find_in_bucket(self, outfit: str, state: str, emotion: str) -> AssetDefinition | None:
        """Finds highest-priority ready asset matching exact (outfit, state, emotion)."""
        bucket = self._index.get((outfit, state, emotion))
        if bucket:
            return bucket[0]
        return None

    def resolve(
        self,
        state: str,
        emotion: str,
        outfit: str | None = None,
    ) -> ResolvedAsset:
        """Resolves visual asset with strict dynamic fallback sequence.

        Lookup order (data-driven entirely from manifest):
        1. Exact match: (outfit, state, emotion)
        2. Emotion fallback in active outfit: manifest.fallbacks.emotion_fallbacks.get(emotion)
        3. State fallback in active outfit: manifest.fallbacks.state_fallbacks.get(state)
        4. Outfit fallback: manifest.compatibility_groups[outfit].fallback_outfit
        5. Absolute default asset: manifest.fallbacks.default_asset_id

        If not an exact match, invokes decoupled on_missing_asset callback if provided.
        """
        active_outfit = outfit or self.manifest.default_outfit
        match_strategy: MatchStrategy | None = None
        selected: AssetDefinition | None = None

        # Level 1: Exact match
        selected = self._find_in_bucket(active_outfit, state, emotion)
        if selected:
            match_strategy = "exact"

        # Level 2: Emotion fallback in active outfit
        if not selected and emotion in self.manifest.fallbacks.emotion_fallbacks:
            fallback_emotion = self.manifest.fallbacks.emotion_fallbacks[emotion]
            selected = self._find_in_bucket(active_outfit, state, fallback_emotion)
            if selected:
                match_strategy = "emotion_fallback"

        # Level 3: State fallback in active outfit (with original emotion or fallback emotion)
        if not selected and state in self.manifest.fallbacks.state_fallbacks:
            fallback_state = self.manifest.fallbacks.state_fallbacks[state]
            # Try with requested emotion
            selected = self._find_in_bucket(active_outfit, fallback_state, emotion)
            if selected:
                match_strategy = "state_fallback"
            elif emotion in self.manifest.fallbacks.emotion_fallbacks:
                # Try with fallback emotion as well
                fallback_emotion = self.manifest.fallbacks.emotion_fallbacks[emotion]
                selected = self._find_in_bucket(active_outfit, fallback_state, fallback_emotion)
                if selected:
                    match_strategy = "state_fallback"

        # Level 4: Outfit fallback chain
        if not selected and active_outfit in self.manifest.compatibility_groups:
            visited_outfits = {active_outfit}
            curr_outfit: str | None = self.manifest.compatibility_groups[active_outfit].fallback_outfit
            while curr_outfit and curr_outfit not in visited_outfits:
                visited_outfits.add(curr_outfit)
                # 4a. Exact in fallback outfit
                selected = self._find_in_bucket(curr_outfit, state, emotion)
                if selected:
                    match_strategy = "outfit_fallback"
                    break
                # 4b. Emotion fallback in fallback outfit
                if emotion in self.manifest.fallbacks.emotion_fallbacks:
                    fb_emo = self.manifest.fallbacks.emotion_fallbacks[emotion]
                    selected = self._find_in_bucket(curr_outfit, state, fb_emo)
                    if selected:
                        match_strategy = "outfit_fallback"
                        break
                # Advance outfit fallback chain
                if curr_outfit in self.manifest.compatibility_groups:
                    curr_outfit = self.manifest.compatibility_groups[curr_outfit].fallback_outfit
                else:
                    curr_outfit = None

        # Level 5: Default asset fallback
        if not selected:
            default_id = self.manifest.fallbacks.default_asset_id
            selected = self._assets_by_id.get(default_id)
            if not selected:
                raise ValueError(
                    f"Default asset '{default_id}' defined in manifest.fallbacks.default_asset_id "
                    f"was not found in assets list for character '{self.manifest.character_id}'."
                )
            match_strategy = "default_fallback"

        assert match_strategy is not None

        is_fallback = match_strategy != "exact"

        # Fire decoupled notification asynchronously/safely without throwing or blocking
        if is_fallback and self._on_missing_asset:
            try:
                self._on_missing_asset(
                    MissingAssetRequest(
                        character_id=self.manifest.character_id,
                        state=state,
                        emotion=emotion,
                        outfit=active_outfit,
                    )
                )
            except Exception as e:  # noqa: BLE001 - Resolver must never crash on decoupled callback error
                logger.warning("Error in on_missing_asset callback: %s", e)

        return ResolvedAsset(
            asset=selected,
            match_strategy=match_strategy,
            is_fallback=is_fallback,
            requested_state=state,
            requested_emotion=emotion,
            requested_outfit=active_outfit,
        )
