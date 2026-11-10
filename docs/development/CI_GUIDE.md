# Project AIC — Continuous Integration (CI) Developer Guide

**Document Version:** 1.0  
**Target Workflow:** `.github/workflows/ci.yml`  
**Applies to:** All pull requests, feature branches, and pushes targeting `main`  
**Governing Policies:** `CODE_REVIEW_POLICY.md` & `AGENTS.md`  

---

## 1. Overview & CI Architecture

Continuous Integration (CI) in **Project AIC** provides automated, reproducible, and deterministic verification of all repository contributions prior to merging into `main`. The CI system is hosted on GitHub Actions and designed to enforce strict code quality, type safety, test passing, and dependency integrity.

```
                           [ Pull Request / Push to main ]
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
         ┌───────────────────────┐                 ┌───────────────────────┐
         │ dependency-validation │                 │      frontend-ci      │
         │   (uv lock & sync)    │                 │   (Modular Check)     │
         └──────────┬────────────┘                 └──────────┬────────────┘
                    │                                         │
                    ▼                                         │ (package.json present?)
         ┌───────────────────────┐                   ├── Yes ──► npm ci, typecheck, lint, build
         │      backend-ci       │                   └── No  ──► Graceful notice: Not run (Skipped)
         │ (Ruff, Mypy, Pytest)  │
         └───────────────────────┘
```

### 1.1. Runner Environment
- **Operating System:** Ubuntu Linux (`ubuntu-latest`).
- **Isolation:** Each workflow run executes in a pristine, ephemeral virtual machine.
- **Resource Profile:** Standard GitHub-hosted runner (2 vCPUs, 7 GB RAM, 14 GB SSD).

### 1.2. Triggers & Concurrency
- **Pull Request Trigger:** Automatically triggers on every open, synchronize, or reopen event for pull requests targeting `main`.
- **Push Trigger:** Triggers on all direct pushes or merges into `main`.
- **Concurrency Group:** `${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress: true`. If a developer pushes subsequent commits to an open PR, redundant in-flight workflow runs are immediately cancelled to save CI minutes and avoid race conditions.

### 1.3. Least-Privilege Permissions
- The workflow explicitly defines root-level permissions:
  ```yaml
  permissions:
    contents: read
  ```
- No write permissions (`contents: write`, `pull-requests: write`, or `actions: write`) are granted, eliminating attack surfaces against pull requests originating from forks or untrusted branches.

### 1.4. Immutable Action Pinning
To defend against supply-chain poisoning and upstream tag hijacking, all third-party actions are pinned to full immutable 40-character commit SHAs, accompanied by descriptive version comments:

| Third-Party Action | Version Tag | Pinned Immutable Commit SHA | Purpose |
| :--- | :--- | :--- | :--- |
| `actions/checkout` | `v4.2.2` | `11bd71901bbe5b1630ceea73d27597364c9af683` | Secure repository checkout |
| `astral-sh/setup-uv` | `v5.3.0` | `1edb52594c857e2b5b13128931090f0640537287` | Fast Python package management and cache |
| `actions/setup-python` | `v5.4.0` | `42375524e23c412d93fb67b49958b491fce71c38` | Python 3.12 runtime environment |
| `actions/setup-node` | `v4.2.0` | `1d0ff469b7ec7b3cb9d8673fde0c81c44821de2a` | Node.js 20 runtime and npm cache |

---

## 2. Automated CI Jobs & Quality Gates

The CI workflow is divided into three distinct, specialized jobs:

### Job 1: `dependency-validation`
- **Execution Target:** `ubuntu-latest` (Timeout: 5 minutes).
- **Working Directory:** `backend/`.
- **Steps:**
  1. Clones repository via pinned `actions/checkout`.
  2. Sets up `uv` package manager with caching on `backend/uv.lock`.
  3. Executes `uv lock --check`: Asserts that `backend/uv.lock` is mathematically in sync with `backend/pyproject.toml`. Fails immediately if dependencies were modified without updating the lockfile.
  4. Executes `uv sync --locked --no-install-project`: Validates dependency resolution tree without building internal package artifacts.

### Job 2: `backend-ci`
- **Execution Target:** `ubuntu-latest` (Timeout: 10 minutes).
- **Prerequisite:** Depends on successful completion of `dependency-validation` (`needs: dependency-validation`).
- **Working Directory:** `backend/`.
- **Steps:**
  1. Checks out repository and sets up `uv` caching.
  2. Sets up Python 3.12 via pinned `actions/setup-python`.
  3. Installs dependencies via `uv sync --locked --extra dev --extra cpu`.
  4. **Linting Gate:** Runs `uv run ruff check .` enforcing line length (100) and PEP 8 standards. (Exit code 0 required).
  5. **Type Safety Gate:** Runs `uv run mypy app tests` verifying static typing across all application and test modules.
  6. **Unit & Integration Test Suite:** Runs `uv run pytest -v` executing all unit, mock background provider, security, and adversarial test suites.

### Job 3: `frontend-ci`
- **Execution Target:** `ubuntu-latest` (Timeout: 5 minutes).
- **Execution Nature:** Modular and forward-compatible.
- **Presence Check:** Step `check-frontend` inspects the repository for `package.json` or `apps/desktop/package.json`.
  - **When absent (Milestone 0 state):** Gracefully logs an informational notice (`Frontend not initialized in Milestone 0`) and skips subsequent steps. The job finishes with status `Not run (Skipped)`.
  - **When present (Milestone 1+ desktop state):** Automatically activates, sets up Node.js 20 with npm caching, installs dependencies via `npm ci`, runs `npm run typecheck`, runs `npm run lint`, and executes `npm run build`.

---

## 3. Hardware Boundary: Hosted CI vs. Real DirectML GPU Execution

A fundamental architectural principle of Project AIC is **strict hardware segregation** and **honest reporting of test environments**.

### 3.1. Hosted CI Capabilities (CPU & Mock Runtime)
- GitHub-hosted `ubuntu-latest` runners are virtualized CPU environments without access to physical GPUs or Microsoft DirectX 12 hardware.
- The CI test runner executes **CPU-based inference** (`onnxruntime` CPU provider) and **offline mock providers** (`MockBackgroundRemovalProvider`).
- DirectML unit tests (`test_isnet_directml_unit.py`, `test_device_discovery.py`, `test_adversarial_isnet_directml_m1.py`) use dependency mocks and simulated DXGI adapters to test concurrency, locking, timeout handlers, and error pathways 100% offline.

### 3.2. Physical DirectML GPU Hardware Boundary
- **Microsoft DirectML** is a proprietary DirectX 12 API exclusive to Microsoft Windows. It does not exist on Linux runners.
- Real hardware validation of the **NVIDIA GeForce RTX 4050 Laptop GPU** occurs exclusively on dedicated local Windows 11 host environments with physical WDDM drivers.
- **Automatic Tier 3 Skipping:** Real-model hardware tests (`test_onnx_real_directml.py` and `test_onnx_real_cpu.py`) use `pytest.mark.skipif` when `isnetis.onnx` or `DmlExecutionProvider` is not detected.
- **Reporting Rule:** Passing hosted CI **must NEVER** be claimed as validation of real DirectML GPU acceleration. Real GPU benchmarks must be verified and documented independently via local benchmark runs (`scripts/run_tier3_benchmark.py`).

---

## 4. Local Verification Runbook for Developers

Developers and agents **must** run the following local verification commands before pushing commits or submitting pull requests:

### 4.1. Prerequisites
Ensure you are in the repository root `D:\Project AIC` and have Python 3.12 and `uv` installed.

### 4.2. Step-by-Step Local Commands

```powershell
# 1. Navigate to backend directory
cd backend

# 2. Verify lockfile synchronization
uv lock --check

# 3. Synchronize development and CPU dependencies
uv sync --locked --extra dev --extra cpu

# 4. Run Ruff linting check (Do NOT run 'ruff format --check' unless specifically tasked)
uv run ruff check .

# 5. Run Mypy static type checker
uv run mypy app tests

# 6. Run full Pytest test suite
uv run pytest -v
```

> **Warning on Working Directory:** Always execute backend verification commands from inside the `backend/` directory (or specify `-c backend/pyproject.toml`). Running pytest from root without specifying configuration causes `asyncio_mode = "auto"` to be omitted, resulting in fixture failures.

---

## 5. Inspecting GitHub Actions CI Results

### 5.1. Using GitHub CLI (`gh`)
You can inspect workflow runs directly from your terminal using the GitHub CLI:

```powershell
# List recent CI workflow runs
gh run list --workflow=ci.yml

# View the status and logs of the latest run
gh run view

# Watch a currently running workflow live
gh run watch

# Check PR status checks
gh pr checks <PR_NUMBER>
```

### 5.2. Using the GitHub Web UI
1. Navigate to the repository on GitHub: `https://github.com/nguyenphanminhkhanh9a-netizen/Project-AIC`.
2. Click on the **Actions** tab.
3. Select the **CI** workflow from the left sidebar.
4. Click on the specific workflow run corresponding to your commit SHA.
5. Review the job status breakdown:
   - `dependency-validation`
   - `backend-ci`
   - `frontend-ci`

### 5.3. Status Taxonomy
In all internal handoffs, audit reports, and PR documentation, CI check results must be classified strictly according to this five-state taxonomy:

| Status Label | Technical Meaning | CI Representation |
| :--- | :--- | :--- |
| **`Passed`** | Step executed on the runner and exited with code 0. | Green checkmark |
| **`Failed`** | Step executed on the runner and returned non-zero exit code. | Red cross |
| **`Pending`** | Step or job is currently queued or running. | Yellow spinner |
| **`Not run`** | Step intentionally not executed because prerequisites (e.g. frontend files) do not exist yet. | Grey symbol / informational log |
| **`Unsupported`** | Check cannot run in hosted environment due to platform incompatibility (e.g. Windows DXGI COM / DirectML hardware checks). | Documented limitation |

---

## 6. CI Integrity & Anti-Cheating Standards

All contributors and AI agents must strictly abide by the **Integrity Mandate** defined in `CODE_REVIEW_POLICY.md`:

1. **No `continue-on-error`:** CI jobs must never use `continue-on-error: true` or shell tricks (e.g. `|| true`) to mask failures.
2. **No Weakened Rules:** Do not relax linting rules, suppress Mypy warnings, or alter test assertions just to force a passing build.
3. **No Unrelated Code Changes:** If a CI job fails due to an application bug, fix the defect cleanly or report it to the Project Owner. Do not refactor unrelated codebase files.
4. **Never Merge or Auto-Merge:** AI agents are strictly forbidden from executing `gh pr merge`, merging via CLI, or enabling GitHub auto-merge. Only the Project Owner possesses the authority to merge pull requests into `main`.

---

## 7. Troubleshooting & Failure Handling

### Issue A: `uv lock --check` fails
- **Symptom:** `error: The lockfile is out of sync with the project configuration.`
- **Cause:** `backend/pyproject.toml` was edited without updating `backend/uv.lock`.
- **Fix:** Run `cd backend; uv lock` locally, test, and commit the updated `uv.lock`.

### Issue B: `ruff check .` fails with lint violations
- **Symptom:** `backend/...: error: [E... / F...] ...`
- **Cause:** Code violates PEP 8 formatting or import rules.
- **Fix:** Fix the reported lines manually or run `uv run ruff check --fix .` on the specific affected files. Re-run `uv run ruff check .` to confirm.

### Issue C: `mypy app tests` fails with type errors
- **Symptom:** `error: Incompatible return value type ...`
- **Cause:** Missing or mismatched type annotation.
- **Fix:** Review the annotated signature and correct the type. Do NOT use `# type: ignore` unless strictly necessary for untyped third-party library boundaries.

### Issue D: Windows-specific forensic scripts fail in CI
- **Symptom:** `FileNotFoundError: .temp_envs/cpu_env` or `DirectML COM error`.
- **Cause:** Attempting to run `scripts/check_wheel_records.py` or `scripts/verify_wddm_and_dxgi.py` on Linux CI runners.
- **Fix:** These scripts are designed strictly for Windows host forensic validation. Do not include them in the Linux CI workflow.
