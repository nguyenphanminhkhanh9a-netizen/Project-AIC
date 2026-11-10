# Dependency Compatibility Guide: ONNX Runtime & DirectML on Windows

This document details the dependency architecture, binary collision forensic analysis, mutual exclusion guardrails, installation workflows, and runtime fallback behavior for ONNX Runtime CPU and DirectML GPU execution providers in Project AIC.

---

## 1. Problem Statement & Architecture: Mutually Exclusive Binary Collision

In Python on Windows, the base package `onnxruntime` (CPU execution) and `onnxruntime-directml` (DirectX 12 DirectML GPU execution) share the exact same top-level Python namespace: `site-packages/onnxruntime`.

### Forensic Wheel Collision Breakdown:
A rigorous comparison between the distribution wheels (`onnxruntime` 1.31.1 and `onnxruntime-directml` 1.24.4) reveals:
- **Total paths in CPU wheel**: 326 files.
- **Total paths in DirectML wheel**: 325 files.
- **Colliding relative paths in `site-packages/onnxruntime/`**: **Exactly 317 files**.
- **Colliding native binaries**:
  - `onnxruntime/capi/onnxruntime.dll`: CPU is 19.3 MB, DirectML is 21.1 MB.
  - `onnxruntime/capi/onnxruntime_pybind11_state.pyd`: CPU is 20.0 MB, DirectML is 26.5 MB.
  - `onnxruntime/capi/onnxruntime_providers_shared.dll`: CPU is 21.8 KB, DirectML is 21.6 KB.
- **Colliding Python modules**: 56 source files have conflicting hashes between versions.

### The Fallacy of Coexistence:
Declaring both packages in the same virtual environment (e.g., base CPU + extra DirectML) does **NOT** achieve coexistence. Instead:
1. Whichever package is extracted last clobbers the native C++ binaries of the other.
2. `pip list` showing both distributions is an illusion of PEP 376 `.dist-info` directories; the physical files on disk belong to only one package.
3. If `pip uninstall onnxruntime` is ever executed, it deletes all 317 common files from `RECORD`, completely corrupting the DirectML installation.
4. `ort.get_available_providers()` is an insufficient check: it only inspects the active pybind extension export table, without verifying DirectX 12 hardware availability, driver binding, or tensor compilation.

Therefore, `onnxruntime` and `onnxruntime-directml` are strictly **mutually exclusive**.

---

## 2. Dependency Specification (`backend/pyproject.toml`)

Project AIC enforces strict mutual exclusion using optional extras, PEP 735 dependency groups, and `tool.uv.conflicts`:

```toml
[project]
name = "project-aic-backend"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.4.0",
    "aiosqlite>=0.20.0",
    "pillow>=13.0.0",
    "numpy>=1.26.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]
cpu = [
    "onnxruntime>=1.19.0",
]
directml = [
    "onnxruntime-directml>=1.19.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]
cpu = [
    "onnxruntime>=1.19.0",
]
directml = [
    "onnxruntime-directml>=1.19.0",
]

[tool.uv]
default-groups = ["dev", "cpu"]
conflicts = [
    [
        { extra = "cpu" },
        { extra = "directml" },
    ],
    [
        { group = "cpu" },
        { group = "directml" },
    ],
]
```

### Installation Workflows:

1. **Default Local Development & Headless CI** (Clean CPU-only):
   ```bash
   uv sync --project backend
   ```
   Installs `onnxruntime` via default group `cpu`. Zero GPU requirements. Suitable for CI runners and Linux/macOS.

2. **Windows GPU Workstation / Benchmark** (Clean DirectML-only):
   ```bash
   uv sync --project backend --no-default-groups --group dev --group directml
   ```
   Installs `onnxruntime-directml` without `onnxruntime`. Enables `DmlExecutionProvider` alongside native CPU execution.

3. **Collision Protection**:
   Attempting to install both:
   ```bash
   uv sync --project backend --extra cpu --extra directml
   ```
   Fails immediately with:
   `error: Extras cpu and directml are incompatible with the declared conflicts`.

---

## 3. Clean Environment Verification Procedures

DirectML and CPU execution must be verified independently in clean, non-clobbered environments:

### Clean CPU-Only Verification:
```powershell
uv run --isolated --with onnxruntime==1.31.1 python -c "
import onnxruntime as ort, numpy as np
assert 'DmlExecutionProvider' not in ort.get_available_providers()
assert 'CPUExecutionProvider' in ort.get_available_providers()
p = ort.__file__.replace('__init__.py', 'datasets/mul_1.onnx')
sess = ort.InferenceSession(p, providers=['CPUExecutionProvider'])
res = sess.run(None, {sess.get_inputs()[0].name: np.ones((3, 2), dtype=np.float32)})
assert res[0].shape == (3, 2)
print('PASS: Clean CPU-only verified')
"
```

### Clean DirectML-Only Verification:
```powershell
uv run --isolated --with onnxruntime-directml==1.24.4 python -c "
import onnxruntime as ort, numpy as np
assert 'DmlExecutionProvider' in ort.get_available_providers()
assert 'CPUExecutionProvider' in ort.get_available_providers()
p = ort.__file__.replace('__init__.py', 'datasets/mul_1.onnx')
sess = ort.InferenceSession(p, providers=['DmlExecutionProvider'])
assert 'DmlExecutionProvider' in sess.get_providers()
res = sess.run(None, {sess.get_inputs()[0].name: np.ones((3, 2), dtype=np.float32)})
assert res[0].shape == (3, 2)
print('PASS: Clean DirectML-only verified')
"
```

---

## 4. Hardware Adapter Mapping & Selection

In ONNX Runtime, `device_id` is an integer ordinal index passed to DXGI `EnumAdapters1`. LUID is a 64-bit kernel structure that cannot be passed as `device_id` directly to ONNX Runtime.

Modern Windows systems often have hybrid graphics (e.g. Intel UHD on Adapter 0 and NVIDIA RTX on Adapter 1). Hardcoding Adapter 0 forces execution onto slow integrated graphics (causing an 11.5x latency penalty), while hardcoding Adapter 1 crashes on single-GPU desktops.

### Unified Device Discovery Architecture:
Project AIC implements `backend/app/pipeline/background/device_discovery.py` as the single source of truth shared across the backend application and benchmark harness:
1. **Explicit Config ID**: `PipelineConfig.directml_device_id` (if configured and valid).
2. **Environment Variable Override**: `AIC_PIPELINE_DIRECTML_DEVICE_ID`.
3. **Dynamic Auto-Detection** (Default when `directml_device_id is None`):
   - Prefers discrete NVIDIA GPU (`VendorId 0x10DE`).
   - Prefers discrete AMD GPU (`VendorId 0x1002`, VRAM >= 1024 MB).
   - Prefers discrete Intel Arc GPU (`VendorId 0x8086`, VRAM >= 2048 MB).
   - Selects single hardware GPU if only 1 exists.
4. **Strict Error Handling**: Software adapters (e.g. Microsoft Basic Render Driver) and non-existent IDs raise `DirectMLDeviceConfigurationError` or `DirectMLDeviceNotFoundError`. Silent fallback is strictly prohibited.

---

## 5. Strict Anti-Silent-Fallback Guardrail

When an invalid device ID or missing driver occurs, ONNX Runtime defaults to silently falling back to `CPUExecutionProvider` without raising an exception from Python.

In Project AIC, `ISNetDirectMLProvider` strictly verifies session providers immediately after creation:

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
