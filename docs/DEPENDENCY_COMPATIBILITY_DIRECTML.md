# Dependency Compatibility Guide: ONNX Runtime & DirectML on Windows

This document details the dependency architecture, package coexistence, installation workflows, and runtime fallback behavior for ONNX Runtime CPU and DirectML GPU execution providers in Project AIC.

---

## 1. Problem Statement & Architecture

In Python on Windows, the base package `onnxruntime` (CPU execution) and `onnxruntime-directml` (DirectX 12 DirectML GPU execution) share the same top-level Python namespace: `onnxruntime`.

If two packages providing the same namespace are installed naively in an unpinned or unmanaged environment, package manager conflicts or library collisions (`onnxruntime_pybind11_state.pyd`) can occur, potentially causing silent fallback to CPU or broken provider enumeration.

Project AIC standardizes this compatibility using `pyproject.toml` dependency separation and strict pre-flight execution provider validation.

---

## 2. Dependency Specification (`backend/pyproject.toml`)

Project AIC defines a clean separation between base CPU dependencies and the DirectML acceleration extra:

```toml
[project]
name = "project-aic-backend"
dependencies = [
    # ...
    "onnxruntime>=1.19.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]
directml = [
    "onnxruntime-directml>=1.19.0",
]
```

### Installation Modes:

1. **CPU-Only / CI / Offline Mode** (Default):
   ```bash
   uv sync --project backend
   ```
   Installs `onnxruntime` with `CPUExecutionProvider`. Suitable for headless CI, Linux/macOS development, and non-GPU environments.

2. **DirectML GPU-Accelerated Mode** (Windows with DirectX 12 dGPU / iGPU):
   ```bash
   uv sync --project backend --extra directml
   ```
   Installs `onnxruntime-directml`, enabling `DmlExecutionProvider` alongside `CPUExecutionProvider`.

---

## 3. Host Environment Verification

On the development and benchmark system (Windows 11 with NVIDIA GeForce RTX 4050 6GB Laptop GPU + Intel UHD Graphics):

| Package | Version | Provider Exported |
|---|---|---|
| `onnxruntime` | 1.31.1 | `CPUExecutionProvider` |
| `onnxruntime-directml` | 1.24.4 | `DmlExecutionProvider`, `CPUExecutionProvider` |

### Provider Enumeration Verification:
```powershell
uv run --project backend python -c "import onnxruntime as ort; print(ort.get_available_providers())"
```
**Output**:
```
['DmlExecutionProvider', 'CPUExecutionProvider']
```

Both providers coexist cleanly in the virtual environment without conflict, because `onnxruntime-directml` incorporates the complete CPU execution provider and delegates GPU operators to DirectX 12 DirectML.

---

## 4. Hardware Adapter Mapping & Selection

DirectML addresses GPUs via DXGI adapter indices:

- **Adapter 0**: `Intel(R) UHD Graphics` (VendorId: `0x8086`, Dedicated VRAM: 128 MB)
- **Adapter 1**: `NVIDIA GeForce RTX 4050 Laptop GPU` (VendorId: `0x10de`, Dedicated VRAM: 5,921 MB)
- **Adapter 2**: `Microsoft Basic Render Driver` (Software renderer)

### Device Targeting Configuration:
Project AIC supports dynamic and explicit device selection:
- Default in `PipelineConfig.directml_device_id`: `0` (or `1` when discrete GPU is auto-detected).
- Environment Variable Override: `AIC_PIPELINE_DIRECTML_DEVICE_ID=1`.
- Benchmark CLI flag: `python scripts/run_tier3_benchmark.py --device-id 1`.

---

## 5. Strict Anti-Silent-Fallback Guardrail

A common failure mode in AI deployment is silent fallback: when a GPU provider fails to load, the runtime quietly falls back to CPU, degrading throughput by up to 15x without throwing an error.

In Project AIC, `ISNetDirectMLProvider` strictly verifies the session providers immediately after creation:

```python
active = session.get_providers()
if "DmlExecutionProvider" not in active:
    raise DirectMLInitializationError(
        f"DirectML session was requested but DmlExecutionProvider is not active on session. "
        f"Active providers: {active}. Silent CPU fallback is rejected."
    )
```

If DirectML runtime is missing or initialization fails:
- It raises `DirectMLNotAvailableError` or `DirectMLInitializationError`.
- It **never** silently switches to CPU.
- The pipeline worker catches provider failures and routes failed items to the Dead Letter Queue (`dlq_path`) with full diagnostic metadata.

---

## 6. PipelineWorker Integration & Test Isolation

`PipelineConfig.use_mock_bg_provider: bool = True` remains the default for unit tests and local development. This ensures:
1. Unit tests run instantaneously without downloading the 176MB `isnetis.onnx` weight file.
2. CI runners without GPUs execute the entire queue worker test suite (`test_queue_and_worker.py`) cleanly.
3. Production / staging environments explicitly enable `use_mock_bg_provider = False` and `onnx_execution_provider = "directml"` via environment variables or configuration files.
