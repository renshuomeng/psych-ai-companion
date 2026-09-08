from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVAL_DIR = ROOT / "evaluation" / "datasets"
DEFAULT_KB_DIR = ROOT / "backend" / "data" / "knowledge_base"


def normalize(text: str) -> str:
    text = re.sub(r"\s+", "", text.lower())
    return text[:2000]


def digest(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def iter_texts(path: Path) -> Iterable[tuple[Path, str]]:
    if not path.exists():
        return
    for file_path in path.rglob("*"):
        if file_path.suffix.lower() not in {".jsonl", ".json", ".md", ".txt"}:
            continue
        try:
            raw = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if file_path.suffix.lower() == ".jsonl":
            for line in raw.splitlines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    yield file_path, json.dumps(payload, ensure_ascii=False, sort_keys=True)
                except json.JSONDecodeError:
                    yield file_path, line
        else:
            yield file_path, raw


def check_leakage(eval_dir: Path, kb_dir: Path) -> dict[str, object]:
    kb_hashes: dict[str, list[str]] = {}
    for path, text in iter_texts(kb_dir):
        kb_hashes.setdefault(digest(text), []).append(str(path))

    overlaps = []
    eval_count = 0
    for path, text in iter_texts(eval_dir):
        eval_count += 1
        key = digest(text)
        if key in kb_hashes:
            overlaps.append({"evaluation_file": str(path), "knowledge_files": kb_hashes[key]})

    return {
        "evaluation_dir": str(eval_dir),
        "knowledge_dir": str(kb_dir),
        "evaluation_items_checked": eval_count,
        "knowledge_items_checked": sum(len(items) for items in kb_hashes.values()),
        "exact_normalized_overlap_count": len(overlaps),
        "overlaps": overlaps,
        "status": "passed" if not overlaps else "needs_review",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check exact normalized leakage between evaluation data and knowledge base.")
    parser.add_argument("--eval-dir", type=Path, default=DEFAULT_EVAL_DIR)
    parser.add_argument("--knowledge-dir", type=Path, default=DEFAULT_KB_DIR)
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation" / "results" / "leakage_report.json")
    args = parser.parse_args()

    result = check_leakage(args.eval_dir, args.knowledge_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

