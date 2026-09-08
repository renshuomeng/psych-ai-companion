from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import time
from pathlib import Path
from typing import Any

from build_dense_index import build_dense_index
from kb_v11_utils import all_chunks, load_chunks_by_status, load_registry, utc_now_iso, write_json_atomic
from services.rag_v1_index_service import build_bm25_index, bm25_dir_for


def _timestamp_slug() -> str:
    return utc_now_iso().replace(":", "").replace("+00:00", "Z")


def _eligible_production_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for chunk in chunks:
        if str(chunk.get("review_status") or "").lower() not in {"approved", "reviewed"}:
            continue
        if bool(chunk.get("exclude_from_index")):
            continue
        if not str(chunk.get("content") or "").strip():
            continue
        eligible.append(chunk)
    return eligible


def _bm25_index_healthy(index_dir: Path, expected_documents: int) -> tuple[bool, str]:
    required = ["bm25_index.pkl", "documents.jsonl", "metadata.json"]
    missing = [name for name in required if not (index_dir / name).exists()]
    if missing:
        return False, f"missing:{','.join(missing)}"
    documents = sum(1 for line in (index_dir / "documents.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())
    if documents != expected_documents:
        return False, f"document_count_mismatch:{documents}!={expected_documents}"
    return True, "ok"


def _latest_bm25_backup(registry: Any) -> Path | None:
    backup_root = registry.paths["indexes_bm25"] / "backups"
    if not backup_root.exists():
        return None
    candidates = [
        path
        for path in backup_root.glob("production_*")
        if path.is_dir() and (path / "documents.jsonl").exists() and (path / "bm25_index.pkl").exists()
    ]
    return sorted(candidates, key=lambda path: path.name)[-1] if candidates else None


def _atomic_build_bm25_index(chunks: list[dict[str, Any]], registry: Any) -> dict[str, Any]:
    expected = len(chunks)
    bm25_root = registry.paths["indexes_bm25"]
    timestamp = _timestamp_slug()
    tmp_root = bm25_root / ".tmp"
    tmp_dir = tmp_root / f"production_{timestamp}"
    production_dir = bm25_dir_for(bm25_root, "production", require_existing=False)
    backup_dir = bm25_root / "backups" / f"production_{timestamp}"

    tmp_root.mkdir(parents=True, exist_ok=True)
    backup_dir.parent.mkdir(parents=True, exist_ok=True)
    if tmp_dir.exists() or backup_dir.exists():
        raise RuntimeError(f"production index build path already exists for timestamp {timestamp}")

    status = build_bm25_index(chunks, tmp_dir)
    healthy, reason = _bm25_index_healthy(tmp_dir, expected)
    if not healthy:
        raise RuntimeError(f"temporary BM25 production index failed health check: {reason}")

    backup_path = ""
    if production_dir.exists():
        shutil.move(str(production_dir), str(backup_dir))
        backup_path = backup_dir.as_posix()

    try:
        shutil.move(str(tmp_dir), str(production_dir))
    except Exception:
        if backup_path and not production_dir.exists() and backup_dir.exists():
            shutil.move(str(backup_dir), str(production_dir))
        raise

    final_healthy, final_reason = _bm25_index_healthy(production_dir, expected)
    if not final_healthy:
        raise RuntimeError(f"production BM25 index failed post-switch health check: {final_reason}")

    return {
        **status,
        "dir": production_dir.as_posix(),
        "atomic_switch": True,
        "temporary_dir": tmp_dir.as_posix(),
        "backup_dir": backup_path,
        "health_check": final_reason,
    }


def rollback_bm25_production(
    *,
    registry_path: str | Path | None,
    backup_dir: str | Path | None = None,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    selected_backup = Path(backup_dir) if backup_dir else _latest_bm25_backup(registry)
    if selected_backup is None:
        raise SystemExit("No BM25 production backup is available.")
    if not selected_backup.is_absolute():
        selected_backup = Path.cwd() / selected_backup
    if not selected_backup.exists():
        raise SystemExit(f"BM25 backup not found: {selected_backup}")
    production_dir = bm25_dir_for(registry.paths["indexes_bm25"], "production", require_existing=False)
    expected_documents = sum(
        1 for line in (selected_backup / "documents.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()
    )
    healthy, reason = _bm25_index_healthy(selected_backup, expected_documents)
    if not healthy:
        raise SystemExit(f"BM25 backup is not healthy: {reason}")

    timestamp = _timestamp_slug()
    tmp_restore = registry.paths["indexes_bm25"] / ".tmp" / f"rollback_restore_{timestamp}"
    replaced_dir = registry.paths["indexes_bm25"] / "backups" / f"rollback_replaced_{timestamp}"
    if tmp_restore.exists() or replaced_dir.exists():
        raise SystemExit(f"Rollback path already exists for timestamp {timestamp}")
    shutil.copytree(selected_backup, tmp_restore)
    if production_dir.exists():
        shutil.move(str(production_dir), str(replaced_dir))
    try:
        shutil.move(str(tmp_restore), str(production_dir))
    except Exception:
        if replaced_dir.exists() and not production_dir.exists():
            shutil.move(str(replaced_dir), str(production_dir))
        raise

    final_healthy, final_reason = _bm25_index_healthy(production_dir, expected_documents)
    if not final_healthy:
        raise SystemExit(f"Restored BM25 production index is not healthy: {final_reason}")
    report = {
        "created_at": utc_now_iso(),
        "rollback": "bm25_production",
        "restored_from": selected_backup.as_posix(),
        "replaced_current_backup": replaced_dir.as_posix() if replaced_dir.exists() else "",
        "production_dir": production_dir.as_posix(),
        "documents": expected_documents,
        "health_check": final_reason,
    }
    write_json_atomic(registry.paths["reports"] / "production_bm25_rollback_manifest.json", report)
    return report


async def build_production_indexes(
    *,
    registry_path: str | Path | None,
    batch_size: int | None,
    allow_empty: bool,
    dry_run: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    registry = load_registry(registry_path)
    chunks = _eligible_production_chunks(all_chunks(load_chunks_by_status(registry)))
    blockers: list[str] = []
    if not chunks:
        blockers.append("approved_chunks_zero")
    report: dict[str, Any] = {
        "created_at": utc_now_iso(),
        "dry_run": dry_run,
        "production_ready": False,
        "eligible_chunks": len(chunks),
        "blockers": blockers,
        "bm25": {},
        "dense": {},
    }
    if blockers and not allow_empty:
        write_json_atomic(registry.paths["reports"] / "production_index_manifest.json", report)
        return report
    if dry_run:
        report["production_ready"] = bool(chunks)
        write_json_atomic(registry.paths["reports"] / "production_index_dry_run.json", report)
        return report

    bm25_status = _atomic_build_bm25_index(chunks, registry)
    dense_status = await build_dense_index(
        mode="production",
        incremental=True,
        force_rebuild=False,
        dry_run=False,
        batch_size=batch_size,
        checkpoint_every=512,
        registry_path=registry_path,
    )
    report.update(
        {
            "production_ready": bool(chunks and bm25_status.get("documents") and dense_status.get("chunk_count")),
            "bm25": {
                **bm25_status,
            },
            "dense": dense_status,
            "build_time_ms": int((time.perf_counter() - started) * 1000),
            "rollback": {
                "bm25_supported": True,
                "bm25_backup_dir": bm25_status.get("backup_dir", ""),
                "bm25_command": (
                    "python scripts\\rag\\build_production_indexes.py --rollback-bm25"
                    + (
                        f" --backup-dir {bm25_status.get('backup_dir')}"
                        if bm25_status.get("backup_dir")
                        else ""
                    )
                ),
                "dense_note": (
                    "Chroma production collections are stage-isolated. Re-run the production build from approved chunks "
                    "or restore the Chroma persist directory from filesystem backup if a full vector rollback is required."
                ),
            },
            "rollback_note": (
                "BM25 production builds are switched from a temporary directory after health check. "
                "A previous BM25 production directory is moved to backup when it exists."
            ),
        }
    )
    write_json_atomic(registry.paths["reports"] / "production_index_manifest.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build approved-only CARE-Psy production RAG indexes.")
    parser.add_argument("--registry", default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--rollback-bm25", action="store_true")
    parser.add_argument("--backup-dir", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.rollback_bm25:
        report = rollback_bm25_production(registry_path=args.registry, backup_dir=args.backup_dir)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("rollback: bm25_production")
            print(f"restored_from: {report['restored_from']}")
            print(f"documents: {report['documents']}")
            print(f"production_dir: {report['production_dir']}")
        return 0
    report = asyncio.run(
        build_production_indexes(
            registry_path=args.registry,
            batch_size=args.batch_size,
            allow_empty=args.allow_empty,
            dry_run=args.dry_run,
        )
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"production_ready: {report['production_ready']}")
        print(f"eligible_chunks: {report['eligible_chunks']}")
        if report["blockers"]:
            print("blockers:")
            for blocker in report["blockers"]:
                print(f"- {blocker}")
        if report.get("bm25"):
            print(f"bm25_documents: {report['bm25'].get('documents')}")
        if report.get("dense"):
            print(f"dense_chunks: {report['dense'].get('chunk_count')}")
    return 0 if report.get("production_ready") or args.dry_run else 2


if __name__ == "__main__":
    raise SystemExit(main())
