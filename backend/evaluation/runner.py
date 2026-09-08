from __future__ import annotations

import asyncio
import csv
import json
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from config import get_settings
from database.db import SessionLocal, init_db
from database.models import EvaluationRun

from .adapters.direct_doubao_adapter import DirectDoubaoAdapter
from .adapters.full_agent_adapter import FullAgentEvaluationAdapter
from .cache import JsonDiskCache
from .datasets import dataset_hash, load_cases
from .metrics import aggregate_scores, metric_delta, score_case
from .registry import FRAMEWORK_REGISTRY, SYSTEM_REGISTRY
from .schemas import AblationConfig, CandidateResult, RunConfig


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
CACHE_DIR = PROJECT_ROOT / "evaluation" / "cache"


def _json_default(value: Any) -> str:
    return str(value)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "not_a_git_repository"


def _run_id(system_id: str) -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{system_id}_{uuid.uuid4().hex[:6]}"


def _adapter_for(config: RunConfig):
    if config.system_id == "direct_doubao":
        return DirectDoubaoAdapter()
    return FullAgentEvaluationAdapter(config.system_id, config.ablation)


def _candidate_from_cache(payload: dict[str, Any]) -> CandidateResult:
    return CandidateResult(**payload)


def _save_db_run(run_id: str, status: str, config: dict[str, Any], summary: dict[str, Any], output_dir: Path) -> None:
    init_db()
    with SessionLocal() as db:
        row = db.get(EvaluationRun, run_id)
        if row:
            row.status = status
            row.config_json = json.dumps(config, ensure_ascii=False)
            row.summary_json = json.dumps(summary, ensure_ascii=False)
            row.output_dir = str(output_dir)
        else:
            db.add(
                EvaluationRun(
                    run_id=run_id,
                    status=status,
                    config_json=json.dumps(config, ensure_ascii=False),
                    summary_json=json.dumps(summary, ensure_ascii=False),
                    output_dir=str(output_dir),
                )
            )
        db.commit()


class EvaluationRunner:
    def __init__(self, results_dir: Path = RESULTS_DIR, cache_dir: Path = CACHE_DIR) -> None:
        self.results_dir = results_dir
        self.cache_dir = cache_dir
        self.candidate_cache = JsonDiskCache(cache_dir / "candidate_generations.json")
        self.judge_cache = JsonDiskCache(cache_dir / "judge_scores.json")

    async def run(self, config: RunConfig) -> dict[str, Any]:
        settings = get_settings()
        frameworks = [item for item in config.frameworks if item in FRAMEWORK_REGISTRY]
        if not frameworks:
            raise ValueError("At least one supported framework is required.")
        if config.limit < 1:
            raise ValueError("limit must be >= 1")
        if not settings.eval_allow_paid_full_run and config.limit > settings.eval_smoke_case_limit:
            raise ValueError(
                f"EVAL_ALLOW_PAID_FULL_RUN=false only allows up to {settings.eval_smoke_case_limit} smoke cases."
            )

        run_id = config.resume_run_id or _run_id(config.system_id)
        output_dir = self.results_dir / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        case_scores_path = output_dir / "case_scores.jsonl"
        raw_generations_path = output_dir / "raw_generations.jsonl"
        raw_judgements_path = output_dir / "raw_judgements.jsonl"
        traces_path = output_dir / "agent_traces.jsonl"

        cases = load_cases(config.dataset_name, limit=config.limit)
        config_payload = {
            **config.model_dump(),
            "frameworks": frameworks,
            "run_id": run_id,
            "git_commit": _git_commit(),
            "dataset_hash": dataset_hash(cases),
            "created_at": datetime.now().isoformat(),
            "judge": {
                "provider": settings.eval_judge_provider,
                "model": settings.eval_judge_model_id,
                "scorer": "local_smoke_heuristic_v1",
                "self_judge": False,
            },
        }
        _write_json(output_dir / "config.json", config_payload)

        completed_case_ids = {row.get("case_id") for row in _read_jsonl(case_scores_path)}
        adapter = _adapter_for(config)
        errors: list[dict[str, Any]] = []

        for case in cases:
            if case.case_id in completed_case_ids:
                continue

            cache_key = self.candidate_cache.key(
                {
                    "version": "competition_eval_v1",
                    "system_id": config.system_id,
                    "ablation": config.ablation.model_dump(),
                    "case": case.model_dump(),
                    "dry_run": config.dry_run,
                }
            )
            cached = self.candidate_cache.get(cache_key) if config.use_cache else None
            if cached:
                candidate = _candidate_from_cache(cached)
            else:
                try:
                    try:
                        candidate = await adapter.generate(case, dry_run=config.dry_run, run_id=run_id)
                    except TypeError as exc:
                        if "run_id" not in str(exc):
                            raise
                        candidate = await adapter.generate(case, dry_run=config.dry_run)
                except Exception as exc:
                    candidate = CandidateResult(
                        system_id=config.system_id,
                        response="",
                        latency_ms=0,
                        errors=[{"stage": "candidate_generation", "type": type(exc).__name__, "message": str(exc)[:300]}],
                    )
                    errors.extend(candidate.errors)
                if config.use_cache:
                    self.candidate_cache.set(cache_key, candidate.model_dump())

            _append_jsonl(
                raw_generations_path,
                {"run_id": run_id, "case_id": case.case_id, "candidate": candidate.model_dump()},
            )
            _append_jsonl(
                traces_path,
                {"run_id": run_id, "case_id": case.case_id, "trace": candidate.trace},
            )

            metric_scores = []
            for framework_id in frameworks:
                judge_key = self.judge_cache.key(
                    {
                        "version": "competition_eval_v1",
                        "framework_id": framework_id,
                        "case_id": case.case_id,
                        "response": candidate.response,
                        "sources": candidate.knowledge_sources,
                    }
                )
                cached_scores = self.judge_cache.get(judge_key) if config.use_cache else None
                if cached_scores:
                    scores = cached_scores
                else:
                    scores = [score.model_dump() for score in score_case(framework_id, case, candidate)]
                    if config.use_cache:
                        self.judge_cache.set(judge_key, scores)
                metric_scores.extend(scores)
                _append_jsonl(
                    raw_judgements_path,
                    {
                        "run_id": run_id,
                        "case_id": case.case_id,
                        "framework_id": framework_id,
                        "scores": scores,
                        "judge": config_payload["judge"],
                    },
                )

            case_row = {
                "run_id": run_id,
                "case_id": case.case_id,
                "case": case.model_dump(),
                "candidate": candidate.model_dump(),
                "scores": metric_scores,
            }
            _append_jsonl(case_scores_path, case_row)

        case_rows = _read_jsonl(case_scores_path)
        summary = {
            "run_id": run_id,
            "status": "completed",
            "system_id": config.system_id,
            "system_name": SYSTEM_REGISTRY.get(config.system_id, {}).get("name", config.system_id),
            "ablation": config.ablation.model_dump(),
            "frameworks_requested": frameworks,
            "output_dir": str(output_dir),
            "generated_at": datetime.now().isoformat(),
            "dry_run": config.dry_run,
            "dataset": config.dataset_name,
            "dataset_hash": config_payload["dataset_hash"],
            "case_count": len(case_rows),
            "errors": errors,
            "judge": config_payload["judge"],
            **aggregate_scores(case_rows),
        }
        _write_json(output_dir / "aggregated_metrics.json", summary)
        _write_json(output_dir / "summary.json", summary)
        self._write_summary_csv(output_dir / "summary.csv", summary)
        self._write_report(output_dir / "report.md", config_payload, summary)
        _save_db_run(run_id, "completed", config_payload, summary, output_dir)
        return summary

    @staticmethod
    def _write_summary_csv(path: Path, summary: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "run_id",
                    "framework_id",
                    "metric_name",
                    "mean",
                    "median",
                    "std",
                    "n",
                    "direction",
                    "implementation_status",
                ],
            )
            writer.writeheader()
            for framework_id, framework in summary.get("frameworks", {}).items():
                for metric_name, metric in framework.get("metrics", {}).items():
                    writer.writerow(
                        {
                            "run_id": summary["run_id"],
                            "framework_id": framework_id,
                            "metric_name": metric_name,
                            "mean": metric.get("mean"),
                            "median": metric.get("median"),
                            "std": metric.get("std"),
                            "n": metric.get("n"),
                            "direction": metric.get("direction"),
                            "implementation_status": metric.get("implementation_status"),
                        }
                    )

    @staticmethod
    def _write_report(path: Path, config: dict[str, Any], summary: dict[str, Any]) -> None:
        lines = [
            "# CARE-Psy Evaluation Center V1 Run Report",
            "",
            f"- Run ID: `{summary['run_id']}`",
            f"- System: `{summary['system_id']}`",
            f"- Dataset: `{summary['dataset']}`",
            f"- Cases: {summary['case_count']}",
            f"- Dry run: {summary['dry_run']}",
            f"- Judge: `{summary['judge']['scorer']}` ({summary['judge']['provider']})",
            "- Cross-framework overall score: not computed",
            "",
            "## Ablation",
            "",
            "```json",
            json.dumps(config.get("ablation", {}), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Framework Metrics",
            "",
        ]
        for framework_id, framework in summary.get("frameworks", {}).items():
            lines.extend([f"### {framework.get('name', framework_id)}", ""])
            for metric_name, metric in framework.get("metrics", {}).items():
                lines.append(
                    f"- {metric_name}: mean={metric.get('mean')}, median={metric.get('median')}, "
                    f"std={metric.get('std')}, n={metric.get('n')}, direction={metric.get('direction')}, "
                    f"status={metric.get('implementation_status')}"
                )
            lines.append("")
        lines.extend(
            [
                "## Notes",
                "",
                "- V1 uses local smoke-compatible heuristic scores. It does not claim official benchmark results.",
                "- Official benchmark resources can be integrated later under `evaluation/external/*`.",
            ]
        )
        path.write_text("\n".join(lines), encoding="utf-8")


def run_evaluation_sync(config: RunConfig) -> dict[str, Any]:
    return asyncio.run(EvaluationRunner().run(config))


def list_saved_runs(limit: int = 20) -> list[dict[str, Any]]:
    runs = []
    for path in sorted(RESULTS_DIR.glob("*/summary.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return runs


def load_run_summary(run_id: str) -> dict[str, Any]:
    path = RESULTS_DIR / run_id / "summary.json"
    if not path.exists():
        raise FileNotFoundError(run_id)
    return json.loads(path.read_text(encoding="utf-8"))


def compare_runs(baseline_run_id: str, candidate_run_id: str) -> dict[str, Any]:
    baseline = load_run_summary(baseline_run_id)
    candidate = load_run_summary(candidate_run_id)
    comparison = {
        "baseline_run_id": baseline_run_id,
        "candidate_run_id": candidate_run_id,
        "generated_at": datetime.now().isoformat(),
        "metric_delta": metric_delta(candidate, baseline),
    }
    output_path = RESULTS_DIR / "competition_evaluation.csv"
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["framework_id", "metric_name", "baseline_mean", "candidate_mean", "delta", "direction"],
        )
        writer.writeheader()
        for framework_id, framework in comparison["metric_delta"].items():
            for metric_name, metric in framework.get("metrics", {}).items():
                writer.writerow({"framework_id": framework_id, "metric_name": metric_name, **metric})
    comparison["export_csv"] = str(output_path)
    _write_json(RESULTS_DIR / "competition_evaluation.json", comparison)
    return comparison


def config_from_payload(payload: dict[str, Any]) -> RunConfig:
    system_id = str(payload.get("system_id") or "full_agent")
    ablation_payload = payload.get("ablation") if isinstance(payload.get("ablation"), dict) else None
    ablation = AblationConfig.for_system(system_id, ablation_payload)
    return RunConfig(
        system_id=system_id,
        frameworks=[str(item) for item in payload.get("frameworks", ["care_bench", "esc_eval", "cpsycoun", "counselbench"])],
        limit=int(payload.get("limit") or 5),
        dry_run=bool(payload.get("dry_run", False)),
        resume_run_id=payload.get("resume_run_id") or None,
        ablation=ablation,
        dataset_name=str(payload.get("dataset_name") or "competition_smoke_v1"),
        use_cache=bool(payload.get("use_cache", True)),
    )
