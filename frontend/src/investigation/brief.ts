// Exportable engineer review brief (Markdown). Mirrors engineering/floodroute_eng/brief.py.

import { formatFactValue } from './groundedAssistant';
import type { ConceptSet, DiagnosticAddendum, InterventionProposal, InvestigationResult } from './types';

const cite = (ids: string[]) => (ids.length ? ' ' + ids.map((i) => `[${i}]`).join(' ') : '');

function causeSection(d: DiagnosticAddendum): string[] {
  const evs = new Map(d.evidence.map((e) => [e.evidence_id, e]));
  const evLine = (id: string, tag: string) => {
    const e = evs.get(id)!;
    return `  - ${tag} [${e.evidence_type}] ${e.summary}${e.data_status === 'mock' ? ' (mock)' : ''} [${e.source_id}]`;
  };
  const L = [
    '## Cause assessment (hypotheses, not a diagnosis)',
    '',
    `**Finding:** ${d.finding}`,
    '',
    `**Why the road may not be the asset to fix:** ${d.impacted_location_note}`,
    '',
  ];
  for (const c of d.possible_causes) {
    L.push(`- **${c.label}**: ${c.status}. ${c.status_basis}`);
    c.supporting_evidence_ids.slice(0, 3).forEach((e) => L.push(evLine(e, 'Supports:')));
    c.counter_evidence_ids.slice(0, 2).forEach((e) => L.push(evLine(e, 'Against:')));
    if (c.mechanism !== 'multiple_or_unknown')
      L.push(`  - Does not prove it: ${c.does_not_prove}`, `  - Unknown: ${c.unknowns.join('; ')}`);
  }
  L.push('', '### Assets to inspect', `${d.owner_note} ${d.assets_note ?? ''}`, '');
  L.push('| Type | Role | ID | Owner | Location |', '|:--|:--|:--|:--|:--|');
  d.assets_to_investigate.forEach((a) =>
    L.push(
      `| ${a.asset_type} | ${a.role} | ${a.asset_id ?? '-'} | ${a.owner ? `${a.owner} (${a.owner_status})` : a.owner_status} | ${a.location_ref ?? '-'} |`,
    ),
  );
  L.push('', '### Next investigation steps', ...d.recommended_next_checks.map((s, i) => `${i + 1}. ${s}`));
  L.push('', '### Cause-matched options (only after checks)');
  d.cause_matched_actions
    .filter((a) => a.kind !== 'investigation')
    .forEach((a) =>
      L.push(
        `- **${a.name}** [${a.kind}, ${a.mechanism}: ${a.mechanism_status}]. Gate: ${a.gate} Applicable if: ${a.applicable_if} ` +
        `Could fail: ${a.could_fail} Downstream checks: ${a.downstream_checks.join('; ')}. Cost: ${a.cost_status}` +
        `${a.quote_inputs?.length ? ` (inputs for a quote: ${a.quote_inputs.join(', ')})` : ''}.`,
      ),
    );
  L.push('', '### Cannot presently be claimed', ...d.intervention_caveats.map((c) => `- ${c}`), ...d.limitations.map((c) => `- ${c}`));
  L.push('- Engineer review required.', '');
  return L;
}

function conceptSection(cs: ConceptSet): string[] {
  const L = [
    '## Concept interventions for preview (not designs)',
    '',
    'Previews show where a measure might sit. They do not mark roads protected or change flood layers.',
    '',
  ];
  for (const c of cs.concepts) {
    L.push(`### ${c.name}${c.intervention_id === cs.featured_intervention_id ? ' (featured preview)' : ''}`);
    L.push(
      `- Type / target: ${c.intervention_type} / ${c.target_asset_type}; geometry: **${c.geometry_status}** (${c.display_badge}). ${c.geometry_note}`,
    );
    L.push(`- Addresses: ${Object.entries(c.mechanism_status).map(([k, v]) => `${k} (${v})`).join(', ')}`);
    L.push(`- Would confirm: ${c.confirm_with.join('; ')}`, `- Would refute: ${c.refute_if.join('; ')}`);
    Object.entries(c.unresolved_checks).forEach(([k, v]) => L.push(`- Unresolved ${k.replace(/_/g, ' ')}: ${v}`));
    L.push(
      c.published_cost_precedents.length
        ? `- Cost context (2018 samples, not quotes): ${c.published_cost_precedents.map((p) => `${p.example_scope}: $${(p.amount_usd ?? 0).toLocaleString('en-US')}`).join('; ')}`
        : `- Cost: ${c.cost_status}`,
    );
  }
  if (cs.alternatives_not_rendered.length)
    L.push('', `Alternatives (cards only): ${cs.alternatives_not_rendered.map((a) => a.name).join('; ')}`);
  return L;
}

export function renderBrief(inv: InvestigationResult, proposal?: InterventionProposal | null, concepts?: ConceptSet | null): string {
  const L: string[] = [];
  L.push(`# Engineer review brief: ${inv.corridor_name || inv.corridor_id}`, '');
  L.push(`Corridor \`${inv.corridor_id}\` · roads ${inv.road_ids.join(', ')} · graph \`${inv.graph_version}\``, '');
  L.push('> Preliminary investigation aid. Not a design, certification, or cost estimate.');
  inv.limitations.forEach((l) => L.push(`> - ${l}`));
  L.push('', '## Why this corridor is a priority');
  const n = inv.network_impact;
  if (n.status === 'available') {
    L.push(`Rank ${n.priority_rank}, impact ${n.impact_metric} ${n.metric_units} (data status: ${n.data_status}) [network_impact].`);
    (n.affected_journeys ?? []).forEach((j) =>
      L.push(`- ${j.label}: ${j.baseline_s} s normal, ${j.reachable ? `${j.flooded_s} s flooded` : 'unreachable'}`),
    );
  } else L.push('Network ranking not available.');
  if (inv.cause_assessment) L.push('', ...causeSection(inv.cause_assessment));
  L.push('', '## Documented flood exposure');
  inv.flood_evidence.forEach((f) =>
    L.push(
      `- **${f.label}** (${f.kind}, ${f.data_status}): exposed ${f.roads_exposed.length}, unknown ${f.roads_unknown.length}; ` +
      `depth: ${f.depth_m.status === 'reported' ? `${f.depth_m.min}–${f.depth_m.max} m` : f.depth_m.status}.${cite(f.citation_ids)} ${f.caveat}`,
    ),
  );
  L.push('', '## Road facts (MassDOT Road Inventory)');
  Object.values(inv.road_facts.summary).forEach((e) => L.push(`- ${e.label}: ${formatFactValue(e)}`));
  L.push('', '## Candidate measures to investigate');
  inv.candidate_methods.forEach((m) => {
    L.push(`### ${m.name}`, m.summary);
    m.sourced_points.forEach((p) => L.push(`- ${p.text}${cite(p.citation_ids)}`));
    m.hypotheses.forEach((h) => L.push(`- *Hypothesis:* ${h}`));
    L.push(`- Failure modes: ${m.failure_modes.join('; ')}`, `- Data needed: ${m.required_data.join('; ')}`);
  });
  if (inv.local_precedents.length) {
    L.push('', '## Local precedent');
    inv.local_precedents.forEach((p) => L.push(`- [${p.status}] ${p.text}${cite(p.citation_ids)}`));
  }
  const c = inv.published_cost_examples;
  L.push('', '## Published cost context (2018 samples, not transferable)');
  c.caveats.forEach((cav) => L.push(`- ${cav}`));
  L.push('', '| Sample | Length | Total | Unit | Key exclusions |', '|:--|--:|--:|--:|:--|');
  c.examples.forEach((e) =>
    L.push(
      `| ${e.title}${cite(e.citation_ids)} | ${e.sample_dimensions.length_ft.toLocaleString('en-US')} ft | ` +
      `$${e.total_usd.toLocaleString('en-US')} | $${e.unit_cost.usd.toLocaleString('en-US')}/${e.unit_cost.per} | ${e.excluded.slice(0, 3).join(', ')} |`,
    ),
  );
  L.push('', `Site-specific estimate: ${c.site_specific_estimate.note}`);
  if (concepts) L.push('', ...conceptSection(concepts));
  L.push('', '## Site investigations needed');
  inv.missing_site_information.forEach((m) => L.push(`- ${m.item}: ${m.status}`));
  if (proposal) {
    L.push('', '## Recorded hypothetical intervention');
    L.push(`- \`${proposal.intervention_id}\`: ${proposal.proposed_method.name} (${proposal.status})`);
    L.push(`- Assumed passability: ${JSON.stringify(proposal.assumed_passability_by_scenario)}`);
    if (proposal.effect_claim)
      L.push(`- Effect claim: ${proposal.effect_claim} (${proposal.effect_status}); rerank eligible: ${proposal.rerank_eligible}`);
    L.push(`- Notes: ${proposal.review_notes}`);
  }
  L.push('', '## References');
  inv.citations.forEach((r) =>
    L.push(`- [${r.citation_id}] ${r.title}${r.page?.pdf_page ? `, PDF p.${r.page.pdf_page}` : ''}. ${r.url ?? ''}`),
  );
  return L.join('\n') + '\n';
}

/** Trigger a browser download of the brief. */
export function downloadBrief(inv: InvestigationResult, proposal?: InterventionProposal | null, concepts?: ConceptSet | null): void {
  const blob = new Blob([renderBrief(inv, proposal, concepts)], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `brief_${inv.corridor_id}.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
