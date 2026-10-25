import type { Citation, ConceptIntervention, ConceptSet } from './types';
import { CitationLinks } from './Citations';

const STATUS_CLASS: Record<string, string> = {
  sourced_design_alignment: 'fr-inv-geo--design',
  sourced_asset_location: 'fr-inv-geo--asset',
  schematic: 'fr-inv-geo--schematic',
  none: 'fr-inv-geo--none',
};

const CHECK_LABEL: Record<string, string> = {
  physical_survey: 'Physical survey',
  ownership_check: 'Ownership check',
  drainage_assessment: 'Drainage assessment',
  permitting: 'Permitting',
};

interface Props {
  concepts: ConceptSet;
  citations: Citation[];
  /** Person 2: fly to / highlight the concept. Must not change flood layers or travel results. */
  onPreview?: (concept: ConceptIntervention) => void;
  previewedId?: string | null;
}

/** Concept intervention cards (Addendum 2, output 1). Geometry provenance is always visible. */
export function ConceptInterventions({ concepts: cs, citations, onPreview, previewedId }: Props) {
  const ids = new Set(citations.map((c) => c.citation_id));
  const cite = (sids: string[]) => sids.filter((s) => ids.has(s));
  return (
    <details open>
      <summary>Concept interventions (preview, not designs)</summary>
      <p className="fr-inv-small fr-inv-muted">
        Previews show where a measure might sit. They do not mark roads protected, change flood layers, or rerank anything.
      </p>
      {cs.concepts.map((c) => {
        const featured = c.intervention_id === cs.featured_intervention_id;
        return (
          <article key={c.intervention_id} className="fr-inv-card" aria-labelledby={`fr-inv-ci-${c.intervention_id}`}>
            <h4 id={`fr-inv-ci-${c.intervention_id}`}>
              {c.name} {featured && <span className="fr-inv-pill">Featured preview</span>}
            </h4>
            <p>
              <span className={`fr-inv-pill ${STATUS_CLASS[c.geometry_status]}`}>{c.display_badge}</span>{' '}
              <span className="fr-inv-small fr-inv-muted">
                {c.intervention_type.replace(/_/g, ' ')} · target: {c.target_asset_type.replace(/_/g, ' ')} · {c.provenance.replace(/_/g, ' ')}
              </span>
            </p>
            <p className="fr-inv-small">
              {c.geometry_note} <CitationLinks ids={cite(c.geometry_source_ids)} citations={citations} />
            </p>
            {c.visual_parameters?.conceptual_height_m != null && (
              <p className="fr-inv-small">
                Display height {c.visual_parameters.conceptual_height_m} m: {c.visual_parameters.basis}
              </p>
            )}
            <p className="fr-inv-small">
              <strong>Addresses:</strong>{' '}
              {Object.entries(c.mechanism_status)
                .map(([m, s]) => `${m.replace(/_/g, ' ')} (${s})`)
                .join(', ')}
            </p>
            <p className="fr-inv-small">
              <strong>Would confirm:</strong> {c.confirm_with.join('; ')}
            </p>
            <p className="fr-inv-small">
              <strong>Would refute:</strong> {c.refute_if.join('; ')}
            </p>
            <ul className="fr-inv-list fr-inv-small">
              {c.evidence_distinction.map((d, i) => (
                <li key={i}>
                  <strong>{d.kind.replace(/_/g, ' ')}:</strong> {d.text}{' '}
                  {d.source_id && <CitationLinks ids={cite([d.source_id])} citations={citations} />}
                </li>
              ))}
            </ul>
            <dl className="fr-inv-facts fr-inv-small">
              {Object.entries(c.unresolved_checks).map(([k, v]) => (
                <div key={k} className="fr-inv-fact--missing">
                  <dt>{CHECK_LABEL[k] ?? k} (unresolved)</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
            <p className="fr-inv-small">
              <strong>Cost:</strong>{' '}
              {c.published_cost_precedents.length
                ? c.published_cost_precedents
                    .map((p) => `${p.example_scope}: $${(p.amount_usd ?? 0).toLocaleString('en-US')} (${p.price_year} sample, not a quote)`)
                    .join('; ')
                : 'estimate unavailable (no published example for this work type)'}
            </p>
            <p className="fr-inv-small fr-inv-muted">
              Nearby roads: {c.related_road_ids.join(', ') || 'none'}. {c.related_road_ids_note}
            </p>
            {onPreview && (
              <button
                type="button"
                onClick={() => onPreview(c)}
                disabled={!c.geometry}
                aria-pressed={previewedId === c.intervention_id}
                title={c.geometry ? 'Show on map (display only)' : 'No geometry to show'}
              >
                {c.geometry ? 'Preview on map' : 'No geometry'}
              </button>
            )}
          </article>
        );
      })}
      {cs.alternatives_not_rendered.length > 0 && (
        <p className="fr-inv-small fr-inv-muted">
          Also considered (cards only): {cs.alternatives_not_rendered.map((a) => a.name).join('; ')}
        </p>
      )}
    </details>
  );
}
