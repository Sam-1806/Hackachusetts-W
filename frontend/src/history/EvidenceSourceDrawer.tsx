import type { EvidenceSource } from "./types";

export interface EvidenceSourceDrawerProps {
  sources: EvidenceSource[];
  limitations?: string[];
  title?: string;
}

export function EvidenceSourceDrawer({
  sources,
  limitations = [],
  title = "Sources & limitations",
}: EvidenceSourceDrawerProps) {
  return (
    <details className="history-sources">
      <summary>
        <span>{title}</span>
        <span className="history-sources__count">{sources.length} sources</span>
      </summary>

      <div className="history-sources__body">
        {sources.length === 0 ? (
          <p className="history-muted">No source records were supplied.</p>
        ) : (
          <ol className="history-source-list">
            {sources.map((source) => (
              <li key={source.id}>
                <a href={source.url} target="_blank" rel="noreferrer">
                  {source.title}
                </a>
                <span>{source.authority}</span>
                {source.accessedDate ? <small>Accessed {source.accessedDate}</small> : null}
                {source.note ? <p>{source.note}</p> : null}
              </li>
            ))}
          </ol>
        )}

        {limitations.length > 0 ? (
          <div className="history-limitations">
            <h4>Interpretation limits</h4>
            <ul>
              {limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </details>
  );
}

