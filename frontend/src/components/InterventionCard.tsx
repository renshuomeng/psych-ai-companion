import { useState } from "react";

import {
  completeIntervention,
  sendInterventionFeedback,
  startIntervention,
  type Intervention,
} from "../api/client";

type InterventionCardProps = {
  interventions: Intervention[];
  sessionId?: string;
};

export default function InterventionCard({
  interventions,
  sessionId,
}: InterventionCardProps) {
  const [active, setActive] = useState<Record<string, string>>({});

  async function start(item: Intervention) {
    if (!item.intervention_id || !sessionId) return;
    await startIntervention({
      intervention_id: item.intervention_id,
      session_id: sessionId,
      type: item.type,
      title: item.title,
    });
    setActive((state) => ({ ...state, [item.intervention_id!]: "started" }));
  }

  async function complete(item: Intervention) {
    if (!item.intervention_id) return;
    await completeIntervention(item.intervention_id, {});
    setActive((state) => ({ ...state, [item.intervention_id!]: "completed" }));
  }

  async function feedback(item: Intervention, helpfulness: number) {
    if (!item.intervention_id) return;
    await sendInterventionFeedback(item.intervention_id, { helpfulness });
    setActive((state) => ({ ...state, [item.intervention_id!]: `feedback:${helpfulness}` }));
  }

  return (
    <section className="result-card">
      <h3>干预推荐</h3>
      {interventions.length === 0 ? (
        <p className="muted">发送消息后会推荐 1-3 个自助调节动作。</p>
      ) : (
        <div className="intervention-list">
          {interventions.map((item) => (
            <article className="intervention-item" key={item.intervention_id ?? `${item.type}-${item.title}`}>
              <span className="mini-type">{item.type}</span>
              <h4>{item.title}</h4>
              <p>{item.description}</p>
              {item.reason && <small>{item.reason}</small>}
              {item.estimated_minutes && <small>预计 {item.estimated_minutes} 分钟</small>}
              {sessionId && item.intervention_id && (
                <div className="compact-actions">
                  <button onClick={() => void start(item)} type="button">开始</button>
                  <button onClick={() => void complete(item)} type="button">完成</button>
                  <button onClick={() => void feedback(item, 5)} type="button">有帮助</button>
                  {active[item.intervention_id] && <span>{active[item.intervention_id]}</span>}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
