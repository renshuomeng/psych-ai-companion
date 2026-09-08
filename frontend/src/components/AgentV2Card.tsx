import type { PsychologicalState, RAGRoute, StrategyPlan } from "../types/api";

type Props = {
  psychologicalState?: PsychologicalState | null;
  strategyPlan?: StrategyPlan | null;
  ragRoute?: RAGRoute | null;
};

function percent(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) return "未知";
  return `${Math.round(value * 100)}%`;
}

function join(items?: string[]) {
  return items && items.length > 0 ? items.join("、") : "暂无";
}

export default function AgentV2Card({ psychologicalState, strategyPlan, ragRoute }: Props) {
  return (
    <section className="result-card agent-v2-card">
      <h3>心理状态与策略</h3>
      {!psychologicalState ? (
        <p className="muted">暂无 Agent V2 分析结果。</p>
      ) : (
        <div className="agent-v2-stack">
          <div className="agent-v2-block">
            <div className="metric-row">
              <span className="pill neutral">{psychologicalState.emotion?.primary ?? "unknown"}</span>
              <strong>{percent(psychologicalState.confidence)}</strong>
            </div>
            <p>
              <strong>原因</strong>：{psychologicalState.cause?.category ?? "unknown"}
              {psychologicalState.cause?.specific ? ` · ${psychologicalState.cause.specific}` : ""}
            </p>
            <p>
              <strong>阶段</strong>：{psychologicalState.stage ?? "unknown"} · <strong>需求</strong>：
              {join(psychologicalState.needs)}
            </p>
            {psychologicalState.information_gaps && psychologicalState.information_gaps.length > 0 && (
              <p className="muted">待澄清：{join(psychologicalState.information_gaps)}</p>
            )}
          </div>

          <div className="agent-v2-block">
            <p>
              <strong>主策略</strong>：{strategyPlan?.primary_strategy ?? "supportive_presence"}
            </p>
            <p>
              <strong>辅助策略</strong>：{join(strategyPlan?.secondary_strategy)}
            </p>
            <p>
              <strong>建议</strong>：{strategyPlan?.should_give_advice ? "给出低负担建议" : "先倾听/澄清"} ·{" "}
              <strong>提问</strong>：{strategyPlan?.should_ask_question ? "是" : "否"}
            </p>
          </div>

          <div className="agent-v2-block">
            <p>
              <strong>RAG 路由</strong>：{ragRoute?.should_retrieve ? "检索知识库" : "本轮不检索"}
            </p>
            <p>
              <strong>范围</strong>：{join(ragRoute?.collections)}
            </p>
            <p className="muted">原因：{join(ragRoute?.reason_codes)}</p>
          </div>
        </div>
      )}
    </section>
  );
}
