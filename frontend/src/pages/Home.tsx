import { useEffect, useState } from "react";

import { getHealth } from "../api/client";

type HomeProps = {
  onStart: () => void;
};

export default function Home({ onStart }: HomeProps) {
  const [dependencies, setDependencies] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    void getHealth()
      .then((result) => setDependencies(result.dependencies ?? null))
      .catch(() => setDependencies(null));
  }, []);

  return (
    <section className="page-stack">
      <div className="hero-panel">
        <div>
          <span className="eyebrow">竞赛项目第一阶段</span>
          <h1>AI 心理陪伴 Web 系统</h1>
          <p>
            面向大学生学习压力、就业焦虑、人际关系、睡眠困扰和孤独感等轻中度情绪场景，
            提供文字陪伴、情绪识别、风险分级和自助调节建议。
          </p>
          <div className="hero-actions">
            <button className="primary-button" onClick={onStart} type="button">
              进入情绪打卡
            </button>
          </div>
        </div>
        <div className="signal-panel" aria-label="系统能力概览">
          <div>
            <strong>Emotion</strong>
            <span>规则识别</span>
          </div>
          <div>
            <strong>Risk</strong>
            <span>高危拦截</span>
          </div>
          <div>
            <strong>Trace</strong>
            <span>Agent 流程</span>
          </div>
        </div>
      </div>

      <section className="notice-band">
        <h2>安全声明</h2>
        <p>
          本系统不是 AI 心理医生，不做医学诊断，不提供药物建议，也不承诺治疗效果。
          遇到自伤、自杀或伤害他人的高危表达时，系统会停止普通疏导并触发危机转介提示。
        </p>
      </section>

      <section className="status-grid" aria-label="系统连接状态">
        {([
          ["豆包文字", dependencies?.ark_configured],
          ["豆包语音", dependencies?.speech_configured],
          ["ffmpeg", dependencies?.ffmpeg],
          ["ffprobe", dependencies?.ffprobe],
        ] as Array<[string, unknown]>).map(([label, value]) => (
          <div className="status-card" key={String(label)}>
            <strong>{label}</strong>
            <span className={value === true || value === "ok" ? "status-ok" : "status-warn"}>
              {value === true || value === "ok" ? "可用" : "待配置"}
            </span>
          </div>
        ))}
      </section>
    </section>
  );
}
