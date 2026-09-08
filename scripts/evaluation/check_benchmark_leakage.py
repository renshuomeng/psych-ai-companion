from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK_DIR = ROOT / "evaluation" / "benchmarks" / "normalized"
DEFAULT_OUTPUT = ROOT / "evaluation" / "benchmarks" / "leakage_report.json"
COMPARISON_TARGETS = {
    "training_normalized": [ROOT / "training" / "normalized"],
    "rag_approved_chunks": [ROOT / "backend" / "data" / "knowledge_base" / "chunks" / "approved" / "chunks.jsonl"],
    "prompts_and_fewshot": [ROOT / "backend" / "prompts", ROOT / "scripts" / "sft"],
}


TEXT_KEYS = {
    "content",
    "text",
    "message",
    "query",
    "question",
    "answer",
    "response",
    "reply",
    "reference_notes",
}


def normalize_text(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text.casefold(), flags=re.UNICODE)


def exact_hash(text: str) -> str:
    return hashlib.sha256(text.strip().casefold().encode("utf-8")).hexdigest()


def normalized_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def _collect_json_text(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        if len(value.strip()) >= 20:
            texts.append(value.strip())
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in TEXT_KEYS:
                texts.extend(_collect_json_text(item))
            elif isinstance(item, (dict, list)):
                texts.extend(_collect_json_text(item))
    elif isinstance(value, list):
        for item in value:
            texts.extend(_collect_json_text(item))
    return texts


def iter_files(paths: list[Path]) -> Iterable[Path]:
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            yield path
            continue
        for child in path.rglob("*"):
            if child.is_file() and child.suffix.lower() in {".jsonl", ".json", ".md", ".txt", ".csv"}:
                yield child


def iter_text_items(paths: list[Path]) -> Iterable[dict[str, str]]:
    for path in iter_files(paths):
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = str(path.relative_to(ROOT)).replace("\\", "/") if path.is_relative_to(ROOT) else str(path)
        if path.suffix.lower() == ".jsonl":
            for index, line in enumerate(raw.splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    texts = _collect_json_text(payload)
                except json.JSONDecodeError:
                    texts = [line]
                for text in texts:
                    yield {"path": relative, "line": str(index), "text": text}
        elif path.suffix.lower() == ".json":
            try:
                texts = _collect_json_text(json.loads(raw))
            except json.JSONDecodeError:
                texts = [raw]
            for text in texts:
                yield {"path": relative, "line": "", "text": text}
        else:
            for block in re.split(r"\n\s*\n", raw):
                if len(block.strip()) >= 20:
                    yield {"path": relative, "line": "", "text": block.strip()}


def build_hash_index() -> dict[str, Any]:
    exact: dict[str, list[dict[str, str]]] = {}
    normalized: dict[str, list[dict[str, str]]] = {}
    counts: dict[str, int] = {}
    for corpus_name, paths in COMPARISON_TARGETS.items():
        count = 0
        for item in iter_text_items(paths):
            count += 1
            entry = {"corpus": corpus_name, "path": item["path"], "line": item["line"]}
            exact.setdefault(exact_hash(item["text"]), []).append(entry)
            normalized.setdefault(normalized_hash(item["text"]), []).append(entry)
        counts[corpus_name] = count
    return {"exact": exact, "normalized": normalized, "counts": counts}


def check_benchmark_leakage(benchmark_dir: Path = DEFAULT_BENCHMARK_DIR) -> dict[str, Any]:
    index = build_hash_index()
    exact_matches: list[dict[str, Any]] = []
    normalized_matches: list[dict[str, Any]] = []
    benchmark_count = 0
    for item in iter_text_items([benchmark_dir]):
        benchmark_count += 1
        benchmark_ref = {"path": item["path"], "line": item["line"]}
        exact_key = exact_hash(item["text"])
        normalized_key = normalized_hash(item["text"])
        if exact_key in index["exact"]:
            exact_matches.append({"benchmark": benchmark_ref, "matches": index["exact"][exact_key]})
        if normalized_key in index["normalized"]:
            normalized_matches.append({"benchmark": benchmark_ref, "matches": index["normalized"][normalized_key]})

    status = "passed" if not exact_matches and not normalized_matches else "failed"
    return {
        "benchmark_dir": str(benchmark_dir.relative_to(ROOT)).replace("\\", "/") if benchmark_dir.is_relative_to(ROOT) else str(benchmark_dir),
        "benchmark_items_checked": benchmark_count,
        "comparison_items_checked": index["counts"],
        "exact_hash_overlap_count": len(exact_matches),
        "normalized_hash_overlap_count": len(normalized_matches),
        "exact_matches": exact_matches,
        "normalized_matches": normalized_matches,
        "status": status,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check CARE-Psy Benchmark V1 leakage against training, RAG, and prompt corpora.")
    parser.add_argument("--benchmark-dir", type=Path, default=DEFAULT_BENCHMARK_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print JSON. This is the default format.")
    args = parser.parse_args()

    result = check_benchmark_leakage(args.benchmark_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    mirror = ROOT / "evaluation" / "results" / "benchmark_leakage_report.json"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
