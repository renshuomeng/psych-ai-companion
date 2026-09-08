# Evaluation Audit

## Implemented Local Evaluation

The evaluation registry includes care_bench, cpsycoun, and related framework metadata. Runners persist evaluation runs, support smoke limits, ablations, comparisons, and frontend dashboard actions. The local smoke path can execute Agent V2 state, strategy, RAG routing, and a dry-run counselor response.

Observed artifacts include a six-line competition smoke dataset, four Agent V2 routing/integration cases, 81 persisted evaluation runs, cached traces, and result files.

## Limits

The metrics implementation is local heuristic scoring. Dry-run adapters use mock replies. Official benchmark adapters are partial or unavailable; no independent judge, blinded human score set, or official leaderboard submission flow was verified. The state-strategy case file named in prior audit notes was absent, while integration cases were present.

| Area | Status |
|---|---|
| Local smoke and ablation runner | `IMPLEMENTED_AND_ACTIVE` |
| Run persistence and dashboard | `IMPLEMENTED_AND_ACTIVE` |
| Agent V2 integration cases | `IMPLEMENTED_AND_ACTIVE` |
| Official benchmark execution | `PARTIALLY_IMPLEMENTED` |
| LLM judge | `NOT_IMPLEMENTED` |
| Human review workflow | `IMPLEMENTED_AND_ACTIVE` |
| Fine-tuned model comparison | `NOT_IMPLEMENTED` |

Local scores must not be presented as official benchmark results.

## Retrieval Benchmark Evidence

The latest actual saved RAG V2 run is `evaluation/rag_v2/results` at `2026-09-02T15:53:49+00:00`: 162 queries, 162 BM25 results, 162 dense results, 162 hybrid results, and 8 ordinary guardrail results. The run's `index_mode` and `runtime_index_mode` are both `staging`.

Actual hybrid results were Hit@5 `0.9568`, Recall@5 `0.6274`, MRR@5 `0.9333`, NDCG@5 `0.9249`, safety leakage `0.0`. The leakage report found zero exact-hash and zero substring hits. These are retrieval-engineering results from a staged run, not an official psychological benchmark or proof of current production parity.

## Candidate and Judge Boundary

The registry contains direct Doubao/full-agent and ablation variants such as no strategy/no psychological state/no RAG, but dry-run adapters can use mock replies. The effective judge is `heuristic_local` / `local_smoke_heuristic_v1`; no external LLM judge call was made. Fine-tuned counselor is not a verified active candidate.

