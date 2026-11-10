"""Background removal providers, image operations, and matting services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.pipeline.background.image_ops import (
    LetterboxMeta,
    apply_soft_alpha_ramp,
    letterbox_preprocess,
    postprocess_mask,
)
from app.pipeline.background.isnet_directml_provider import (
    DirectMLConcurrencyError,
    DirectMLError,
    DirectMLInitializationError,
    DirectMLNotAvailableError,
    ISNetDirectMLProvider,
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

    provider_name = cfg.onnx_execution_provider.strip().lower()
    if provider_name in ("directml", "dml"):
        return ISNetDirectMLProvider(config=cfg)
    elif provider_name in ("cpu", "cpu_mock", ""):
        return ISNetONNXProvider(config=cfg)
    else:
        raise ValueError(
            f"Unsupported execution provider '{cfg.onnx_execution_provider}'. "
            f"Supported options: 'cpu', 'directml'."
        )


__all__ = [
    "DirectMLConcurrencyError",
    "DirectMLError",
    "DirectMLInitializationError",
    "DirectMLNotAvailableError",
    "ISNetDirectMLProvider",
    "ISNetONNXProvider",
    "LetterboxMeta",
    "MockBackgroundRemovalProvider",
    "apply_soft_alpha_ramp",
    "get_background_removal_provider",
    "letterbox_preprocess",
    "postprocess_mask",
]
