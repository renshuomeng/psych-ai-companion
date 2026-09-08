import { useEffect, useState } from "react";

import {
  ApiError,
  getDebugAgent,
  getDebugRag,
  getKnowledgeStatus,
  runRetrievalDebug,
  type KnowledgeStatusResponse,
} from "../api/client";

function readableError(err: unknown): string {
  if (err instanceof ApiError) return err.detail.message;
  return err instanceof Error ? err.message : "开发调试接口失败。";
}

export default function DeveloperDashboard({ onOpenEvaluation }: { onOpenEvaluation: () => void }) {
  const [knowledge, setKnowledge] = useState<KnowledgeStatusResponse | null>(null);
  const [agent, setAgent] = useState<Record<string, unknown> | null>(null);
  const [rag, setRag] = useState<Record<string, unknown> | null>(null);
  const [query, setQuery] = useState("论文压力 睡不着 怎么办");
  const [retrieval, setRetrieval] = useState<Record<string, unknown> | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    setMessage("");
    try {
      const [knowledgeResponse, agentResponse, ragResponse] = await Promise.all([
        getKnowledgeStatus(),
        getDebugAgent(),
        getDebugRag(),
      ]);
      setKnowledge(knowledgeResponse);
      setAgent(agentResponse);
      setRag(ragResponse);
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function runRetrieval() {
    if (!query.trim()) return;
    setLoading(true);
    setMessage("");
    try {
      setRetrieval(await runRetrievalDebug(query.trim()));
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-stack developer-page">
      <div className="section-heading wide-heading">
        <span className="eyebrow">Developer Mode</span>
        <h1>Developer Dashboard</h1>
        <p>调试 Evaluation、RAG、Agent Trace 和实验配置。Production KB 发布仍由 Admin 控制。</p>
      </div>

      {message && <div className="error-banner">{message}</div>}

      <section className="status-grid">
        <article className="status-card">
          <span>KB Sources</span>
          <strong>{knowledge?.source_count ?? 0}</strong>
        </article>
        <article className="status-card">
          <span>KB Chunks</span>
          <strong>{knowledge?.chunk_count ?? 0}</strong>
        </article>
        <article className="status-card">
          <span>Agent V2</span>
          <strong>{String(agent?.agent_v2_enabled ?? "")}</strong>
        </article>
        <article className="status-card">
          <span>RAG Mode</span>
          <strong>{String(rag?.index_mode ?? "")}</strong>
        </article>
      </section>

      <section className="review-layout">
        <section className="result-card">
          <div className="panel-title-row">
            <div>
              <h2>Evaluation</h2>
              <p>运行 smoke/full evaluation、对比 run、执行 no-RAG/no-strategy/no-psych-state ablation。</p>
            </div>
            <button disabled={loading} onClick={onOpenEvaluation} type="button">
              打开 Evaluation Center
            </button>
          </div>
        </section>

        <section className="result-card">
          <h2>Retrieval Debug</h2>
          <div className="debug-query-row">
            <input onChange={(event) => setQuery(event.target.value)} value={query} />
            <button disabled={loading} onClick={runRetrieval} type="button">
              Run
            </button>
          </div>
          {retrieval && <pre>{JSON.stringify(retrieval, null, 2)}</pre>}
        </section>
      </section>

      <section className="review-layout">
        <section className="result-card">
          <h2>Agent Debug</h2>
          <pre>{JSON.stringify(agent, null, 2)}</pre>
        </section>
        <section className="result-card">
          <h2>RAG Debug</h2>
          <pre>{JSON.stringify(rag, null, 2)}</pre>
        </section>
      </section>

      <button className="primary-button" disabled={loading} onClick={refresh} type="button">
        {loading ? "刷新中..." : "刷新状态"}
      </button>
    </section>
  );
}
