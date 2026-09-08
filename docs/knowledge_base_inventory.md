# 当前知识库资源与结构说明

更新时间：2026-08-16

本文档基于当前仓库实际文件盘点，说明 CARE-Psy / AI 心理陪伴系统里的“知识库”到底包含哪些资源、由哪些目录和索引构成、当前聊天回答实际会使用哪些部分。

## 一句话结论

当前项目里“知识库”不是单一文件，而是两套并存的检索资源：

1. **旧版中文示例知识库 / Legacy KB**
   - 面向竞赛原型演示的中文自助建议。
   - 当前 SQLite 中有 5 个知识源、15 个 chunk。
   - 资料都标记为 `source_unverified` / `reviewed=false`，所以前端会显示“待审核”。
   - 当 RAG V1 没有检索到足够相关资料，且 `RAG_V1_USE_FALLBACK=true` 时，会回退使用它。

2. **RAG Knowledge Base V1**
   - 按 `knowledge_sources_v1.yaml` 管理的正式 RAG 管线。
   - Registry 中登记 24 个来源。
   - 当前成功或部分下载 15 个来源，主要来自 CCI 和 NHS。
   - 当前生成 4057 个 pending chunk，全部为英文。
   - 当前普通聊天可通过 `RAGRouter -> RAG V1` 使用其中的 `interventions` 和 `professional_knowledge` collection。

高危安全回复不依赖普通 RAG。用户上传的图片、音频、视频、聊天历史、Memory、模型参数也不属于知识库。

## 运行时使用关系

正式聊天现在的知识检索链路是：

```text
User / MultimodalProcessor
-> RiskAgent
-> PsychologicalStateAnalyzer
-> StrategyPlanner
-> RAGRouter
-> RAG V1
-> 如 V1 不足且 RAG_V1_USE_FALLBACK=true，则回退 Legacy KB
-> CounselorAgent
-> SafetyAgent
```

关键配置：

```env
RAG_ENABLED=true
RAG_V1_ENABLED=true
RAG_V1_USE_FALLBACK=true
RAG_STAGING_MODE=true
RAG_ROUTER_ENABLED=true
```

含义：

- `RAG_V1_ENABLED=true`：优先走 RAG V1。
- `RAG_V1_USE_FALLBACK=true`：RAG V1 不足时允许回退旧版中文示例知识库。
- `RAG_STAGING_MODE=true`：允许使用 `review_status=pending` 的 V1 chunk 做开发演示。
- 如果要让页面只显示 RAG V1 来源，可设置 `RAG_V1_USE_FALLBACK=false`。
- 如果要正式部署，只使用人工审核资料，应在审核后设置 `RAG_STAGING_MODE=false`。

## Legacy KB：旧版中文示例知识库

### 位置

```text
backend/data/knowledge_base.json
backend/data/knowledge_base/manifests/seed_sources.jsonl
backend/data/knowledge_base/raw/*.md
backend/database/psych_ai.sqlite
```

### 当前 SQLite 中的实际规模

| 表/资源 | 数量 |
|---|---:|
| `knowledge_source` | 5 |
| `knowledge_chunk` | 15 |
| `knowledge_chunks_fts` | 15 |

### `seed_sources.jsonl` 中的 5 个中文种子源

| source_id | 标题 | 主题 | 审核状态 | 用途 |
|---|---|---|---|---|
| `kb_study_001` | 学习与论文压力自助建议 | `academic_stress` | 未审核 | 论文/学习压力、任务拆分 |
| `kb_sleep_001` | 睡眠卫生与压力性失眠自助建议 | `sleep` | 未审核 | 睡眠卫生、睡前放松 |
| `kb_job_001` | 就业焦虑下的下一步行动 | `career` | 未审核 | 求职、面试、行动拆分 |
| `kb_relationship_001` | 人际压力与沟通边界 | `relationship` | 未审核 | 室友、朋友、人际边界 |
| `kb_crisis_001` | 危机支持边界与现实求助 | `crisis_support` | 未审核 | 危机支持边界说明 |

这些就是你前端截图里出现“学习与论文压力自助建议”的来源。它来自旧版中文示例知识库，不是 CCI/NHS 那批英文 RAG V1 来源。

### `knowledge_base.json` 中的旧示例条目

该文件中还有 7 条更早期的中文演示条目：

| source_id | 标题 | section |
|---|---|---|
| `kb_study_001` | 学习压力 | 任务拆分 |
| `kb_exam_001` | 考试焦虑 | 可控范围 |
| `kb_job_001` | 就业焦虑 | 求职节奏 |
| `kb_sleep_001` | 睡眠卫生建议 | 睡前行为调整 |
| `kb_breathing_001` | 呼吸训练 | 一分钟稳定练习 |
| `kb_relationship_001` | 人际关系 | 沟通前准备 |
| `kb_crisis_001` | 危机支持边界 | 即时安全 |

当前数据库中主要体现的是 `seed_sources.jsonl` 导入后的 5 个 source、15 个 chunk。

## RAG Knowledge Base V1：正式 RAG 知识库

### Registry 入口

```text
backend/data/knowledge_base/sources/knowledge_sources_v1.yaml
```

这是 RAG V1 的唯一自动下载 allowlist。也就是说，自动下载脚本只允许处理该 YAML 中登记的来源，不能随意联网扩展资料。

### 目录结构

```text
backend/data/knowledge_base/
├── sources/
│   └── knowledge_sources_v1.yaml
├── raw/
│   ├── auto/              # 自动下载的原始网页/PDF/ZIP
│   └── manual/            # 用户手动放入的合法资料，目前为空
├── parsed/                # 解析后的结构化 JSON
├── cleaned/               # 清洗后的结构化 JSON
├── chunks/
│   ├── pending/           # 当前 4057 个 chunk 都在这里
│   ├── approved/          # 当前为空
│   └── rejected/          # 当前为空
├── indexes/
│   ├── bm25/              # BM25 关键词索引
│   └── chroma/            # Chroma staging 向量索引
└── reports/               # 下载、构建、审核和 smoke test 报告
```

### 当前构建规模

| 项目 | 当前数量 |
|---|---:|
| Registry sources | 24 |
| Auto-download sources | 24 |
| 成功下载 sources | 14 |
| 部分成功 sources | 1 |
| 下载失败 sources | 9 |
| 下载文件数 | 128 |
| 原始 `raw/auto` 文件 | 282 |
| 解析文档 | 179 |
| 清洗文档 | 179 |
| pending chunks | 4057 |
| approved chunks | 0 |
| rejected chunks | 0 |
| chunk 总字符数 | 1,824,820 |

### 当前 chunk 状态

| 字段 | 当前状态 |
|---|---|
| language | 全部 `en` |
| review_status | 全部 `pending` |
| evidence_level | 全部 `B` |
| user_facing | 全部 `true` |
| target_collection | `interventions` 4044 条，`professional_knowledge` 13 条 |

这就是为什么前端会显示“待审核”：RAG V1 当前虽然有官方来源，但 chunk 层面的人工审核还没有完成。

## RAG V1 Collection 设计

`knowledge_sources_v1.yaml` 里定义了 8 个 collection：

| collection | 含义 | 当前是否有 chunk |
|---|---|---|
| `professional_knowledge` | 心理教育、低风险支持知识 | 有，13 条 |
| `interventions` | 可执行自助技术和练习 | 有，4044 条 |
| `helping_skills` | 共情、倾听、协作等助人技能 | 当前无 chunk |
| `campus_support` | 大学生/校园支持资料 | 当前无 chunk |
| `safety` | 自伤/自杀安全资料，仅安全系统路由 | 当前无 chunk |
| `evidence` | 指南、综述、证据检查 | 当前无 chunk |
| `governance` | 实施、边界、治理资料 | 当前无 chunk |
| `case_rag` | 案例/对话数据，单独索引 | 当前无 chunk |

当前普通用户回答只允许优先使用用户可见的低风险资料，主要是：

```text
interventions
professional_knowledge
campus_support
```

但当前 `campus_support` 没有成功下载内容，所以实际主要是 `interventions` 和少量 `professional_knowledge`。

## RAG V1 已登记来源清单

### 当前成功或部分下载的来源

| source_id | 机构 | 标题 | collection | 状态 | 文件数 |
|---|---|---|---|---|---:|
| `CCI_ANXIETY` | Centre for Clinical Interventions | Anxiety self-help resources | `interventions` | success | 13 |
| `CCI_WORRY_RUMINATION` | Centre for Clinical Interventions | Worry and Rumination self-help resources | `interventions` | success | 18 |
| `CCI_PROCRASTINATION` | Centre for Clinical Interventions | Procrastination self-help resources | `interventions` | success | 11 |
| `CCI_PERFECTIONISM` | Centre for Clinical Interventions | Perfectionism self-help resources | `interventions` | success | 12 |
| `CCI_SELF_COMPASSION` | Centre for Clinical Interventions | Self-Compassion self-help resources | `interventions` | success | 9 |
| `CCI_SELF_ESTEEM` | Centre for Clinical Interventions | Self-Esteem self-help resources | `interventions` | success | 22 |
| `CCI_SLEEP` | Centre for Clinical Interventions | Sleep and insomnia self-help resources | `interventions` | success | 3 |
| `CCI_SOCIAL_ANXIETY` | Centre for Clinical Interventions | Social Anxiety self-help resources | `interventions` | success | 29 |
| `CCI_DISTRESS_TOLERANCE` | Centre for Clinical Interventions | Tolerating Distress self-help resources | `interventions` | success | 6 |
| `NHS_CBT_HUB` | NHS / Every Mind Matters | Self-help CBT techniques | `professional_knowledge` | success | 1 |
| `NHS_THOUGHT_RECORD` | NHS / Every Mind Matters | Thought record | `interventions` | partial | 1 |
| `NHS_PROBLEM_SOLVING` | NHS / Every Mind Matters | Problem solving | `interventions` | success | 1 |
| `NHS_WORRIES` | NHS / Every Mind Matters | Tackling your worries | `interventions` | success | 1 |
| `NHS_TODO_LIST` | NHS / Every Mind Matters | Tackling your to-do list | `interventions` | success | 1 |
| `NHS_SLEEP` | NHS / Every Mind Matters | How to fall asleep faster and sleep better | `interventions` | success | 1 |

### 已登记但当前下载失败的来源

这些来源在 YAML 里存在，但当前没有进入 chunk，原因主要是 `robots.txt` 限制或跳转域名不在 allowlist。

| source_id | 机构 | 标题 | collection | 状态 |
|---|---|---|---|---|
| `WHO_SELFHELP_2026` | WHO | Psychological self-help interventions | `interventions` | failed |
| `WHO_DWM_STRESS_2020` | WHO | Doing What Matters in Times of Stress | `interventions` | failed |
| `WHO_HELPING_SKILLS_2025` | WHO / UNICEF | Foundational helping skills training manual | `helping_skills` | failed |
| `WHO_PSYCH_IMPLEMENTATION_2024` | WHO | Psychological interventions implementation manual | `governance` | failed |
| `WHO_MHGAP_2023` | WHO | mhGAP guideline, third edition | `safety` | failed |
| `WHO_SAFETY_PLANNING_2023` | WHO | Safety planning interventions | `safety` | failed |
| `WHO_LIVE_LIFE_2021` | WHO | LIVE LIFE suicide prevention guide | `safety` | failed |
| `MOE_HIGHER_ED_MH_GUIDE_2018` | 教育部 | 高等学校学生心理健康教育指导纲要 | `campus_support` | failed |
| `MOE_STUDENT_MH_ACTION_2023_2025` | 教育部等十七部门 | 学生心理健康工作专项行动计划 | `campus_support` | failed |

## 当前 chunk 来源分布

| source_id | chunk 数 |
|---|---:|
| `CCI_SOCIAL_ANXIETY` | 939 |
| `CCI_SELF_ESTEEM` | 527 |
| `CCI_WORRY_RUMINATION` | 518 |
| `CCI_PERFECTIONISM` | 514 |
| `CCI_PROCRASTINATION` | 393 |
| `CCI_SELF_COMPASSION` | 385 |
| `CCI_DISTRESS_TOLERANCE` | 318 |
| `CCI_ANXIETY` | 305 |
| `CCI_SLEEP` | 80 |
| `NHS_PROBLEM_SOLVING` | 15 |
| `NHS_TODO_LIST` | 15 |
| `NHS_WORRIES` | 14 |
| `NHS_CBT_HUB` | 13 |
| `NHS_SLEEP` | 13 |
| `NHS_THOUGHT_RECORD` | 8 |

## 当前 topic 覆盖

当前高频 topic 包括：

| topic | chunk 数 |
|---|---:|
| `behavioural_experiments` | 1453 |
| `avoidance` | 1347 |
| `exposure` | 1244 |
| `social_anxiety` | 939 |
| `relationships` | 939 |
| `academic_stress` | 907 |
| `anxiety` | 858 |
| `worry` | 545 |
| `self_evaluation` | 535 |
| `self_esteem` | 527 |
| `core_beliefs` | 527 |
| `self_acceptance` | 527 |
| `rumination` | 518 |
| `mindfulness` | 518 |
| `uncertainty` | 518 |
| `perfectionism` | 514 |
| `procrastination` | 408 |
| `task_starting` | 393 |
| `self_compassion` | 385 |
| `distress_tolerance` | 318 |
| `emotion_regulation` | 318 |

从 topic 看，目前知识库最强的是：社交焦虑、回避、暴露练习、学业压力、焦虑、担忧反刍、完美主义、拖延、自我评价、自我关怀、痛苦耐受。

比较弱或为空的是：中文校园政策、中文本土心理中心资料、高危安全 guideline、就业焦虑专门资料、正式案例 RAG。

## 索引构成

### BM25 索引

位置：

```text
backend/data/knowledge_base/indexes/bm25/
```

文件：

```text
bm25_index.pkl
documents.jsonl
metadata.json
```

作用：

- 用于关键词检索。
- 当前覆盖全部 4057 个 pending chunk。
- 中文问题会先经过双语词典扩展，再用英文关键词提升命中率。

### Chroma staging 向量索引

位置：

```text
backend/data/knowledge_base/indexes/chroma/
```

作用：

- 用于向量检索。
- 当前是 staging collection。
- 配置中 `RAG_V1_MAX_DENSE_CHUNKS=512`，所以 dense 索引并不一定覆盖全部 4057 个 chunk。
- BM25 仍覆盖全量 chunk。

## 手动资料区

当前 manual 区域为空：

```text
backend/data/knowledge_base/raw/manual/
```

设计上允许你以后手动放入：

| manual zone | 路径 | 目标 collection | 用途 |
|---|---|---|---|
| `manual_textbooks` | `raw/manual/textbooks` | `professional_knowledge` | 合法获得的教材/章节 |
| `manual_papers` | `raw/manual/papers` | `evidence` | 综述、指南、论文 |
| `manual_campus` | `raw/manual/campus` | `campus_support` | 学校心理中心、校园支持资料 |
| `manual_cases` | `raw/manual/cases` | `case_rag` | 合法案例/对话数据，不进入普通 Knowledge RAG |

这些目前只是目录设计，没有实际资料。

## 审核字段解释

前端显示的几个字段含义如下：

| 字段 | 含义 |
|---|---|
| `source_unverified` | 来源证据级别未验证，常见于项目内置示例资料 |
| `review_status=pending` | RAG V1 chunk 已生成，但还没人工审核 |
| `reviewed=false` | Legacy KB 示例资料未人工审核 |
| `approved` / `reviewed` | 资料已人工审核，可作为更正式来源 |
| `rejected` | 资料不应进入回答引用 |

所以，“待审核”不等于资料一定错误，而是表示它还没有完成你项目定义的人工审核流程。

## 当前系统会如何选择知识来源

1. `RAGRouter` 根据心理状态、原因、需求和策略判断是否需要知识库。
2. 如果需要 RAG：
   - 优先使用 RAG V1。
   - 会按 collection、topics、用户可见性、审核状态、相关度过滤。
   - 当前 `RAG_STAGING_MODE=true`，所以 pending chunk 可以用于开发演示。
3. 如果 RAG V1 检索不足：
   - 当 `RAG_V1_USE_FALLBACK=true` 时，回退旧版中文 Legacy KB。
   - 这就是页面中可能出现“学习与论文压力自助建议”等中文示例来源的原因。
4. 高危风险场景：
   - 跳过普通 RAG。
   - 使用固定危机转介和安全闸门。

## 当前知识库的主要问题

1. **RAG V1 全部 chunk 仍是 pending**
   - 需要人工审核后，才能更有底气在比赛答辩中说“引用资料已审核”。

2. **RAG V1 当前主要是英文资料**
   - 中文提问依赖双语词典改写检索。
   - 可继续加入中文校园支持和中文心理健康教育资料。

3. **安全、校园、治理 collection 目前为空**
   - WHO 和 MOE 资料因 robots/下载限制没有自动进入知识库。
   - 可以由用户手动合法下载后放入 manual 区域，再构建。

4. **Legacy KB 是演示性质**
   - 它能保证中文场景有 fallback，但来源标注为 `source_unverified`。
   - 正式演示若想更严谨，可以关闭 fallback 或先审核这 5 个中文种子源。

## 建议的下一步

优先做三件事：

1. **审核 30-50 条高频 chunk**
   - 优先主题：论文拖延、完美主义、睡眠、焦虑、担忧反刍、自我关怀。
   - 把通过的 chunk 从 `pending` 标到 `approved` 或 `reviewed`。

2. **补中文校园支持资料**
   - 把学校心理中心公开页面、学校咨询流程、校内求助渠道整理为 Markdown 或 JSON。
   - 放入 `backend/data/knowledge_base/raw/manual/campus/`。
   - 目标 collection：`campus_support`。

3. **决定是否关闭 Legacy KB fallback**
   - 若想演示“更严格来源”，设置：

```env
RAG_V1_USE_FALLBACK=false
```

   - 若想保证中文场景稳定命中，则保留 fallback，但前端会继续显示“待审核”。
