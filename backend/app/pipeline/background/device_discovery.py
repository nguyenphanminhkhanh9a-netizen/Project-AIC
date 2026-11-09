"""DXGI hardware discovery and DirectML device resolution module.

Provides unified, robust enumeration of Direct3D 12 adapters, LUID extraction,
discrete GPU auto-detection (dGPU preference), and strict configuration validation.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import uuid
from ctypes import wintypes
from dataclasses import dataclass

from app.pipeline.background.isnet_directml_provider import DirectMLInitializationError

logger = logging.getLogger(__name__)

# Known PCI Vendor IDs
VENDOR_NVIDIA = 0x10DE
VENDOR_AMD = 0x1002
VENDOR_INTEL = 0x8086
VENDOR_MICROSOFT = 0x1414

# DXGI Flags
DXGI_ADAPTER_FLAG_NONE = 0
DXGI_ADAPTER_FLAG_REMOTE = 1
DXGI_ADAPTER_FLAG_SOFTWARE = 2


class DirectMLDeviceError(DirectMLInitializationError):
    """Base exception for DirectML device resolution errors."""


class DirectMLDeviceNotFoundError(DirectMLDeviceError):
    """Raised when configured or requested DirectML adapter does not exist."""


class DirectMLDeviceConfigurationError(DirectMLDeviceError):
    """Raised when DirectML device configuration is invalid."""


class DirectMLDeviceDiscoveryError(DirectMLDeviceError):
    """Raised when DXGI adapter discovery fails and no explicit device ID was provided."""


@dataclass(frozen=True)
class DXGIAdapterInfo:
    """Represents metadata for a discovered DXGI display adapter."""

    index: int
    description: str
    dedicated_vram_bytes: int
    dedicated_vram_mb: int
    shared_ram_mb: int
    vendor_id: int
    device_id: int
    flags: int
    luid: int

    @property
    def is_software(self) -> bool:
        """True if adapter is a CPU software rasterizer (WARP / Basic Render Driver)."""
        return bool(self.flags & DXGI_ADAPTER_FLAG_SOFTWARE)

    @property
    def is_discrete(self) -> bool:
        """Heuristic check for dedicated discrete GPU (high VRAM or discrete vendor)."""
        if self.is_software:
            return False
        if self.vendor_id == VENDOR_NVIDIA:
            return True
        if self.vendor_id == VENDOR_AMD and self.dedicated_vram_mb >= 1024:
            return True
        if self.vendor_id == VENDOR_INTEL and self.dedicated_vram_mb >= 2048:
            return True
        return self.dedicated_vram_mb > 1024


def enumerate_dxgi_adapters() -> list[DXGIAdapterInfo]:
    """Enumerates all DXGI adapters using COM IDXGIFactory1::EnumAdapters1 on Windows.

    Returns:
        List of DXGIAdapterInfo objects. Empty list if non-Windows.
    """
    adapters: list[DXGIAdapterInfo] = []
    if sys.platform != "win32":
        return adapters

    try:
        class LUID(ctypes.Structure):
            _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

        class DXGI_ADAPTER_DESC1(ctypes.Structure):
            _fields_ = [
                ("Description", wintypes.WCHAR * 128),
                ("VendorId", wintypes.UINT),
                ("DeviceId", wintypes.UINT),
                ("SubSysId", wintypes.UINT),
                ("Revision", wintypes.UINT),
                ("DedicatedVideoMemory", ctypes.c_size_t),
                ("DedicatedSystemMemory", ctypes.c_size_t),
                ("SharedSystemMemory", ctypes.c_size_t),
                ("AdapterLuid", LUID),
                ("Flags", wintypes.UINT),
            ]

        dxgi = ctypes.oledll.dxgi  # type: ignore[attr-defined]
        factory = ctypes.c_void_p()
        iid_idxgifactory1 = uuid.UUID("{770aae78-f26f-4dba-a829-253c83d1b387}")
        riid = (ctypes.c_byte * 16)(*iid_idxgifactory1.bytes_le)
        hr = dxgi.CreateDXGIFactory1(riid, ctypes.byref(factory))
        if hr != 0 or not factory.value:
            raise OSError(f"CreateDXGIFactory1 failed with HRESULT 0x{hr:08X}")

        vtable = ctypes.cast(
            ctypes.cast(factory.value, ctypes.POINTER(ctypes.c_void_p))[0],
            ctypes.POINTER(ctypes.c_void_p),
        )
        enum_adapters1 = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p)
        )(vtable[12])
        get_desc1_proto = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(DXGI_ADAPTER_DESC1)
        )

        idx = 0
        while True:
            adapter = ctypes.c_void_p()
            if enum_adapters1(factory, idx, ctypes.byref(adapter)) != 0:
                break
            if adapter.value is None:
                break
            v = ctypes.cast(
                ctypes.cast(adapter.value, ctypes.POINTER(ctypes.c_void_p))[0],
                ctypes.POINTER(ctypes.c_void_p),
            )
            desc = DXGI_ADAPTER_DESC1()
            get_desc1_proto(v[10])(adapter, ctypes.byref(desc))

            vram_mb = int(desc.DedicatedVideoMemory // (1024 * 1024))
            shared_mb = int(desc.SharedSystemMemory // (1024 * 1024))
            luid_val = (desc.AdapterLuid.HighPart << 32) | desc.AdapterLuid.LowPart

            adapters.append(
                DXGIAdapterInfo(
                    index=idx,
                    description=str(desc.Description),
                    dedicated_vram_bytes=int(desc.DedicatedVideoMemory),
                    dedicated_vram_mb=vram_mb,
                    shared_ram_mb=shared_mb,
                    vendor_id=int(desc.VendorId),
                    device_id=int(desc.DeviceId),
                    flags=int(desc.Flags),
                    luid=luid_val,
                )
            )
            idx += 1
    except Exception as exc:
        logger.warning("DXGI adapter enumeration failed: %s", exc)
        raise DirectMLDeviceDiscoveryError(f"Failed to enumerate DXGI adapters: {exc}") from exc

    return adapters


def resolve_directml_adapter(config_id: int | None = None) -> DXGIAdapterInfo:
    """Resolves the DXGIAdapterInfo to use for DirectML execution.

    Precedence Hierarchy:
    1. Explicit config_id (if passed and not None).
    2. Environment variable AIC_PIPELINE_DIRECTML_DEVICE_ID (if set and non-empty).
    3. Dynamic auto-detection:
       - Prefer discrete NVIDIA GPU (VendorId 0x10DE).
       - Prefer discrete AMD GPU (VendorId 0x1002, VRAM >= 1024MB).
       - Prefer discrete Intel GPU (VendorId 0x8086, VRAM >= 2048MB).
       - Single hardware GPU: if only 1 non-software adapter exists, select it.
    """
    adapters: list[DXGIAdapterInfo] | None = None
    discovery_error: Exception | None = None

    try:
        adapters = enumerate_dxgi_adapters()
    except (DirectMLDeviceDiscoveryError, OSError) as exc:
        discovery_error = exc

    # Tier 1: Explicit config_id
    if config_id is not None:
        if config_id < 0:
            raise DirectMLDeviceConfigurationError(
                f"Invalid directml_device_id: {config_id} (must be >= 0)"
            )
        if adapters is not None and len(adapters) > 0:
            for a in adapters:
                if a.index == config_id:
                    if a.is_software:
                        raise DirectMLDeviceConfigurationError(
                            f"Configured directml_device_id {config_id} ({a.description}) is a software adapter. "
                            f"DirectML requires hardware GPU acceleration."
                        )
                    return a
            avail_str = ", ".join(
                f"[Index {a.index}: {a.description}]" for a in adapters if not a.is_software
            )
            raise DirectMLDeviceNotFoundError(
                f"Configured directml_device_id {config_id} does not exist. Available hardware adapters: {avail_str}. "
                f"Silent CPU fallback is rejected."
            )
        if discovery_error is not None:
            logger.warning(
                "DXGI discovery unavailable; proceeding with configured device_id %d without hardware check",
                config_id,
            )
            return DXGIAdapterInfo(
                index=config_id,
                description=f"DirectML Adapter {config_id} (Unverified)",
                dedicated_vram_bytes=0,
                dedicated_vram_mb=0,
                shared_ram_mb=0,
                vendor_id=0,
                device_id=0,
                flags=0,
                luid=0,
            )

    # Tier 2: Environment Variable override
    env_val = os.environ.get("AIC_PIPELINE_DIRECTML_DEVICE_ID")
    if env_val is not None and env_val.strip() != "":
        try:
            target_id = int(env_val.strip())
        except ValueError as val_err:
            raise DirectMLDeviceConfigurationError(
                f"Environment variable AIC_PIPELINE_DIRECTML_DEVICE_ID='{env_val}' is not a valid integer adapter index."
            ) from val_err

        if target_id < 0:
            raise DirectMLDeviceConfigurationError(
                f"AIC_PIPELINE_DIRECTML_DEVICE_ID must be >= 0, got {target_id}"
            )

        if adapters is not None and len(adapters) > 0:
            for a in adapters:
                if a.index == target_id:
                    if a.is_software:
                        raise DirectMLDeviceConfigurationError(
                            f"AIC_PIPELINE_DIRECTML_DEVICE_ID={target_id} ({a.description}) is a software adapter."
                        )
                    return a
            avail_str = ", ".join(
                f"[Index {a.index}: {a.description}]" for a in adapters if not a.is_software
            )
            raise DirectMLDeviceNotFoundError(
                f"DirectML device_id {target_id} from AIC_PIPELINE_DIRECTML_DEVICE_ID does not exist. Available adapters: {avail_str}. "
                f"Silent CPU fallback is rejected."
            )
        if discovery_error is not None:
            logger.warning(
                "DXGI discovery unavailable; using env var device_id %d",
                target_id,
            )
            return DXGIAdapterInfo(
                index=target_id,
                description=f"DirectML Adapter {target_id} (Unverified)",
                dedicated_vram_bytes=0,
                dedicated_vram_mb=0,
                shared_ram_mb=0,
                vendor_id=0,
                device_id=0,
                flags=0,
                luid=0,
            )

    # Tier 3: Auto-detection
    if discovery_error is not None:
        raise DirectMLDeviceDiscoveryError(
            f"Cannot auto-detect DirectML device because DXGI adapter discovery failed: {discovery_error}. "
            f"Please specify 'directml_device_id' or set 'AIC_PIPELINE_DIRECTML_DEVICE_ID'."
        ) from discovery_error

    if not adapters:
        raise DirectMLDeviceNotFoundError(
            "No graphics adapters discovered on the system. DirectML execution provider requires a DirectX 12 GPU."
        )

    hw_adapters = [a for a in adapters if not a.is_software]
    if not hw_adapters:
        raise DirectMLDeviceNotFoundError(
            "No hardware graphics adapters found (only software/WARP adapters detected). DirectML acceleration rejected."
        )

    # Case: Single hardware GPU
    if len(hw_adapters) == 1:
        selected = hw_adapters[0]
        logger.info(
            "Auto-detected single hardware GPU for DirectML: Index %d (%s, %d MB VRAM)",
            selected.index,
            selected.description,
            selected.dedicated_vram_mb,
        )
        return selected

    # Case: Multi-GPU (e.g. Intel UHD + NVIDIA RTX)
    nvidia_adapters = [a for a in hw_adapters if a.vendor_id == VENDOR_NVIDIA]
    if nvidia_adapters:
        best_nvidia = max(nvidia_adapters, key=lambda a: a.dedicated_vram_mb)
        logger.info(
            "Auto-detected discrete NVIDIA GPU for DirectML: Index %d (%s, %d MB VRAM)",
            best_nvidia.index,
            best_nvidia.description,
            best_nvidia.dedicated_vram_mb,
        )
        return best_nvidia

    amd_discrete = [a for a in hw_adapters if a.vendor_id == VENDOR_AMD and a.is_discrete]
    if amd_discrete:
        best_amd = max(amd_discrete, key=lambda a: a.dedicated_vram_mb)
        logger.info(
            "Auto-detected discrete AMD GPU for DirectML: Index %d (%s, %d MB VRAM)",
            best_amd.index,
            best_amd.description,
            best_amd.dedicated_vram_mb,
        )
        return best_amd

    intel_discrete = [a for a in hw_adapters if a.vendor_id == VENDOR_INTEL and a.is_discrete]
    if intel_discrete:
        best_intel = max(intel_discrete, key=lambda a: a.dedicated_vram_mb)
        return best_intel

    best_vram = max(hw_adapters, key=lambda a: a.dedicated_vram_mb)
    if best_vram.dedicated_vram_mb > 512:
        return best_vram

    return hw_adapters[0]


def get_directml_device_id(config_id: int | None = None) -> int:
    """Interface Contract: Returns the resolved integer DirectML device ID."""
    adapter = resolve_directml_adapter(config_id)
    return adapter.index
