import type { Citation } from './types';

interface Props {
  ids: string[];
  citations: Citation[];
}

/** Inline citation chips. External links open in a new tab; network_impact is an internal record. */
export function CitationLinks({ ids, citations }: Props) {
  if (!ids.length) return null;
  return (
    <span className="fr-inv-cites">
      {ids.map((id) => {
        const c = citations.find((x) => x.citation_id === id);
        if (!c?.url) {
          return (
            <span key={id} className="fr-inv-cite" title={c?.title ?? 'Network impact record'}>
              [{id === 'network_impact' ? 'network' : id}]
            </span>
          );
        }
        const page = c.page?.pdf_page ? `, PDF p.${c.page.pdf_page}` : '';
        return (
          <a
            key={id}
            className="fr-inv-cite"
            href={c.url}
            target="_blank"
            rel="noopener noreferrer"
            title={`${c.title}${page}`}
            aria-label={`Source: ${c.title}${page} (opens in new tab)`}
          >
            [{id}]
          </a>
        );
      })}
    </span>
  );
}
