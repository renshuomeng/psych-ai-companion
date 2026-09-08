from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from kb_v11_utils import (
    all_chunks,
    has_unsafe_operational_detail,
    load_chunks_by_status,
    load_registry,
    normalize_review_status,
    split_chunks_by_status,
    utc_now_iso,
    write_chunks_by_status,
    write_json_atomic,
)


TARGET_COLLECTIONS = {"campus_support", "evidence", "governance", "safety"}
INTERNAL_USE_MODES = {"agent_policy_only", "clinical_reference_only", "evidence_only"}
TRUSTED_AUTHORITIES = {"tier_a", "tier_b", "clinical_public_service", "official_public_source"}
COMMON_HOLD_REASON_MARKERS = {
    "too_short",
    "版权/导航",
    "网页元数据",
    "错误页",
    "目录",
    "页码碎片",
    "非知识正文",
}
SAFETY_HOLD_REASON_MARKERS = {
    "自伤方式",
    "减害细节",
    "临床治疗",
    "操作性细节",
    "求助信息，来源可靠但属于高风险内容，需安全专项复核",
}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _collection(chunk: dict[str, Any]) -> str:
    return str(chunk.get("target_collection") or chunk.get("collection") or "").strip()


def _reason_text(chunk: dict[str, Any]) -> str:
    return str(chunk.get("rejection_reason") or chunk.get("review_comment") or "")


def _has_marker(text: str, markers: set[str]) -> bool:
    return any(marker in text for marker in markers)


def eligibility_reason(chunk: dict[str, Any]) -> tuple[bool, str]:
    collection = _collection(chunk)
    if collection not in TARGET_COLLECTIONS:
        return False, "not_target_collection"
    if normalize_review_status(chunk.get("review_status")) == "approved":
        return False, "already_approved"
    if _as_bool(chunk.get("exclude_from_index")):
        return False, "exclude_from_index"

    content = str(chunk.get("content") or "").strip()
    if has_unsafe_operational_detail(content):
        return False, "unsafe_operational_detail"
    if len(content) < 120:
        return False, "too_short"
    if not _as_bool(chunk.get("eligible_for_approval")):
        return False, "source_not_eligible_for_approval"

    authority = str(chunk.get("source_authority") or "").strip().lower()
    if authority and authority not in TRUSTED_AUTHORITIES:
        return False, "source_authority_not_trusted"

    reason = _reason_text(chunk)
    if _has_marker(reason, COMMON_HOLD_REASON_MARKERS):
        return False, "previous_review_reason_requires_hold"

    use_mode = str(chunk.get("use_mode") or "").strip()
    risk_scope = str(chunk.get("risk_scope") or "").strip()
    if collection == "safety":
        if use_mode != "safety_only" or risk_scope != "safety_route_only":
            return False, "safety_scope_mismatch"
        if len(content) < 160:
            return False, "safety_chunk_too_short"
        if _has_marker(reason, SAFETY_HOLD_REASON_MARKERS):
            return False, "safety_specialist_review_required"
        return True, "route_scoped_safety_production"

    if collection == "evidence":
        if use_mode not in {"clinical_reference_only", "evidence_only"}:
            return False, "evidence_scope_mismatch"
        return True, "route_scoped_evidence_production"

    if collection in {"campus_support", "governance"}:
        if use_mode not in INTERNAL_USE_MODES:
            return False, "internal_scope_mismatch"
        return True, f"route_scoped_{collection}_production"

    return False, "not_eligible"


def _approval_comment(collection: str) -> str:
    return (
        f"Route-scoped production approval for {collection}: indexed for dedicated router/internal safety use only; "
        "not allowed for ordinary user-facing self-help retrieval."
    )


def approve_route_scoped_chunks(
    *,
    registry_path: str | Path | None,
    apply: bool,
    reviewed_by: str,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    grouped = load_chunks_by_status(registry)
    chunks = all_chunks(grouped)
    now = utc_now_iso()

    eligible_indexes: list[int] = []
    held = Counter()
    before = Counter(_collection(chunk) for chunk in chunks if _collection(chunk) in TARGET_COLLECTIONS)
    before_status = Counter(
        (_collection(chunk), normalize_review_status(chunk.get("review_status")))
        for chunk in chunks
        if _collection(chunk) in TARGET_COLLECTIONS
    )

    for index, chunk in enumerate(chunks):
        eligible, reason = eligibility_reason(chunk)
        if eligible:
            eligible_indexes.append(index)
        elif _collection(chunk) in TARGET_COLLECTIONS and reason != "already_approved":
            held[reason] += 1

    changed_by_collection = Counter()
    changed_from_status = Counter()
    if apply:
        for index in eligible_indexes:
            chunk = dict(chunks[index])
            collection = _collection(chunk)
            previous_reason = str(chunk.pop("rejection_reason", "") or "")
            chunk["review_status"] = "approved"
            chunk["reviewed_at"] = now
            chunk["reviewed_by"] = reviewed_by
            chunk["review_comment"] = _approval_comment(collection)
            chunk["previous_rejection_reason"] = previous_reason
            chunk["approval_basis"] = "route_scoped_source_review_plus_automatic_safety_validation"
            chunk["route_scoped_production_approved"] = True
            chunk["ordinary_retrieval_allowed"] = False
            chunk["user_facing"] = False
            chunk["exclude_from_index"] = False
            chunks[index] = chunk
            changed_by_collection[collection] += 1
            changed_from_status[normalize_review_status(grouped_status_for_original(chunk, grouped))] += 1
        write_chunks_by_status(registry, split_chunks_by_status(chunks))
    else:
        for index in eligible_indexes:
            chunk = chunks[index]
            changed_by_collection[_collection(chunk)] += 1
            changed_from_status[normalize_review_status(chunk.get("review_status"))] += 1

    after_status = Counter(
        (_collection(chunk), normalize_review_status(chunk.get("review_status")))
        for chunk in chunks
        if _collection(chunk) in TARGET_COLLECTIONS
    )
    report = {
        "created_at": now,
        "applied": apply,
        "reviewed_by": reviewed_by,
        "target_collections": sorted(TARGET_COLLECTIONS),
        "eligible_for_route_scoped_approval": len(eligible_indexes),
        "changed_by_collection": dict(sorted(changed_by_collection.items())),
        "changed_from_status": dict(sorted(changed_from_status.items())),
        "held_by_reason": dict(sorted(held.items())),
        "before_collection_counts": dict(sorted(before.items())),
        "before_status_counts": {
            f"{collection}:{status}": count for (collection, status), count in sorted(before_status.items())
        },
        "after_status_counts": {
            f"{collection}:{status}": count for (collection, status), count in sorted(after_status.items())
        },
        "ordinary_retrieval_guardrail": {
            "user_facing": False,
            "note": "Approved chunks remain route-scoped by collection/use_mode/risk_scope; ordinary RAG filtering still excludes them.",
        },
    }
    report_path = registry.paths["reports"] / "route_scoped_production_review.json"
    write_json_atomic(report_path, report)
    report["report_path"] = report_path.as_posix()
    return report


def grouped_status_for_original(chunk: dict[str, Any], grouped: dict[str, list[dict[str, Any]]]) -> str:
    chunk_id = str(chunk.get("chunk_id") or "")
    for status, rows in grouped.items():
        if any(str(row.get("chunk_id") or "") == chunk_id for row in rows):
            return status
    return str(chunk.get("review_status") or "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve route-scoped internal/safety KB chunks for production indexes.")
    parser.add_argument("--registry", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reviewed-by", default="Codex route-scoped production review")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = approve_route_scoped_chunks(
        registry_path=args.registry,
        apply=bool(args.apply),
        reviewed_by=args.reviewed_by,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"applied: {report['applied']}")
        print(f"eligible_for_route_scoped_approval: {report['eligible_for_route_scoped_approval']}")
        print(f"changed_by_collection: {json.dumps(report['changed_by_collection'], ensure_ascii=False)}")
        print(f"held_by_reason: {json.dumps(report['held_by_reason'], ensure_ascii=False)}")
        print(f"report_path: {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
