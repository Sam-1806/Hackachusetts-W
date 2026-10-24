import { CitationLinks } from './Citations';
import type { Citation, DiagnosticAddendum, EvidenceItem } from './types';

const STATUS_LABEL: Record<string, string> = {
  possible: 'Possible',
  evidence_supported: 'Evidence supported',
  unresolved: 'Unresolved',
};

const TYPE_LABEL: Record<string, string> = {
  observed_report: 'Report',
  observed_measurement: 'Measurement',
  published_model: 'Published model/study',
  gis_derived: 'GIS',
  engineering_record: 'Record',
  hypothesis: 'Hypothesis',
  unknown: 'Unknown',
};

function citeIds(e: EvidenceItem, citations: Citation[]): string[] {
  const paged = e.pdf_page ? `${e.source_id}#p${e.pdf_page}` : null;
  if (paged && citations.some((c) => c.citation_id === paged)) return [paged];
  return citations.some((c) => c.citation_id === e.source_id) ? [e.source_id] : [];
}

function Evidence({ id, evs, citations, tag }: { id: string; evs: Map<string, EvidenceItem>; citations: Citation[]; tag: string }) {
  const e = evs.get(id);
  if (!e) return null;
  return (
    <li className={`fr-inv-block fr-inv-block--${e.data_status === 'mock' ? 'caveat' : 'sourced'}`}>
      <span className="fr-inv-tag">
        {tag} · {TYPE_LABEL[e.evidence_type] ?? e.evidence_type}
        {e.data_status === 'mock' ? ' · mock' : ''}
      </span>{' '}
      {e.summary} <CitationLinks ids={citeIds(e, citations)} citations={citations} />
    </li>
  );
}

interface Props {
  diagnosis: DiagnosticAddendum;
  citations: Citation[];
}

/** Cause hypotheses, assets to inspect and next checks. Statuses are evidence categories, never probabilities. */
export function CauseAssessment({ diagnosis: d, citations }: Props) {
  const evs = new Map(d.evidence.map((e) => [e.evidence_id, e]));
  const causeAssets = d.assets_to_investigate.filter((a) => a.role === 'possible_cause_asset');
  return (
    <>
      <details open>
        <summary>Possible causes (not a diagnosis)</summary>
        <p>
          <strong>{d.finding}</strong>
        </p>
        <p className="fr-inv-banner" role="note">
          {d.impacted_location_note}
        </p>
        {d.possible_causes.map((c) => (
          <article key={c.mechanism} className="fr-inv-card">
            <h4>
              {c.label}{' '}
              <span className={`fr-inv-pill fr-inv-pill--status-${c.status}`}>{STATUS_LABEL[c.status] ?? c.status}</span>
            </h4>
            <p className="fr-inv-small fr-inv-muted">{c.status_basis}</p>
            {(c.supporting_evidence_ids.length > 0 || c.counter_evidence_ids.length > 0) && (
              <ul className="fr-inv-blocks">
                {c.supporting_evidence_ids.slice(0, 3).map((id) => (
                  <Evidence key={id} id={id} evs={evs} citations={citations} tag="Supports" />
                ))}
                {c.counter_evidence_ids.slice(0, 2).map((id) => (
                  <Evidence key={id} id={id} evs={evs} citations={citations} tag="Against" />
                ))}
              </ul>
            )}
            {c.mechanism !== 'multiple_or_unknown' && (
              <>
                <p className="fr-inv-small">
                  <strong>Does not prove it:</strong> {c.does_not_prove}
                </p>
                <p className="fr-inv-small">
                  <strong>Unknown:</strong> {c.unknowns.join('; ')}
                </p>
              </>
            )}
          </article>
        ))}
      </details>

      <details>
        <summary>Assets to inspect</summary>
        <p className="fr-inv-small">
          {d.owner_note} {d.assets_note}
        </p>
        <table className="fr-inv-table">
          <caption className="fr-inv-visually-hidden">Assets that may need inspection, with mapped owner where sourced</caption>
          <thead>
            <tr>
              <th scope="col">Asset</th>
              <th scope="col">Owner</th>
              <th scope="col">Location</th>
            </tr>
          </thead>
          <tbody>
            {causeAssets.map((a, i) => (
              <tr key={`${a.asset_type}-${a.asset_id ?? i}`}>
                <th scope="row">
                  {a.asset_type.replace(/_/g, ' ')}
                  {a.asset_id ? ` ${a.asset_id}` : ''}
                </th>
                <td>{a.owner ? `${a.owner} (mapped, unverified)` : <em>unknown</em>}</td>
                <td className="fr-inv-small">{a.location_ref}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      <details open>
        <summary>Next investigation steps</summary>
        <ol className="fr-inv-list">
          {d.recommended_next_checks.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ol>
        <p className="fr-inv-small">
          <strong>Only after checks:</strong>
        </p>
        <ul className="fr-inv-list fr-inv-small">
          {d.cause_matched_actions
            .filter((a) => a.kind !== 'investigation')
            .map((a) => (
              <li key={a.action_id}>
                <strong>{a.name}</strong> ({a.kind}; {a.mechanism.replace(/_/g, ' ')}: {a.mechanism_status}). {a.gate} Could fail:{' '}
                {a.could_fail} Cost: {a.cost_status === 'cost_estimate_unavailable' ? 'estimate unavailable' : 'see 2018 samples'}.
              </li>
            ))}
        </ul>
        <ul className="fr-inv-list fr-inv-small fr-inv-muted">
          {d.intervention_caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </details>
    </>
  );
}
