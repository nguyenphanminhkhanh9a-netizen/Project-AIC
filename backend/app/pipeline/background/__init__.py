"""Background removal providers, image operations, and matting services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.pipeline.background.image_ops import (
    LetterboxMeta,
    apply_soft_alpha_ramp,
    letterbox_preprocess,
    postprocess_mask,
)
from app.pipeline.background.isnet_provider import ISNetONNXProvider
from app.pipeline.background.mock_provider import MockBackgroundRemovalProvider
from app.pipeline.config import PipelineConfig, pipeline_config

if TYPE_CHECKING:
    from app.domain.pipeline import BackgroundRemovalProvider


def get_background_removal_provider(
    config: PipelineConfig | None = None,
) -> BackgroundRemovalProvider:
    """Factory creating appropriate BackgroundRemovalProvider based on configuration."""
    cfg = config if config is not None else pipeline_config
    if cfg.use_mock_bg_provider:
        return MockBackgroundRemovalProvider()
    return ISNetONNXProvider(config=cfg)


__all__ = [
    "ISNetONNXProvider",
    "LetterboxMeta",
    "MockBackgroundRemovalProvider",
    "apply_soft_alpha_ramp",
    "get_background_removal_provider",
    "letterbox_preprocess",
    "postprocess_mask",
]
