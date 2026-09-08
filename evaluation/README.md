# CARE-Psy Evaluation Center V1

This module evaluates the CARE-Psy system as a complete agent pipeline rather than only a base model.

## What It Evaluates

- Direct Doubao baseline
- Current Full Agent
- Agent without RAG
- Agent without StrategyPlanner
- Agent without PsychologicalStateAnalyzer
- Custom ablation switches

The full agent adapter records response text, risk, emotion, psychological state, strategy plan, RAG route, knowledge sources, latency, and trace.

## Frameworks

Framework definitions live in `evaluation/benchmarks/registry.yaml`. V1 preserves official metric names and marks the local implementation as compatible smoke scoring unless the official evaluator has been integrated.

No cross-framework overall psychological score is computed.

## CLI

```bash
python -m evaluation.run --system full_agent --framework esc_eval --limit 5
python -m evaluation.run --system direct_doubao --framework all --limit 5
python -m evaluation.run --system full_agent --dry-run
python -m evaluation.run --compare --baseline-run RUN_A --candidate-run RUN_B
```

By default `EVAL_ALLOW_PAID_FULL_RUN=false`, so only up to `EVAL_SMOKE_CASE_LIMIT` cases can run unless the environment explicitly allows a paid full run.

## Outputs

Each run writes to `evaluation/results/<run_id>/`:

- `config.json`
- `raw_generations.jsonl`
- `raw_judgements.jsonl`
- `agent_traces.jsonl`
- `case_scores.jsonl`
- `aggregated_metrics.json`
- `summary.json`
- `summary.csv`
- `report.md`

Run comparison exports `evaluation/results/competition_evaluation.csv`.

## Isolation

Evaluation sessions use `eval_<run_id>_<case_id>` identifiers and do not create normal user conversations. RAG retrieval logs may still be written for observability, but they are separated by the `eval_` session prefix.

