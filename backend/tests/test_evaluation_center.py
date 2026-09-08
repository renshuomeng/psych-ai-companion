import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_registry_keeps_required_metric_names():
    from backend.evaluation.registry import FRAMEWORK_REGISTRY

    assert "WAI Goal" in [item["name"] for item in FRAMEWORK_REGISTRY["care_bench"]["metrics"]]
    assert "Overall" in [item["name"] for item in FRAMEWORK_REGISTRY["esc_eval"]["metrics"]]
    assert "Comprehensiveness" in [item["name"] for item in FRAMEWORK_REGISTRY["cpsycoun"]["metrics"]]
    assert "Toxicity" in [item["name"] for item in FRAMEWORK_REGISTRY["counselbench"]["metrics"]]
    assert FRAMEWORK_REGISTRY["counselbench"]["metrics"][-1]["direction"] == "lower_is_better"


def test_ablation_config_for_systems():
    from backend.evaluation.schemas import AblationConfig

    assert AblationConfig.for_system("full_agent").rag is True
    assert AblationConfig.for_system("agent_without_rag").rag is False
    assert AblationConfig.for_system("agent_without_strategy").strategy is False
    assert AblationConfig.for_system("agent_without_psychological_state").psychological_state is False
    assert AblationConfig.for_system("custom_agent", {"risk": False, "safety": False}).risk is False


def test_smoke_dataset_loads_cases():
    from backend.evaluation.datasets import dataset_hash, load_cases

    cases = load_cases(limit=3)
    assert len(cases) == 3
    assert cases[0].case_id.startswith("smoke_")
    assert dataset_hash(cases)


def test_metric_scoring_has_no_cross_framework_total():
    from backend.evaluation.datasets import load_cases
    from backend.evaluation.metrics import aggregate_scores, score_case
    from backend.evaluation.schemas import CandidateResult

    case = load_cases(limit=1)[0]
    candidate = CandidateResult(
        system_id="full_agent",
        response="听起来论文拖延让你很焦虑。我们先把任务拆成一个很小的一步，今天只写标题和三行提纲，可以吗？",
        latency_ms=10,
        psychological_state={"cause": {"category": "thesis"}, "needs": ["problem_solving"]},
    )
    scores = [score.model_dump() for score in score_case("esc_eval", case, candidate)]
    summary = aggregate_scores([{"candidate": candidate.model_dump(), "scores": scores}])

    assert "esc_eval" in summary["frameworks"]
    assert "Overall" in summary["frameworks"]["esc_eval"]["metrics"]
    assert "overall" not in summary
    assert any("No cross-framework" in note for note in summary["notes"])


@pytest.mark.asyncio
async def test_direct_doubao_adapter_dry_run():
    from backend.evaluation.adapters.direct_doubao_adapter import DirectDoubaoAdapter
    from backend.evaluation.datasets import load_cases

    result = await DirectDoubaoAdapter().generate(load_cases(limit=1)[0], dry_run=True)

    assert result.system_id == "direct_doubao"
    assert result.response
    assert result.provider_metadata["provider"] == "dry_run_mock"


@pytest.mark.asyncio
async def test_runner_writes_case_level_outputs(tmp_path):
    from backend.evaluation.runner import EvaluationRunner
    from backend.evaluation.schemas import AblationConfig, RunConfig

    runner = EvaluationRunner(results_dir=tmp_path / "results", cache_dir=tmp_path / "cache")
    summary = await runner.run(
        RunConfig(
            system_id="direct_doubao",
            frameworks=["esc_eval"],
            limit=2,
            dry_run=True,
            ablation=AblationConfig.for_system("direct_doubao"),
        )
    )

    output_dir = Path(summary["output_dir"])
    assert (output_dir / "case_scores.jsonl").exists()
    assert (output_dir / "raw_generations.jsonl").exists()
    assert (output_dir / "raw_judgements.jsonl").exists()
    assert (output_dir / "agent_traces.jsonl").exists()
    assert (output_dir / "summary.csv").exists()
    assert summary["case_count"] == 2
    assert summary["frameworks"]["esc_eval"]["metrics"]["Overall"]["n"] == 2


@pytest.mark.asyncio
async def test_runner_resume_skips_existing_cases(tmp_path):
    from backend.evaluation.runner import EvaluationRunner
    from backend.evaluation.schemas import AblationConfig, RunConfig

    runner = EvaluationRunner(results_dir=tmp_path / "results", cache_dir=tmp_path / "cache")
    first = await runner.run(
        RunConfig(
            system_id="direct_doubao",
            frameworks=["cpsycoun"],
            limit=1,
            dry_run=True,
            ablation=AblationConfig.for_system("direct_doubao"),
        )
    )
    second = await runner.run(
        RunConfig(
            system_id="direct_doubao",
            frameworks=["cpsycoun"],
            limit=1,
            dry_run=True,
            resume_run_id=first["run_id"],
            ablation=AblationConfig.for_system("direct_doubao"),
        )
    )

    lines = (Path(second["output_dir"]) / "case_scores.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


@pytest.mark.asyncio
async def test_compare_runs_exports_csv(tmp_path, monkeypatch):
    import backend.evaluation.runner as runner_module
    from backend.evaluation.runner import EvaluationRunner, compare_runs
    from backend.evaluation.schemas import AblationConfig, RunConfig

    monkeypatch.setattr(runner_module, "RESULTS_DIR", tmp_path / "results")
    runner = EvaluationRunner(results_dir=tmp_path / "results", cache_dir=tmp_path / "cache")
    baseline = await runner.run(
        RunConfig(
            system_id="direct_doubao",
            frameworks=["counselbench"],
            limit=1,
            dry_run=True,
            ablation=AblationConfig.for_system("direct_doubao"),
        )
    )
    candidate = await runner.run(
        RunConfig(
            system_id="direct_doubao",
            frameworks=["counselbench"],
            limit=1,
            dry_run=True,
            ablation=AblationConfig.for_system("direct_doubao"),
            use_cache=False,
        )
    )

    comparison = compare_runs(baseline["run_id"], candidate["run_id"])

    assert Path(comparison["export_csv"]).exists()
    assert "counselbench" in comparison["metric_delta"]


def test_config_from_payload_maps_custom_ablation():
    from backend.evaluation.runner import config_from_payload

    config = config_from_payload(
        {
            "system_id": "custom_agent",
            "frameworks": ["care_bench"],
            "limit": 2,
            "dry_run": True,
            "ablation": {"rag": False, "strategy": False},
        }
    )

    assert config.frameworks == ["care_bench"]
    assert config.ablation.rag is False
    assert config.ablation.strategy is False


def test_leakage_checker_reports_status(tmp_path):
    from scripts.evaluation.check_leakage import check_leakage

    eval_dir = tmp_path / "eval"
    kb_dir = tmp_path / "kb"
    eval_dir.mkdir()
    kb_dir.mkdir()
    (eval_dir / "cases.jsonl").write_text(json.dumps({"turns": ["论文焦虑怎么办"]}, ensure_ascii=False), encoding="utf-8")
    (kb_dir / "source.md").write_text("睡眠卫生建议", encoding="utf-8")

    result = check_leakage(eval_dir, kb_dir)

    assert result["status"] == "passed"
    assert result["exact_normalized_overlap_count"] == 0
