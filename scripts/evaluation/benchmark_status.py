from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "evaluation" / "benchmarks" / "registry.yaml"
PACK_PATH = ROOT / "evaluation" / "benchmarks" / "packs" / "care_psy_core_v1.yaml"
MANIFEST_PATH = ROOT / "evaluation" / "benchmarks" / "frozen_manifest.json"
LEAKAGE_PATH = ROOT / "evaluation" / "benchmarks" / "leakage_report.json"


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def status_payload() -> dict[str, Any]:
    registry = load_yaml(REGISTRY_PATH)
    pack = load_yaml(PACK_PATH)
    manifest = load_json(MANIFEST_PATH)
    leakage = load_json(LEAKAGE_PATH)
    datasets = []
    ready_count = 0
    not_ready_reasons: list[str] = []
    for dataset in pack.get("datasets", []):
        if not isinstance(dataset, dict):
            continue
        path = ROOT / str(dataset.get("normalized_path", ""))
        enabled = bool(dataset.get("enabled"))
        row_count = count_jsonl(path) if enabled else 0
        if enabled and row_count:
            ready_count += row_count
        if enabled and not row_count:
            not_ready_reasons.append(f"{dataset.get('dataset_id')} has no rows")
        datasets.append(
            {
                "dataset_id": dataset.get("dataset_id"),
                "status": dataset.get("status"),
                "enabled": enabled,
                "sample_count": row_count if enabled else dataset.get("sample_count", 0),
                "path": dataset.get("normalized_path"),
            }
        )

    manifest_ok = bool(manifest.get("frozen")) and manifest.get("registry_sha256") == sha256_file(REGISTRY_PATH)
    manifest_ok = manifest_ok and manifest.get("pack_sha256") == sha256_file(PACK_PATH)
    leakage_ok = leakage.get("status") == "passed"
    if not manifest_ok:
        not_ready_reasons.append("frozen_manifest_hash_mismatch_or_missing")
    if not leakage_ok:
        not_ready_reasons.append("benchmark_leakage_report_not_passed")

    return {
        "registry_version": registry.get("version"),
        "default_pack": registry.get("default_pack"),
        "pack_id": pack.get("pack_id"),
        "pack_status": registry.get("benchmark_packs", {}).get(pack.get("pack_id", ""), {}).get("status"),
        "ready_case_count": ready_count,
        "datasets": datasets,
        "external_benchmarks": registry.get("external_benchmarks", {}),
        "manifest": {
            "exists": MANIFEST_PATH.exists(),
            "frozen": bool(manifest.get("frozen")),
            "hashes_match_current_files": manifest_ok,
            "path": str(MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"),
        },
        "leakage": {
            "exists": LEAKAGE_PATH.exists(),
            "status": leakage.get("status", "missing"),
            "exact_hash_overlap_count": leakage.get("exact_hash_overlap_count"),
            "normalized_hash_overlap_count": leakage.get("normalized_hash_overlap_count"),
        },
        "production_ready": ready_count == 160 and manifest_ok and leakage_ok,
        "not_ready_reasons": not_ready_reasons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Report CARE-Psy Benchmark V1 readiness.")
    parser.add_argument("--json", action="store_true", help="Print JSON. This is the default format.")
    args = parser.parse_args()
    _ = args
    print(json.dumps(status_payload(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except ModuleNotFoundError as exc:
        if exc.name == "yaml":
            raise SystemExit("PyYAML is required. Install backend/requirements.txt first.") from exc
        raise
