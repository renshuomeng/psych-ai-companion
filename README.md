# AI 心理陪伴 Web 系统

面向大学生学习压力、就业焦虑、人际关系、睡眠困扰、孤独感等轻中度情绪场景的 AI 心理陪伴与自助调节助手。系统不是医疗系统，不做医学诊断，不提供药物建议，不承诺治疗效果。

当前版本支持文字、图片、音频上传、浏览器麦克风录音、视频上传、摄像头录制入口、多 Agent 风险闭环、豆包/火山方舟文本与多模态调用、SQLite 元数据、访问码、公网演示、会话删除、情绪感知 RAG、原因/策略评测和真实反馈报告。

## 运行模式

- `development`：React Vite 开发服务器 `5173`，FastAPI `8001 --reload`，Vite proxy 将 `/api` 转发到后端。
- `public_demo`：先构建 `frontend/dist`，FastAPI 单端口托管前端和 `/api`，Cloudflare Quick Tunnel 暴露临时 HTTPS。
- `production`：生产构建，支持固定域名、Cloudflare Named Tunnel 或 Docker Compose + Caddy。

前端生产环境只使用同源 `/api`，不要在生产代码中写死 `localhost` 后端地址。

## 配置

复制模板：

```powershell
Copy-Item .env.example .env
```

在 `.env` 填写豆包/火山方舟配置和公网访问码：

```env
ARK_API_KEY=
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL_ID=doubao-seed-2-0-lite-260215
DOUBAO_VISION_MODEL_ID=doubao-seed-2-0-lite-260215
DOUBAO_VIDEO_MODEL_ID=doubao-seed-2-0-lite-260215

VOLC_SPEECH_API_KEY=
VOLC_SPEECH_RESOURCE_ID=volc.bigasr.auc_turbo
VOLC_SPEECH_APP_ID=
VOLC_SPEECH_ACCESS_KEY=

PUBLIC_ACCESS_ENABLED=false
PUBLIC_ACCESS_CODE=

FFMPEG_PATH=
FFPROBE_PATH=
```

情绪感知检索权重可在 `.env` 调整，默认语义相关性占主要权重，情绪、原因、策略和风险兼容性作为排序辅助。

Agent V2 心理状态与 RAG 路由可在 `.env` 调整：

```env
AGENT_V2_ENABLED=true
PSYCHOLOGICAL_STATE_ANALYZER_ENABLED=true
STRATEGY_PLANNER_ENABLED=true
RAG_ROUTER_ENABLED=true
PSY_STATE_LOW_CONFIDENCE_THRESHOLD=0.55
RAG_STAGING_MODE=true
```

`.env` 已被忽略。不要向任何人发送 `.env`、API Key、访问码或 Cloudflare token。

## 本地开发

```powershell
.\scripts\start_dev.ps1
```

打开：

```text
http://127.0.0.1:5173
http://127.0.0.1:8001/api/health
```

关闭：

```powershell
.\scripts\stop_dev.ps1
```

## 生产单端口预览

```powershell
.\scripts\build_production.ps1
cd backend
$env:APP_ENV="public_demo"
$env:SERVE_FRONTEND="true"
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

访问 `http://127.0.0.1:8001` 会看到 React 页面，`http://127.0.0.1:8001/api/health` 仍是 API。

## 临时公网分享

先在 `.env` 写入：

```env
PUBLIC_ACCESS_CODE=你的演示访问码
```

启动：

```powershell
.\scripts\start_public_demo.ps1
```

脚本会检查 Python、Node、npm、cloudflared、`.env`、`ARK_API_KEY`，构建前端，启动 FastAPI 单端口服务，再启动 Cloudflare Quick Tunnel。

关闭：

```powershell
.\scripts\stop_public_demo.ps1
```

检查：

```powershell
.\scripts\check_public_demo.ps1
```

Quick Tunnel 地址是临时地址，进程停止后失效。公开演示时电脑必须保持开机和联网。正式展示应使用 Named Tunnel 或云服务器。

## 固定公网地址

Named Tunnel 说明在 `deployment/cloudflare/README.md`。不要把 Cloudflare 账号、域名、token、credentials JSON 写进仓库。

## Docker 部署

```powershell
$env:PUBLIC_DOMAIN="your-domain.example.com"
docker compose up --build -d
```

Dockerfile 使用多阶段构建：先构建 React，再安装 Python 后端和 ffmpeg；`.env` 不复制进镜像，上传目录和 SQLite 走 volume。Caddy 负责 HTTPS、请求体大小限制和安全响应头。

## ffmpeg

音频、视频验证和转码依赖 `ffmpeg` / `ffprobe`。检查：

```powershell
ffmpeg -version
ffprobe -version
```

缺失时接口会返回 `ffmpeg_not_found`，不会伪装成功。

如果 Windows PATH 没被后端进程继承，可以在 `.env` 显式填写：

```env
FFMPEG_PATH=C:\path\to\ffmpeg.exe
FFPROBE_PATH=C:\path\to\ffprobe.exe
```

## 隐私与安全

- 首页和多模态页显示非医疗诊断声明。
- 公网模式使用后端访问码验证，成功后颁发 HttpOnly cookie。
- `/docs` 和 `/redoc` 在 `public_demo`、`production` 默认关闭。
- 限流覆盖聊天、上传、任务和访问码接口。
- 上传文件使用 UUID 文件名，限制大小、类型、视频时长和单会话附件数。
- 默认 `UPLOAD_RETENTION_HOURS=24`，启动和定时任务会清理过期文件。
- 用户可在多模态页面删除当前会话数据。
- 不在浏览器 localStorage 保存访问码或模型 token。
- high risk 危机转介不依赖豆包额度。
- 自杀、轻生、自伤、伤害他人等调试词会触发 `high + crisis_referral`；否定语境和转述语境会分别降为低风险或中风险确认。

## 真实 API 测试

```powershell
python scripts\test_ark_text.py
python scripts\test_ark_image.py path\to\image.jpg
python scripts\test_doubao_asr.py path\to\audio.wav
python scripts\test_ark_video.py path\to\video.mp4
python scripts\test_multimodal_flow.py
```

烟测：

```powershell
python scripts\smoke_test_public.py
python scripts\smoke_test_multimodal.py
python scripts\smoke_test_safety.py
python scripts\check_secrets.py
```

## 常见错误

- `ark_provider_not_configured`：未设置 `ARK_API_KEY`。
- `speech_provider_not_configured`：未设置豆包语音凭证。
- `provider_unauthorized`：Key 错误或无效。
- `provider_forbidden`：账号没有模型或接口权限。
- `model_not_available`：模型 ID / Endpoint ID 不存在或未开通。
- `rate_limited`：请求过快或供应商限流。
- `quota_exceeded`：额度或余额不足。
- `provider_timeout`：供应商超时。
- `ffmpeg_not_found`：本机缺少 ffmpeg/ffprobe。

## 验收命令

```powershell
python -m pytest backend\tests -q
cd frontend
npm run build
npm audit
```

## Multi-Conversation Chat

聊天页已升级为类似现代 AI Chat 的多会话结构：左侧显示历史对话，右侧显示当前对话消息流和输入区。当前业务层统一使用 `Conversation`，为了兼容已有 Memory、Risk、Attachment、RAG 日志和上传目录：

```text
conversation_id == session_id
```

核心数据结构：

- `conversation`：`id/title/owner_id/created_at/updated_at/last_message_at/is_archived/title_manually_set`。
- `chat_message`：`message_id/conversation_id/session_id/role/content/sequence/message_type/attachments_json/metadata_json/created_at`。
- `attachment`：继续保留 `session_id`，新增 `conversation_id/message_id`，用于把图片、音频、视频归属到具体对话和消息。

核心 API：

```text
POST   /api/conversations
GET    /api/conversations
GET    /api/conversations/{conversation_id}
GET    /api/conversations/{conversation_id}/messages
PATCH  /api/conversations/{conversation_id}
DELETE /api/conversations/{conversation_id}
POST   /api/conversations/{conversation_id}/messages
```

前端只把 `lastConversationId`、浏览器 owner id 和打卡偏好保存在 `localStorage`，完整聊天历史以 SQLite 为准。刷新 `/chat/{conversation_id}` 时会重新从后端加载该对话，不会重新调用豆包，也不会重复生成 assistant message。

隔离策略：

- Message、Memory、Summary、Risk、Attachment、Intervention、Retrieval log 都按当前 `conversation_id/session_id` 查询。
- 默认 `GLOBAL_MEMORY_ACROSS_CONVERSATIONS=false`，不同对话不共享长期记忆。
- 删除对话会清理该对话的消息、附件文件、Memory、Summary、Risk、Intervention、检索日志和请求指标。

数据库迁移：

```powershell
python scripts\migrate_conversations.py
```

脚本会先备份 `backend/database/psych_ai.sqlite`，再做幂等 schema 更新，并把旧 session 数据登记为 legacy conversation。不会删除旧聊天数据。

## CARE-Psy Phase 0-3：评测、RAG、记忆和竞赛导出

本阶段新增系统审计文档、固定评测集、知识库导入、混合检索、情绪感知检索、分层记忆、多模态证据解释、风险维度、干预闭环和竞赛材料导出。消融实验本轮按需求不运行。

知识库目录：

```text
backend/data/knowledge_base/
├── manifests/
├── raw/
├── knowledge/
│   ├── stress/
│   ├── anxiety/
│   ├── sleep/
│   ├── loneliness/
│   ├── emotion_regulation/
│   └── interpersonal/
├── interventions/
├── campus/
├── safety/
├── cases/
├── processed/
└── indexes/
```

把 `.md`、`.txt`、`.docx`、`.pdf` 或 `.json` 放入 `raw/` 或上面的分类目录，在 `manifests/*.jsonl` 填写 `source_id/title/topic/evidence_level/file_path` 等 metadata 后运行。建议补充 `reviewed/usage_note/emotion/cause/strategy/risk_level/intervention`，用于情绪感知检索和证据展示：

```powershell
python scripts\build_knowledge_base.py
python scripts\inspect_knowledge_base.py
python scripts\test_rag_query.py --query "论文压力让我睡不着怎么办" --mode emotion_aware_hybrid_rerank --emotion anxiety --cause academic_stress --strategy task_breakdown --risk-level low
```

当前默认 `EMBEDDING_PROVIDER=local` 使用确定性的本地哈希向量，单位是中文字符数近似，不是随机向量。向量结果、BM25/SQLite FTS 关键词结果和心理元数据会合并重排序；若相关度低于 `RAG_MIN_RELEVANCE_SCORE`，系统返回“知识库暂未检索到高度相关资料”，不会伪造来源。目录名保留 `CHROMA_PERSIST_DIR` 配置，后续安装并接入 ChromaDB provider 时可以替换当前本地向量后端。

记忆采用四层上下文：最近消息、滚动摘要、结构化用户偏好、安全关键状态。用户可在多模态页查看、关闭、重建和删除当前 session 的记忆。风险状态独立保存，不进入普通知识库索引。

评测与导出：

```powershell
python scripts\run_evaluation.py
python scripts\export_competition_results.py
python scripts\check_private_files.py
```

`run_evaluation.py` 会输出 emotion、cause、strategy、risk、safety_redteam、RAG、memory、latency 和 baseline 脚手架指标。`run_ablation.py` 保留在仓库中，但本轮按需求不运行、不报告未运行数值。

评测结果写入 `evaluation/results/<timestamp>/`，竞赛材料写入 `competition_results/`。这些目录已被 `.gitignore` 忽略，不应提交真实用户数据、上传文件、数据库、日志、API Key 或公网 token。

本项目不构成医疗建议。遇到即时危险，请联系身边可信任的人、学校辅导员、当地紧急服务或已审核的危机支持资源。

## RAG Knowledge Base V1

RAG V1 最初作为离线知识库基础设施构建；当前版本已经通过 `RAGRouter` 接入 `/api/chat`、`/api/chat/multimodal` 和多会话聊天。高危安全场景仍跳过普通 RAG。

唯一允许自动下载的来源清单是：

```text
backend/data/knowledge_base/sources/knowledge_sources_v1.yaml
```

Codex 和脚本禁止自动搜索、扩展、替换、绕过登录、绕过 CAPTCHA、绕过付费墙或下载未列入 registry 的心理资料。自动下载只处理 `enabled=true` 且 `auto_download=true` 的条目，并且 redirect 后最终域名仍必须属于该 source 的 `allowed_domains`。

目录结构：

```text
backend/data/knowledge_base/
├── sources/knowledge_sources_v1.yaml
├── raw/
│   ├── auto/
│   └── manual/
│       ├── textbooks/
│       ├── papers/
│       ├── campus/
│       └── cases/
├── parsed/
├── cleaned/
├── chunks/
│   ├── pending/
│   ├── approved/
│   └── rejected/
├── indexes/
│   ├── chroma/
│   └── bm25/
└── reports/
```

手动资料放置规则：

- 合法获得的教材章节放入 `backend/data/knowledge_base/raw/manual/textbooks/`
- 合法获得的论文/指南放入 `backend/data/knowledge_base/raw/manual/papers/`
- 校园心理中心、自建校园支持卡片放入 `backend/data/knowledge_base/raw/manual/campus/`
- 案例/对话数据以后放入 `backend/data/knowledge_base/raw/manual/cases/`，本阶段只保留目录，不进入 Knowledge RAG

运行：

```powershell
python scripts\rag\download_sources.py --registry backend\data\knowledge_base\sources\knowledge_sources_v1.yaml
python scripts\rag\build_knowledge_base.py --registry backend\data\knowledge_base\sources\knowledge_sources_v1.yaml
python scripts\rag\test_retrieval.py --query "论文一直拖延，迟迟无法开始怎么办？"
```

构建产物：

- `reports/download_manifest.jsonl`：每个下载文件的 URL、状态、SHA256、大小和 MIME
- `reports/download_summary.json`：下载汇总
- `reports/chunk_review.csv`：全量人工审核表
- `reports/chunk_review_sample.csv`：抽样审核表
- `reports/build_report.json` 与 `reports/rag_v1_build_report.md`：构建报告
- `indexes/chroma/`：Chroma staging collections
- `indexes/bm25/`：BM25 离线索引

默认所有机器解析 chunk 都是 `review_status=pending`。本阶段建立的是 staging index，便于开发测试；正式 production collection 以后只能使用人工审核为 `approved` 的 chunk。

Embedding 配置：

```env
RAG_EMBEDDING_PROVIDER=local
RAG_EMBEDDING_MODEL=BAAI/bge-m3
RAG_EMBEDDING_CACHE_DIR=./data/knowledge_base/models
```

RAG V1 不使用哈希向量冒充真实 embedding。如果 `sentence-transformers` 或 BGE-M3 模型无法下载/加载，脚本会报告 `embedding_model_download_failed`，但会保留已经完成的 download、parse、clean 和 chunk 结果。

## CARE-Psy Knowledge Base V2

V2 是在现有 RAG 基础设施上的资料治理升级，不是第二套向量库。默认 Registry 已切换为：

```text
backend/data/knowledge_base/sources/knowledge_sources.yaml
```

V2 来源优先来自 WHO、UNICEF、CCI、NHS、NIMH、NIA、SAMHSA、VA、NICE、中国国家卫健委和教育部等官方或高可信机构。来源先进入候选清单，再按 authority、evidence、relevance、legal usability、freshness、non-redundancy 评分；不会自动使用博客、论坛、营销号、盗版教材、付费论文或评测/训练数据。

关键治理字段：

- `population_tags`：儿童、青少年、大学生、职场人、孕产妇、父母、照护者、老年人、创伤/丧失人群等。
- `topic_tags`：压力、焦虑、睡眠、拖延、完美主义、人际、亲子、职场、求职、哀伤、创伤、疾病科普、安全等。
- `use_mode`：`direct_user_support`、`psychoeducation_only`、`helping_skills_only`、`agent_policy_only`、`safety_only`、`evidence_only`、`clinical_reference_only`。
- `risk_scope`：普通检索只允许 `normal/general`；自伤/自杀/危机资料只能走 `safety_route_only`。
- `clinical_only`：临床指南和证据资料不能作为普通自助建议。

普通聊天 RAG 只会使用：

```text
user_facing=true
clinical_only=false
use_mode=direct_user_support
risk_scope=normal/general
```

用户询问“我是不是抑郁症/强迫症/双相/PTSD”等问题时，`RAGRouter` 会改走 `psychoeducation_only`，用于一般科普和求助边界，不做诊断。高危表达仍由 `RiskAgent -> SafetyAgent` 处理，不走普通相似度检索。

V2 常用命令：

```powershell
python scripts\rag\discover_sources.py
python scripts\rag\select_sources.py
python scripts\rag\download_sources.py --limit 10 --timeout 12
python scripts\rag\build_knowledge_base.py --mode staging --sample-mode --sample-limit 1024
python scripts\rag\health_check.py
python scripts\rag\generate_rag_v2_eval_dataset.py
python scripts\rag\run_retrieval_benchmark.py --limit 40 --top-k 5 --mode staging
python scripts\rag\generate_kb_v2_reports.py
```

V2 主要报告：

- `docs/knowledge_base_v2_prebuild_audit.md`
- `docs/knowledge_base_v2_completion_report.md`
- `backend/data/knowledge_base/reports/source_candidates.csv`
- `backend/data/knowledge_base/reports/knowledge_coverage_v2.md`
- `backend/data/knowledge_base/reports/review_safety.csv`
- `backend/data/knowledge_base/reports/review_children.csv`
- `backend/data/knowledge_base/reports/review_interventions.csv`
- `backend/data/knowledge_base/reports/review_chinese.csv`

当前 V2 是 staging-ready，不是 production-ready。原因是自动解析的 chunk 默认全部为 `pending`，需要人工审核后才能进入 production index。

## Agent V2：Psychological State + Strategy Planner + RAG Router

正式聊天链路已升级为：

```text
User / MultimodalProcessor
-> RiskAgent
-> high risk: SafetyAgent crisis referral
-> PsychologicalStateAnalyzer
-> StrategyPlanner
-> RAGRouter
-> RAG V1
-> CounselorAgent
-> SafetyAgent
```

核心输出：

- `psychological_state`：情绪、原因、需求、对话阶段、置信度和待澄清信息。
- `strategy_plan`：主策略、辅助策略、是否给建议、是否提问、是否使用 RAG。
- `rag_route`：是否检索、检索 collection、检索 query、metadata filter 和跳过原因。

前端聊天页的“查看分析过程”会展示以上三个模块。高危表达仍然优先进入危机转介，不走普通 RAG。当前 RAG V1 chunk 多数仍是 `pending`，因此开发演示默认 `RAG_STAGING_MODE=true`；正式部署前应完成资料人工审核并改为 `false`。
