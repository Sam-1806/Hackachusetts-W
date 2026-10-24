import { useEffect, useState, type FormEvent } from 'react';
import { AssumptionError, FIXED_NOTES, makeNetworkAssumption } from './networkAssumption';
import type { ConceptSet, InvestigationResult, NetworkAssumptionForReview } from './types';

interface Props {
  investigation: InvestigationResult;
  concepts: ConceptSet;
  /** Road ids in the current graph (defaults to the corridor's roads). */
  knownRoadIds?: string[];
  /** Person 2 forwards to Person 1 only when record.rerank_requested is true. */
  onSubmit?: (record: NetworkAssumptionForReview) => void;
}

/** Addendum 2, output 2: explicit network what-if. Nothing is pre-selected. */
export function NetworkAssumptionForm({ investigation: inv, concepts, knownRoadIds, onSubmit }: Props) {
  const roads = knownRoadIds ?? inv.road_ids;
  const [conceptId, setConceptId] = useState(concepts.featured_intervention_id ?? concepts.concepts[0]?.intervention_id ?? '');
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [preserved, setPreserved] = useState<string[]>([]);
  const [explicit, setExplicit] = useState(false);
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<NetworkAssumptionForReview | null>(null);

  useEffect(() => {
    setConceptId(concepts.featured_intervention_id ?? concepts.concepts[0]?.intervention_id ?? '');
    setScenarios([]);
    setPreserved([]);
    setExplicit(false);
    setSaved(null);
    setError(null);
  }, [concepts]);

  const concept = concepts.concepts.find((c) => c.intervention_id === conceptId);
  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  function submit(e: FormEvent) {
    e.preventDefault();
    try {
      const rec = makeNetworkAssumption(concepts, conceptId, {
        scenarioIds: scenarios,
        preservedRoadIds: preserved,
        knownRoadIds: roads,
        knownScenarioIds: inv.flood_evidence.map((f) => f.scenario_id),
        notes: note ? [note] : [],
        explicitlySelect: explicit,
      });
      setSaved(rec);
      setError(null);
      onSubmit?.(rec);
    } catch (err) {
      setError(err instanceof AssumptionError ? err.message : 'Could not create network assumption.');
    }
  }

  return (
    <form className="fr-inv-form" onSubmit={submit} aria-labelledby="fr-inv-na-title" noValidate>
      <h3 id="fr-inv-na-title">Network what-if (for reranking)</h3>
      <p className="fr-inv-muted">{FIXED_NOTES.join(' ')}</p>

      <label htmlFor="fr-inv-na-concept">Concept</label>
      <select id="fr-inv-na-concept" value={conceptId} onChange={(e) => setConceptId(e.target.value)}>
        {concepts.concepts.map((c) => (
          <option key={c.intervention_id} value={c.intervention_id}>
            {c.name}
          </option>
        ))}
      </select>
      {concept?.intervention_type === 'drainage_upgrade' && (
        <p className="fr-inv-small fr-inv-error">
          Drainage concepts can be saved as drafts only. A counterfactual needs a validated before/after flood analysis first.
        </p>
      )}

      <fieldset>
        <legend>Scenarios</legend>
        {inv.flood_evidence.map((f) => (
          <label key={f.scenario_id} className="fr-inv-option">
            <input
              type="checkbox"
              checked={scenarios.includes(f.scenario_id)}
              onChange={() => setScenarios((s) => toggle(s, f.scenario_id))}
            />
            {f.label}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Roads to assume passable (none selected by default)</legend>
        {concept && (
          <p className="fr-inv-small fr-inv-muted">
            Nearby roads for reference: {concept.related_road_ids.join(', ') || 'none'}. Being near a concept does not mean protected.
          </p>
        )}
        {roads.map((r) => (
          <label key={r} className="fr-inv-option">
            <input type="checkbox" checked={preserved.includes(r)} onChange={() => setPreserved((s) => toggle(s, r))} />
            {r}
          </label>
        ))}
      </fieldset>

      <label htmlFor="fr-inv-na-note">Assumption note (optional)</label>
      <textarea id="fr-inv-na-note" rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />

      <label className="fr-inv-option">
        <input type="checkbox" checked={explicit} onChange={(e) => setExplicit(e.target.checked)} />I explicitly select this assumption
        for a network counterfactual
      </label>

      {error && (
        <p className="fr-inv-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={!conceptId}>
        {explicit ? 'Send what-if for reranking' : 'Save draft'}
      </button>
      {saved && (
        <p className="fr-inv-success" role="status">
          {saved.rerank_requested
            ? `Selected: ${saved.hypothetical_preserved_road_ids.join(', ')} assumed passable in ${saved.scenario_ids.join(', ')}.`
            : 'Draft saved. No rerank requested.'}
        </p>
      )}
    </form>
  );
}
