import type { Risk } from "../api/client";

type RiskCardProps = {
  risk: Risk | null;
};

const RISK_LABELS = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
};

export default function RiskCard({ risk }: RiskCardProps) {
  if (!risk) {
    return (
      <section className="result-card">
        <h3>风险等级</h3>
        <p className="muted">系统会优先检查自伤、自杀或伤害他人的表达。</p>
      </section>
    );
  }

  return (
    <section className={`result-card risk-card risk-${risk.level}`}>
      <h3>风险等级</h3>
      <div className="metric-row">
        <span className={`pill risk-${risk.level}`}>{RISK_LABELS[risk.level]}</span>
        <strong>{risk.action}</strong>
      </div>
      <p>{risk.reason}</p>
      {risk.dimensions && (
        <ul className="compact-list">
          {Object.entries(risk.dimensions)
            .filter(([key]) => !key.startsWith("matched_"))
            .map(([key, value]) => (
              <li key={key}>
                <strong>{key}</strong>：{String(value)}
              </li>
            ))}
        </ul>
      )}
    </section>
  );
}
