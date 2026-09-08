import type { Emotion, EvidenceItem } from "../types/api";

type Props = {
  evidence: EvidenceItem[];
  emotion: Emotion | null;
};

export default function EvidencePanel({ evidence, emotion }: Props) {
  return (
    <section className="result-card">
      <h3>证据解释</h3>
      {evidence.length === 0 ? (
        <p className="muted">暂无统一证据对象。</p>
      ) : (
        <ul className="evidence-list">
          {evidence.slice(0, 6).map((item) => (
            <li key={item.evidence_id}>
              <div>
                <strong>{item.source}</strong>
                <span>{item.modality}</span>
              </div>
              <p>{item.observation}</p>
              <small>
                置信度 {Math.round(item.confidence * 100)}% ·{" "}
                {item.is_explicit_user_statement ? "用户明确信息" : "辅助观察"} ·{" "}
                {item.risk_relevant ? "风险相关" : "非风险触发"}
              </small>
            </li>
          ))}
        </ul>
      )}
      {emotion?.conflicting_evidence && emotion.conflicting_evidence.length > 0 && (
        <div className="soft-alert">
          <strong>冲突证据</strong>
          {emotion.conflicting_evidence.map((item, index) => (
            <p key={`${item.source}-${index}`}>{item.source}：{item.content}</p>
          ))}
        </div>
      )}
      {emotion?.uncertainty && <p className="muted">{emotion.uncertainty}</p>}
    </section>
  );
}
