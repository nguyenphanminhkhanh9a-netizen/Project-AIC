"""Unit tests for DXGI device discovery and DirectML adapter resolution."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.pipeline.background.device_discovery import (
    DXGI_ADAPTER_FLAG_NONE,
    DXGI_ADAPTER_FLAG_SOFTWARE,
    VENDOR_INTEL,
    VENDOR_MICROSOFT,
    VENDOR_NVIDIA,
    DirectMLDeviceConfigurationError,
    DirectMLDeviceDiscoveryError,
    DirectMLDeviceNotFoundError,
    DXGIAdapterInfo,
    get_directml_device_id,
    resolve_directml_adapter,
)


def _make_adapter(
    index: int,
    description: str,
    vendor_id: int,
    dedicated_vram_mb: int = 4096,
    flags: int = DXGI_ADAPTER_FLAG_NONE,
    device_id: int = 0x1234,
) -> DXGIAdapterInfo:
    return DXGIAdapterInfo(
        index=index,
        description=description,
        dedicated_vram_bytes=dedicated_vram_mb * 1024 * 1024,
        dedicated_vram_mb=dedicated_vram_mb,
        shared_ram_mb=8192,
        vendor_id=vendor_id,
        device_id=device_id,
        flags=flags,
        luid=0x1000 + index,
    )


def test_dual_gpu_intel_and_nvidia_selects_nvidia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 1: System with Intel iGPU (0) and NVIDIA dGPU (1) automatically selects NVIDIA dGPU."""
    monkeypatch.delenv("AIC_PIPELINE_DIRECTML_DEVICE_ID", raising=False)

    mock_adapters = [
        _make_adapter(0, "Intel(R) UHD Graphics", VENDOR_INTEL, dedicated_vram_mb=128),
        _make_adapter(1, "NVIDIA GeForce RTX 4050 Laptop GPU", VENDOR_NVIDIA, dedicated_vram_mb=5921),
        _make_adapter(2, "Microsoft Basic Render Driver", VENDOR_MICROSOFT, dedicated_vram_mb=0, flags=DXGI_ADAPTER_FLAG_SOFTWARE),
    ]

    with patch("app.pipeline.background.device_discovery.enumerate_dxgi_adapters", return_value=mock_adapters):
        selected = resolve_directml_adapter(config_id=None)
        assert selected.index == 1
        assert selected.vendor_id == VENDOR_NVIDIA
        assert "RTX 4050" in selected.description
        assert get_directml_device_id(config_id=None) == 1


def test_single_intel_igpu_selects_intel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 2: System with only Intel integrated GPU selects the Intel adapter."""
    monkeypatch.delenv("AIC_PIPELINE_DIRECTML_DEVICE_ID", raising=False)

    mock_adapters = [
        _make_adapter(0, "Intel(R) Iris(R) Xe Graphics", VENDOR_INTEL, dedicated_vram_mb=128),
        _make_adapter(1, "Microsoft Basic Render Driver", VENDOR_MICROSOFT, dedicated_vram_mb=0, flags=DXGI_ADAPTER_FLAG_SOFTWARE),
    ]

    with patch("app.pipeline.background.device_discovery.enumerate_dxgi_adapters", return_value=mock_adapters):
        selected = resolve_directml_adapter(config_id=None)
        assert selected.index == 0
        assert selected.vendor_id == VENDOR_INTEL
        assert get_directml_device_id(config_id=None) == 0


def test_single_discrete_gpu_selects_index_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 3: Single GPU desktop PC with NVIDIA as Adapter 0 selects index 0."""
    monkeypatch.delenv("AIC_PIPELINE_DIRECTML_DEVICE_ID", raising=False)

    mock_adapters = [
        _make_adapter(0, "NVIDIA GeForce RTX 4070", VENDOR_NVIDIA, dedicated_vram_mb=12288),
        _make_adapter(1, "Microsoft Basic Render Driver", VENDOR_MICROSOFT, dedicated_vram_mb=0, flags=DXGI_ADAPTER_FLAG_SOFTWARE),
    ]

    with patch("app.pipeline.background.device_discovery.enumerate_dxgi_adapters", return_value=mock_adapters):
        selected = resolve_directml_adapter(config_id=None)
        assert selected.index == 0
        assert selected.vendor_id == VENDOR_NVIDIA
        assert get_directml_device_id(config_id=None) == 0


def test_env_var_override_and_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 4: Environment variable override behavior and precedence rules."""
    mock_adapters = [
        _make_adapter(0, "Intel(R) UHD Graphics", VENDOR_INTEL, dedicated_vram_mb=128),
        _make_adapter(1, "NVIDIA GeForce RTX 4050 Laptop GPU", VENDOR_NVIDIA, dedicated_vram_mb=5921),
    ]

    with patch("app.pipeline.background.device_discovery.enumerate_dxgi_adapters", return_value=mock_adapters):
        # 4A: Valid override to adapter 0
        monkeypatch.setenv("AIC_PIPELINE_DIRECTML_DEVICE_ID", "0")
        assert get_directml_device_id(config_id=None) == 0

        # 4B: Valid override to adapter 1
        monkeypatch.setenv("AIC_PIPELINE_DIRECTML_DEVICE_ID", "1")
        assert get_directml_device_id(config_id=None) == 1

        # 4C: Malformed non-integer string
        monkeypatch.setenv("AIC_PIPELINE_DIRECTML_DEVICE_ID", "not_an_int")
        with pytest.raises(DirectMLDeviceConfigurationError) as exc_4c:
            resolve_directml_adapter(config_id=None)
        assert "not a valid integer" in str(exc_4c.value)

        # 4D: Negative integer
        monkeypatch.setenv("AIC_PIPELINE_DIRECTML_DEVICE_ID", "-5")
        with pytest.raises(DirectMLDeviceConfigurationError) as exc_4d:
            resolve_directml_adapter(config_id=None)
        assert "must be >= 0" in str(exc_4d.value)

        # 4E: Explicit config_id takes precedence over env var
        monkeypatch.setenv("AIC_PIPELINE_DIRECTML_DEVICE_ID", "0")
        assert get_directml_device_id(config_id=1) == 1


def test_device_id_not_found_or_software_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 5: Requesting non-existent or software adapter raises explicit error."""
    monkeypatch.delenv("AIC_PIPELINE_DIRECTML_DEVICE_ID", raising=False)

    mock_adapters = [
        _make_adapter(0, "Intel(R) UHD Graphics", VENDOR_INTEL, dedicated_vram_mb=128),
        _make_adapter(1, "NVIDIA GeForce RTX 4050 Laptop GPU", VENDOR_NVIDIA, dedicated_vram_mb=5921),
        _make_adapter(2, "Microsoft Basic Render Driver", VENDOR_MICROSOFT, dedicated_vram_mb=0, flags=DXGI_ADAPTER_FLAG_SOFTWARE),
    ]

    with patch("app.pipeline.background.device_discovery.enumerate_dxgi_adapters", return_value=mock_adapters):
        # 5A: Out of bounds index
        with pytest.raises(DirectMLDeviceNotFoundError) as exc_5a:
            resolve_directml_adapter(config_id=99)
        assert "does not exist" in str(exc_5a.value)
        assert "[Index 0: Intel(R) UHD Graphics]" in str(exc_5a.value)
        assert "[Index 1: NVIDIA GeForce RTX 4050 Laptop GPU]" in str(exc_5a.value)

        # 5B: Software adapter explicitly selected
        with pytest.raises(DirectMLDeviceConfigurationError) as exc_5b:
            resolve_directml_adapter(config_id=2)
        assert "is a software adapter" in str(exc_5b.value)


def test_dxgi_discovery_failure_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 6: Discovery failure raises DirectMLDeviceDiscoveryError for auto-detect,
    or falls back gracefully for explicit ID in offline/mock testing."""
    monkeypatch.delenv("AIC_PIPELINE_DIRECTML_DEVICE_ID", raising=False)

    with patch(
        "app.pipeline.background.device_discovery.enumerate_dxgi_adapters",
        side_effect=DirectMLDeviceDiscoveryError("CreateDXGIFactory1 failed with HRESULT 0x887A0002"),
    ):
        # 6A: Auto-detection without configured ID raises DirectMLDeviceDiscoveryError
        with pytest.raises(DirectMLDeviceDiscoveryError) as exc_6a:
            resolve_directml_adapter(config_id=None)
        assert "Cannot auto-detect DirectML device because DXGI adapter discovery failed" in str(exc_6a.value)

        # 6B: Explicit configured ID provided when DXGI discovery fails allows mock testing
        unverified = resolve_directml_adapter(config_id=1)
        assert unverified.index == 1
        assert "Unverified" in unverified.description
