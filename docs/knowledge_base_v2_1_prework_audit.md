# CARE-Psy Knowledge Base V2.1 Prework Audit

生成时间：2026-08-28

本文档根据当前本地文件生成，不把历史报告中的旧状态当成事实。

## 仓库状态

- 项目根目录：`C:/Users/renshuomeng/Documents/Codex/2026-06-30/ban/psych-ai-companion`
- Git 状态：当前目录不是 Git 仓库

## Source / Document / Chunk

- Source registry：`backend/data/knowledge_base/sources/knowledge_sources.yaml`
- Source 数量：67
- Enabled source：67
- Auto-download source：65
- Cleaned 文档：315
- Chunk 总数：13127
- Pending：13127
- Approved：0
- Rejected：0

## Index

- BM25 staging documents：13127
- BM25 production documents：0
- Dense staging vectors：13127
- Dense production vectors：0
- Dense embedding model：`BAAI/bge-m3`
- Dense embedding dimension sample：1024

结论：staging 索引已经是全量，不再是 1024 条抽样索引；production 索引仍然为空，因为没有 approved chunk。

## Retrieval Config

- Runtime index mode：`staging`
- BM25 enabled：true
- Dense enabled：true
- BM25 candidate top-k：16
- Dense candidate top-k：12
- Min relevance score：0.26
- Min vector score：0.46
- Hybrid fusion：`rrf`
- RRF k：45

## RAG V2 Benchmark

- Query file：`evaluation/rag_v2/retrieval_queries.jsonl`
- Query count：162
- Benchmark result：`evaluation/rag_v2/results/benchmark_summary.json`
- Failure analysis：`evaluation/rag_v2/results/failure_analysis.csv`
- Leakage report：`evaluation/rag_v2/results/benchmark_leakage_report.json`

核心结果：

- BM25 Hit@5：0.6481
- Dense Hit@5：0.8148
- Hybrid Hit@5：0.8765
- Hybrid MRR@5：0.7593
- Hybrid NDCG@5：0.7891
- Hybrid duplicate retrieval rate：0.0
- Hybrid wrong use-mode retrieval rate：0.0
- Hybrid safety leakage rate：0.0
- Ordinary RAG safety leakage rate：0.0
- Benchmark leakage check：pass

## Chinese Retrieval

- 所有 162 条 benchmark query 均为中文。
- 当前系统通过中文 query + 双语词表扩展召回英文/中文资料。
- 中文 direct_user_support chunk：282 条，主题主要为 `stress`。
- 当前短板不是“中文问题不能检索”，而是中文原生资料覆盖仍有限，很多有效来源来自英文 CCI/WHO/NHS/NIMH 材料。

## Production Readiness

当前 production ready：false。

阻断项：

- `approved_chunks_zero`
- `production_bm25_missing`
- `production_dense_missing`

这些阻断项是预期结果：系统没有把 pending chunk 误放入 production。

## Phase 0 结论

已完成：

- 全量 staging dense index：13127 vectors
- 完整 162-query benchmark
- BM25 / Dense / Hybrid 对比
- failure_analysis.csv
- benchmark leakage check
- 安全泄漏检查：0
- use-mode 错用检查：0

未完成且不能自动完成：

- Production RAG 激活：需要人工审核后产生 approved chunk。
- 高风险 chunk 通过：需要逐条人工审核，不能由 source-level 自动传播。
- 中文原生资料覆盖扩充：需要继续补充可靠中文官方/高校心理健康资料。
