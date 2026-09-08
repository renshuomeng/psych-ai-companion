import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  decideKnowledgeChunk,
  decideKnowledgeSource,
  listKnowledgeChunks,
  listKnowledgeSources,
  type KnowledgeReviewChunk,
  type KnowledgeReviewSource,
} from "../api/client";

type Queue = "all" | "safety" | "intervention";

function readableError(err: unknown): string {
  if (err instanceof ApiError) return err.detail.message;
  return err instanceof Error ? err.message : "知识审核操作失败。";
}

export default function KnowledgeReview() {
  const [sources, setSources] = useState<KnowledgeReviewSource[]>([]);
  const [chunks, setChunks] = useState<KnowledgeReviewChunk[]>([]);
  const [queue, setQueue] = useState<Queue>("safety");
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [comment, setComment] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const visibleSources = useMemo(
    () => sources.filter((item) => !selectedSourceId || item.source_id === selectedSourceId),
    [selectedSourceId, sources],
  );

  async function refresh(nextQueue = queue) {
    setLoading(true);
    setMessage("");
    try {
      const [sourceResponse, chunkResponse] = await Promise.all([
        listKnowledgeSources(),
        listKnowledgeChunks({ status: "pending", queue: nextQueue }),
      ]);
      setSources(sourceResponse.items);
      setChunks(chunkResponse.items);
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function sourceAction(sourceId: string, decision: "approve" | "reject" | "flag") {
    setLoading(true);
    setMessage("");
    try {
      await decideKnowledgeSource(sourceId, decision, { comment, reason: comment });
      setComment("");
      await refresh();
      setMessage(`Source ${decision}: ${sourceId}`);
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  async function chunkAction(chunkId: string, decision: "approve" | "reject") {
    setLoading(true);
    setMessage("");
    try {
      await decideKnowledgeChunk(chunkId, decision, { comment, reason: comment });
      setComment("");
      await refresh();
      setMessage(`Chunk ${decision}: ${chunkId}`);
    } catch (err) {
      setMessage(readableError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-stack review-page">
      <div className="section-heading wide-heading">
        <span className="eyebrow">Reviewer Mode</span>
        <h1>Knowledge Review</h1>
        <p>审核知识来源和 pending chunks。审核记录会写入后端 audit log，不记录心理聊天正文。</p>
      </div>

      {message && <div className={message.includes("失败") || message.includes("无权") ? "error-banner" : "notice-band"}>{message}</div>}

      <section className="review-toolbar">
        <label>
          <span>队列</span>
          <select
            onChange={(event) => {
              const next = event.target.value as Queue;
              setQueue(next);
              void refresh(next);
            }}
            value={queue}
          >
            <option value="safety">Safety Priority</option>
            <option value="intervention">Intervention Review</option>
            <option value="all">All Pending</option>
          </select>
        </label>
        <label>
          <span>Source</span>
          <select onChange={(event) => setSelectedSourceId(event.target.value)} value={selectedSourceId}>
            <option value="">全部来源</option>
            {sources.map((source) => (
              <option key={source.source_id} value={source.source_id}>
                {source.source_id}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Comment</span>
          <input onChange={(event) => setComment(event.target.value)} placeholder="审核意见" value={comment} />
        </label>
        <button className="primary-button" disabled={loading} onClick={() => refresh()} type="button">
          {loading ? "刷新中..." : "刷新"}
        </button>
      </section>

      <section className="review-layout">
        <div className="review-column">
          <section className="result-card">
            <h2>Knowledge Sources</h2>
            <div className="compact-table">
              {visibleSources.slice(0, 20).map((source) => (
                <article key={source.source_id}>
                  <div>
                    <strong>{source.title}</strong>
                    <span>{source.organization}</span>
                  </div>
                  <small>
                    {source.source_id} · {source.review_priority || "P2"} · pending chunks {source.pending_chunks}
                  </small>
                  <div className="compact-actions">
                    <button disabled={loading} onClick={() => sourceAction(source.source_id, "approve")} type="button">
                      Approve
                    </button>
                    <button disabled={loading} onClick={() => sourceAction(source.source_id, "reject")} type="button">
                      Reject
                    </button>
                    <button disabled={loading} onClick={() => sourceAction(source.source_id, "flag")} type="button">
                      Flag
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>

        <div className="review-column">
          <section className="result-card">
            <h2>Pending Chunks</h2>
            <div className="compact-table">
              {chunks.map((chunk) => (
                <article key={chunk.chunk_id}>
                  <div>
                    <strong>{chunk.title}</strong>
                    <span>{chunk.review_priority || "P2"} · {chunk.target_collection}</span>
                  </div>
                  <small>{chunk.chunk_id} · {chunk.source_id}</small>
                  <p>{chunk.content_preview}</p>
                  <div className="compact-actions">
                    <button disabled={loading} onClick={() => chunkAction(chunk.chunk_id, "approve")} type="button">
                      Approve
                    </button>
                    <button disabled={loading} onClick={() => chunkAction(chunk.chunk_id, "reject")} type="button">
                      Reject
                    </button>
                  </div>
                </article>
              ))}
              {!chunks.length && <p className="muted">当前队列没有 pending chunk。</p>}
            </div>
          </section>
        </div>
      </section>
    </section>
  );
}
