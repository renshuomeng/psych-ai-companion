# Retrieval Benchmark Audit

## Last Actual Run

The latest result directory is `evaluation/rag_v2/results`, created `2026-09-02T15:53:49+00:00`. It contains 162 BM25 records, 162 dense records, 162 hybrid records, and 8 ordinary guardrail records. The benchmark summary explicitly says `index_mode=staging` and `runtime_index_mode=staging` for that run.

## Actual Results

| Method | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR@5 | NDCG@5 | Safety leakage |
|---|---:|---:|---:|---:|---:|---:|---:|
| BM25 | 0.9568 | 0.9568 | 0.9568 | 0.5914 | 0.9568 | 0.9552 | 0.0000 |
| Dense | 0.7037 | 0.8086 | 0.8395 | 0.4787 | 0.7572 | 0.7721 | 0.0000 |
| Hybrid | 0.9136 | 0.9506 | 0.9568 | 0.6274 | 0.9333 | 0.9249 | 0.0000 |

Additional hybrid values: no-result 0.0062, wrong-population retrieval 0.1321, wrong-use-mode retrieval 0.0, duplicate retrieval 0.0, language-preference accuracy 0.0407. These are engineering benchmark values, not clinical outcomes.

## Dataset and Leakage

The benchmark has 162 queries, all preferred language `zh`, 144 direct-user-support cases, 10 psychoeducation cases, and 8 safety cases. The leakage report checked 162 queries against 13,166 chunks and found zero exact-hash and zero substring hits.

## Target vs Actual

`Hit@5 >= 0.70` style thresholds must be treated as planned targets unless present in a result file. The table above is the last actual saved run. It does not prove the current production runtime is benchmark-equivalent because the benchmark was staged and the current effective runtime uses production indexes.
