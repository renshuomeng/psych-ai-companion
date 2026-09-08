from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from kb_v11_utils import (
    CHUNK_STATUSES,
    all_chunks,
    has_unsafe_operational_detail,
    load_chunks_by_status,
    load_registry,
    normalize_review_status,
    split_chunks_by_status,
    utc_now_iso,
    write_chunks_by_status,
)


CSV_FIELDS = [
    "chunk_id",
    "source_id",
    "title",
    "target_collection",
    "topic",
    "topics",
    "language",
    "section",
    "chunk_type",
    "evidence_level",
    "source_authority",
    "review_priority",
    "review_status",
    "decision",
    "reviewed_by",
    "review_comment",
    "official_page_url",
    "downloaded_url",
    "content_preview",
]


def _parse_topics(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(item) for item in value if str(item).strip()}
    if value is None:
        return set()
    text = str(value).strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return {str(item) for item in parsed if str(item).strip()}
        except json.JSONDecodeError:
            pass
    return {item.strip() for item in text.replace("，", ",").split(",") if item.strip()}


def _matches(chunk: dict[str, Any], args: argparse.Namespace) -> bool:
    if getattr(args, "status", None) and normalize_review_status(chunk.get("review_status")) != args.status:
        return False
    if getattr(args, "source_id", None) and str(chunk.get("source_id") or "") != args.source_id:
        return False
    if getattr(args, "collection", None) and str(chunk.get("target_collection") or "") != args.collection:
        return False
    if getattr(args, "topic", None):
        topics = _parse_topics(chunk.get("topics"))
        if chunk.get("topic"):
            topics.add(str(chunk["topic"]))
        if args.topic not in topics:
            return False
    if getattr(args, "contains", None):
        haystack = " ".join(
            [
                str(chunk.get("title") or ""),
                str(chunk.get("section") or ""),
                str(chunk.get("topic") or ""),
                str(chunk.get("content") or ""),
            ]
        ).lower()
        if args.contains.lower() not in haystack:
            return False
    return True


def _selected_chunks(args: argparse.Namespace) -> tuple[Any, list[dict[str, Any]]]:
    registry = load_registry(args.registry)
    grouped = load_chunks_by_status(registry)
    selected = [chunk for chunk in all_chunks(grouped) if _matches(chunk, args)]
    limit = max(int(getattr(args, "limit", 50) or 50), 1)
    return registry, selected[:limit]


def _preview(content: str, width: int = 280) -> str:
    normalized = " ".join(content.split())
    return normalized[:width]


def cmd_list(args: argparse.Namespace) -> int:
    _, chunks = _selected_chunks(args)
    for chunk in chunks:
        print(
            json.dumps(
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "source_id": chunk.get("source_id"),
                    "collection": chunk.get("target_collection"),
                    "topic": chunk.get("topic"),
                    "review_status": chunk.get("review_status"),
                    "preview": _preview(str(chunk.get("content") or ""), 160),
                },
                ensure_ascii=False,
            )
        )
    print(f"total_listed: {len(chunks)}")
    return 0


def _csv_row(chunk: dict[str, Any]) -> dict[str, Any]:
    topics = chunk.get("topics") or []
    if isinstance(topics, list):
        topics_text = ";".join(str(item) for item in topics)
    else:
        topics_text = str(topics)
    return {
        "chunk_id": chunk.get("chunk_id", ""),
        "source_id": chunk.get("source_id", ""),
        "title": chunk.get("title", ""),
        "target_collection": chunk.get("target_collection", ""),
        "topic": chunk.get("topic", ""),
        "topics": topics_text,
        "language": chunk.get("language", ""),
        "section": chunk.get("section", ""),
        "chunk_type": chunk.get("chunk_type", ""),
        "evidence_level": chunk.get("evidence_level", ""),
        "source_authority": chunk.get("source_authority", ""),
        "review_priority": chunk.get("review_priority", ""),
        "review_status": normalize_review_status(chunk.get("review_status")),
        "decision": "",
        "reviewed_by": chunk.get("reviewed_by", ""),
        "review_comment": chunk.get("review_comment", ""),
        "official_page_url": chunk.get("official_page_url", ""),
        "downloaded_url": chunk.get("downloaded_url", ""),
        "content_preview": _preview(str(chunk.get("content") or "")),
    }


def cmd_export(args: argparse.Namespace) -> int:
    registry, chunks = _selected_chunks(args)
    default_name = f"review_batch_{utc_now_iso().replace(':', '').replace('+', 'Z')}.csv"
    output = Path(args.output) if args.output else registry.paths["reports"] / default_name
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for chunk in chunks:
            writer.writerow(_csv_row(chunk))
    print(output.as_posix())
    print(f"exported: {len(chunks)}")
    return 0


def _is_high_risk_review_item(chunk: dict[str, Any]) -> bool:
    collection = str(chunk.get("target_collection") or chunk.get("collection") or "").lower()
    use_mode = str(chunk.get("use_mode") or "").lower()
    risk_scope = str(chunk.get("risk_scope") or "").lower()
    topics = _parse_topics(chunk.get("topics")) | _parse_topics(chunk.get("topic_tags")) | {str(chunk.get("topic") or "")}
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


def cmd_high_risk(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    grouped = load_chunks_by_status(registry)
    rows = [
        chunk
        for chunk in all_chunks(grouped)
        if _matches(chunk, args) and _is_high_risk_review_item(chunk)
    ][: max(int(args.limit or 500), 1)]
    output = Path(args.output) if args.output else registry.paths["reports"] / "review_priority_high_risk.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for chunk in rows:
            writer.writerow(_csv_row(chunk))
    print(output.as_posix())
    print(f"high_risk_exported: {len(rows)}")
    return 0


def _load_all_chunks_by_id(registry: Any) -> dict[str, dict[str, Any]]:
    grouped = load_chunks_by_status(registry)
    chunks_by_id: dict[str, dict[str, Any]] = {}
    for chunk in all_chunks(grouped):
        chunk_id = str(chunk.get("chunk_id") or "")
        if chunk_id:
            chunks_by_id[chunk_id] = chunk
    return chunks_by_id


def _apply_decision(
    chunk: dict[str, Any],
    *,
    decision: str,
    reviewed_by: str,
    review_comment: str = "",
    rejection_reason: str = "",
) -> dict[str, Any]:
    updated = dict(chunk)
    updated["review_status"] = normalize_review_status(decision)
    updated["reviewed_at"] = utc_now_iso()
    updated["reviewed_by"] = reviewed_by
    if review_comment:
        updated["review_comment"] = review_comment
    if rejection_reason:
        updated["rejection_reason"] = rejection_reason
    return updated


def cmd_import(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    chunks_by_id = _load_all_chunks_by_id(registry)
    changed = 0
    with Path(args.csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            chunk_id = str(row.get("chunk_id") or "")
            if not chunk_id or chunk_id not in chunks_by_id:
                continue
            decision = str(row.get("decision") or row.get("review_status") or "").strip().lower()
            if decision not in {"approved", "reviewed", "rejected", "blocked", "pending"}:
                continue
            reviewed_by = str(row.get("reviewed_by") or args.reviewed_by or "").strip()
            if normalize_review_status(decision) in {"approved", "rejected"} and not reviewed_by:
                raise SystemExit(f"reviewed_by is required for {chunk_id}")
            chunks_by_id[chunk_id] = _apply_decision(
                chunks_by_id[chunk_id],
                decision=decision,
                reviewed_by=reviewed_by,
                review_comment=str(row.get("review_comment") or ""),
                rejection_reason=str(row.get("rejection_reason") or ""),
            )
            changed += 1
    write_chunks_by_status(registry, split_chunks_by_status(list(chunks_by_id.values())))
    print(f"changed: {changed}")
    return 0


def cmd_single(args: argparse.Namespace, decision: str) -> int:
    registry = load_registry(args.registry)
    chunks_by_id = _load_all_chunks_by_id(registry)
    if args.chunk_id not in chunks_by_id:
        raise SystemExit(f"chunk not found: {args.chunk_id}")
    chunks_by_id[args.chunk_id] = _apply_decision(
        chunks_by_id[args.chunk_id],
        decision=decision,
        reviewed_by=args.reviewed_by,
        review_comment=args.comment or "",
        rejection_reason=args.reason or "",
    )
    write_chunks_by_status(registry, split_chunks_by_status(list(chunks_by_id.values())))
    print(f"{decision}: {args.chunk_id}")
    return 0


def cmd_bulk_source(args: argparse.Namespace, decision: str) -> int:
    if args.confirm_source_id != args.source_id:
        raise SystemExit("--confirm-source-id must exactly match --source-id")
    registry = load_registry(args.registry)
    chunks_by_id = _load_all_chunks_by_id(registry)
    changed = 0
    for chunk_id, chunk in list(chunks_by_id.items()):
        if str(chunk.get("source_id") or "") != args.source_id:
            continue
        if args.status and normalize_review_status(chunk.get("review_status")) != args.status:
            continue
        chunks_by_id[chunk_id] = _apply_decision(
            chunk,
            decision=decision,
            reviewed_by=args.reviewed_by,
            review_comment=args.comment or "",
            rejection_reason=args.reason or "",
        )
        changed += 1
    write_chunks_by_status(registry, split_chunks_by_status(list(chunks_by_id.values())))
    print(f"{decision}: {changed} chunks from {args.source_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review CARE-Psy RAG chunks and move them through pending/approved/rejected.")
    parser.add_argument("--registry", default="backend/data/knowledge_base/sources/knowledge_sources_v1.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_filters(target: argparse.ArgumentParser) -> None:
        target.add_argument("--status", choices=CHUNK_STATUSES, default="pending")
        target.add_argument("--source-id")
        target.add_argument("--collection")
        target.add_argument("--topic")
        target.add_argument("--contains")
        target.add_argument("--limit", type=int, default=50)

    list_parser = sub.add_parser("list")
    add_filters(list_parser)
    list_parser.set_defaults(func=cmd_list)

    export_parser = sub.add_parser("export-review")
    add_filters(export_parser)
    export_parser.add_argument("--output")
    export_parser.set_defaults(func=cmd_export)

    high_risk_parser = sub.add_parser("high-risk")
    add_filters(high_risk_parser)
    high_risk_parser.set_defaults(status="pending")
    high_risk_parser.add_argument("--output")
    high_risk_parser.set_defaults(func=cmd_high_risk)

    import_parser = sub.add_parser("import-review")
    import_parser.add_argument("csv_path")
    import_parser.add_argument("--reviewed-by", default="")
    import_parser.set_defaults(func=cmd_import)

    approve_parser = sub.add_parser("approve")
    approve_parser.add_argument("chunk_id")
    approve_parser.add_argument("--reviewed-by", required=True)
    approve_parser.add_argument("--comment")
    approve_parser.add_argument("--reason")
    approve_parser.set_defaults(func=lambda args: cmd_single(args, "approved"))

    reject_parser = sub.add_parser("reject")
    reject_parser.add_argument("chunk_id")
    reject_parser.add_argument("--reviewed-by", required=True)
    reject_parser.add_argument("--comment")
    reject_parser.add_argument("--reason")
    reject_parser.set_defaults(func=lambda args: cmd_single(args, "rejected"))

    bulk_approve = sub.add_parser("bulk-approve-source")
    bulk_approve.add_argument("--source-id", required=True)
    bulk_approve.add_argument("--confirm-source-id", required=True)
    bulk_approve.add_argument("--status", choices=CHUNK_STATUSES, default="pending")
    bulk_approve.add_argument("--reviewed-by", required=True)
    bulk_approve.add_argument("--comment")
    bulk_approve.add_argument("--reason")
    bulk_approve.set_defaults(func=lambda args: cmd_bulk_source(args, "approved"))

    bulk_reject = sub.add_parser("bulk-reject-source")
    bulk_reject.add_argument("--source-id", required=True)
    bulk_reject.add_argument("--confirm-source-id", required=True)
    bulk_reject.add_argument("--status", choices=CHUNK_STATUSES, default="pending")
    bulk_reject.add_argument("--reviewed-by", required=True)
    bulk_reject.add_argument("--comment")
    bulk_reject.add_argument("--reason")
    bulk_reject.set_defaults(func=lambda args: cmd_bulk_source(args, "rejected"))
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
