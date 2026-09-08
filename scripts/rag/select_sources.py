from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "rag"))
sys.path.insert(0, str(ROOT / "backend"))

from kb_v2_catalog import (  # noqa: E402
    CANDIDATES,
    COVERAGE_MATRIX,
    EVALUATION_SOURCE_IDS,
    REPORTS_DIR,
    SOURCES_DIR,
    V1_REGISTRY,
    V2_REGISTRY,
    registry_source_from_candidate,
    utc_now_iso,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


def _listify(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    return [str(value)]


def _infer_use_mode(source: dict[str, Any]) -> str:
    collection = str(source.get("target_collection") or source.get("collection") or "")
    topics = {str(item) for item in _listify(source.get("topics"))}
    source_type = str(source.get("source_type") or "").lower()
    if collection == "safety" or topics & {"self_harm", "suicide", "suicidal_thoughts", "suicidal_plan"}:
        return "safety_only"
    if collection == "helping_skills" or "training" in source_type:
        return "helping_skills_only"
    if collection == "governance" or "policy" in source_type or "implementation" in source_type:
        return "agent_policy_only"
    if collection == "evidence" or "guideline" in source_type:
        return "clinical_reference_only"
    sensitive = {"bipolar", "bipolar_disorder", "psychosis", "eating_disorders", "OCD", "BDD", "PTSD", "substance_use", "dementia"}
    if topics & sensitive:
        return "psychoeducation_only"
    return "direct_user_support" if bool(source.get("user_facing", True)) else "psychoeducation_only"


def _authority_from_v1(source: dict[str, Any]) -> str:
    organization = str(source.get("organization") or "").lower()
    if "world health organization" in organization or organization == "who":
        return "tier_a"
    if "教育部" in organization or "国家" in organization:
        return "tier_a"
    if "nhs" in organization or "government" in organization or "centre for clinical interventions" in organization:
        return "tier_a"
    return "tier_b" if str(source.get("evidence_level") or "").upper() in {"A", "B"} else "tier_c"


def _upgrade_existing_source(source: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(source)
    collection = str(upgraded.get("target_collection") or upgraded.get("collection") or "professional_knowledge")
    topics = _listify(upgraded.get("topics"))
    use_mode = str(upgraded.get("use_mode") or _infer_use_mode(upgraded))
    risk_scope = "safety_route_only" if collection == "safety" or use_mode == "safety_only" else "normal"
    clinical_only = use_mode in {"clinical_reference_only", "evidence_only"}
    user_facing = use_mode == "direct_user_support" and collection in {"interventions", "professional_knowledge", "campus_support"}
    language_preference = _listify(upgraded.get("language_preference") or upgraded.get("language"))
    if not language_preference:
        language_preference = ["en"]
    upgraded.update(
        {
            "version": upgraded.get("version") or "v2",
            "target_collection": collection,
            "collection": collection,
            "official_url": upgraded.get("official_url") or upgraded.get("official_page_url") or "",
            "download_url": upgraded.get("download_url") or "",
            "language_preference": language_preference,
            "language": upgraded.get("language") or language_preference[0],
            "translation_group_id": upgraded.get("translation_group_id") or upgraded.get("id"),
            "topics": topics,
            "topic_tags": _listify(upgraded.get("topic_tags") or topics),
            "population_tags": _listify(upgraded.get("population_tags")) or ["university_students", "young_adults", "adults"],
            "life_stage_tags": _listify(upgraded.get("life_stage_tags")),
            "use_mode": use_mode,
            "risk_scope": risk_scope,
            "clinical_only": clinical_only,
            "user_facing": user_facing,
            "source_authority": upgraded.get("source_authority") or _authority_from_v1(upgraded),
            "license": upgraded.get("license") or upgraded.get("license_note") or "official_public_source_or_local_rag_only",
            "review_status": upgraded.get("review_status") or "pending",
            "eligible_for_approval": bool(upgraded.get("eligible_for_approval", True)),
            "quality_checked": bool(upgraded.get("quality_checked", False)),
            "expert_reviewed": bool(upgraded.get("expert_reviewed", False)),
            "last_checked_at": upgraded.get("last_checked_at") or "",
            "document_hash": upgraded.get("document_hash") or "",
        }
    )
    download = dict(upgraded.get("download") or {})
    allowed_domains = [str(item) for item in download.get("allowed_domains") or []]
    if "nhs" in str(upgraded.get("organization") or "").lower() and "assets.nhs.uk" not in allowed_domains:
        allowed_domains.append("assets.nhs.uk")
        download["allowed_domains"] = allowed_domains
        upgraded["download"] = download
    return upgraded


def _manual_acquisition_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in candidates:
        if item.get("downloadable") and item.get("auto_download", True) and item.get("decision") != "manual_review":
            continue
        rows.append(
            {
                "title": item["title"],
                "source": item["organization"],
                "official_url": item["official_url"],
                "why_useful": item.get("decision_reason", ""),
                "population": ",".join(item.get("population") or []),
                "topic": ",".join(item.get("topics") or []),
                "license": item.get("license", ""),
                "access_type": "manual_review_or_manual_download",
                "priority": "P1" if int(item.get("source_quality_score") or 0) >= 65 else "P2",
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_registry() -> dict[str, Any]:
    v1 = _load_yaml(V1_REGISTRY)
    sources_by_id: dict[str, dict[str, Any]] = {}
    for source in v1.get("sources") or []:
        source_id = str(source.get("id") or "")
        if not source_id:
            continue
        sources_by_id[source_id] = _upgrade_existing_source(source)

    selected = 0
    rejected = 0
    manual_review = 0
    for candidate in CANDIDATES:
        decision = str(candidate.get("decision") or "")
        if decision == "reject":
            rejected += 1
            continue
        if decision == "manual_review":
            manual_review += 1
        else:
            selected += 1
        source_id = str(candidate["candidate_id"])
        candidate_source = registry_source_from_candidate(candidate)
        if source_id in sources_by_id:
            merged = {**sources_by_id[source_id], **candidate_source}
            merged["download"] = sources_by_id[source_id].get("download") or candidate_source["download"]
            merged["auto_download"] = bool(sources_by_id[source_id].get("auto_download", candidate_source.get("auto_download")))
            sources_by_id[source_id] = _upgrade_existing_source(merged)
        else:
            sources_by_id[source_id] = _upgrade_existing_source(candidate_source)

    output = dict(v1)
    output.update(
        {
            "version": 2,
            "registry_name": "care_psy_knowledge_base_v2",
            "created_for": "psych-ai-companion",
            "knowledge_base_version": "V2",
            "coverage_matrix": str(COVERAGE_MATRIX.relative_to(ROOT)).replace("\\", "/"),
            "default_review_status": "pending",
            "default_chunk_review_required": True,
            "sources": sorted(sources_by_id.values(), key=lambda item: str(item.get("id") or "")),
        }
    )
    processing = dict(output.get("processing_policy") or {})
    fields = list(processing.get("metadata_fields") or [])
    for field in [
        "version",
        "translation_group_id",
        "population_tags",
        "topic_tags",
        "life_stage_tags",
        "collection",
        "use_mode",
        "risk_scope",
        "clinical_only",
        "source_authority",
        "license",
        "document_hash",
        "content_hash",
        "quality_checked",
        "expert_reviewed",
        "eligible_for_approval",
    ]:
        if field not in fields:
            fields.append(field)
    processing["metadata_fields"] = fields
    output["processing_policy"] = processing
    output.setdefault("index_policy", {})
    output["index_policy"]["ordinary_retrieval_filter"] = {
        "user_facing": True,
        "clinical_only": False,
        "use_mode": ["direct_user_support"],
        "risk_scope": ["normal", "general"],
    }
    return {
        "registry": output,
        "summary": {
            "created_at": utc_now_iso(),
            "registry_path": V2_REGISTRY.as_posix(),
            "sources": len(output["sources"]),
            "selected_candidates": selected,
            "manual_review_candidates": manual_review,
            "rejected_candidates": rejected,
        },
    }


def write_outputs() -> dict[str, Any]:
    built = build_registry()
    _write_yaml(V2_REGISTRY, built["registry"])
    manual_rows = _manual_acquisition_rows(CANDIDATES)
    _write_csv(REPORTS_DIR / "manual_acquisition_candidates.csv", manual_rows)
    exclusion = {
        "version": 1,
        "purpose": "Evaluation and training datasets must not be imported into the professional Knowledge RAG.",
        "excluded_sources": [{"id": item, "reason": "benchmark_or_training_leakage_risk"} for item in EVALUATION_SOURCE_IDS],
    }
    _write_yaml(SOURCES_DIR / "excluded_evaluation_sources.yaml", exclusion)
    summary_path = REPORTS_DIR / "source_selection_summary.json"
    summary_path.write_text(json.dumps(built["summary"], ensure_ascii=False, indent=2), encoding="utf-8")
    return {**built["summary"], "manual_acquisition_csv": (REPORTS_DIR / "manual_acquisition_candidates.csv").as_posix()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Select CARE-Psy Knowledge Base V2 sources and write the V2 registry.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = write_outputs()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"sources: {report['sources']}")
        print(f"registry: {report['registry_path']}")
        print(f"manual acquisition: {report['manual_acquisition_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
