from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "rag"))
sys.path.insert(0, str(ROOT / "backend"))

import _bootstrap  # noqa: F401,E402
from build_production_indexes import _bm25_index_healthy, _eligible_production_chunks  # noqa: E402
from check_production_readiness import _readiness_payload  # noqa: E402
from approve_route_scoped_production_chunks import eligibility_reason  # noqa: E402
from review_sources import _is_children_or_adolescent_chunk, _is_high_risk_chunk, _is_perinatal_chunk  # noqa: E402
from run_retrieval_benchmark import _case_filter  # noqa: E402


def test_high_risk_review_does_not_treat_plain_p0_as_crisis() -> None:
    chunk = {
        "target_collection": "interventions",
        "use_mode": "direct_user_support",
        "risk_scope": "normal",
        "review_priority": "P0",
        "topics": ["anxiety"],
        "content": "A grounding exercise that invites the user to notice breathing and take a small next step.",
    }
    assert _is_high_risk_chunk(chunk) is False


def test_high_risk_review_keeps_safety_chunks_separate() -> None:
    chunk = {
        "target_collection": "safety",
        "use_mode": "safety_only",
        "risk_scope": "safety_route_only",
        "review_priority": "P0",
        "topics": ["self_harm"],
        "content": "Safety planning guidance for crisis support and referral.",
    }
    assert _is_high_risk_chunk(chunk) is True


def test_production_index_uses_approved_chunks_only() -> None:
    rows = [
        {"chunk_id": "pending", "review_status": "pending", "content": "pending content"},
        {"chunk_id": "approved", "review_status": "approved", "content": "approved content"},
        {"chunk_id": "excluded", "review_status": "approved", "content": "excluded content", "exclude_from_index": True},
    ]
    eligible = _eligible_production_chunks(rows)
    assert [row["chunk_id"] for row in eligible] == ["approved"]


def test_route_scoped_internal_chunk_can_be_approved_for_dedicated_production_index() -> None:
    eligible, reason = eligibility_reason(
        {
            "chunk_id": "safety_1",
            "target_collection": "safety",
            "review_status": "pending",
            "source_authority": "tier_a",
            "eligible_for_approval": True,
            "use_mode": "safety_only",
            "risk_scope": "safety_route_only",
            "content": "Safety planning should focus on immediate support, reducing isolation, contacting trusted people, and using local emergency or crisis resources when danger may be present.",
        }
    )

    assert eligible is True
    assert reason == "route_scoped_safety_production"


def test_route_scoped_internal_chunk_holds_operational_detail() -> None:
    eligible, reason = eligibility_reason(
        {
            "chunk_id": "unsafe_1",
            "target_collection": "safety",
            "review_status": "pending",
            "source_authority": "tier_a",
            "eligible_for_approval": True,
            "use_mode": "safety_only",
            "risk_scope": "safety_route_only",
            "content": "This unsafe text includes a lethal dose and should never enter the production safety index.",
        }
    )

    assert eligible is False
    assert reason == "unsafe_operational_detail"


def test_benchmark_population_is_not_a_hard_filter() -> None:
    case = {
        "query": "我最近学习压力很大",
        "expected_use_modes": ["direct_user_support"],
        "expected_population_tags": ["university_students"],
    }
    metadata_filter = _case_filter(case)
    assert metadata_filter["use_mode"] == ["direct_user_support"]
    assert "population_tags" not in metadata_filter


def test_review_priority_classifiers_keep_young_adults_separate() -> None:
    assert not _is_children_or_adolescent_chunk({"population_tags": ["young_adults"]})
    assert _is_children_or_adolescent_chunk({"population_tags": ["adolescents"]})
    assert _is_perinatal_chunk({"population_tags": ["postpartum_people"]})


def test_bm25_health_check_validates_required_files(tmp_path: Path) -> None:
    (tmp_path / "bm25_index.pkl").write_bytes(b"placeholder")
    (tmp_path / "documents.jsonl").write_text('{"chunk_id":"one"}\n', encoding="utf-8")
    (tmp_path / "metadata.json").write_text('{"documents":1}\n', encoding="utf-8")
    assert _bm25_index_healthy(tmp_path, 1) == (True, "ok")
    healthy, reason = _bm25_index_healthy(tmp_path, 2)
    assert healthy is False
    assert reason.startswith("document_count_mismatch")


def test_v2_1_readiness_gate_reports_core_checks() -> None:
    payload = _readiness_payload()
    expected_checks = {
        "registry_valid",
        "benchmark_leakage_passed",
        "training_leakage_guard_configured",
        "approved_production_chunks_gt_zero",
        "full_dense_coverage_for_production",
        "full_bm25_coverage_for_production",
        "safety_leakage_zero",
        "wrong_use_mode_zero",
        "full_retrieval_benchmark_completed",
        "production_manifest_exists",
        "rollback_supported",
    }
    assert expected_checks <= set(payload["checks"])
