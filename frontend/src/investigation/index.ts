// Public surface of the Person 3 investigation module.
export { InvestigationDrawer } from './InvestigationDrawer';
export type { InvestigationDrawerProps } from './InvestigationDrawer';
export { AssistantChat } from './AssistantChat';
export { InterventionForm } from './InterventionForm';
export { CauseAssessment } from './CauseAssessment';
export { ConceptInterventions } from './ConceptInterventions';
export { NetworkAssumptionForm } from './NetworkAssumptionForm';
export { makeNetworkAssumption, validateNetworkAssumption, loadConcepts, AssumptionError } from './networkAssumption';
export { answerDeterministic, isGroundedAnswer } from './groundedAssistant';
export { makeProposal, validateProposal, defaultEffectClaim, ProposalError } from './proposal';
export { renderBrief, downloadBrief } from './brief';
export type * from './types';

import type { InvestigationResult } from './types';

/** Load an InvestigationResult JSON (e.g. served from results/engineering/). */
export async function loadInvestigation(url: string): Promise<InvestigationResult> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load investigation (${res.status})`);
  const data = (await res.json()) as InvestigationResult;
  if (!data.corridor_id || !Array.isArray(data.candidate_methods)) throw new Error('Not an InvestigationResult');
  return data;
}
