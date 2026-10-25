import { useState } from 'react';
import './investigation.css';
import { AssistantChat } from './AssistantChat';
import { downloadBrief } from './brief';
import { CauseAssessment } from './CauseAssessment';
import { CitationLinks } from './Citations';
import { formatFactValue, isMock, mockParts } from './groundedAssistant';
import { InterventionForm } from './InterventionForm';
import { ConceptInterventions } from './ConceptInterventions';
import { NetworkAssumptionForm } from './NetworkAssumptionForm';
import type {
  ConceptIntervention,
  ConceptSet,
  InterventionProposal,
  InvestigationResult,
  NetworkAssumptionForReview,
  RemoteAsk,
} from './types';

export interface InvestigationDrawerProps {
  /** InvestigationResult for the selected corridor (results/engineering/investigation_<corridor_id>.json). */
  investigation: InvestigationResult | null;
  onProposeIntervention?: (proposal: InterventionProposal) => void;
  onClose?: () => void;
  askRemote?: RemoteAsk;
  /** Addendum 2, output 1: concept geometry for preview (results/engineering/concepts_<corridor_id>.json). */
  concepts?: ConceptSet | null;
  /** Person 2: show a concept on the map. Display only. */
  onPreviewConcept?: (concept: ConceptIntervention) => void;
  previewedConceptId?: string | null;
  /** Addendum 2, output 2: explicit network what-if. Forward to Person 1 only when rerank_requested. */
  onSubmitNetworkAssumption?: (record: NetworkAssumptionForReview) => void;
  /** Road ids in the current graph for the what-if form (defaults to corridor roads). */
  knownRoadIds?: string[];
}

const usd = (v: number) => `$${v.toLocaleString('en-US')}`;

export function InvestigationDrawer({
  investigation: inv,
  onProposeIntervention,
  onClose,
  askRemote,
  concepts,
  onPreviewConcept,
  previewedConceptId,
  onSubmitNetworkAssumption,
  knownRoadIds,
}: InvestigationDrawerProps) {
  const [lastProposal, setLastProposal] = useState<InterventionProposal | null>(null);

  if (!inv) {
    return (
      <aside className="fr-inv" aria-label="Road investigation">
        <p className="fr-inv-muted">Select a corridor to see its investigation.</p>
      </aside>
    );
  }

  const n = inv.network_impact;
  const cites = inv.citations;
  const costs = inv.published_cost_examples;
  const handlePropose = (p: InterventionProposal) => {
    setLastProposal(p);
    onProposeIntervention?.(p);
  };

  return (
    <aside className="fr-inv" aria-labelledby="fr-inv-title">
      <header className="fr-inv-header">
        <div>
          <p className="fr-inv-eyebrow">Road investigation</p>
          <h2 id="fr-inv-title">{inv.corridor_name || inv.corridor_id}</h2>
          <p className="fr-inv-muted fr-inv-small">
            {inv.corridor_id} · {inv.road_ids.length} roads · graph {inv.graph_version}
          </p>
        </div>
        <div className="fr-inv-header-actions">
          <button type="button" onClick={() => downloadBrief(inv, lastProposal, concepts?.corridor_id === inv.corridor_id ? concepts : null)}>
            Export brief
          </button>
          {onClose && (
            <button type="button" onClick={onClose} aria-label="Close investigation panel">
              ×
            </button>
          )}
        </div>
      </header>

      {isMock(inv) && (
        <p className="fr-inv-banner" role="note">
          Mock inputs: {mockParts(inv).join(', ')}. Those numbers are placeholders, not results.
        </p>
      )}

      <details open>
        <summary>Why this corridor</summary>
        {n.status === 'available' ? (
          <>
            <p>
              Rank <strong>{n.priority_rank}</strong> · {n.impact_metric} {n.metric_units}{' '}
              <CitationLinks ids={['network_impact']} citations={cites} />
            </p>
            <table className="fr-inv-table">
              <caption className="fr-inv-visually-hidden">Representative journeys, normal versus flooded</caption>
              <thead>
                <tr>
                  <th scope="col">Journey</th>
                  <th scope="col">Normal</th>
                  <th scope="col">Flooded</th>
                </tr>
              </thead>
              <tbody>
                {(n.affected_journeys ?? []).map((j) => (
                  <tr key={j.journey_id}>
                    <th scope="row">{j.label}</th>
                    <td>{j.baseline_s} s</td>
                    <td>{j.reachable ? `${j.flooded_s} s` : <strong>Unreachable</strong>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {n.assumptions?.length ? <p className="fr-inv-muted fr-inv-small">Assumptions: {n.assumptions.join('; ')}</p> : null}
          </>
        ) : (
          <p className="fr-inv-muted">{n.note ?? 'Network ranking not available.'}</p>
        )}
      </details>

      {inv.cause_assessment && <CauseAssessment diagnosis={inv.cause_assessment} citations={cites} />}

      <details open>
        <summary>Flood evidence</summary>
        <ul className="fr-inv-list">
          {inv.flood_evidence.map((f) => (
            <li key={f.scenario_id}>
              <span className={`fr-inv-pill fr-inv-pill--${f.kind}`}>
                {f.kind === 'future_model' ? 'Projected' : f.kind === 'historical_observed' ? 'Observed' : 'Unknown type'}
              </span>{' '}
              <strong>{f.label}</strong> <span className="fr-inv-muted">({f.data_status})</span>
              <br />
              Exposed {f.roads_exposed.length} · unknown {f.roads_unknown.length} · depth:{' '}
              {f.depth_m.status === 'reported' ? `${f.depth_m.min}–${f.depth_m.max} m` : <em>{f.depth_m.status}</em>}{' '}
              <CitationLinks ids={f.citation_ids} citations={cites} />
              <br />
              <span className="fr-inv-muted fr-inv-small">{f.caveat}</span>
            </li>
          ))}
        </ul>
      </details>

      <details>
        <summary>Road facts</summary>
        <dl className="fr-inv-facts">
          {Object.entries(inv.road_facts.summary).map(([k, e]) => (
            <div key={k} className={e.status === 'not_available' ? 'fr-inv-fact--missing' : undefined}>
              <dt>{e.label}</dt>
              <dd>
                {formatFactValue(e)}
                {e.note && e.status !== 'not_available' ? <span className="fr-inv-muted fr-inv-small"> · {e.note}</span> : null}
              </dd>
            </div>
          ))}
        </dl>
        <p className="fr-inv-small">
          Inventory segments: {inv.road_facts.matched_inventory_segment_ids.join(', ') || 'none matched'}{' '}
          <CitationLinks ids={inv.road_facts.citation_ids} citations={cites} />
        </p>
      </details>

      <details open>
        <summary>Candidate methods to investigate</summary>
        <p className="fr-inv-muted fr-inv-small">Options to evaluate, not a recommended fix. A licensed engineer must review.</p>
        {inv.candidate_methods.map((m) => (
          <article key={m.method_id} className="fr-inv-card">
            <h4>{m.name}</h4>
            <p>{m.summary}</p>
            {m.cause_gate && (
              <p className="fr-inv-small fr-inv-block fr-inv-block--caveat">
                <span className="fr-inv-tag">Cause check</span> {m.cause_gate}
              </p>
            )}
            <ul className="fr-inv-blocks">
              {m.sourced_points.map((p, i) => (
                <li key={i} className="fr-inv-block fr-inv-block--sourced">
                  <span className="fr-inv-tag">Sourced</span> {p.text} <CitationLinks ids={p.citation_ids} citations={cites} />
                </li>
              ))}
              {m.hypotheses.map((h, i) => (
                <li key={`h${i}`} className="fr-inv-block fr-inv-block--hypothesis">
                  <span className="fr-inv-tag">Hypothesis</span> {h}
                </li>
              ))}
            </ul>
            <p className="fr-inv-small">
              <strong>Could fail by:</strong> {m.failure_modes.join('; ')}
            </p>
            <p className="fr-inv-small">
              <strong>Unknown for screening:</strong>{' '}
              {m.screening
                .filter((c) => c.status === 'unknown')
                .map((c) => c.check)
                .join('; ') || 'none'}
            </p>
          </article>
        ))}
        {inv.other_methods_considered.length > 0 && (
          <p className="fr-inv-small fr-inv-muted">
            Also considered: {inv.other_methods_considered.map((o) => `${o.name} (${o.reason})`).join('; ')}
          </p>
        )}
      </details>

      {inv.local_precedents.length > 0 && (
        <details>
          <summary>Local precedent</summary>
          <ul className="fr-inv-list">
            {inv.local_precedents.map((p) => (
              <li key={p.precedent_id}>
                <span className="fr-inv-pill">{p.status.replace(/_/g, ' ')}</span> {p.text}{' '}
                <CitationLinks ids={p.citation_ids} citations={cites} />
              </li>
            ))}
          </ul>
          <p className="fr-inv-muted fr-inv-small">Study findings are not evidence a measure is approved, funded, or built.</p>
        </details>
      )}

      <details>
        <summary>Published cost context (2018 samples)</summary>
        <ul className="fr-inv-list fr-inv-small">
          {costs.caveats.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
        <table className="fr-inv-table">
          <caption className="fr-inv-visually-hidden">Published 2018 sample costs, not estimates for this corridor</caption>
          <thead>
            <tr>
              <th scope="col">Sample</th>
              <th scope="col">Length</th>
              <th scope="col">Total</th>
              <th scope="col">Per 100 ft</th>
            </tr>
          </thead>
          <tbody>
            {costs.examples.map((e) => (
              <tr key={e.precedent_id}>
                <th scope="row">
                  {e.title} <CitationLinks ids={e.citation_ids} citations={cites} />
                  <div className="fr-inv-muted fr-inv-small">Excludes: {e.excluded.slice(0, 4).join(', ')}</div>
                </th>
                <td>{e.sample_dimensions.length_ft.toLocaleString('en-US')} ft</td>
                <td>{usd(e.total_usd)}</td>
                <td>{usd(e.unit_cost.usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="fr-inv-small">
          <strong>This corridor:</strong> {costs.site_specific_estimate.note}
        </p>
      </details>

      <details>
        <summary>Missing site information ({inv.missing_site_information.length})</summary>
        <ul className="fr-inv-list">
          {inv.missing_site_information.map((m) => (
            <li key={m.item}>
              <strong>{m.item}</strong>: {m.status}
              <br />
              <span className="fr-inv-muted fr-inv-small">{m.why_needed}</span>
            </li>
          ))}
        </ul>
      </details>

      {concepts && concepts.corridor_id === inv.corridor_id && (
        <ConceptInterventions concepts={concepts} citations={cites} onPreview={onPreviewConcept} previewedId={previewedConceptId} />
      )}

      <AssistantChat investigation={inv} askRemote={askRemote} />
      <InterventionForm investigation={inv} onSubmit={handlePropose} />
      {concepts && concepts.corridor_id === inv.corridor_id && (
        <NetworkAssumptionForm
          investigation={inv}
          concepts={concepts}
          knownRoadIds={knownRoadIds}
          onSubmit={onSubmitNetworkAssumption}
        />
      )}

      <details>
        <summary>Sources and limitations</summary>
        <ul className="fr-inv-list fr-inv-small">
          {inv.limitations.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
        <ol className="fr-inv-list fr-inv-small">
          {cites.map((c) => (
            <li key={c.citation_id}>
              [{c.citation_id}]{' '}
              {c.url ? (
                <a href={c.url} target="_blank" rel="noopener noreferrer">
                  {c.title}
                </a>
              ) : (
                c.title
              )}
              {c.page?.pdf_page ? `, PDF p.${c.page.pdf_page}` : ''}
            </li>
          ))}
        </ol>
      </details>
    </aside>
  );
}
