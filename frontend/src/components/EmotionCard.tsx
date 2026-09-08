import type { Emotion } from "../api/client";

type EmotionCardProps = {
  emotion: Emotion | null;
};

const DIMENSION_LABELS = {
  valence: "效价",
  arousal: "激活",
  control: "控制感",
  intensity: "强度",
};

const LEVEL_LABELS: Record<string, string> = {
  positive: "偏正面",
  negative: "偏负面",
  neutral: "中性",
  high: "高",
  medium: "中",
  low: "低",
};

function dimensionPercent(name: keyof typeof DIMENSION_LABELS, score: number) {
  if (name === "valence") {
    return Math.round(((score + 1) / 2) * 100);
  }
  return Math.round(score * 100);
}

export default function EmotionCard({ emotion }: EmotionCardProps) {
  if (!emotion) {
    return (
      <section className="result-card">
        <h3>情绪识别</h3>
        <p className="muted">发送一条消息后，这里会展示规则识别结果。</p>
      </section>
    );
  }

  return (
    <section className="result-card">
      <h3>情绪识别</h3>
      <div className="metric-row">
        <span className="pill neutral">{emotion.label}</span>
        <strong>{Math.round(emotion.intensity * 100)}%</strong>
      </div>
      <div className="progress-track" aria-label="情绪强度">
        <span
          className="progress-bar"
          style={{ width: `${Math.round(emotion.intensity * 100)}%` }}
        />
      </div>
      {emotion.dimensions && (
        <div className="dimension-stack">
          {(Object.keys(DIMENSION_LABELS) as Array<keyof typeof DIMENSION_LABELS>).map((name) => {
            const item = emotion.dimensions![name];
            const percent = dimensionPercent(name, item.score);
            return (
              <div className="dimension-row" key={name}>
                <div>
                  <strong>{DIMENSION_LABELS[name]}</strong>
                  <span>{LEVEL_LABELS[item.label] ?? item.label}</span>
                </div>
                <div className="progress-track" aria-label={DIMENSION_LABELS[name]}>
                  <span className="progress-bar" style={{ width: `${percent}%` }} />
                </div>
                <small>{name === "valence" ? item.score.toFixed(2) : `${Math.round(item.score * 100)}%`}</small>
              </div>
            );
          })}
        </div>
      )}
      {Array.isArray(emotion.evidence) ? (
        <ul className="compact-list">
          {emotion.evidence.map((item, index) => (
            <li key={`${item.source}-${index}`}>
              <strong>{item.source}</strong>：{item.content}
            </li>
          ))}
        </ul>
      ) : (
        <p>{emotion.evidence}</p>
      )}
    </section>
  );
}
