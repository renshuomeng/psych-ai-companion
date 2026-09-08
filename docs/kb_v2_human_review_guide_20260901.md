# CARE-Psy Knowledge Base V2.1 人工审核指南

更新时间：2026-09-01

## 目标

本指南用于把当前 staging RAG 知识库逐步推进到 production RAG。核心原则是：production 只能使用已经审核通过的 chunk；任何 pending chunk 都不能进入正式聊天回答。

## 当前审核状态

- 知识源：67 个启用
- cleaned 文档：320 份
- chunk 总数：13166
- 当前审核状态：pending 1648，approved 6631，rejected 4887
- staging 索引：BM25 8279，Dense 8279
- production 索引：BM25 6631，Dense 6631
- production readiness：READY

审核导入后，staging 已重建为 approved + pending 的可索引集合；rejected/blocked chunk 不再进入 staging，也不会进入 production。当前 production 可用于普通心理陪伴中的已审核自助建议引用，但剩余 pending 仍不能进入正式聊天引用。

## 当前待审核文件

- 剩余 pending 明细：`reports/pending_chunks_remaining_20260901.csv`：1648
- 剩余 pending 聚合报告：`reports/pending_chunks_remaining_20260901.md`
- P0 safety/high-risk：`reports/review_priority_p0_safety.csv`：150
- P1 ordinary interventions：`reports/review_priority_p1_interventions.csv`：49
- P1 children/adolescent：`reports/review_priority_p1_children.csv`：1260
- P2 general：`reports/review_priority_p2_general.csv`：189

建议顺序：

1. 先审核剩余 high-risk / safety-only pending：安全危机、自伤/自杀、伤人、家暴、未成年人保护、严重精神病性风险、危险操作细节。
2. 再审核 `p1_interventions`：普通自助干预材料，这是扩充正式聊天 RAG 覆盖面的最快路径。
3. 再审核 `p1_children`：儿童/青少年资料必须更谨慎，适合单独看。
4. 最后审核 `p2_general`，或暂时保持 pending。

## Source-Level 审核

查看 source：

```powershell
python scripts\rag\review_sources.py list --limit 20
python scripts\rag\review_sources.py inspect CCI_ANXIETY
```

记录 source 审核：

```powershell
python scripts\rag\review_sources.py approve CCI_ANXIETY --reviewed-by "你的名字" --comment "确认来源可信，下载内容与官方页面一致"
```

注意：`approve` 只记录 source 级人工审核，不会自动把 chunk 标为 approved。

## Chunk-Level 审核

导出一批 chunk：

```powershell
python scripts\rag\review_chunks.py export-review --source-id CCI_ANXIETY --limit 100 --output reports\cci_anxiety_review_batch.csv
```

逐条批准：

```powershell
python scripts\rag\review_chunks.py approve CHUNK_ID --reviewed-by "你的名字" --comment "内容适合普通自助支持"
```

逐条拒绝：

```powershell
python scripts\rag\review_chunks.py reject CHUNK_ID --reviewed-by "你的名字" --reason "包含临床诊断边界外内容"
```

导入审核 CSV：

```powershell
python scripts\rag\review_chunks.py import-review reports\cci_anxiety_review_batch.csv --reviewed-by "你的名字"
```

## 审核后进入正式 RAG

每次审核一批后，运行：

```powershell
python scripts\rag\build_production_indexes.py --dry-run
python scripts\rag\build_production_indexes.py --batch-size 64
python scripts\rag\kb_status.py --write
python scripts\rag\check_production_readiness.py
```

只有 `approved` chunks 会进入 production。普通 RAG 会拒绝药物剂量、自伤/自杀方法、危险操作、复杂诊断类越界问题；危机文本仍由 RiskAgent / SafetyAgent 接管。

## 最新验证

- `python -X utf8 scripts\rag\run_retrieval_benchmark.py --mode staging --candidate-k 50 --top-k 5 --json`
  - cases：162
  - Hybrid Hit@5：0.7593
  - Ordinary RAG safety leakage：0.0
  - Hybrid wrong use-mode：0.0
- `python -X utf8 scripts\rag\check_production_readiness.py --json`
  - production_ready：true
  - blockers：[]

## 不允许的做法

- 不允许把 pending chunk 直接改成 approved。
- 不允许把 source-level 审核伪装成专家 chunk-level 审核。
- 不允许把 safety-only chunk 放进普通心理陪伴回答。
- 不允许为追求召回率放宽 RiskAgent + SafetyAgent 的安全闸门。
