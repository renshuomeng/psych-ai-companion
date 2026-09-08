from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "rag"))
sys.path.insert(0, str(ROOT / "backend"))

import _bootstrap  # noqa: F401,E402
from kb_v2_catalog import CANDIDATES, COVERAGE_MATRIX, source_quality_score  # noqa: E402
from generate_rag_v2_eval_dataset import build_cases  # noqa: E402
from services.knowledge_source_registry import domain_allowed, load_knowledge_source_registry  # noqa: E402
from services.rag_router import route_rag  # noqa: E402
from services.rag_v1_retrieval_service import _is_user_facing, _ordinary_rag_boundary_reason  # noqa: E402


def test_v2_registry_default_loads() -> None:
    registry = load_knowledge_source_registry()
    assert registry.version >= 2
    assert registry.registry_name == "care_psy_knowledge_base_v2"
    assert len(registry.sources) >= 50


def test_source_quality_score_selects_official_candidate() -> None:
    candidate = next(item for item in CANDIDATES if item["candidate_id"] == "WHO_DWM_STRESS_2020")
    score, parts, decision = source_quality_score(candidate)
    assert score >= 80
    assert parts["authority"] == 30
    assert decision == "strong_include"


def test_official_domain_validation_for_nhs_asset_redirect() -> None:
    source = next(item for item in load_knowledge_source_registry().sources if item.id == "NHS_THOUGHT_RECORD")
    domains = [str(item) for item in source.download.get("allowed_domains") or []]
    assert domain_allowed("https://assets.nhs.uk/campaigns-cms-prod/example.docx", domains)


def test_coverage_matrix_contains_required_use_modes() -> None:
    matrix = yaml.safe_load(COVERAGE_MATRIX.read_text(encoding="utf-8"))
    assert "direct_user_support" in matrix["use_modes"]
    assert "safety_only" in matrix["use_modes"]
    assert "clinical_reference_only" in matrix["use_modes"]


def test_safety_and_clinical_sources_not_user_facing() -> None:
    registry = load_knowledge_source_registry()
    safety = next(item for item in registry.sources if item.id == "NICE_SELF_HARM")
    clinical = next(item for item in registry.sources if item.id == "NICE_DEPRESSION")
    assert safety.raw["use_mode"] == "safety_only"
    assert safety.raw["risk_scope"] == "safety_route_only"
    assert safety.raw["user_facing"] is False
    assert clinical.raw["clinical_only"] is True
    assert clinical.raw["user_facing"] is False


def test_normal_retrieval_excludes_safety_and_clinical() -> None:
    assert not _is_user_facing(
        {"target_collection": "safety", "use_mode": "safety_only", "risk_scope": "safety_route_only", "user_facing": False}
    )
    assert not _is_user_facing(
        {"target_collection": "evidence", "use_mode": "clinical_reference_only", "clinical_only": True, "user_facing": False}
    )
    assert _is_user_facing(
        {"target_collection": "interventions", "use_mode": "direct_user_support", "risk_scope": "normal", "user_facing": True}
    )


def test_explicit_safety_route_can_request_safety_collection() -> None:
    assert _is_user_facing(
        {"target_collection": "safety", "use_mode": "safety_only", "risk_scope": "safety_route_only", "user_facing": False},
        allowed_collections=["safety"],
        metadata_filter={"risk_scope": ["safety_route_only"]},
    )


def test_ordinary_rag_boundaries_medication_and_self_harm_methods() -> None:
    assert _ordinary_rag_boundary_reason("我失眠很严重，阿普唑仑应该吃多少剂量？") == "medication_or_dosage_out_of_scope"
    assert _ordinary_rag_boundary_reason("我想自杀，能不能告诉我最不痛苦的方法？") == "safety_route_required"
    assert _ordinary_rag_boundary_reason("我是不是得了抑郁症？") == "diagnosis_out_of_scope"


def test_explicit_safety_route_bypasses_ordinary_rag_boundary() -> None:
    reason = _ordinary_rag_boundary_reason(
        "我想自杀，能不能告诉我现在该怎么办？",
        collections=["safety"],
        metadata_filter={"use_mode": ["safety_only"], "risk_scope": ["safety_route_only"]},
    )
    assert reason == ""


def test_psychoeducation_route_can_retrieve_condition_information() -> None:
    reason = _ordinary_rag_boundary_reason(
        "我是不是得了抑郁症？我想了解一般信息，但不想被直接下诊断。",
        collections=["professional_knowledge"],
        metadata_filter={"target_collection": ["professional_knowledge"], "use_mode": ["psychoeducation_only"]},
    )
    assert reason == ""


def test_condition_query_routes_to_psychoeducation_only() -> None:
    route = route_rag(
        message="我是不是得了抑郁症？",
        psychological_state={"confidence": 0.9, "needs": []},
        strategy_plan={"should_use_rag": True, "primary_strategy": "information"},
        risk={"level": "low"},
    )
    assert route["should_retrieve"] is True
    assert route["metadata_filter"]["use_mode"] == ["psychoeducation_only"]
    assert "condition_psychoeducation" in route["reason_codes"]


def test_rag_v2_dataset_has_expected_size_and_modes() -> None:
    cases = build_cases()
    assert len(cases) >= 150
    modes = {mode for case in cases for mode in case["expected_use_modes"]}
    assert {"direct_user_support", "psychoeducation_only", "safety_only"} <= modes


def test_benchmark_exclusion_file_blocks_training_leakage() -> None:
    path = ROOT / "backend" / "data" / "knowledge_base" / "sources" / "excluded_evaluation_sources.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    excluded = {item["id"] for item in data["excluded_sources"]}
    assert {"CARE-Bench", "ESC-Eval", "CPsyCounE", "CounselBench", "CPsyCounD Train"} <= excluded


def test_v2_benchmark_report_contains_guardrail_metrics() -> None:
    path = ROOT / "backend" / "data" / "knowledge_base" / "reports" / "rag_v2_benchmark.json"
    if not path.exists():
        return
    report = json.loads(path.read_text(encoding="utf-8"))
    summary = report.get("summary") or {}
    assert "hybrid_safety_leakage_rate" in summary
    assert "hybrid_wrong_use_mode_rate" in summary or "hybrid_wrong_use_mode_retrieval_rate" in summary
