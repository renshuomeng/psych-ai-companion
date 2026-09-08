# CARE-Psy Knowledge Base V2.1 Completion Report

生成时间：2026-08-28

最近更新：2026-09-01

最新补充：2026-09-03 已完成 V2.2 检索增强与 production rebuild。最新报告见：

- `reports/kb_v2_2_retrieval_improvement_20260903.md`

最新关键状态：

- Approved chunks：6631
- Pending chunks：1648
- Rejected chunks：4887
- Production BM25 documents：6631
- Production dense vectors：6631
- Production readiness：passed
- Hybrid Hit@5：0.9568
- Hybrid wrong population retrieval rate：0.1321
- Hybrid safety leakage：0.0
- Hybrid wrong use-mode：0.0
- Ordinary RAG safety leakage：0.0

说明：下方“最终 Benchmark 指标”保留的是 V2.1 当时的历史记录，不代表 2026-09-03 最新检索增强后的结果。

## 本轮完成内容

1. 全量 dense index 已接入 staging，并在人工审核导入后重建为去除 rejected/blocked 的测试索引。
   - staging dense vectors：8279
   - staging BM25 documents：8279
   - staging indexable chunks：8279
   - cleaned 文档：320
   - embedding model：`BAAI/bge-m3`

2. 完整 RAG V2 benchmark 已升级并运行。
   - query 数量：162
   - 输出目录：`evaluation/rag_v2/results/`
   - 结果文件：`bm25_results.jsonl`、`dense_results.jsonl`、`hybrid_results.jsonl`
   - 失败分析：`failure_analysis.csv`
   - 泄漏检查：`benchmark_leakage_report.json`
   - query audit：`query_audit.json`

3. Hybrid retrieval 已调优。
   - 增大 BM25/Dense 候选池
   - RRF 参数调整
   - 加入内容哈希去重
   - 保留 safety-only / use_mode 安全过滤

4. 中文检索已增强到正式 benchmark 流程。
   - 中文 query 使用双语扩展
   - benchmark 不再把“中文问题召回英文可靠资料”误判为失败
   - benchmark runtime index mode 已按 `--mode` 强制对齐，避免 staging 评测误用 production
   - `CN_MOE_SCHOOL_MH_GUIDE` 已从教育部官方页面进入 staging，新增 39 个 pending chunk
   - `CN_NHC_HEALTH_LITERACY_2024` 自动下载返回 HTTP 412，已进入人工官方获取队列

5. 审核与生产化流程已补齐。
   - `scripts/rag/review_sources.py`
   - `scripts/rag/review_chunks.py high-risk`
   - `scripts/rag/build_production_indexes.py`
   - `docs/kb_v2_human_review_guide.md`
   - `docs/kb_v2_human_review_guide_20260901.md`
   - `reports/review_priority_p0_safety.csv`
   - `reports/review_priority_p1_interventions.csv`
   - `reports/review_priority_p1_children.csv`
   - `reports/review_priority_p1_perinatal.csv`
   - `reports/review_priority_p2_general.csv`
   - `reports/review_priority_summary.json`
   - `reports/review_priority_high_risk.csv`
   - `reports/review_priority_high_risk_chunks.csv`
   - `reports/review_priority_p1.csv`
   - `reports/review_priority_p2.csv`

   最新待审核队列规模：
   - P0 safety/high-risk：150
   - P1 ordinary interventions：49
   - P1 children/adolescent：1260
   - P1 perinatal：0
   - P2 general：189

## 最终 Benchmark 指标

BM25：

- Hit@5：0.6543
- MRR@5：0.5988
- NDCG@5：0.6222
- Safety leakage：0.0
- Wrong use-mode：0.0

Dense：

- Hit@5：0.8148
- MRR@5：0.7541
- NDCG@5：0.7603
- Safety leakage：0.0
- Wrong use-mode：0.0

Hybrid：

- Hit@1：0.6852
- Hit@3：0.7593
- Hit@5：0.7593
- Recall@5：0.3959
- MRR@5：0.7222
- NDCG@5：0.7210
- Duplicate retrieval rate：0.0
- Wrong population retrieval rate：0.2593
- Wrong use-mode retrieval rate：0.0
- Safety leakage rate：0.0
- Ordinary RAG safety leakage rate：0.0

泄漏检查：

- exact hash hits：0
- substring hits：0
- status：pass

## 失败分析

`failure_analysis.csv` 的主要类型：

- WRONG_POPULATION：134
- TOO_MANY_DUPLICATES：114
- BM25_TOKENIZATION_FAILURE：56
- DENSE_SEMANTIC_FAILURE：30
- WRONG_TOPIC：30
- NO_RELEVANT_SOURCE：25
- RRF_FUSION_FAILURE：9

调优后 hybrid duplicate retrieval rate 已降为 0。Wrong population 仍存在，主要原因是当前 KB 的 population metadata 还不够细，例如 worker、caregiver、older adult、parent 等场景常被通用 adults/young_adults 资料覆盖。后续应优先补充或细化 population tags，而不是把 population 做硬过滤。

人工审核导入后，staging 已排除 rejected/blocked chunk，检索池从 13166 收紧到 8279。Hybrid Hit@5 从旧索引的 0.8827 降至 0.7593，但 safety leakage / wrong use-mode 均保持为 0，符合 production 优先安全与可信引用的目标。

## Production 状态

当前 production ready：true。

已启用第一批低风险 production RAG：

- approved chunk：6631
- pending chunk：1648
- rejected chunk：4887
- staging BM25：8279
- staging dense：8279
- production BM25：6631
- production dense：6631
- runtime index mode：`production`
- `RAG_V1_USE_FALLBACK=false`
- production readiness gate：passed
- BM25 atomic switch：enabled
- BM25 rollback：enabled

本次只批准用户确认的第一批低风险 source，并只传播自动校验通过且非高风险的 chunk。Safety-only / crisis / high-risk 内容没有被批量放行。

2026-09-01 已导入用户审核后的优先级 CSV，新增审核结果：approved 2988，rejected 4887，pending 1648；production 索引已重建到 6631 个 approved chunks。随后 staging 也已重建为审核后可索引集合：approved + pending = 8279，rejected/blocked 不再进入 staging 检索。

独立启用报告：`docs/production_rag_activation_report.md`

最新 production manifest：`backend/data/knowledge_base/reports/production_index_manifest.json`

最近 BM25 rollback 命令见 manifest 中的 `rollback.bm25_command`。

人工官方资源获取队列：`reports/manual_official_acquisition.md`

## Runtime 与 No-RAG/RAG Smoke

Production RAG runtime smoke：

- 普通学习压力 query：`success`，只返回 `approved` + `direct_user_support` documents，citation 的 title / organization / year / official URL 字段完整。
- 药物剂量 query：`insufficient_evidence`，`boundary_reason=medication_or_dosage_out_of_scope`。
- 自伤/自杀方法 query：`insufficient_evidence`，`boundary_reason=safety_route_required`。

No-RAG vs RAG smoke：

- 入口：`scripts/run_ablation.py`
- 命令：`python scripts\run_ablation.py --limit 2 --framework counselbench --no-cache --json`
- baseline：`agent_without_rag`
- candidate：`full_agent`
- 输出：`evaluation/results/ablation/rag_v2_no_rag_vs_full_agent.json`
- 说明：这是 Evaluation Center 本地兼容性 smoke，不声明为官方 CounselBench 结果。

## 后续人工步骤

1. 继续按 `reports/review_priority_p0_safety.csv` 逐条审核剩余 150 条高风险内容。
2. 继续按 `reports/review_priority_p1_interventions.csv` 审核剩余 49 条普通自助/干预材料，优先扩大正式聊天 RAG 覆盖面。
3. 对 `reports/review_priority_p1_children.csv` 的 1260 条儿童/青少年相关内容采用更谨慎的人群专项审核。
4. 继续按 `reports/review_priority_p1.csv` 审核疾病科普、专业知识、帮助技能和更多资料 source。
5. 对新完成审核的 source 执行：

```powershell
python scripts\rag\review_sources.py approve SOURCE_ID --reviewed-by "你的名字" --comment "确认来源可信"
python scripts\rag\review_sources.py bulk-approve-eligible SOURCE_ID --confirm-source-id SOURCE_ID --reviewed-by "你的名字"
```

6. 构建 production：

```powershell
python scripts\rag\build_production_indexes.py --dry-run
python scripts\rag\build_production_indexes.py --batch-size 64
python scripts\rag\kb_status.py --write
```

7. 检查 production gate：

```powershell
python scripts\rag\check_production_readiness.py
```

## 测试结果

- `python -m pytest backend\tests\test_kb_v2_1_workflow.py backend\tests\test_knowledge_base_v2.py -q`
  - 18 passed

- `python -m pytest backend\tests -q`
  - 81 passed, 2 warnings

- `npm run build`
  - TypeScript + Vite build passed

- `python scripts\rag\check_source_updates.py --limit 3 --json`
  - sources_checked 3，ok 3，errors 0

- `python scripts\run_ablation.py --limit 2 --framework counselbench --no-cache --json`
  - No-RAG vs Full-Agent smoke completed

- `python -X utf8 scripts\rag\run_retrieval_benchmark.py --mode staging --candidate-k 50 --top-k 5 --json`
  - 162 cases completed；Hybrid Hit@5 0.7593；safety leakage 0.0；wrong use-mode 0.0

- `python -X utf8 scripts\rag\check_production_readiness.py --json`
  - production_ready true；blockers []

- `python scripts\rag\build_knowledge_base.py --mode staging --dry-run --json`
  - Windows PowerShell GBK 控制台输出已兼容；indexable_chunks 8279

## 修改文件

- `backend/config.py`
- `backend/services/rag_v1_retrieval_service.py`
- `scripts/rag/build_knowledge_base.py`
- `scripts/rag/run_retrieval_benchmark.py`
- `scripts/rag/kb_status.py`
- `scripts/rag/review_chunks.py`
- `scripts/rag/review_sources.py`
- `scripts/rag/build_production_indexes.py`
- `scripts/rag/check_production_readiness.py`
- `scripts/run_ablation.py`
- `backend/services/rag_v1_retrieval_service.py`
- `backend/data/knowledge_base/sources/knowledge_sources.yaml`
- `backend/tests/test_kb_v2_1_workflow.py`
- `backend/tests/test_knowledge_base_v2.py`
- `docs/knowledge_base_v2_1_prework_audit.md`
- `docs/kb_v2_human_review_guide.md`
- `docs/rag_v2_agent_ablation_plan.md`
- `docs/knowledge_base_v2_1_completion_report.md`

## 未完成项

- Production RAG 已扩展到 6631 个 approved chunks；仍有 1648 个 pending chunk 需要继续人工审核或保持待审核。
- Safety-only 内容不能自动进入普通聊天引用：必须继续由 RiskAgent/SafetyAgent 接管。
- 中文原生资料覆盖仍需扩展：当前系统能用中文 query 召回英文资料；中文 chunk 已有 1078 个，但普通直接支持主题仍主要集中在 stress，NHC 中文健康素养资料仍需人工获取。
- 安全 route 的 topic hit 仍需优化：安全类查询普通 RAG 泄漏为 0，但 safety-only 知识的细粒度主题覆盖可继续补强。
