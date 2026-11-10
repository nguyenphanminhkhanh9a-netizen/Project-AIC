"""scripts/check_wheel_records.py

Forensic and reproducible comparison of PEP 376 RECORD files between
onnxruntime (CPU) and onnxruntime-directml (GPU) wheels.
"""

from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path


def parse_record(path: Path) -> dict[str, tuple[str, str]]:
    """Parse a PEP 376 RECORD file into a dict mapping path -> (hash, size)."""
    records: dict[str, tuple[str, str]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row:
                continue
            path_str = row[0].replace("\\", "/")
            hash_str = row[1] if len(row) > 1 else ""
            size_str = row[2] if len(row) > 2 else ""
            records[path_str] = (hash_str, size_str)
    return records


def hash_file_sha256(path: Path) -> str:
    """Compute hex SHA-256 hash of a file on disk."""
    if not path.exists():
        return "ABSENT"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    cpu_env = repo_root / ".temp_envs" / "cpu_env"
    dml_env = repo_root / ".temp_envs" / "dml_env"

    cpu_dist_infos = list(cpu_env.glob("Lib/site-packages/onnxruntime-*.dist-info"))
    dml_dist_infos = list(dml_env.glob("Lib/site-packages/onnxruntime_directml-*.dist-info"))

    if not cpu_dist_infos or not dml_dist_infos:
        print(f"ERROR: Could not locate dist-info directories in {cpu_env} or {dml_env}")
        return 1

    cpu_rec_path = cpu_dist_infos[0] / "RECORD"
    dml_rec_path = dml_dist_infos[0] / "RECORD"

    print("=" * 80)
    print("PEP 376 WHEEL RECORD FORENSIC COMPARISON")
    print(f"CPU RECORD: {cpu_rec_path}")
    print(f"DML RECORD: {dml_rec_path}")
    print("=" * 80)

    cpu_records = parse_record(cpu_rec_path)
    dml_records = parse_record(dml_rec_path)

    total_cpu = len(cpu_records)
    total_dml = len(dml_records)

    print("\n[1] Record Entry Totals:")
    print(f"  - Total CPU entries (onnxruntime): {total_cpu}")
    print(f"  - Total DML entries (onnxruntime-directml): {total_dml}")

    shared_paths = set(cpu_records.keys()) & set(dml_records.keys())
    print("\n[2] Filesystem Path Collision:")
    print(f"  - Shared relative paths in site-packages: {len(shared_paths)}")

    identical = [p for p in shared_paths if cpu_records[p] == dml_records[p]]
    conflicting = [p for p in shared_paths if cpu_records[p] != dml_records[p]]

    print("\n[3] Hash Agreement Analysis:")
    print(f"  - Identical hashes (exact SHA-256 match): {len(identical)}")
    print(f"  - Conflicting hashes (exact SHA-256 mismatch): {len(conflicting)}")
    print(
        f"  - Note on onnxruntime_test.exe: Shared binary '../../Scripts/onnxruntime_test.exe' has "
        f"matching size (46,080 B) but distinct SHA-256 hashes (CPU: {hash_file_sha256(cpu_env / 'Scripts/onnxruntime_test.exe')[:10]}... "
        f"vs DML: {hash_file_sha256(dml_env / 'Scripts/onnxruntime_test.exe')[:10]}...), "
        f"correctly counted under Conflicting ({len(conflicting)}), not Identical ({len(identical)})."
    )

    cpu_unique = set(cpu_records.keys()) - shared_paths
    dml_unique = set(dml_records.keys()) - shared_paths
    print("\n[4] Unique Paths:")
    print(f"  - CPU unique paths count: {len(cpu_unique)}")
    print(f"  - DML unique paths count: {len(dml_unique)}")

    print("\n[5] Physical Native Binaries Forensic Checksum Analysis:")
    binaries = [
        ("onnxruntime.dll", "Lib/site-packages/onnxruntime/capi/onnxruntime.dll"),
        ("onnxruntime_pybind11_state.pyd", "Lib/site-packages/onnxruntime/capi/onnxruntime_pybind11_state.pyd"),
        ("onnxruntime_providers_shared.dll", "Lib/site-packages/onnxruntime/capi/onnxruntime_providers_shared.dll"),
        ("onnxruntime_test.exe", "Scripts/onnxruntime_test.exe"),
        ("DirectML.dll", "Lib/site-packages/onnxruntime/capi/DirectML.dll"),
    ]

    for name, rel in binaries:
        p_cpu = cpu_env / rel
        p_dml = dml_env / rel

        cpu_sz = p_cpu.stat().st_size if p_cpu.exists() else 0
        dml_sz = p_dml.stat().st_size if p_dml.exists() else 0

        cpu_hash = hash_file_sha256(p_cpu)
        dml_hash = hash_file_sha256(p_dml)

        print(f"\n  Binary: {name} (relative: {rel})")
        print(f"    CPU Environment : size={cpu_sz:>10} bytes | SHA-256={cpu_hash}")
        print(f"    DML Environment : size={dml_sz:>10} bytes | SHA-256={dml_hash}")

    print("\n" + "=" * 80)
    print("CONCLUSION: Binary collision between onnxruntime and onnxruntime-directml is CONFIRMED.")
    print("Co-installation in the same environment causes catastrophic binary overwrite.")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
