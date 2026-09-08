# CARE-Psy KB V2.2 Retrieval Improvement Report

生成时间：2026-09-03

## 结论

本轮继续完善知识库工程化能力，但没有自动批准剩余 pending 内容。

- Production RAG：已启用，approved-only。
- Approved chunks：6631
- Pending chunks：1648
- Rejected chunks：4887
- Production BM25 documents：6631
- Production dense vectors：6631
- Production readiness：passed，blockers 为空
- Ordinary RAG safety leakage：0.0
- Hybrid safety leakage：0.0
- Hybrid wrong use-mode：0.0

## 本轮完成

1. 中文 BM25 检索增强已保留并重建索引。
   - BM25 内部搜索文本加入 topic/population 的中英文别名。
   - 别名只参与索引检索，不写入返回给前端的 chunk content，因此不会污染引用内容。

2. 增加 chunk 级主题/人群派生。
   - 根据 section/content 自动补充细粒度标签，例如 `school_support`、`student_mental_health`、`emotion_regulation`、`distress_tolerance`、`postpartum`、`perinatal`、`older_adults` 等。
   - 已对 `UNICEF_PARENTING_MH` 中部分已 approved chunk 产生更细标签，例如 teen meltdown、express emotions、starting school、postpartum depression 相关片段。

3. 增加 query 级中文人群识别和排序增强。
   - 中文 query 可推断 `older_adults`、`children`、`adolescents`、`pregnant_people`、`postpartum_people`、`workers`、`university_students`、`people_experiencing_grief` 等隐含人群。
   - 检索排序会奖励主题兼容 chunk，轻微惩罚明显错人群 chunk。
   - 当候选集中已经有兼容人群资料时，最终结果会过滤明显错人群来源，减少不相关来源混入。

4. 尝试补抓缺失官方来源。
   - `NIA_LONELINESS`：官网返回 HTTP 405，未下载。
   - `NIA_DEPRESSION_OLDER_ADULTS`：官网返回 HTTP 405，未下载。
   - `SAMHSA_FAMILY_SUPPORT`：官网返回 HTTP 403，未下载。
   - `SAMHSA_TRAUMA_INFORMED_CARE`：官网返回 HTTP 403，未下载。
   - `UNICEF_ADOLESCENT_MH`：官网返回 HTTP 403，未下载。
   - 没有创建占位文件，也没有把这些来源伪装成已入库资源。

## 指标变化

对 162 条 RAG V2 benchmark query 重新评估：

| 指标 | V2.1 初始 | V2.2 本轮 |
| --- | ---: | ---: |
| BM25 Hit@5 | 0.6543 | 0.9568 |
| Hybrid Hit@1 | 0.6852 | 0.9136 |
| Hybrid Hit@5 | 0.7593 | 0.9568 |
| Hybrid Recall@5 | 0.3959 | 0.6274 |
| Hybrid MRR@5 | 0.7222 | 0.9333 |
| Hybrid wrong population | 0.2593 | 0.1321 |
| Hybrid wrong use-mode | 0.0 | 0.0 |
| Hybrid safety leakage | 0.0 | 0.0 |
| Ordinary RAG safety leakage | 0.0 | 0.0 |

最新 benchmark 文件：

- `backend/data/knowledge_base/reports/rag_v2_benchmark.json`
- `evaluation/rag_v2/results/benchmark_summary.json`
- `evaluation/rag_v2/results/failure_analysis.csv`
- `evaluation/rag_v2/results/benchmark_leakage_report.json`

## 重建结果

Staging rebuild：

- parsed documents：320
- total chunks：13166
- staging indexable chunks：8279
- staging BM25 documents：8279
- staging dense vectors：8279
- known parse warning：`WHO_DWM_STRESS_2020/Hindi.pdf` 实际内容不是有效 PDF，解析失败，不影响整体构建。

Production rebuild：

- eligible approved chunks：6631
- production BM25 documents：6631
- production dense vectors：6631
- production readiness：passed

## 仍未完成的部分

这些部分不能自动“完成”，因为会影响心理健康系统的可信引用和安全边界：

1. 剩余 1648 个 pending chunk 仍需人工审核。
   - 其中包括 safety-only/high-risk、儿童青少年、临床参考、特殊人群资料。
   - 未审核内容不会进入正式聊天 RAG。

2. 老年孤独、围产期、丧亲哀伤、家庭暴力、物质使用危机、严重精神病性体验等专项覆盖仍不足。
   - 当前 registry 已登记部分来源，但 NIA/SAMHSA/UNICEF 官方页面被 405/403 拦截，本地未取得可解析 raw 文件。
   - 需要人工从官网保存页面/PDF 后放入对应 raw/manual 目录，再运行解析、审核和 production rebuild。

3. `campus_support` production dense count 仍为 0。
   - 高校/学生心理健康政策类来源目前主要是 pending 或 agent_policy_only，不能直接用于普通陪伴回复引用。

## 本轮修改文件

- `backend/services/rag_v1_pipeline.py`
- `backend/services/rag_v1_retrieval_service.py`
- `backend/tests/test_rag_v1_pipeline.py`
- `backend/tests/test_rag_v1_chat_integration.py`

## 本轮备份

- `backend/data/knowledge_base/backups/before_v2_2_chunk_tag_rebuild_20260902_231150`

## 关键命令

```powershell
python -X utf8 scripts\rag\download_sources.py --source-id NIA_LONELINESS --source-id NIA_DEPRESSION_OLDER_ADULTS --source-id UNICEF_ADOLESCENT_MH --source-id SAMHSA_FAMILY_SUPPORT --source-id SAMHSA_TRAUMA_INFORMED_CARE --timeout 30 --json
python -X utf8 scripts\rag\build_knowledge_base.py --mode staging --json
python -X utf8 scripts\rag\build_production_indexes.py --dry-run
python -X utf8 scripts\rag\build_production_indexes.py --batch-size 64
python -X utf8 scripts\rag\kb_status.py --write --json
python -X utf8 scripts\rag\check_production_readiness.py --json
python -X utf8 scripts\rag\run_retrieval_benchmark.py --mode staging --candidate-k 50 --top-k 5 --json
```

