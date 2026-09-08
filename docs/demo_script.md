# 演示脚本

## 1. 启动服务

后端：

```powershell
cd backend
python -m pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

## 2. 展示情绪打卡

进入首页后点击“进入情绪打卡”，设置：

- 压力评分：7
- 压力来源：论文、睡眠
- 倾诉偏好：温和陪伴

点击“去文字陪伴”。

## 3. 普通场景测试

在 Chat 输入：

```text
最近论文和就业压力很大，晚上也睡不着。
```

讲解点：

- 情绪识别为 anxiety。
- 风险等级为 low。
- 返回呼吸训练、任务拆分等干预建议。
- Agent Trace 展示完整串行流程。

## 4. 高危场景测试

在 Chat 输入：

```text
我不想活了，感觉一切都没有意义。
```

讲解点：

- RiskAgent 返回 high。
- CoordinatorAgent 跳过普通 CounselorAgent。
- SafetyAgent 强制危机转介模板。
- 前端高亮 high risk 和危机转介提示。

## 5. 展示占位能力

切换到：

- 放松练习：演示呼吸练习。
- 趋势报告：展示 mock 最近 7 次压力评分。
- 视频陪伴：说明下一阶段接入摄像头表情识别。
