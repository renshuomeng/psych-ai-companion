# CARE-Psy KB V2.1 Remaining Work Audit 2026-09-01

## 当前状态

- total chunks：13166
- approved chunks：6631
- pending chunks：1648
- rejected chunks：4887
- BM25 staging documents：8279
- Dense staging vectors：8279
- BM25 production documents：6631
- Dense production vectors：6631
- Production readiness：READY

## 已完成的工程验收项

- 全量 staging dense index 已建立，不再是 1024 sample。
- 162-query RAG benchmark 已完成，BM25 / Dense / Hybrid 均有指标。
- Benchmark runtime index mode 已修复，`--mode staging` 不再误用 production。
- Safety leakage = 0，wrong use-mode = 0。
- Source/chunk review workflow 已可用。
- Production index 已使用 approved-only chunks 构建。
- BM25 production build 支持临时目录、健康检查、备份和 rollback。
- `kb_status.py` 和 `check_production_readiness.py` 已可用。
- 9 月 1 日用户审核表已导入并进入 production。
- `scripts/run_ablation.py` 已修复为 Evaluation Center 的 No-RAG vs Full-Agent smoke 对照入口。
- Production RAG runtime smoke 已完成：普通中文学习压力问题只返回 approved direct_user_support citation。
- 普通 RAG 已增加越界边界保护：药物剂量、自伤/自杀方法、危险操作、复杂诊断类问题在没有显式 safety route 时返回 `insufficient_evidence`。
- `kb_status.py` staging indexable 统计已修正：rejected/blocked 不再计入 staging 可索引数量。
- 审核导入后已重建 staging 索引：BM25 8279 documents，Dense 8279 vectors。
- 最新 162-query benchmark 已基于审核后 staging 重跑。
- `build_knowledge_base.py --json` 已兼容 Windows PowerShell 默认 GBK 控制台，避免中文 JSON 报告输出时报 `UnicodeEncodeError`。

## 仍未完全完成但不能自动伪造的事项

1. 剩余 1648 个 pending chunk 仍需要人工复核。
   - 原因：这些行在用户审核表中仍被标为 `pending`，不能由脚本擅自改成 approved。
   - 已生成清单：`reports/pending_chunks_remaining_20260901.csv`
   - 聚合报告：`reports/pending_chunks_remaining_20260901.md`

2. Safety-only 资料尚未进入 production safety collection。
   - 原因：P0 safety 当前剩余 150 条 pending，仍需要逐条人工判断；未审核 safety-only 内容不能自动放入 production。
   - 正确做法：继续由 RiskAgent/SafetyAgent 处理危机文本；不要把未审安全资料放入普通 RAG。

3. 中文原生 direct_user_support 仍偏少。
   - 当前中文 chunks：1078。
   - 当前中文 direct-user-support chunks：282，主题主要集中在 stress。
   - `CN_NHC_HEALTH_LITERACY_2024` 自动下载返回 HTTP 412，需要人工从官方页面保存资料后再入库。

4. Full Agent No-RAG vs RAG 大规模付费评测没有自动运行。
   - 原因：真实 LLM 评测可能消耗 API 费用；目前已有 Evaluation Center 接口和 ablation 开关。
   - 当前状态：已完成 2 条 CounselBench smoke，对照结果写入 `evaluation/results/ablation/rag_v2_no_rag_vs_full_agent.json`。
   - 建议：由项目负责人决定是否开启付费完整评测。

## 本次可继续执行的下一步

- 继续人工判断 1648 个 pending chunk，或保持 pending。
- 对 `CN_NHC_HEALTH_LITERACY_2024` 执行人工官方下载。
- 若要继续提高 Hybrid Hit@5，优先补充中文直引资料、细化 population metadata，并对剩余 pending 中的直接支持材料做人工审核。

## 最新人工审核队列

- `reports/review_priority_p0_safety.csv`：150
- `reports/review_priority_p1_interventions.csv`：49
- `reports/review_priority_p1_children.csv`：1260
- `reports/review_priority_p1_perinatal.csv`：0
- `reports/review_priority_p2_general.csv`：189
- `reports/review_priority_summary.json`：已于 2026-09-01 重新导出

## 最新 Staging Benchmark

- 命令：`python -X utf8 scripts\rag\run_retrieval_benchmark.py --mode staging --candidate-k 50 --top-k 5 --json`
- cases：162
- BM25 Hit@5：0.6543
- Dense Hit@5：0.8148
- Hybrid Hit@5：0.7593
- Hybrid MRR@5：0.7222
- Hybrid NDCG@5：0.7210
- Ordinary RAG safety leakage：0.0
- Hybrid wrong use-mode：0.0

说明：Hybrid Hit@5 比旧 staging 结果下降，是因为 rejected/blocked chunk 已被排除，测试索引更接近真实审核流程；安全指标仍保持为 0。

## 已补跑验证

- `python -m pytest backend\tests\test_knowledge_base_v2.py backend\tests\test_kb_v2_1_workflow.py backend\tests\test_rag_v1_chat_integration.py -q`
  - 22 passed, 2 warnings
- `python -m pytest backend\tests -q`
  - 81 passed, 2 warnings
- `npm run build`
  - passed
- `python scripts\rag\kb_status.py --write`
  - Production Ready: True
- `python scripts\rag\check_production_readiness.py`
  - production_status: READY
- `python scripts\rag\check_source_updates.py --limit 3 --json`
  - sources_checked: 3, ok: 3, errors: 0
- `python -X utf8 scripts\rag\check_production_readiness.py --json`
  - production_ready: true, blockers: []
- `python scripts\rag\build_knowledge_base.py --mode staging --dry-run --json`
  - exit code 0, indexable_chunks: 8279
