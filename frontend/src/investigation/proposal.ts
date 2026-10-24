// InterventionProposal creation/validation. Mirrors engineering/floodroute_eng/intervention.py.
// The UI can only create 'hypothetical' proposals; it never edits flood data or marks a road fixed.
// effect_claim (Causal Diagnosis Addendum):
//   access_only            -> idealized passability for the network counterfactual; no flood/loss reduction claimed
//   hydraulic_or_drainage  -> unquantified unless hazard_update_evidence is supplied; passability stays 'unchanged'

import type { CandidateMethod, CauseMatchedAction, EffectClaim, InterventionProposal, InvestigationResult } from './types';

export const ASSUMPTION_NOTE =
  'Idealized assumption for network counterfactual only. Physical effectiveness has not been modelled or verified.';
export const UNQUANTIFIED_NOTE =
  'Unquantified drainage/hydraulic proposal. Road exposure, property-loss projections and network ranking stay unchanged until validated before/after flood analysis is supplied.';
const HYDRAULIC_METHODS = new Set(['drainage_backflow']);

export class ProposalError extends Error { }

const randomId = () =>
  'iv-' +
  (globalThis.crypto?.randomUUID?.().replace(/-/g, '').slice(0, 8) ?? Math.random().toString(16).slice(2, 10));

type Lookup = { kind: 'method'; rec: CandidateMethod } | { kind: 'action'; rec: CauseMatchedAction };

function lookup(inv: InvestigationResult, id: string): Lookup {
  const m =
    inv.candidate_methods.find((c) => c.method_id === id) ??
    inv.other_methods_considered.find((o) => o.method_id === id && o.details)?.details;
  if (m) return { kind: 'method', rec: m };
  const a = inv.cause_assessment?.cause_matched_actions.find((x) => x.action_id === id);
  if (a) return { kind: 'action', rec: a };
  throw new ProposalError(`'${id}' is not a candidate method or cause-matched action for ${inv.corridor_id}`);
}

export function defaultEffectClaim(inv: InvestigationResult, id: string): EffectClaim {
  const l = lookup(inv, id);
  const drainage = (l.kind === 'action' && l.rec.mechanism !== 'coastal_overland') || HYDRAULIC_METHODS.has(id);
  return drainage ? 'hydraulic_or_drainage' : 'access_only';
}

export function makeProposal(
  inv: InvestigationResult,
  methodId: string,
  scenarioIds: string[],
  opts: {
    roadIds?: string[];
    reviewNotes?: string;
    interventionId?: string;
    effectClaim?: EffectClaim;
    hazardUpdateEvidence?: { source_ids: string[]; description: string };
  } = {},
): InterventionProposal {
  const l = lookup(inv, methodId);
  const effect = opts.effectClaim ?? defaultEffectClaim(inv, methodId);
  const all = inv.flood_evidence.map((f) => f.scenario_id);
  const unknown = scenarioIds.filter((s) => !all.includes(s));
  if (unknown.length) throw new ProposalError(`Unknown scenario ids: ${unknown.join(', ')}`);
  const quantified = effect === 'access_only' || !!opts.hazardUpdateEvidence;
  if (quantified && !scenarioIds.length)
    throw new ProposalError('Select at least one scenario the measure is assumed to withstand');

  const name = l.rec.name;
  const category = l.kind === 'method' ? l.rec.category : l.rec.kind;
  const sourceIds =
    l.kind === 'method'
      ? [...new Set(l.rec.sourced_points.flatMap((p) => p.citation_ids.map((c) => c.split('#')[0])))].sort()
      : [...new Set(l.rec.source_ids)].sort();
  const note =
    effect === 'access_only'
      ? ASSUMPTION_NOTE
      : quantified
        ? 'Hydraulic effect per supplied hazard update evidence; engineer review required.'
        : UNQUANTIFIED_NOTE;
  const notes = (opts.reviewNotes ?? '').trim();
  const proposal: InterventionProposal = {
    intervention_id: opts.interventionId ?? randomId(),
    corridor_id: inv.corridor_id,
    road_ids: opts.roadIds ?? [...inv.road_ids],
    graph_version: inv.graph_version,
    proposed_method: { method_id: methodId, name, category },
    status: 'hypothetical',
    assumed_passability_by_scenario: Object.fromEntries(
      all.map((s) => [s, quantified && scenarioIds.includes(s) ? 'assumed_open' : 'unchanged']),
    ),
    review_notes: (notes ? notes + ' ' : '') + note,
    source_ids: sourceIds,
    created_at: new Date().toISOString(),
    effect_claim: effect,
    mechanism: l.kind === 'action' ? l.rec.mechanism : null,
    effect_status:
      effect === 'access_only' ? 'idealized_access_assumption' : quantified ? 'hazard_update_supplied' : 'unquantified_proposal',
    rerank_eligible: quantified,
    requested_scenarios: [...scenarioIds],
    ...(opts.hazardUpdateEvidence ? { hazard_update_evidence: opts.hazardUpdateEvidence } : {}),
  };
  validateProposal(proposal, inv);
  return proposal;
}

export function validateProposal(p: InterventionProposal, inv?: InvestigationResult): void {
  if (!/^[A-Za-z0-9_.:-]{1,64}$/.test(p.intervention_id)) throw new ProposalError('Invalid intervention_id');
  if (!['hypothetical', 'implemented', 'verified'].includes(p.status)) throw new ProposalError('Invalid status');
  if (!p.road_ids.length) throw new ProposalError('road_ids must not be empty');
  const vals = Object.values(p.assumed_passability_by_scenario);
  if (vals.some((v) => v !== 'assumed_open' && v !== 'unchanged')) throw new ProposalError('Invalid passability value');
  const effect = p.effect_claim ?? 'access_only';
  const opens = vals.includes('assumed_open');
  if (effect === 'access_only' && !opens) throw new ProposalError('Proposal does not assume passability in any scenario');
  if (effect === 'hydraulic_or_drainage' && opens && !(p.hazard_update_evidence?.source_ids.length && p.hazard_update_evidence.description))
    throw new ProposalError('hydraulic_or_drainage proposals cannot change passability without hazard_update_evidence');
  if (p.status !== 'hypothetical' && (!p.status_evidence?.source_ids.length || !p.status_evidence.reviewer))
    throw new ProposalError(`status '${p.status}' requires status_evidence with source_ids and reviewer`);
  if (inv) {
    if (p.corridor_id !== inv.corridor_id) throw new ProposalError('corridor_id does not match investigation');
    const extra = p.road_ids.filter((r) => !inv.road_ids.includes(r));
    if (extra.length) throw new ProposalError(`road_ids outside corridor: ${extra.join(', ')}`);
  }
}
