from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
import re
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
    write_jsonl_atomic,
)


REVIEW_FIELDS = [
    "review_id",
    "created_at",
    "source_id",
    "decision",
    "reviewed_by",
    "comment",
    "propagated_chunks",
    "held_for_chunk_review",
]


def _reviews_path(registry: Any) -> Path:
    return registry.paths["reports"] / "source_reviews.jsonl"


def _read_reviews(registry: Any) -> list[dict[str, Any]]:
    path = _reviews_path(registry)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_reviews(registry: Any, rows: list[dict[str, Any]]) -> None:
    write_jsonl_atomic(_reviews_path(registry), rows)


def _source_map(registry: Any) -> dict[str, Any]:
    return {source.id: source for source in registry.sources}


def _source_chunks(grouped: dict[str, list[dict[str, Any]]], source_id: str) -> list[dict[str, Any]]:
    return [chunk for chunk in all_chunks(grouped) if str(chunk.get("source_id") or "") == source_id]


def _parse_list(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(item) for item in value if str(item).strip()}
    if value in (None, "", []):
        return set()
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return {str(item) for item in parsed if str(item).strip()}
        except json.JSONDecodeError:
            pass
    return {item.strip() for item in str(value).replace("，", ",").split(",") if item.strip()}


def _is_high_risk_chunk(chunk: dict[str, Any]) -> bool:
    collection = str(chunk.get("target_collection") or chunk.get("collection") or "").lower()
    use_mode = str(chunk.get("use_mode") or "").lower()
    risk_scope = str(chunk.get("risk_scope") or "").lower()
    topics = _parse_list(chunk.get("topics")) | _parse_list(chunk.get("topic_tags")) | {str(chunk.get("topic") or "")}
    sensitive_topics = {
        "self_harm",
        "suicide",
        "suicidal_thoughts",
        "suicidal_plan",
        "acute_crisis",
        "harm_to_others",
        "domestic_violence",
        "minor_safeguarding",
        "perinatal_crisis",
        "severe_psychosis",
        "substance_crisis",
    }
    return bool(
        collection == "safety"
        or use_mode == "safety_only"
        or risk_scope == "safety_route_only"
        or bool(sensitive_topics & {topic.strip() for topic in topics})
        or has_unsafe_operational_detail(str(chunk.get("content") or ""))
    )


def _normalized_tokens(*values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        if isinstance(value, list):
            tokens.update(_normalized_tokens(*value))
            continue
        text = str(value or "").strip().lower()
        if not text:
            continue
        tokens.add(text)
        tokens.update(item for item in re.split(r"[\s,;/|，；、\-_]+", text) if item)
    return tokens


def _is_children_or_adolescent_chunk(chunk: dict[str, Any]) -> bool:
    tokens = _normalized_tokens(
        chunk.get("population_tags"),
        chunk.get("life_stage_tags"),
        chunk.get("topics"),
        chunk.get("topic_tags"),
        chunk.get("topic"),
        chunk.get("title"),
    )
    markers = {
        "child",
        "children",
        "adolescent",
        "adolescents",
        "teen",
        "teens",
        "youth",
        "minor",
        "minors",
        "parent",
        "parents",
        "parenting",
        "亲子",
        "儿童",
        "青少年",
        "未成年",
    }
    return bool(tokens & markers)


def _is_perinatal_chunk(chunk: dict[str, Any]) -> bool:
    tokens = _normalized_tokens(
        chunk.get("population_tags"),
        chunk.get("life_stage_tags"),
        chunk.get("topics"),
        chunk.get("topic_tags"),
        chunk.get("topic"),
        chunk.get("title"),
    )
    markers = {
        "perinatal",
        "pregnancy",
        "pregnant",
        "postpartum",
        "postnatal",
        "maternal",
        "mother",
        "mothers",
        "孕产",
        "孕期",
        "产后",
        "母亲",
    }
    return bool(tokens & markers)


def _automatic_chunk_issues(chunk: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    required = [
        "chunk_id",
        "source_id",
        "title",
        "target_collection",
        "content",
        "official_page_url",
        "content_sha256",
        "use_mode",
        "risk_scope",
        "population_tags",
        "topic_tags",
        "license",
    ]
    for key in required:
        if chunk.get(key) in (None, "", []):
            issues.append(f"missing:{key}")
    content = str(chunk.get("content") or "")
    if len(content) < 80:
        issues.append("too_short")
    if len(content) > 2500:
        issues.append("too_long")
    if has_unsafe_operational_detail(content):
        issues.append("unsafe_operational_detail")
    if bool(chunk.get("clinical_only")) and bool(chunk.get("user_facing")):
        issues.append("clinical_only_marked_user_facing")
    if not bool(chunk.get("eligible_for_approval")):
        issues.append("source_not_marked_eligible_for_approval")
    if _is_high_risk_chunk(chunk):
        issues.append("requires_chunk_level_high_risk_review")
    return issues


def _latest_review_by_source(registry: Any) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in _read_reviews(registry):
        latest[str(row.get("source_id") or "")] = row
    return latest


def _record_review(
    registry: Any,
    *,
    source_id: str,
    decision: str,
    reviewed_by: str,
    comment: str,
    propagated_chunks: int = 0,
    held_for_chunk_review: int = 0,
) -> dict[str, Any]:
    if not reviewed_by.strip():
        raise SystemExit("--reviewed-by is required; source review cannot be inferred automatically")
    reviews = _read_reviews(registry)
    row = {
        "review_id": f"SRCREV_{source_id}_{len(reviews) + 1:05d}",
        "created_at": utc_now_iso(),
        "source_id": source_id,
        "decision": decision,
        "reviewed_by": reviewed_by,
        "comment": comment,
        "propagated_chunks": propagated_chunks,
        "held_for_chunk_review": held_for_chunk_review,
    }
    reviews.append(row)
    _write_reviews(registry, reviews)
    return row


def _source_summary(registry: Any, source_id: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    sources = _source_map(registry)
    source = sources.get(source_id)
    high_risk = sum(1 for chunk in chunks if _is_high_risk_chunk(chunk))
    eligible = sum(1 for chunk in chunks if not _automatic_chunk_issues(chunk))
    return {
        "source_id": source_id,
        "title": source.title if source else "",
        "organization": source.organization if source else "",
        "collection": source.target_collection if source else "",
        "enabled": source.enabled if source else False,
        "review_priority": source.raw.get("review_priority", "") if source else "",
        "use_mode": source.raw.get("use_mode", "") if source else "",
        "official_page_url": source.official_page_url if source else "",
        "chunk_count": len(chunks),
        "eligible_for_source_level_approval": eligible,
        "held_for_chunk_review": len(chunks) - eligible,
        "high_risk_chunks": high_risk,
        "review_status_counts": dict(Counter(normalize_review_status(chunk.get("review_status")) for chunk in chunks)),
    }


def cmd_list(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    grouped = load_chunks_by_status(registry)
    latest = _latest_review_by_source(registry)
    rows: list[dict[str, Any]] = []
    for source in registry.sources:
        if args.collection and source.target_collection != args.collection:
            continue
        chunks = _source_chunks(grouped, source.id)
        summary = _source_summary(registry, source.id, chunks)
        review = latest.get(source.id, {})
        summary["latest_source_decision"] = review.get("decision", "pending")
        summary["latest_reviewed_by"] = review.get("reviewed_by", "")
        rows.append(summary)
    for row in rows[: max(int(args.limit or 100), 1)]:
        print(json.dumps(row, ensure_ascii=False))
    print(f"total_listed: {min(len(rows), max(int(args.limit or 100), 1))}")
    print(f"source_reviews: {_reviews_path(registry).as_posix()}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    source = _source_map(registry).get(args.source_id)
    if not source:
        raise SystemExit(f"source not found: {args.source_id}")
    chunks = _source_chunks(load_chunks_by_status(registry), args.source_id)
    payload = _source_summary(registry, args.source_id, chunks)
    payload["raw"] = source.raw
    payload["latest_review"] = _latest_review_by_source(registry).get(args.source_id, {})
    payload["sample_chunks"] = [
        {
            "chunk_id": chunk.get("chunk_id"),
            "review_status": chunk.get("review_status"),
            "section": chunk.get("section"),
            "issues": _automatic_chunk_issues(chunk),
            "content_preview": " ".join(str(chunk.get("content") or "").split())[:220],
        }
        for chunk in chunks[: max(int(args.limit or 5), 1)]
    ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_review(args: argparse.Namespace, decision: str) -> int:
    registry = load_registry(args.registry)
    if args.source_id not in _source_map(registry):
        raise SystemExit(f"source not found: {args.source_id}")
    row = _record_review(
        registry,
        source_id=args.source_id,
        decision=decision,
        reviewed_by=args.reviewed_by,
        comment=args.comment or args.reason or "",
    )
    print(json.dumps(row, ensure_ascii=False, indent=2))
    if decision == "approved":
        print("source_approved_only: chunk status unchanged; run bulk-approve-eligible to propagate eligible non-high-risk chunks.")
    return 0


def cmd_bulk_approve_eligible(args: argparse.Namespace) -> int:
    if args.confirm_source_id != args.source_id:
        raise SystemExit("--confirm-source-id must exactly match SOURCE_ID")
    registry = load_registry(args.registry)
    if args.source_id not in _source_map(registry):
        raise SystemExit(f"source not found: {args.source_id}")
    grouped = load_chunks_by_status(registry)
    chunks = all_chunks(grouped)
    changed = 0
    held = 0
    now = utc_now_iso()
    for index, chunk in enumerate(chunks):
        if str(chunk.get("source_id") or "") != args.source_id:
            continue
        if normalize_review_status(chunk.get("review_status")) != "pending":
            continue
        issues = _automatic_chunk_issues(chunk)
        if issues:
            held += 1
            chunk["review_hold_reasons"] = issues
            continue
        chunks[index] = {
            **chunk,
            "review_status": "approved",
            "reviewed_at": now,
            "reviewed_by": args.reviewed_by,
            "review_comment": args.comment or "source-level review propagated after automatic chunk validation",
            "approval_basis": "human_source_review_plus_automatic_chunk_validation",
            "source_reviewed": True,
            "chunk_level_review_required": False,
        }
        changed += 1
    write_chunks_by_status(registry, split_chunks_by_status(chunks))
    row = _record_review(
        registry,
        source_id=args.source_id,
        decision="approved_with_eligible_chunk_propagation",
        reviewed_by=args.reviewed_by,
        comment=args.comment or "",
        propagated_chunks=changed,
        held_for_chunk_review=held,
    )
    print(json.dumps(row, ensure_ascii=False, indent=2))
    print(f"approved_chunks: {changed}")
    print(f"held_for_chunk_review: {held}")
    return 0


def cmd_export_priority(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    grouped = load_chunks_by_status(registry)
    chunks = all_chunks(grouped)
    output_dir = Path(args.output_dir) if args.output_dir else Path("reports")
    if not output_dir.is_absolute():
        output_dir = Path.cwd() / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "source_id",
        "chunk_id",
        "title",
        "target_collection",
        "use_mode",
        "risk_scope",
        "review_priority",
        "review_status",
        "issues",
        "content_preview",
    ]
    pending_chunks = [
        chunk
        for chunk in chunks
        if normalize_review_status(chunk.get("review_status")) == "pending"
    ]
    high_risk = [chunk for chunk in pending_chunks if _is_high_risk_chunk(chunk)]
    p1_non_high_risk = [
        chunk
        for chunk in pending_chunks
        if str(chunk.get("review_priority") or "").upper() == "P1" and not _is_high_risk_chunk(chunk)
    ]
    p1_interventions = [
        chunk
        for chunk in pending_chunks
        if str(chunk.get("target_collection") or "") == "interventions"
        and str(chunk.get("use_mode") or "") == "direct_user_support"
        and not _is_high_risk_chunk(chunk)
        and not _is_children_or_adolescent_chunk(chunk)
        and not _is_perinatal_chunk(chunk)
    ]
    p1_children = [
        chunk
        for chunk in pending_chunks
        if not _is_high_risk_chunk(chunk)
        and _is_children_or_adolescent_chunk(chunk)
        and str(chunk.get("chunk_id") or "") not in {str(item.get("chunk_id") or "") for item in p1_interventions}
    ]
    p1_perinatal = [
        chunk
        for chunk in pending_chunks
        if not _is_high_risk_chunk(chunk)
        and _is_perinatal_chunk(chunk)
        and str(chunk.get("chunk_id") or "") not in {str(item.get("chunk_id") or "") for item in p1_interventions}
    ]
    high_risk_ids = {str(chunk.get("chunk_id") or "") for chunk in high_risk}
    p1_children_ids = {str(chunk.get("chunk_id") or "") for chunk in p1_children}
    p1_perinatal_ids = {str(chunk.get("chunk_id") or "") for chunk in p1_perinatal}
    p1_intervention_ids = {str(chunk.get("chunk_id") or "") for chunk in p1_interventions}
    p2_general = [
        chunk
        for chunk in pending_chunks
        if str(chunk.get("chunk_id") or "") not in high_risk_ids
        and str(chunk.get("chunk_id") or "") not in p1_children_ids
        and str(chunk.get("chunk_id") or "") not in p1_perinatal_ids
        and str(chunk.get("chunk_id") or "") not in p1_intervention_ids
    ]
    buckets = {
        "p0_safety": high_risk,
        "p1_interventions": p1_interventions,
        "p1_children": p1_children,
        "p1_perinatal": p1_perinatal,
        "p2_general": p2_general,
        # Compatibility with earlier V2.1 reports.
        "high_risk": high_risk,
        "p1": p1_non_high_risk,
        "p2": [
            chunk
            for chunk in pending_chunks
            if str(chunk.get("review_priority") or "").upper() not in {"P0", "P1"} and not _is_high_risk_chunk(chunk)
        ],
    }
    summary: dict[str, Any] = {"created_at": utc_now_iso(), "buckets": {}}
    for name, rows in buckets.items():
        path = output_dir / f"review_priority_{name}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for chunk in rows:
                writer.writerow(
                    {
                        "source_id": chunk.get("source_id", ""),
                        "chunk_id": chunk.get("chunk_id", ""),
                        "title": chunk.get("title", ""),
                        "target_collection": chunk.get("target_collection", ""),
                        "use_mode": chunk.get("use_mode", ""),
                        "risk_scope": chunk.get("risk_scope", ""),
                        "review_priority": chunk.get("review_priority", ""),
                        "review_status": normalize_review_status(chunk.get("review_status")),
                        "issues": ";".join(_automatic_chunk_issues(chunk)),
                        "content_preview": " ".join(str(chunk.get("content") or "").split())[:260],
                    }
                )
        summary["buckets"][name] = {"rows": len(rows), "path": path.as_posix()}
        print(f"{name}: {len(rows)} -> {path.as_posix()}")
    summary_path = output_dir / "review_priority_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"summary -> {summary_path.as_posix()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review CARE-Psy knowledge sources without faking chunk-level expert review.")
    parser.add_argument("--registry", default="backend/data/knowledge_base/sources/knowledge_sources.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--collection")
    list_parser.add_argument("--limit", type=int, default=100)
    list_parser.set_defaults(func=cmd_list)

    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("source_id")
    inspect_parser.add_argument("--limit", type=int, default=5)
    inspect_parser.set_defaults(func=cmd_inspect)

    approve_parser = sub.add_parser("approve")
    approve_parser.add_argument("source_id")
    approve_parser.add_argument("--reviewed-by", required=True)
    approve_parser.add_argument("--comment", default="")
    approve_parser.set_defaults(func=lambda args: cmd_review(args, "approved"))

    reject_parser = sub.add_parser("reject")
    reject_parser.add_argument("source_id")
    reject_parser.add_argument("--reviewed-by", required=True)
    reject_parser.add_argument("--reason", required=True)
    reject_parser.set_defaults(func=lambda args: cmd_review(args, "rejected"))

    flag_parser = sub.add_parser("flag")
    flag_parser.add_argument("source_id")
    flag_parser.add_argument("--reviewed-by", required=True)
    flag_parser.add_argument("--comment", required=True)
    flag_parser.set_defaults(func=lambda args: cmd_review(args, "flagged_for_followup"))

    bulk_parser = sub.add_parser("bulk-approve-eligible")
    bulk_parser.add_argument("source_id")
    bulk_parser.add_argument("--confirm-source-id", required=True)
    bulk_parser.add_argument("--reviewed-by", required=True)
    bulk_parser.add_argument("--comment", default="")
    bulk_parser.set_defaults(func=cmd_bulk_approve_eligible)

    export_parser = sub.add_parser("export-priority")
    export_parser.add_argument("--output-dir", default="reports")
    export_parser.set_defaults(func=cmd_export_priority)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
