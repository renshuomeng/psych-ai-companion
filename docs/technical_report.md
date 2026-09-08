# 技术报告

## 架构概览

项目采用前后端分离结构：

- `frontend`：React + Vite + TypeScript 单页应用。
- `backend`：FastAPI 服务，提供结构化 API。
- `evaluation`：安全与普通场景测试样例。
- `docs`：设计、技术和演示说明。

## 后端 Agent 流程

`CoordinatorAgent` 串行调用以下模块：

1. `EmotionAgent`：基于关键词和打卡信息识别情绪标签与强度。
2. `RiskAgent`：基于关键词判断 low、medium、high。
3. `InterventionAgent`：根据情绪推荐 1-3 个自助干预。
4. `CounselorAgent`：低中风险时生成模板化共情回复。
5. `SafetyAgent`：检查诊断、药物建议、治疗承诺和 high risk 普通聊天等问题。

## API

### GET `/api/health`

返回服务状态。

### POST `/api/chat`

接收用户文本、打卡信息和可选表情识别结果，返回：

- `emotion`
- `risk`
- `reply`
- `interventions`
- `agent_trace`

### GET `/api/report`

返回最近 7 次 mock 压力评分和情绪趋势。

### GET/POST `/api/stt`

第一阶段占位，返回未实现说明。

## 大模型接入

`backend/services/llm_service.py` 中实现 `generate_text(prompt: str)`，通过 `.env` 的 `LLM_PROVIDER` 切换：

- `mock`：默认模式，不调用真实模型。
- `ollama`：请求本地 Ollama `/api/generate`。
- `qwen`：请求兼容 OpenAI 格式的 Qwen `/chat/completions`。

`CounselorAgent` 仅在 low/medium risk 流程中调用大模型。模型调用失败时会回退到模板回复；high risk 流程仍由 `RiskAgent` 和 `SafetyAgent` 强制危机转介。
