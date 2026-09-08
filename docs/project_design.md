# 项目设计

## 项目定位

AI 心理陪伴 Web 系统面向大学生轻中度情绪困扰场景，提供文字化陪伴、自助调节建议和基础风险识别。系统强调安全边界：不做医学诊断，不提供药物建议，不承诺治疗效果。

## 第一阶段范围

第一阶段实现纯文字版最小可运行闭环：

- 用户填写压力评分、压力来源和倾诉偏好。
- 用户在 Chat 页面输入文字。
- 前端调用后端 `/api/chat`。
- 后端通过串行 Agent 流程生成结构化 JSON。
- 前端展示回复、情绪、风险、干预和 Agent Trace。

## 页面设计

- Home：介绍项目定位和安全声明。
- CheckIn：采集压力评分、压力来源、倾诉偏好，保存到 localStorage。
- Chat：完成核心对话演示。
- Relaxation：提供呼吸练习卡片。
- Report：展示 mock 压力趋势。
- VideoCompanion：预留摄像头表情识别入口。

## 安全策略

系统优先执行 RiskAgent。当检测到自伤、自杀、伤害他人等高危表达时，CoordinatorAgent 会跳过普通 CounselorAgent，直接返回危机转介模板。SafetyAgent 会再次检查 high risk 回复，确保没有继续普通疏导。
