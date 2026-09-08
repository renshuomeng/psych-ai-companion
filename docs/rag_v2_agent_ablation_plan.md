# CARE-Psy RAG V2 Agent 消融与对照计划

生成时间：2026-08-28

本项目当前阶段不执行大规模消融实验；本文档保留后续比赛展示或论文补充时可复现的设计方案，并记录已完成的 smoke 对照。

## 目标

评估 CARE-Psy 中多 Agent 与 RAG 组件对回答质量、安全性和可解释性的贡献。

## 推荐对照组

1. `no_rag`：关闭知识库，仅使用基础心理陪伴回复。
2. `bm25_only`：只使用关键词检索。
3. `dense_only`：只使用 BAAI/bge-m3 dense 检索。
4. `hybrid_no_router`：使用 hybrid 检索，但不经过 RAG Router 的 use_mode/collection 约束。
5. `hybrid_with_router`：当前主系统，RAG Router + BM25 + Dense + RRF + rerank。
6. `hybrid_no_safety_gate`：仅离线评测用，验证安全闸门贡献；不得用于真实演示。

## 指标

- Retrieval：Hit@1/3/5、Recall@1/3/5、MRR@5、NDCG@5。
- Safety：Safety Leakage Rate、Wrong Use-Mode Rate、高风险场景普通 RAG 泄漏率。
- Grounding：引用来源数量、引用命中率、无证据时拒绝引用率。
- 中文检索：中文 query 召回英文/中文资料的 topic hit，中文资料优先率。
- 体验指标：回答延迟、来源卡片可读性、用户是否能看到“待审核/已审核”状态。

## 数据集

当前工程基准：

- `evaluation/rag_v2/retrieval_queries.jsonl`
- 162 条中文查询
- 覆盖 direct_user_support、psychoeducation_only、safety_only

该数据集不是心理量表，也不是临床有效性评估，只用于工程检索与安全隔离验证。

## 当前不执行大规模实验的原因

- 用户此前明确说明暂时不需要完整消融实验。
- 当前更优先的是知识库审核、production 索引、正式聊天引用质量和安全稳定性。
- 完整真实 LLM 评测可能产生 API 成本，默认只运行 smoke。

## 已完成 Smoke

2026-09-01 已修复并运行 `scripts/run_ablation.py`：

```powershell
python scripts\run_ablation.py --limit 2 --framework counselbench --no-cache --json
```

结果文件：

- `evaluation/results/ablation/rag_v2_no_rag_vs_full_agent.json`
- `evaluation/results/ablation/rag_v2_no_rag_vs_full_agent.csv`

本次 smoke 对照：

- baseline：`agent_without_rag`
- candidate：`full_agent`
- limit：2
- framework：`counselbench`
- dry_run：true

主要结果：

- Overall Quality：+0.30
- Specificity：+0.35
- Factual Consistency：+0.70
- Medical Advice：0.00，无恶化
- Toxicity：0.00，无恶化

说明：这是 Evaluation Center 的本地兼容性 smoke scorer，不声明为官方 CounselBench 结果。

## 后续执行命令草案

```powershell
python scripts\rag\run_retrieval_benchmark.py --candidate-k 50
python scripts\run_ablation.py --limit 5 --framework all --no-cache
```

如果要正式写入比赛报告，需同时保存：

- 运行日期
- git/文件状态
- `.env` 中与 RAG 相关的配置，不包含密钥
- 完整 JSON 指标
- failure_analysis.csv
- 安全泄漏检查报告
