// NetworkAssumptionForReview creation/validation. Mirrors engineering/floodroute_eng/network_assumption.py.
// Separate from ConceptIntervention (geometry) and from InterventionProposal.

import type { ConceptSet, NetworkAssumptionForReview } from './types';

export const FIXED_NOTES = [
  'Hypothetical access assumption for network analysis only.',
  'Does not imply hydraulic validation, physical protection, or changed flood extents.',
];

export class AssumptionError extends Error {}

export function makeNetworkAssumption(
  set: ConceptSet,
  interventionId: string,
  opts: {
    scenarioIds: string[];
    preservedRoadIds: string[];
    knownRoadIds: string[];
    knownScenarioIds: string[];
    notes?: string[];
    explicitlySelect?: boolean;
    hazardUpdateEvidence?: { source_ids: string[]; description: string };
  },
): NetworkAssumptionForReview {
  const concept = set.concepts.find((c) => c.intervention_id === interventionId);
  if (!concept) throw new AssumptionError(`Unknown concept intervention_id '${interventionId}'`);
  const selected = !!opts.explicitlySelect;
  const rec: NetworkAssumptionForReview = {
    schema_version: 'network-assumption-v0.1',
    intervention_id: interventionId,
    intervention_type: concept.intervention_type,
    graph_version: set.graph_version,
    scenario_ids: [...new Set(opts.scenarioIds)],
    hypothetical_preserved_road_ids: [...new Set(opts.preservedRoadIds)],
    selection_status: selected ? 'explicitly_selected_for_counterfactual' : 'draft',
    assumption_notes: [...FIXED_NOTES, ...(opts.notes ?? []).map((n) => n.trim()).filter(Boolean)],
    created_at: new Date().toISOString(),
    rerank_requested: selected,
    ...(opts.hazardUpdateEvidence ? { hazard_update_evidence: opts.hazardUpdateEvidence } : {}),
  };
  validateNetworkAssumption(rec, opts.knownRoadIds, opts.knownScenarioIds);
  return rec;
}

export function validateNetworkAssumption(rec: NetworkAssumptionForReview, knownRoadIds: string[], knownScenarioIds: string[]): void {
  const badR = rec.hypothetical_preserved_road_ids.filter((r) => !knownRoadIds.includes(r));
  const badS = rec.scenario_ids.filter((s) => !knownScenarioIds.includes(s));
  if (badR.length) throw new AssumptionError(`Preserved roads not in graph ${rec.graph_version}: ${badR.join(', ')}`);
  if (badS.length) throw new AssumptionError(`Unknown scenario ids: ${badS.join(', ')}`);
  if (!FIXED_NOTES.every((n) => rec.assumption_notes.includes(n))) throw new AssumptionError('Required assumption notes removed');
  if (rec.selection_status === 'explicitly_selected_for_counterfactual') {
    if (!rec.scenario_ids.length) throw new AssumptionError('Select at least one scenario before requesting a counterfactual');
    if (!rec.hypothetical_preserved_road_ids.length)
      throw new AssumptionError('Select at least one preserved road explicitly before requesting a counterfactual');
    if (rec.intervention_type === 'drainage_upgrade' && !(rec.hazard_update_evidence?.source_ids.length && rec.hazard_update_evidence.description))
      throw new AssumptionError(
        'Drainage concepts need hazard_update_evidence (validated before/after flood analysis) before a network counterfactual can be requested',
      );
  }
  if (rec.rerank_requested && rec.selection_status !== 'explicitly_selected_for_counterfactual')
    throw new AssumptionError('rerank_requested is only allowed for explicitly selected assumptions');
}

/** Load a ConceptSet JSON (results/engineering/concepts_<corridor>.json or fixtures/sample_concept_interventions.json). */
export async function loadConcepts(url: string): Promise<ConceptSet> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load concepts (${res.status})`);
  const data = (await res.json()) as ConceptSet;
  if (!Array.isArray(data.concepts)) throw new Error('Not a ConceptSet');
  return data;
}
