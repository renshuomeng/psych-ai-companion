import type { MultimodalChatResponse } from "../types/api";

type Props = {
  metrics?: MultimodalChatResponse["request_metrics"];
};

export default function SystemMetricsCard({ metrics }: Props) {
  return (
    <section className="result-card">
      <h3>系统指标</h3>
      {!metrics ? (
        <p className="muted">暂无请求指标。</p>
      ) : (
        <div className="metrics-grid">
          <div>
            <strong>{metrics.total_duration_ms ?? 0} ms</strong>
            <span>总延迟</span>
          </div>
          <div>
            <strong>{String(metrics.estimated_cost?.calculation_status ?? "unknown")}</strong>
            <span>成本估算</span>
          </div>
          <div>
            <strong>{String(metrics.token_usage?.status ?? "recorded")}</strong>
            <span>Token</span>
          </div>
        </div>
      )}
    </section>
  );
}
