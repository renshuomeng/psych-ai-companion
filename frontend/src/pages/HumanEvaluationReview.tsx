import { useEffect, useState } from "react";

import {
  ApiError,
  exportHumanEvaluationCsv,
  listHumanEvaluationCases,
  scoreHumanEvaluationCase,
  type HumanEvaluationCase,
} from "../api/client";

function readableError(err: unknown): string {
  if (err instanceof ApiError) return err.detail.message;
  return err instanceof Error ? err.message : "人工评测操作失败。";
}

export default function HumanEvaluationReview() {
  const [runId, setRunId] = useState("");
  const [cases, setCases] = useState<HumanEvaluationCase[]>([]);
  const [scoreByCase, setScoreByCase] = useState<Record<string, number>>({});
  const [commentByCase, setCommentByCase] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    setMessage("");
    try {
      const response = await listHumanEvaluationCases(runId || undefined);
      setRunId(response.run_id || runId);
      setCases(response.items);
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function save(caseId: string) {
    setLoading(true);
    setMessage("");
    try {
      await scoreHumanEvaluationCase({
        run_id: runId,
        case_id: caseId,
        score: scoreByCase[caseId] ?? null,
        comment: commentByCase[caseId] || "",
        llm_judge_reviewed: true,
      });
      setMessage(`已保存人工复核：${caseId}`);
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  async function exportCsv() {
    setLoading(true);
    try {
      const csv = await exportHumanEvaluationCsv();
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "care_psy_human_evaluation_review.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-stack human-eval-page">
      <div className="section-heading wide-heading">
        <span className="eyebrow">Reviewer Mode</span>
        <h1>Human Evaluation</h1>
        <p>复核 LLM Judge 结果并记录人工评分。这里使用评测数据，不浏览普通用户私人对话。</p>
      </div>

      {message && <div className={message.includes("失败") || message.includes("无权") ? "error-banner" : "notice-band"}>{message}</div>}

      <section className="review-toolbar">
        <label>
          <span>Run ID</span>
          <input onChange={(event) => setRunId(event.target.value)} placeholder="留空使用最新 run" value={runId} />
        </label>
        <button className="primary-button" disabled={loading} onClick={refresh} type="button">
          加载
        </button>
        <button disabled={loading} onClick={exportCsv} type="button">
          导出 CSV
        </button>
      </section>

      <section className="case-list">
        {cases.map((item) => (
          <article key={item.case_id}>
            <div>
              <strong>{item.case_id}</strong>
              <span>{item.case.tags?.join(" / ")}</span>
            </div>
            <p>{item.candidate.response || "无候选回复"}</p>
            <div className="human-score-row">
              <label>
                <span>Score</span>
                <input
                  max={10}
                  min={0}
                  onChange={(event) => setScoreByCase((current) => ({ ...current, [item.case_id]: Number(event.target.value) }))}
                  type="number"
                  value={scoreByCase[item.case_id] ?? ""}
                />
              </label>
              <label>
                <span>Comment</span>
                <input
                  onChange={(event) => setCommentByCase((current) => ({ ...current, [item.case_id]: event.target.value }))}
                  value={commentByCase[item.case_id] ?? ""}
                />
              </label>
              <button disabled={loading} onClick={() => save(item.case_id)} type="button">
                保存复核
              </button>
            </div>
          </article>
        ))}
        {!cases.length && <section className="placeholder-panel">暂无可复核 case。先由 Developer 运行一次 Evaluation。</section>}
      </section>
    </section>
  );
}
