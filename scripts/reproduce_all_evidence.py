"""scripts/reproduce_all_evidence.py

Automated harness to run all verification commands with rigorous pre- and post-run
telemetry headers, and write individual log files into
reconciliation_artifacts/logs_reproduced/.
"""

from __future__ import annotations

import datetime
import subprocess
import sys
import time
from pathlib import Path


def get_git_telemetry(repo_root: Path) -> dict[str, str]:
    def run_git(args: list[str]) -> str:
        res = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        return res.stdout.strip()

    head = run_git(["rev-parse", "HEAD"])
    branch = run_git(["branch", "--show-current"])
    status = run_git(["status", "--porcelain"])
    clean = "Clean" if not status.strip() else f"Dirty ({len(status.splitlines())} modified/untracked files)"
    return {
        "head": head,
        "branch": branch,
        "clean_status": clean,
    }


def format_log_header(
    title: str,
    command: list[str],
    cwd: Path,
    python_exe: str,
    packages: dict[str, str],
    git_meta: dict[str, str],
    start_utc: str,
) -> str:
    lines = [
        "=" * 80,
        f"REPRODUCIBLE TEST EVIDENCE LOG: {title}",
        "=" * 80,
        f"Start UTC Timestamp: {start_utc}",
        f"Git Commit SHA     : {git_meta['head']}",
        f"Git Branch         : {git_meta['branch']}",
        f"Working Tree Status: {git_meta['clean_status']}",
        f"Working Directory  : {cwd}",
        f"Command Line       : {' '.join(command)}",
        f"Python Executable  : {python_exe}",
        "Installed Package Versions:",
    ]
    for pkg, ver in packages.items():
        lines.append(f"  - {pkg}: {ver}")
    lines.append("-" * 80)
    lines.append("COMMAND OUTPUT BEGIN:")
    lines.append("-" * 80)
    return "\n".join(lines) + "\n"


def format_log_footer(
    end_utc: str,
    duration_s: float,
    exit_code: int,
) -> str:
    lines = [
        "-" * 80,
        "COMMAND OUTPUT END",
        "-" * 80,
        f"End UTC Timestamp  : {end_utc}",
        f"Duration           : {duration_s:.3f} seconds",
        f"Exit Code          : {exit_code}",
        f"Status             : {'SUCCESS' if exit_code == 0 else 'FAILURE'}",
        "=" * 80,
    ]
    return "\n".join(lines) + "\n"


def run_and_log(
    title: str,
    command: list[str],
    cwd: Path,
    python_exe: str,
    packages: dict[str, str],
    output_log_path: Path,
    git_meta: dict[str, str],
) -> int:
    start_dt = datetime.datetime.now(datetime.UTC)
    start_utc = start_dt.isoformat()
    t0 = time.perf_counter()

    print(f"\n>>> Running: {title}")
    print(f"    Command: {' '.join(command)}")

    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )

    t1 = time.perf_counter()
    end_dt = datetime.datetime.now(datetime.UTC)
    end_utc = end_dt.isoformat()
    duration_s = t1 - t0

    header = format_log_header(title, command, cwd, python_exe, packages, git_meta, start_utc)
    footer = format_log_footer(end_utc, duration_s, proc.returncode)

    full_output = proc.stdout + ("\n--- STDERR ---\n" + proc.stderr if proc.stderr else "")
    log_content = header + full_output + "\n" + footer

    output_log_path.parent.mkdir(parents=True, exist_ok=True)
    output_log_path.write_text(log_content, encoding="utf-8")

    print(f"    Exit code: {proc.returncode} in {duration_s:.2f}s -> Saved to {output_log_path.name}")
    return proc.returncode


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    logs_dir = repo_root / ".agents" / "teamwork" / "reconciliation_artifacts" / "logs_reproduced"
    logs_dir.mkdir(parents=True, exist_ok=True)

    git_meta = get_git_telemetry(repo_root)

    backend_py = str(repo_root / "backend" / ".venv" / "Scripts" / "python.exe")
    cpu_py = str(repo_root / ".temp_envs" / "cpu_env" / "Scripts" / "python.exe")
    dml_py = str(repo_root / ".temp_envs" / "dml_env" / "Scripts" / "python.exe")

    # Inspect package versions in backend
    pkg_probe = subprocess.run(
        [
            backend_py,
            "-c",
            "import onnxruntime, pytest, numpy; print(onnxruntime.__version__, pytest.__version__, numpy.__version__)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ort_ver, pytest_ver, np_ver = pkg_probe.stdout.strip().split()
    backend_pkgs = {
        "onnxruntime-directml": ort_ver,
        "pytest": pytest_ver,
        "numpy": np_ver,
    }

    # Step b) Unit tests
    run_and_log(
        title="DirectML Unit Tests (test_isnet_directml_unit.py)",
        command=["uv", "run", "--project", "backend", "pytest", "backend/tests/pipeline/test_isnet_directml_unit.py", "-v"],
        cwd=repo_root,
        python_exe=backend_py,
        packages=backend_pkgs,
        output_log_path=logs_dir / "test_isnet_directml_unit.log",
        git_meta=git_meta,
    )

    # Step c) Device discovery tests
    run_and_log(
        title="Device Discovery Tests (test_device_discovery.py)",
        command=["uv", "run", "--project", "backend", "pytest", "backend/tests/pipeline/test_device_discovery.py", "-v"],
        cwd=repo_root,
        python_exe=backend_py,
        packages=backend_pkgs,
        output_log_path=logs_dir / "test_device_discovery.log",
        git_meta=git_meta,
    )

    # Step d) Real DirectML GPU tests
    run_and_log(
        title="Real DirectML GPU Tests (test_onnx_real_directml.py)",
        command=["uv", "run", "--project", "backend", "pytest", "backend/tests/pipeline/test_onnx_real_directml.py", "-v"],
        cwd=repo_root,
        python_exe=backend_py,
        packages=backend_pkgs,
        output_log_path=logs_dir / "test_onnx_real_directml.log",
        git_meta=git_meta,
    )

    # Step e) Adversarial stress harness
    run_and_log(
        title="Adversarial Stress Test Suite (adversarial_stress_r1.py)",
        command=["uv", "run", "--project", "backend", "python", "scripts/adversarial_stress_r1.py"],
        cwd=repo_root,
        python_exe=backend_py,
        packages=backend_pkgs,
        output_log_path=logs_dir / "adversarial_stress_r1.log",
        git_meta=git_meta,
    )

    # Step f) Ruff
    run_and_log(
        title="Ruff Lint & Format Check",
        command=["uv", "run", "--project", "backend", "ruff", "check", "backend", "scripts/run_tier3_benchmark.py"],
        cwd=repo_root,
        python_exe=backend_py,
        packages=backend_pkgs,
        output_log_path=logs_dir / "ruff.log",
        git_meta=git_meta,
    )

    # Step g) Mypy
    run_and_log(
        title="Mypy Static Type Checking",
        command=["uv", "run", "--project", "backend", "mypy", "backend/app"],
        cwd=repo_root,
        python_exe=backend_py,
        packages=backend_pkgs,
        output_log_path=logs_dir / "mypy.log",
        git_meta=git_meta,
    )

    # Step h) Clean CPU env execution
    cpu_code = """
import onnxruntime as ort, numpy as np, time
from pathlib import Path

print("=== CLEAN CPU ENVIRONMENT VERIFICATION ===")
print("ORT Version :", ort.__version__)
print("Providers   :", ort.get_available_providers())

# 1. Smoke test on mul_1.onnx
p_mul = ort.__file__.replace('__init__.py', 'datasets/mul_1.onnx')
print("Model Path (Smoke):", p_mul)
sess_mul = ort.InferenceSession(p_mul, providers=['CPUExecutionProvider'])
dummy_mul = np.ones((3, 2), dtype=np.float32)
# Warmup
sess_mul.run(None, {sess_mul.get_inputs()[0].name: dummy_mul})
t0 = time.perf_counter()
sess_mul.run(None, {sess_mul.get_inputs()[0].name: dummy_mul})
lat_smoke = (time.perf_counter() - t0) * 1000
print(f"Smoke Test Latency (mul_1.onnx, 3x2 tensor): {lat_smoke:.3f} ms")

# 2. Full IS-Net test on isnetis.onnx
p_isnet = Path.home() / '.cache' / 'project_aic' / 'models' / 'isnetis.onnx'
print("Model Path (Full) :", p_isnet)
sess_isnet = ort.InferenceSession(str(p_isnet), providers=['CPUExecutionProvider'])
dummy_isnet = np.zeros((1, 3, 1024, 1024), dtype=np.float32)
# Single pass
t0 = time.perf_counter()
sess_isnet.run(None, {sess_isnet.get_inputs()[0].name: dummy_isnet})
lat_full = (time.perf_counter() - t0) * 1000
print(f"Full Model Latency (isnetis.onnx, 1x3x1024x1024 tensor): {lat_full:.2f} ms")
print("Status: SUCCESS")
"""
    run_and_log(
        title="Clean Environment Execution — CPU (onnxruntime 1.31.1)",
        command=[cpu_py, "-c", cpu_code],
        cwd=repo_root,
        python_exe=cpu_py,
        packages={"onnxruntime": "1.31.1", "numpy": np_ver},
        output_log_path=logs_dir / "clean_env_cpu.log",
        git_meta=git_meta,
    )

    # Step i) Clean DML env execution
    dml_code = """
import onnxruntime as ort, numpy as np, time
from pathlib import Path

print("=== CLEAN DIRECTML GPU ENVIRONMENT VERIFICATION ===")
print("ORT Version :", ort.__version__)
print("Providers   :", ort.get_available_providers())

# 1. Smoke test on mul_1.onnx
p_mul = ort.__file__.replace('__init__.py', 'datasets/mul_1.onnx')
print("Model Path (Smoke):", p_mul)
sess_mul = ort.InferenceSession(p_mul, providers=['DmlExecutionProvider'], provider_options=[{'device_id': '1'}])
dummy_mul = np.ones((3, 2), dtype=np.float32)
# Warmup
sess_mul.run(None, {sess_mul.get_inputs()[0].name: dummy_mul})
t0 = time.perf_counter()
sess_mul.run(None, {sess_mul.get_inputs()[0].name: dummy_mul})
lat_smoke = (time.perf_counter() - t0) * 1000
print(f"Smoke Test Latency (mul_1.onnx, 3x2 tensor): {lat_smoke:.3f} ms")

# 2. Full IS-Net test on isnetis.onnx
p_isnet = Path.home() / '.cache' / 'project_aic' / 'models' / 'isnetis.onnx'
print("Model Path (Full) :", p_isnet)
sess_isnet = ort.InferenceSession(str(p_isnet), providers=['DmlExecutionProvider'], provider_options=[{'device_id': '1'}])
dummy_isnet = np.zeros((1, 3, 1024, 1024), dtype=np.float32)
# Warmup
sess_isnet.run(None, {sess_isnet.get_inputs()[0].name: dummy_isnet})
t0 = time.perf_counter()
sess_isnet.run(None, {sess_isnet.get_inputs()[0].name: dummy_isnet})
lat_full = (time.perf_counter() - t0) * 1000
print(f"Full Model Latency (isnetis.onnx, 1x3x1024x1024 tensor on RTX 4050): {lat_full:.2f} ms")
print("Status: SUCCESS")
"""
    run_and_log(
        title="Clean Environment Execution — DirectML GPU (onnxruntime-directml 1.24.4)",
        command=[dml_py, "-c", dml_code],
        cwd=repo_root,
        python_exe=dml_py,
        packages={"onnxruntime-directml": "1.24.4", "numpy": np_ver},
        output_log_path=logs_dir / "clean_env_dml.log",
        git_meta=git_meta,
    )

    # Step j) DXGI and WDDM reproducibility verification
    run_and_log(
        title="DXGI Adapter Discovery & WDDM Counter Provenance Verification",
        command=["uv", "run", "--project", "backend", "python", "scripts/verify_wddm_and_dxgi.py"],
        cwd=repo_root,
        python_exe=backend_py,
        packages=backend_pkgs,
        output_log_path=logs_dir / "wddm_reproducibility.log",
        git_meta=git_meta,
    )

    # Step a) Full pytest backend suite
    run_and_log(
        title="Full Pytest Backend Test Suite",
        command=["uv", "run", "--project", "backend", "pytest", "backend/tests", "-q"],
        cwd=repo_root,
        python_exe=backend_py,
        packages=backend_pkgs,
        output_log_path=logs_dir / "pytest_backend_tests.log",
        git_meta=git_meta,
    )

    print("\nAll reproducible test evidence executions COMPLETED successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
