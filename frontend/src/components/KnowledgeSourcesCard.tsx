import type { KnowledgeSource } from "../types/api";

type Props = {
  sources: KnowledgeSource[];
  retrievalStatus?: string;
};

function sourceHref(source: KnowledgeSource): string {
  return source.official_page_url || source.downloaded_url || "";
}

export default function KnowledgeSourcesCard({ sources, retrievalStatus }: Props) {
  return (
    <section className="result-card">
      <h3>知识来源</h3>
      {retrievalStatus === "insufficient_evidence" && (
        <p className="muted">知识库暂未检索到高度相关资料，本轮回复以一般性陪伴为主。</p>
      )}
      {sources.length === 0 ? (
        <p className="muted">暂无可引用来源。</p>
      ) : (
        <ul className="source-list">
          {sources.map((source) => {
            const href = sourceHref(source);
            return (
              <li key={`${source.source_id}-${source.section}`}>
                <strong>
                  {source.citation_label ? `${source.citation_label} · ` : ""}
                  {source.title}
                </strong>
                <span>{[source.organization, source.year, source.section].filter(Boolean).join(" · ")}</span>
                <small>
                  {source.evidence_level || "source_unverified"} · 相关度{" "}
                  {Math.round((source.relevance_score ?? 0) * 100)}% ·{" "}
                  {source.is_verified ? "已标注来源" : "待审核"}
                </small>
                {href && (
                  <a href={href} rel="noreferrer" target="_blank">
                    查看官方资料
                  </a>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
