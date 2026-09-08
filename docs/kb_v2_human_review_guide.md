# CARE-Psy Knowledge Base V2.1 人工审核指南

生成时间：2026-08-28

## 目标

本指南用于把当前 staging RAG 知识库逐步推进到 production RAG。核心原则是：production 只能使用已经审核通过的 chunk；任何 pending chunk 都不能进入生产回答。

## 当前审核状态

- 知识源：67 个启用
- cleaned 文档：320 份
- chunk 总数：13166
- 当前审核状态：pending 9523，approved 3643，rejected 0
- staging 索引：BM25 13166，Dense 13166
- production 索引：BM25 3643，Dense 3643

这表示第一批低风险 source 已经进入 production RAG。当前 production 可用于普通心理陪伴中的已审核自助建议引用，但全库仍未完成审核，高风险与 clinical-only 内容不能进入普通回答。

补充：`CN_MOE_SCHOOL_MH_GUIDE` 已从教育部官方页面自动获取并进入 staging，新增 39 个 pending chunk；`CN_NHC_HEALTH_LITERACY_2024` 的官方页面在自动下载时返回 HTTP 412，已放入人工获取队列。

## 审核队列

已生成以下 CSV：

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

建议审核顺序：

1. 先审核 high-risk：安全危机、自伤/自杀、伤人、家暴、未成年人保护、严重精神病性风险、危险操作细节。
2. 再审核 `p1_interventions`：仍 pending 的普通自助干预材料，这是扩充正式聊天 RAG 覆盖面的最快路径。
3. 再审核 `p1_children` / `p1_perinatal`：这些人群更敏感，适合单独看。
4. 最后审核 `p2_general`，或暂缓。

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

## 批量批准 eligible chunk

在完成 source 人工审核后，可以显式传播到自动校验通过且非高风险的 chunk：

```powershell
python scripts\rag\review_sources.py bulk-approve-eligible CCI_ANXIETY --confirm-source-id CCI_ANXIETY --reviewed-by "你的名字" --comment "source reviewed; eligible chunks passed automatic validation"
```

传播后 chunk 会写入：

- `review_status=approved`
- `approval_basis=human_source_review_plus_automatic_chunk_validation`
- `reviewed_by`
- `reviewed_at`

高风险 chunk 不会被 source-level 批量批准，会保留在 pending，并写入 `review_hold_reasons`。

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

## 生产索引构建

只有存在 approved chunk 时才构建 production：

```powershell
python scripts\rag\build_production_indexes.py --dry-run
python scripts\rag\build_production_indexes.py --batch-size 64
python scripts\rag\kb_status.py --write
```

当前已有 3643 个 approved chunk，production build 会使用 approved-only 数据构建。BM25 production 构建采用临时目录健康检查后再切换；如果已有旧 production BM25，会自动备份。

最近一次 production BM25 备份：

```text
backend/data/knowledge_base/indexes/bm25/backups/production_2026-08-28T100623+0000
```

回滚最近一次 BM25 production：

```powershell
python scripts\rag\build_production_indexes.py --rollback-bm25
```

或指定某个备份：

```powershell
python scripts\rag\build_production_indexes.py --rollback-bm25 --backup-dir backend\data\knowledge_base\indexes\bm25\backups\production_YYYY-MM-DDTHHMMSS+0000
```

## 不允许的做法

- 不允许把 pending chunk 直接复制到 approved。
- 不允许把 source-level 审核伪装成专家 chunk-level 审核。
- 不允许把 safety-only chunk 放进普通心理陪伴回答。
- 不允许为追求召回率放宽 RiskAgent + SafetyAgent 的安全闸门。

## 进入 production 的最低条件

- 至少一批核心 source 完成人工审核。
- eligible 非高风险 chunk 已批量或逐条 approved。
- high-risk chunk 已单独审核或继续保持 pending。
- `python scripts\rag\build_production_indexes.py` 成功构建 approved-only 索引。
- `python scripts\rag\run_retrieval_benchmark.py --candidate-k 50` 的 `hybrid_safety_leakage_rate=0` 且 `hybrid_wrong_use_mode_retrieval_rate=0`。
- `python scripts\rag\kb_status.py --write` 中 `production_ready=true`。
