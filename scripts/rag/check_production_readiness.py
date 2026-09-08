from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "rag"))

import _bootstrap  # noqa: F401,E402
from kb_status import build_status  # noqa: E402


def _readiness_payload(registry_path: str | None = None) -> dict:
    status = build_status(registry_path)
    benchmark = status.get("benchmark") or {}
    benchmark_summary = benchmark.get("summary") or {}
    production_indexable = status["chunks"]["indexable_production"]
    dense_production = status["indexes"]["dense_production_vectors"]
    bm25_production = status["indexes"]["bm25_production_documents"]
    production_manifest = ROOT / "backend" / "data" / "knowledge_base" / "reports" / "production_index_manifest.json"
    leakage_report = ROOT / "evaluation" / "rag_v2" / "results" / "benchmark_leakage_report.json"
    checks = {
        "registry_valid": bool(status["registry"]["sources"] and status["registry"]["hash"]),
        "benchmark_leakage_passed": False,
        "training_leakage_guard_configured": (
            ROOT / "backend" / "data" / "knowledge_base" / "sources" / "excluded_evaluation_sources.yaml"
        ).exists(),
        "approved_production_chunks_gt_zero": production_indexable > 0,
        "full_dense_coverage_for_production": dense_production >= production_indexable > 0,
        "full_bm25_coverage_for_production": bm25_production >= production_indexable > 0,
        "safety_leakage_zero": benchmark_summary.get("hybrid_safety_leakage_rate") == 0,
        "wrong_use_mode_zero": (
            benchmark_summary.get("hybrid_wrong_use_mode_retrieval_rate", benchmark_summary.get("hybrid_wrong_use_mode_rate"))
            == 0
        ),
        "full_retrieval_benchmark_completed": bool(benchmark.get("exists") and benchmark.get("cases") == status["queries"]["count"]),
        "production_manifest_exists": production_manifest.exists(),
        "rollback_supported": True,
    }
    if leakage_report.exists():
        try:
            checks["benchmark_leakage_passed"] = json.loads(leakage_report.read_text(encoding="utf-8")).get("status") == "pass"
        except Exception:
            checks["benchmark_leakage_passed"] = False
    blockers = [name for name, passed in checks.items() if not passed]
    return {
        "production_ready": not blockers,
        "staging_ready": status["staging_ready"],
        "blockers": blockers,
        "checks": checks,
        "approved_chunks": status["chunks"]["approved"],
        "pending_chunks": status["chunks"]["pending"],
        "bm25_production_documents": bm25_production,
        "dense_production_vectors": dense_production,
        "benchmark_cases": benchmark.get("cases"),
        "production_manifest": production_manifest.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether CARE-Psy Knowledge Base V2.1 can be used in production mode.")
    parser.add_argument("--registry", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = _readiness_payload(args.registry)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        status = "READY" if payload["production_ready"] else "NOT_READY"
        print(f"production_status: {status}")
        print(f"approved_chunks: {payload['approved_chunks']}")
        print(f"pending_chunks: {payload['pending_chunks']}")
        print(f"bm25_production_documents: {payload['bm25_production_documents']}")
        print(f"dense_production_vectors: {payload['dense_production_vectors']}")
        print(f"benchmark_cases: {payload['benchmark_cases']}")
        if payload["blockers"]:
            print("blockers:")
            for item in payload["blockers"]:
                print(f"- {item}")
    return 0 if payload["production_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
