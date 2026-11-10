## Summary

This pull request completes **Task 0.5B-2** (DirectML GPU Acceleration for IS-Net Anime Background Removal) on branch `feature/m0-task-05b-directml` at verified HEAD commit `0f78e996a7b7e930b9addbc3eeb7fa0500c6d9c0` (diverging from `main` at base commit `0baf954102524256f40bab036a472b1581bf8e61`).

It introduces DirectX 12 GPU acceleration via Microsoft ONNX Runtime DirectML Execution Provider (`DmlExecutionProvider`), hardened concurrency lifecycle management to prevent deadlocks, dynamic COM DXGI hardware discovery for discrete GPU prioritization, and strict package isolation preventing binary collisions between CPU and GPU ONNX Runtime wheels.

### Key Highlights
- **4.74x Average End-to-End Pipeline Speedup**: Full pipeline execution (image load, letterbox preprocessing, GPU inference, unpadding, alpha ramp calculation, RGBA compositing, and PNG encoding) accelerates from **1188.53 ms** (CPU, 4 threads) to **250.63 ms** (NVIDIA GeForce RTX 4050 Laptop GPU) across 5 standardized Tier 3 anime test fixtures.
- **12.87x Average Model Inference Speedup**: Pure forward inference pass `session.run()` accelerates from **1006.02 ms** (CPU) to **78.14 ms** (DirectML RTX 4050), reaching **52.09 ms (19.55x speedup)** on simple backgrounds.
- **Deferred Release Lifecycle Pattern**: Resolves potential AB-BA lock inversions between inference execution and session release. When session release is triggered from an active inference thread, session destruction is safely deferred until the critical section exits cleanly.
- **Dynamic DXGI Hardware Discovery**: Implements native Windows COM adapter enumeration (`IDXGIFactory1::EnumAdapters1`) to auto-detect and select the discrete GPU (NVIDIA RTX 4050, Adapter 1) over integrated graphics (Intel UHD, Adapter 0) with dedicated VRAM heuristics and `AIC_PIPELINE_DIRECTML_DEVICE_ID` environment override support.
- **Strict Dependency Isolation**: Configures mutually exclusive `cpu` and `directml` package extras via `[tool.uv.conflicts]` in `backend/pyproject.toml`, preventing silent clobbering across 317 shared files in `site-packages/onnxruntime`.
- **Full Test Suite & Static Analysis**: **353 passed, 0 failed, 0 skipped** across the backend test suite on Windows 11 host. Zero Ruff violations and zero Mypy static typing errors across 46 modules.

---

## Implementation Details

### 1. DirectML Execution Provider Integration
- **File**: `backend/app/pipeline/background/isnet_directml_provider.py`
- **Session Configuration**:
  - Configures `ort.SessionOptions`: `execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL` (preventing DirectX 12 command queue hazards), `enable_mem_pattern = False` (avoiding Direct3D 12 buffer reallocation corruptions), and `graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL`.
  - Configures thread allocation: `inter_op_num_threads = 1` and `intra_op_num_threads = 1` to prevent CPU thread thrashing while GPU compute executes.
  - Binds providers: `["DmlExecutionProvider"]` with `provider_options = [{"device_id": str(device_id)}]`.
- **Anti-Silent-Fallback Guardrail**: Validates session providers post-creation via `assert "DmlExecutionProvider" in session.get_providers()`. If DirectML fails to initialize, raises an explicit `RuntimeError` rather than silently degrading to CPU.

### 2. Concurrency & Deferred Release Lifecycle
- Coordinates multi-threaded execution through two synchronization primitives:
  - `_load_lock`: Synchronizes session creation, loading, and disposal.
  - `_inference_lock`: Protects active model execution.
- **Deferred Release**: If `release()` is called while the current thread owns `_inference_lock` (e.g. within an error recovery pathway), session destruction is deferred until the inference block completes, eliminating self-deadlock.

### 3. Dynamic DXGI Hardware Discovery
- **File**: `backend/app/pipeline/background/device_discovery.py`
- Utilizes `ctypes` to invoke Windows DirectX Graphics Infrastructure (DXGI) COM interfaces:
  - Calls `IDXGIFactory1::EnumAdapters1` to retrieve `DXGI_ADAPTER_DESC1` structures.
  - Inspects PCI Vendor ID (`0x10DE` for NVIDIA, `0x1002` for AMD, `0x8086` for Intel, `0x1414` for Microsoft WARP), dedicated video memory, and adapter flags (`DXGI_ADAPTER_FLAG_SOFTWARE`).
- **Adapter Resolution Hierarchy**:
  1. Explicit configuration parameter `PipelineConfig.directml_device_id`.
  2. Environment variable override `AIC_PIPELINE_DIRECTML_DEVICE_ID`.
  3. Dynamic heuristic: Selects discrete GPU with highest dedicated VRAM (Adapter 1, NVIDIA RTX 4050, 5,921 MB VRAM) over integrated graphics (Adapter 0, Intel UHD, 128 MB VRAM).

### 4. Dependency Conflict Guardrail
- **File**: `backend/pyproject.toml`
- Forensic analysis revealed 317 shared filesystem paths in `site-packages/onnxruntime` between `onnxruntime` 1.31.1 (326 total entries) and `onnxruntime-directml` 1.24.4 (325 total entries), with 254 identical files and 63 conflicting native binaries and modules (including `onnxruntime.dll`, `onnxruntime_pybind11_state.pyd`, `onnxruntime_providers_shared.dll`, and `onnxruntime_test.exe`).
- Mutual exclusion is declared via `tool.uv.conflicts`:
  ```toml
  [tool.uv]
  default-groups = ["dev", "cpu"]
  conflicts = [
      [{ extra = "cpu" }, { extra = "directml" }],
      [{ group = "cpu" }, { group = "directml" }],
  ]
  ```
  Prevents accidental co-installation and subsequent uninstallation cascades.

---

## Performance Results

### 1. Test System & Protocol
- **Host Hardware**: 13th Gen Intel Core i7-13620H (16 vCPUs, 2.40 GHz), 32 GB RAM, Windows 11 Build 26100.3194.
- **GPU Accelerator**: NVIDIA GeForce RTX 4050 Laptop GPU (5,921 MB dedicated VRAM, DirectML device ID 1, LUID `0x000000000000FC5C`).
- **Model**: IS-Net Anime (`isnetis.onnx`, 176 MB, SHA-256 `f15622d853e8260172812b657053460e20806f04b9e05147d49af7bed31a6e99`).
- **Protocol**: 5 Tier 3 anime fixtures, 2 warmup iterations per image, 10 official timed iterations per image.
- **Metric Scope**:
  - **End-to-End (E2E) Pipeline Latency**: Entire processing pipeline (decode, letterbox, forward pass, unpad, alpha ramp, RGBA, PNG encode).
  - **Model Inference-Only Latency**: Wall-clock time exclusively inside `session.run()`.

### 2. Official 10-Iteration Benchmark Results (`benchmark_report.json`)

#### Table 1: End-to-End Pipeline Latency Comparison
| Sample ID | Image Dimensions | CPU Latency (Mean ± Std) [Min, Max] | DirectML Latency (Mean ± Std) [Min, Max] | E2E Speedup |
|---|---|---|---|---|
| `sample_01_simple_bg` | 848x1264 | 1183.37 ± 52.95 ms [1085.1, 1272.3] | 208.63 ± 10.30 ms [198.6, 225.8] | **5.67x** |
| `sample_02_complex_bg` | 848x1264 | 1194.51 ± 57.38 ms [1097.5, 1284.5] | 255.42 ± 8.08 ms [244.9, 274.6] | **4.68x** |
| `sample_03_long_hair` | 848x1264 | 1190.87 ± 69.87 ms [1117.9, 1341.7] | 259.08 ± 5.16 ms [254.4, 270.0] | **4.60x** |
| `sample_04_small_accessories` | 848x1264 | 1179.08 ± 62.91 ms [1070.1, 1286.0] | 269.65 ± 4.54 ms [264.2, 277.5] | **4.37x** |
| `sample_05_translucent_costume` | 848x1264 | 1194.81 ± 53.40 ms [1135.8, 1285.9] | 260.34 ± 5.12 ms [255.0, 271.9] | **4.59x** |
| **5-IMAGE AVERAGE** | — | **1188.53 ms** | **250.63 ms** | **4.74x** |

#### Table 2: Stage-Wise Breakdown (Preprocessing vs Model Inference vs Postprocessing)
| Sample ID | Preprocessing (CPU / DML) | Model Inference (CPU / DML) | Postprocessing + PNG (CPU / DML) | Inference Speedup |
|---|---|---|---|---|
| `sample_01_simple_bg` | 39.25 ms / 36.73 ms | 1018.44 ms / **52.09 ms** | 125.68 ms / 119.81 ms | **19.55x** |
| `sample_02_complex_bg` | 50.21 ms / 48.33 ms | 1015.14 ms / **82.34 ms** | 129.16 ms / 124.75 ms | **12.33x** |
| `sample_03_long_hair` | 49.99 ms / 48.58 ms | 1006.73 ms / **85.69 ms** | 134.15 ms / 124.81 ms | **11.75x** |
| `sample_04_small_accessories` | 49.63 ms / 46.12 ms | 985.11 ms / **85.91 ms** | 144.34 ms / 137.62 ms | **11.47x** |
| `sample_05_translucent_costume` | 50.76 ms / 48.64 ms | 1004.64 ms / **84.66 ms** | 139.41 ms / 127.04 ms | **11.86x** |
| **AVERAGE** | **47.97 ms** / **45.68 ms** | **1006.02 ms** / **78.14 ms** | **134.55 ms** / **126.81 ms** | **12.87x** |

### 3. Historical Single-Run Pure Inference Stage Latency
- The single-sample timing of **1497.48 ms (CPU) vs 49.39 ms (DirectML)** (30.32x speedup) originates from `data/tier3_output/sample_01_simple_bg_comparison.json`.
- It reflects an isolated single-pass measurement (`std = 0.0`) strictly timing `session.run()`, excluding preprocessing (51.12 ms CPU / 53.89 ms DML) and postprocessing (181.67 ms CPU / 187.16 ms DML). Total E2E in that run was 1730.27 ms vs 290.44 ms (5.96x).
- This metric is designated as **Historical Single-Run Pure Inference** and is decoupled from the official 10-iteration benchmark averages in `benchmark_report.json`.

### 4. Kernel-Level Hardware Utilization Proof
Windows Performance Counters (`\GPU Engine(*)\Utilization Percentage`) demonstrate active 3D compute during inference:
- **Run 1 (Process-isolated filter, PID 19756)**: **92.11% active 3D utilization** on NVIDIA RTX 4050 (`LUID 0x000000000000FC5C`) with **0.00%** on Intel UHD.
- **Run 2 (System-wide query, PID 12632)**: **96.39% active 3D utilization** on NVIDIA RTX 4050 with **4.57%** on Intel UHD (ambient desktop DWM compositor baseline, not inference load).
- *(Note: Historical execution timestamps for counter samples are classified as NOT VERIFIED due to omitted OS timestamp properties in PowerShell output).*

### 5. Numerical Accuracy & Alpha Invariance
- **Sub-LSB FP32 Precision**: 100.00% of alpha channel pixels across all 5 anime test fixtures match within ±1 alpha value (`max_diff <= 1/255`), confirming arithmetic invariance under DirectX 12 HLSL FP32 SIMD execution.
- **Pixel Partitioning**: 100% exact categorization across transparent (`alpha == 0`), solid (`alpha == 255`), and transitional alpha categories.

---

## Testing

### 1. Test Suite Summary
Execution of the complete backend test suite on Windows 11 host yields:
- **353 passed, 0 failed, 0 skipped, 6 warnings** in ~65–75 seconds.
- Breakdown:
  - `backend/tests/pipeline/test_isnet_directml_unit.py`: 33 passed (DirectML offline unit tests, lock ordering, error handling, session recovery, and deferred release).
  - `backend/tests/pipeline/test_device_discovery.py`: 6 passed (DXGI COM enumeration, vendor heuristic precedence, environment variable override).
  - `backend/tests/pipeline/test_onnx_real_directml.py`: 6 passed (5 physical anime fixtures on NVIDIA RTX 4050 + explicit hardware execution provider binding assertion).
  - `scripts/adversarial_stress_r1.py`: 4/4 scenarios passed (concurrent release races, self-release bursts, rapid shutdown, 20-thread release storms).
  - Core Regression Suites: 308 passed (legacy M0 Task 0.4, Phase 0.5A pipeline core, quality gates, deduplication, storage, SSRF guard, and queue worker).

### 2. Static Analysis & Linting
- **Ruff**: `uv run --project backend ruff check backend scripts/run_tier3_benchmark.py` -> `All checks passed!` (0 violations).
- **Mypy**: `uv run --project backend mypy backend/app` -> `Success: no issues found in 46 source files` (0 errors).

### 3. Verification Commands
To independently reproduce and verify results on Windows:

```powershell
# 1. Verify target HEAD commit
git rev-parse HEAD
# Expected: 0f78e996a7b7e930b9addbc3eeb7fa0500c6d9c0

# 2. Run full backend test suite
uv run --project backend pytest backend/tests -q
# Expected: 353 passed, 6 warnings

# 3. Verify static analysis and type checking
uv run --project backend ruff check backend scripts/run_tier3_benchmark.py
uv run --project backend mypy backend/app

# 4. Run real DirectML GPU hardware tests (requires DirectX 12 GPU)
uv run --project backend pytest backend/tests/pipeline/test_onnx_real_directml.py -v

# 5. Run adversarial concurrency stress tests
uv run --project backend python scripts/adversarial_stress_r1.py

# 6. Verify wheel distribution RECORD collision analysis
python scripts/check_wheel_records.py
```

---

## Compatibility & Safety

### 1. Environmental & CI Boundaries
- Remote GitHub Actions CI is not configured for this branch (`gh pr checks 7` reports no checks).
- DirectML GPU acceleration requires physical Windows DirectX 12 hardware drivers. Headless virtualized cloud CI runners lack DirectX 12 GPUs and cannot execute physical DirectML tests without dedicated hardware runners.
- All test results documented herein reflect local host execution on Windows 11 with physical NVIDIA RTX 4050 hardware.

### 2. Mock vs Real Hardware Separation
- Unit tests (`test_isnet_directml_unit.py`) and adversarial stress tests use mocks and isolation wrappers to validate lifecycle and concurrency logic without requiring GPU hardware.
- Real hardware tests (`test_onnx_real_directml.py`) actively bind to `DmlExecutionProvider` and require physical DirectX 12 hardware.

### 3. Audit Provenance Constraints
- Previous independent audit claims are formally classified as `REPORT-ONLY / NO INDEPENDENT RAW LOGS` because auditors did not capture standalone stdout/stderr console logs to disk.
- Execution reproducibility on HEAD commit `0f78e996a7b7e930b9addbc3eeb7fa0500c6d9c0` is fully evidenced via the 11 reproduction logs in `reconciliation_artifacts/logs_reproduced/`.

### 4. Repository Artifact Boundaries
- Exactly **5 test and data files are committed** to the GitHub branch: `backend/tests/pipeline/test_isnet_directml_unit.py`, `backend/tests/pipeline/test_device_discovery.py`, `backend/tests/pipeline/test_onnx_real_directml.py`, `scripts/adversarial_stress_r1.py`, and `data/tier3_output/benchmark_report.json`.
- The remaining 14 historical evidence reports and 11 reproduction logs are strictly `LOCAL ONLY` artifacts governed by `.gitignore`.

### 5. Backward Compatibility & Safety
- The CPU IS-Net ONNX pipeline established in Task 0.5B-1 (PR #6) remains fully operational via `CPUExecutionProvider` and independent `cpu` virtual environments.
- Anti-silent-fallback prevents accidental performance degradation: GPU initialization failure raises an immediate exception rather than silently defaulting to CPU within DirectML execution pathways.

---

## Related Task/Issue

- **Pull Request**: #7 (`nguyenphanminhkhanh9a-netizen/Project-AIC#7`)
- **Milestone**: Milestone 0 (M0) — Foundation & Proof of Concept
- **Task**: Task 0.5B-2 (DirectML GPU Acceleration for IS-Net Anime)
- **Preceding Tasks**:
  - Task 0.5A (Pipeline Core, Protocols, Storage & Quality Gates — PR #5, commit `bb9cc16`)
  - Task 0.5B-1 (CPU IS-Net ONNX Provider — PR #6, commit `0baf954`)
- **Branch**: `feature/m0-task-05b-directml`
- **Base Commit**: `0baf954102524256f40bab036a472b1581bf8e61`
- **Target HEAD Commit**: `0f78e996a7b7e930b9addbc3eeb7fa0500c6d9c0`
