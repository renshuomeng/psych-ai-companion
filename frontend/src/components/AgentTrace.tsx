import type { AgentTraceItem } from "../types/api";

type AgentTraceProps = {
  trace: AgentTraceItem[];
};

export default function AgentTrace({ trace }: AgentTraceProps) {
  return (
    <section className="result-card">
      <h3>Agent Trace</h3>
      {trace.length === 0 ? (
        <p className="muted">这里会显示多 Agent 串行流程。</p>
      ) : (
        <ol className="trace-list">
          {trace.map((item, index) => (
            <li key={`${typeof item === "string" ? item : item.agent}-${index}`}>
              {typeof item === "string" ? (
                item
              ) : (
                <>
                  <strong>{item.agent}</strong> [{item.status}]：{item.summary}
                </>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
