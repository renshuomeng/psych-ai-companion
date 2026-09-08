# CARE-Psy Production RAG Activation Report

生成时间：2026-08-28

最近更新：2026-09-01

最新补充：2026-09-03 已重建 approved-only production indexes，并完成 V2.2 检索增强验证。最新报告见：

- `reports/kb_v2_2_retrieval_improvement_20260903.md`

最新状态：

- Production ready：true
- Approved chunks：6631
- Pending chunks：1648
- Rejected chunks：4887
- Production BM25 documents：6631
- Production dense vectors：6631
- Hybrid Hit@5：0.9568
- Hybrid wrong population retrieval rate：0.1321
- Hybrid safety leakage：0.0
- Ordinary RAG safety leakage：0.0

说明：后文保留了 2026-09-01 初次启用 production RAG 时的历史指标；请以后续报告与 `kb_status.py --write` 生成结果为准。

## 结论

Production RAG 已启用第一批低风险知识源。

- Production ready：true
- Approved chunks：6631
- Pending chunks：1648
- Rejected chunks：4887
- Staging BM25 documents：8279
- Staging dense vectors：8279
- Production BM25 documents：6631
- Production dense vectors：6631
- Runtime index mode：`production`
- Staging mode：false
- Legacy fallback：false
- Production readiness gate：passed
- BM25 atomic switch：enabled
- BM25 rollback：enabled

## 本次批准的 Source

用户确认批准第一批 source，`reviewed_by` 记录为：`你的名字`。

已传播到 approved 的 eligible chunks：

- `CCI_SOCIAL_ANXIETY`：918
- `CCI_WORRY_RUMINATION`：556
- `CCI_SELF_COMPASSION`：421
- `CCI_PROCRASTINATION`：406
- `CCI_DISTRESS_TOLERANCE`：350
- `CCI_ANXIETY`：331
- `WHO_DWM_STRESS_2020`：247
- `CCI_ASSERTIVENESS`：186
- `CCI_SLEEP`：107
- `NHS_TODO_LIST`：30
- `NHS_PROBLEM_SOLVING`：28
- `NHS_WORRIES`：24
- `NHS_SLEEP`：22
- `NHS_THOUGHT_RECORD`：17

初次启用合计：3643 approved chunks。2026-09-01 导入用户后续审核表后，production 已扩展到 6631 approved chunks。

## 未批量放行的内容

- Held for review：306 条来自第一批 source 的 chunk 被自动保留。
- Safety-only / crisis / high-risk 内容没有被批量放行。
- 其他 source 仍保持 pending。

## 运行时配置

根目录 `.env` 已写入：

```dotenv
RAG_ENABLED=true
RAG_V1_ENABLED=true
RAG_INDEX_MODE=production
RAG_STAGING_MODE=false
RAG_V1_USE_FALLBACK=false
```

关闭 fallback 的原因：production 模式下如果 approved-only RAG 没有检索到足够证据，应返回 insufficient evidence，而不是退回旧的未审核检索库。

## 生产索引

生产索引 manifest：

- `backend/data/knowledge_base/reports/production_index_manifest.json`

索引内容：

- BM25 production：6631 documents
- Dense production：6631 vectors
- Chroma production collections：approved chunks across enabled production collections
- Embedding model：`BAAI/bge-m3`
- New embeddings：0
- Cache hits：6631
- BM25 atomic switch：true
- BM25 backup：`backend/data/knowledge_base/indexes/bm25/backups/production_2026-09-01T034252+0000`

如需回滚最近一次 BM25 production，可运行：

```powershell
python scripts\rag\build_production_indexes.py --rollback-bm25
```

或使用 manifest 中记录的 `rollback.bm25_command` 指定备份目录。

## 待审核队列

已重新导出精细审核队列：

- `reports/review_priority_p0_safety.csv`：150
- `reports/review_priority_p1_interventions.csv`：49
- `reports/review_priority_p1_children.csv`：1260
- `reports/review_priority_p1_perinatal.csv`：0
- `reports/review_priority_p2_general.csv`：189
- `reports/review_priority_summary.json`

本轮补充后，staging 总 chunk 为 13166，其中中文 chunk 为 1078；审核导入后 staging 可索引集合已收紧为 8279 个 approved/pending chunks，rejected/blocked 不再进入 staging 检索。`CN_MOE_SCHOOL_MH_GUIDE` 已进入 staging pending，`CN_NHC_HEALTH_LITERACY_2024` 仍在人工官方获取队列。

## 烟测结果

普通焦虑/睡眠问题：

- retrieval_status：success
- index_mode：production
- returned documents：3
- 所有返回文档均为 approved
- use_mode：direct_user_support
- risk_scope：normal

越界文本走普通 RAG 过滤：

- 药物剂量 query：`insufficient_evidence`，`boundary_reason=medication_or_dosage_out_of_scope`
- 自伤/自杀方法 query：`insufficient_evidence`，`boundary_reason=safety_route_required`
- 普通 RAG 不返回 safety-only 文档

真实聊天中，高风险输入仍应由 RiskAgent / SafetyAgent 接管，不应依赖普通 RAG 直接处理危机。

## 测试结果

- `python -m pytest backend\tests -q`
  - 81 passed, 2 warnings

- `npm run build`
  - TypeScript + Vite build passed

- `reports/production_rag_runtime_smoke_20260901.json`
  - ordinary academic-stress query returned approved direct_user_support documents
  - medication dosage and self-harm method queries returned insufficient_evidence boundary responses

- `python -X utf8 scripts\rag\run_retrieval_benchmark.py --mode staging --candidate-k 50 --top-k 5 --json`
  - 162 cases completed
  - Hybrid Hit@5：0.7593
  - ordinary RAG safety leakage：0.0
  - wrong use-mode：0.0

- `python -X utf8 scripts\rag\check_production_readiness.py --json`
  - production_ready true；blockers []

## 备份

启用前审核数据备份：

- `backend/data/knowledge_base/backups/production_activation_20260828_124950`

`.env` 启用前备份：

- `.env.bak_before_production_rag_20260828_125246`

## 后续建议

下一步优先审核并上线：

1. 疾病科普类 `psychoeducation_only` source，例如 NIMH / NICE / CCI depression/anxiety/OCD/PTSD 等。
2. 中文官方/高校心理健康资料，提升中文原生引用比例。
3. Safety-only 高风险知识源还剩 150 条 pending，必须逐条审核后再进入 SafetyAgent 专用生产集合。
