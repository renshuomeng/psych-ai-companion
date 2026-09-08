# CARE-Psy Evaluation Center V1 Completion Report

Generated at: 2026-08-19

## Scope

This update implements a system-level competition evaluation center for CARE-Psy. It evaluates the whole agent pipeline rather than only a base model or a fine-tuned model.

Fine-tuning, SFT dataset construction, and ablation experiments beyond runnable switches were not started.

## Implemented

- Backend evaluation package: `backend/evaluation/`
- Full agent adapter: RiskAgent, EmotionAgent, PsychologicalStateAnalyzer, StrategyPlanner, RAG Router/Retrieval, CounselorAgent, SafetyAgent
- Direct Doubao baseline adapter
- Ablation switches: risk, psychological_state, strategy, rag, safety
- Framework registry and metric names for CARE-Bench, ESC-Eval, CPsyCounE, CounselBench
- Local compatible smoke scorer with case-level results and aggregation
- CLI: `python -m evaluation.run`
- Admin API:
  - `GET /api/admin/evaluation/registry`
  - `POST /api/admin/evaluation/run`
  - `GET /api/admin/evaluation/runs`
  - `GET /api/admin/evaluation/runs/{run_id}`
  - `POST /api/admin/evaluation/compare`
- Frontend Evaluation Center page
- Result files:
  - `config.json`
  - `raw_generations.jsonl`
  - `raw_judgements.jsonl`
  - `agent_traces.jsonl`
  - `case_scores.jsonl`
  - `aggregated_metrics.json`
  - `summary.json`
  - `summary.csv`
  - `report.md`
- Comparison export: `evaluation/results/competition_evaluation.csv`
- Leakage checker: `scripts/evaluation/check_leakage.py`
- External official-resource placeholders under `evaluation/external/*`

## Important Evaluation Policy

V1 does not claim official benchmark scores. It preserves official-style metric names and reports local compatible smoke scores only.

No cross-framework overall psychological score is computed. ESC-Eval `Overall` and CounselBench `Overall Quality` are retained because they are framework-specific metric names.

## Smoke Runs

Direct Doubao real smoke run:

- Run ID: `20260819_204551_direct_doubao_0c1523`
- Cases: 5
- Error count: 1
- Note: one provider connection failure was recorded as a case-level generation error.

Current Full Agent real smoke run:

- Run ID: `20260819_204632_full_agent_9a7151`
- Cases: 5
- Error count: 0
- Knowledge-source cases: 2

Comparison export:

- `evaluation/results/competition_evaluation.csv`
- Full Agent improved over Direct Doubao on most compatible smoke dimensions in this run. Treat these as smoke-test indicators, not official benchmark conclusions.

## Verification

- `python -m pytest backend\tests -q`
  - Result: 61 passed, 2 third-party deprecation warnings
- `npm run build`
  - Result: success
- `python scripts\evaluation\check_leakage.py`
  - Result: passed, exact normalized overlap count = 0

## Known Limitations

- Official CARE-Bench, ESC-Eval, CPsyCounE, and CounselBench evaluators are not vendored yet.
- The current scorer is a deterministic local heuristic for smoke evaluation, not a human or LLM judge.
- `EVAL_JUDGE_PROVIDER` and `EVAL_JUDGE_MODEL_ID` are recorded, but V1 defaults to `heuristic_local`.
- Full Agent dry-run can still load local RAG/embedding components, so first run may be slow even without paid generation.
- RAG retrieval logs may be written with `eval_` session IDs for observability; normal user conversations are not created.

## Next Optimization Steps

1. Add an optional LLM-as-judge provider that is separate from the candidate model and records `self_judge`.
2. Integrate official benchmark scripts into `evaluation/external/*` after license/download checks.
3. Add manually reviewed gold cases for safety and counseling quality.
4. Run matched ablation smoke suites: full_agent vs no_rag vs no_strategy vs no_psychological_state.
5. Add a frontend detail drawer for each case trace and retrieved source list.

