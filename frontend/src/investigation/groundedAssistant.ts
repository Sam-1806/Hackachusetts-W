// Deterministic, evidence-grounded responder. TypeScript port of
// engineering/floodroute_eng/assistant.py (answer_deterministic). Keep intents in sync.
// Every answer block is built from InvestigationResult fields only.

import type { AnswerBlock, AssistantAnswer, CandidateMethod, EvidenceItem, InvestigationResult } from './types';

const NA = 'not available / requires site survey';

const INTENTS: [string, RegExp][] = [
  ['guarantee', /\b(guarantee|will (it|this) work|fix(ed)? (it|the)|solve|prevent|keep .* open|effective)\b/],
  ['cost', /(\b(costs?|prices?|budget|dollars?|expensive|cheap|estimates?|how much)\b|\$)/],
  ['inspect', /\b(inspect\w*|who owns|owner\w*|which assets?|what should (we|i) check|next (steps?|checks?))\b/],
  ['cause', /\b(caus\w*|why does it flood|root|clog\w*|blocked|catch ?basins?|outfalls?|diagnos\w*|source of (the )?water|where does the water)\b/],
  ['missing', /\b(missing|unknown|survey|data (do we )?need|gaps?|what else)\b/],
  ['method', /\b(rais(e|ed|ing)|elevat\w*|berm|deployable|temporary barrier|drain\w*|backflow|tide gate|detour|alternate|seawall)\b/],
  ['candidates', /\b(options?|measures?|recommend\w*|what (can|could|should)|solutions?|interventions?|investigate)\b/],
  ['network', /\b(why|priorit\w*|rank\w*|important|journeys?|access|hospital|fire|reachable)\b/],
  ['flood', /\b(flood\w*|water|depth|scenario|surge|storm|2018|2050|historic\w*|inundat\w*)\b/],
  ['road', /\b(road facts?|width|lanes?|surface|material|pavement|traffic|aadt|jurisdiction|made of)\b/],
  ['precedent', /\b(precedent|study|plan(ned)?|morrissey|massdot|dcr|proposal)\b/],
  ['sources', /\b(sources?|references?|citations?|documents?|links?)\b/],
];

const METHOD_KEYWORDS: [string, RegExp][] = [
  ['raised_roadway', /rais|elevat/],
  ['vegetated_berm', /berm|embankment/],
  ['deployable_barrier', /deployable|temporary/],
  ['drainage_backflow', /drain|backflow|tide gate|pump/],
  ['alternate_access', /detour|alternate/],
  ['seawall_extension', /seawall/],
];

export const SUGGESTED_QUESTIONS = [
  'Why is this corridor a priority?',
  'What might be causing the flooding?',
  'What should be inspected, and who owns it?',
  'What flood evidence do we have?',
  'What options could we investigate?',
  'What do published costs look like?',
  'What site information is missing?',
];

const b = (kind: AnswerBlock['kind'], text: string, citation_ids: string[] = []): AnswerBlock => ({
  kind,
  text,
  citation_ids,
});

export function classify(question: string): string {
  const q = question.toLowerCase();
  for (const [intent, pat] of INTENTS) if (pat.test(q)) return intent;
  return 'overview';
}

const mentionedMethod = (question: string): string | null => {
  const q = question.toLowerCase();
  return METHOD_KEYWORDS.find(([, pat]) => pat.test(q))?.[0] ?? null;
};

const fmtUsd = (v: number) => (v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : `$${v.toLocaleString('en-US')}`);

const MOCK_LABELS: [string, string][] = [
  ['road_ids', 'corridor road IDs'],
  ['flood_exposure', 'flood exposure'],
  ['network_impact', 'network ranking'],
];

/** Names of inputs still marked mock, in a fixed order. */
export function mockParts(inv: InvestigationResult): string[] {
  const st = inv.provenance.input_data_status;
  return MOCK_LABELS.filter(([k]) => JSON.stringify(st[k] ?? null).includes('mock')).map(([, label]) => label);
}

export function isMock(inv: InvestigationResult): boolean {
  return mockParts(inv).length > 0;
}

function network(inv: InvestigationResult): AnswerBlock[] {
  const n = inv.network_impact;
  if (n.status !== 'available') return [b('unknown', 'No network ranking record is available for this corridor yet.')];
  const of = n.candidates_total ? ` of ${n.candidates_total} candidates` : '';
  const out = [
    b(
      'sourced',
      `Priority rank ${n.priority_rank}${of} with impact ${n.impact_metric} ${n.metric_units} across ${n.journeys_total} representative journeys.`,
      ['network_impact'],
    ),
    ...(n.evidence_text ?? []).slice(0, 2).map((t) => b('sourced', t, ['network_impact'])),
  ];
  for (const j of n.affected_journeys ?? []) {
    out.push(
      j.reachable
        ? b('sourced', `${j.label}: ${j.baseline_s} s normal vs ${j.flooded_s} s flooded.`, ['network_impact'])
        : b('sourced', `${j.label}: unreachable in the flood scenario (baseline ${j.baseline_s} s).`, ['network_impact']),
    );
  }
  const exp = n.detour_or_disconnect_evidence?.detour_flood_exposure;
  if (!exp || exp === 'unknown')
    out.push(
      b('unknown', 'Whether the detour route itself floods in this scenario: not available (needs flood exposure for the detour roads).'),
    );
  return out;
}

function flood(inv: InvestigationResult): AnswerBlock[] {
  const out: AnswerBlock[] = [];
  for (const f of inv.flood_evidence) {
    const kind =
      f.kind === 'future_model' ? 'Projected scenario' : f.kind === 'historical_observed' ? 'Observed historical event' : 'Scenario';
    out.push(
      b(
        'sourced',
        `${kind} '${f.label}': ${f.roads_exposed.length} corridor roads exposed, ${f.roads_unknown.length} unknown (data status: ${f.data_status}).`,
        f.citation_ids,
      ),
    );
    if (f.depth_m.status !== 'reported') out.push(b('unknown', `Flood depth at the road for ${f.scenario_id}: ${NA}.`));
    out.push(b('caveat', f.caveat));
  }
  return out.length ? out : [b('unknown', 'No flood evidence is attached to this corridor.')];
}

export function formatFactValue(e: InvestigationResult['road_facts']['summary'][string]): string {
  if (e.status === 'not_available') return NA;
  if (e.range) {
    const [lo, hi] = e.range;
    return (lo === hi ? `${lo}` : `${lo}-${hi}`) + (e.unit ? ` ${e.unit}` : '');
  }
  return e.distinct_values?.join(', ') ?? String(e.value);
}

function road(inv: InvestigationResult): AnswerBlock[] {
  const rf = inv.road_facts;
  const out = Object.values(rf.summary).map((e) =>
    e.status === 'not_available'
      ? b('unknown', `${e.label}: ${NA}.`)
      : b('sourced', `${e.label}: ${formatFactValue(e)}${e.note ? ` (${e.note})` : ''}.`, rf.citation_ids),
  );
  if (rf.unmatched_road_ids.length) out.push(b('unknown', `No inventory match for roads ${rf.unmatched_road_ids.join(', ')}.`));
  return out;
}

function citeFor(inv: InvestigationResult, ev: EvidenceItem): string[] {
  const ids = new Set(inv.citations.map((c) => c.citation_id));
  const paged = ev.pdf_page ? `${ev.source_id}#p${ev.pdf_page}` : null;
  if (paged && ids.has(paged)) return [paged];
  return ids.has(ev.source_id) ? [ev.source_id] : [];
}

function evBlock(inv: InvestigationResult, ev: EvidenceItem, prefix = ''): AnswerBlock {
  const cites = citeFor(inv, ev);
  const text = `${prefix}[${ev.evidence_type.replace(/_/g, ' ')}] ${ev.summary}`;
  if (ev.data_status === 'mock') return b('caveat', `${text} (mock fixture value)`);
  return cites.length ? b('sourced', text, cites) : b('unknown', `${text} (source not resolvable)`);
}

function cause(inv: InvestigationResult): AnswerBlock[] {
  const d = inv.cause_assessment;
  if (!d) return [b('unknown', 'No cause assessment is attached to this corridor; the cause of flooding is not established.')];
  const evs = new Map(d.evidence.map((e) => [e.evidence_id, e]));
  const out = [b('caveat', d.finding), b('caveat', d.impacted_location_note)];
  for (const c of d.possible_causes) {
    if (c.mechanism === 'multiple_or_unknown') {
      out.push(b('hypothesis', `${c.label}: ${c.status}. ${c.status_basis}`));
      continue;
    }
    if (c.status === 'unresolved') {
      out.push(b('unknown', `${c.label}: unresolved. Needs: ${c.unknowns.slice(0, 2).join('; ')}.`));
      continue;
    }
    out.push(b('hypothesis', `Possibly ${c.label.toLowerCase()} (${c.status.replace(/_/g, ' ')}). ${c.status_basis}`));
    c.supporting_evidence_ids.slice(0, 2).forEach((id) => out.push(evBlock(inv, evs.get(id)!, 'Supports: ')));
    c.counter_evidence_ids.slice(0, 1).forEach((id) => out.push(evBlock(inv, evs.get(id)!, 'Against: ')));
    out.push(b('caveat', `Does not prove it: ${c.does_not_prove}`));
    out.push(b('unknown', `Missing: ${c.unknowns.slice(0, 2).join('; ')}.`));
  }
  return out;
}

function inspect(inv: InvestigationResult): AnswerBlock[] {
  const d = inv.cause_assessment;
  if (!d) return [b('unknown', 'No cause assessment is attached; assets to inspect are not identified.')];
  const evs = new Map(d.evidence.map((e) => [e.evidence_id, e]));
  const out = [b('caveat', d.impacted_location_note)];
  const byType = new Map<string, typeof d.assets_to_investigate>();
  for (const a of d.assets_to_investigate)
    if (a.role === 'possible_cause_asset') byType.set(a.asset_type, [...(byType.get(a.asset_type) ?? []), a]);
  for (const [t, items] of byType) {
    const knownOwner = [...new Set(items.map((a) => a.owner).filter((o): o is string => !!o))].sort();
    const owner = knownOwner.length ? `owner as mapped (unverified): ${knownOwner.join(', ')}` : 'owner: unknown';
    const locs = items.slice(0, 2).map((a) => (a.asset_id ? `${a.asset_id} at ` : '') + (a.location_ref ?? ''));
    const evIds = [...new Set(items.flatMap((a) => a.evidence_ids))].sort();
    const cites = [...new Set(evIds.filter((e) => evs.has(e)).flatMap((e) => citeFor(inv, evs.get(e)!)))].sort();
    const sourced = knownOwner.length > 0 && cites.length > 0;
    const count = t === 'catch_basin' ? (d.assets_note ?? '').replace(/\.$/, '') : `${items.length} listed`;
    const title = t.replace(/_/g, ' ').replace(/\b\w/g, (ch) => ch.toUpperCase());
    out.push(b(sourced ? 'sourced' : 'unknown', `${title} (${count}; ${owner}): ${locs.join('; ')}.`, sourced ? cites : []));
  }
  if (d.owner_note) {
    const cb = d.evidence.filter((e) => e.source_id === 'BWSC.cb');
    out.push(b(cb.length ? 'sourced' : 'caveat', d.owner_note, cb.length ? citeFor(inv, cb[0]) : []));
  }
  const ref = d.evidence.find((e) => e.evidence_id.startsWith('ev-311ref-'));
  if (ref) out.push(evBlock(inv, ref));
  out.push(b('hypothesis', `Next checks: ${d.recommended_next_checks.join('; ')}.`));
  return out;
}

function methodBlocks(m: CandidateMethod): AnswerBlock[] {
  const out = [b('hypothesis', `Candidate to investigate: ${m.name}. ${m.summary}`)];
  if (m.cause_gate) out.push(b('caveat', `Cause check: ${m.cause_gate}`));
  m.sourced_points.forEach((p) => out.push(b('sourced', p.text, p.citation_ids)));
  m.hypotheses.forEach((h) => out.push(b('hypothesis', h)));
  const unknown = m.screening.filter((c) => c.status === 'unknown').map((c) => c.check);
  if (unknown.length) out.push(b('unknown', `Needed before screening further: ${unknown.join('; ')}.`));
  out.push(b('hypothesis', `Ways it could fail: ${m.failure_modes.join('; ')}.`));
  return out;
}

function candidates(inv: InvestigationResult): AnswerBlock[] {
  const out = [
    b('caveat', `${inv.candidate_methods.length} methods to evaluate, not a recommended fix. A licensed engineer must review.`),
  ];
  if (inv.cause_assessment)
    out.push(b('caveat', `Cause not established. Start with: ${inv.cause_assessment.recommended_next_checks.slice(0, 3).join('; ')}.`));
  for (const m of inv.candidate_methods) {
    out.push(b('hypothesis', `${m.name}: ${m.summary}`));
    if (m.cause_gate) out.push(b('caveat', `Cause check: ${m.cause_gate}`));
    const first = m.sourced_points[0];
    if (first) out.push(b('sourced', first.text, first.citation_ids));
    out.push(b('hypothesis', `Could fail by: ${m.failure_modes[0].toLowerCase()}.`));
  }
  for (const o of inv.other_methods_considered ?? []) out.push(b('caveat', `Not offered: ${o.name} (${o.reason})`));
  return out;
}

function method(inv: InvestigationResult, question: string): AnswerBlock[] {
  const mid = mentionedMethod(question);
  if (mid) {
    const m = inv.candidate_methods.find((c) => c.method_id === mid);
    if (m) return methodBlocks(m);
    const other = inv.other_methods_considered?.find((o) => o.method_id === mid);
    if (other?.details)
      return [b('caveat', `Not in the top candidates (${other.reason}), but it passed screening.`), ...methodBlocks(other.details)];
    if (other) return [b('caveat', `${other.name} is not among the current candidates: ${other.reason}`)];
  }
  return candidates(inv);
}

function cost(inv: InvestigationResult, question: string): AnswerBlock[] {
  const c = inv.published_cost_examples;
  const d = inv.cause_assessment;
  if (d && /drain|clean|catch ?basin|inlet|pipe|outfall|tide gate|cctv|maint/.test(question.toLowerCase())) {
    const out = [
      b(
        'unknown',
        'cost_estimate_unavailable: no published cost example in the evidence set for drainage, maintenance or outfall work. The 2018 barrier/raised-road samples do not apply.',
      ),
    ];
    for (const a of d.cause_matched_actions)
      if (a.cost_status === 'cost_estimate_unavailable' && a.mechanism !== 'coastal_overland')
        out.push(b('hypothesis', `${a.name}: inputs needed for a quote: ${(a.quote_inputs ?? []).join(', ')}.`));
    return out;
  }
  const mid = mentionedMethod(question);
  const examples = mid ? c.examples.filter((e) => e.method_id === mid) : c.examples;
  if (mid && !examples.length)
    return [
      b('unknown', `No published cost example in the evidence set for ${mid.replace(/_/g, ' ')}.`),
      b('hypothesis', c.estimating_method_guidance[1]),
    ];
  const out = c.caveats.slice(0, 2).map((cav) => b('caveat', cav));
  for (const e of examples) {
    out.push(
      b(
        'sourced',
        `${e.title}: ${fmtUsd(e.total_usd)} for a ${e.sample_dimensions.length_ft.toLocaleString('en-US')}-ft sample ` +
        `(${fmtUsd(e.unit_cost.usd)} per ${e.unit_cost.per}, ${e.contingency}). Excludes: ${e.excluded.slice(0, 4).join(', ')}.`,
        e.citation_ids,
      ),
    );
  }
  if (!mid)
    c.methods_without_cost_precedent.forEach((m) =>
      out.push(b('unknown', `No published cost example in the evidence set for ${m.replace(/_/g, ' ')}.`)),
    );
  out.push(b('unknown', 'Site-specific cost for this corridor: not estimated (separate engineering task).'));
  out.push(b('hypothesis', c.estimating_method_guidance[1]));
  return out;
}

const missing = (inv: InvestigationResult) =>
  inv.missing_site_information.map((m) => b('unknown', `${m.item}: ${m.status}. ${m.why_needed}`));

function precedent(inv: InvestigationResult): AnswerBlock[] {
  if (!inv.local_precedents.length) return [b('unknown', 'No local study precedent in the evidence set for this corridor.')];
  return [
    ...inv.local_precedents.map((p) => b('sourced', `[${p.status.replace(/_/g, ' ')}] ${p.text}`, p.citation_ids)),
    b('caveat', 'Study findings are not evidence that a measure is approved, funded, or built.'),
  ];
}

const sources = (inv: InvestigationResult) =>
  inv.citations.map((c) =>
    b('sourced', `${c.title}${c.page?.pdf_page ? `, PDF p.${c.page.pdf_page}` : ''}: ${c.url ?? 'internal record'}`, [c.citation_id]),
  );

function guarantee(question: string): AnswerBlock[] {
  const head = b('caveat', 'This tool cannot say whether a measure would keep the road open. No hydraulic or structural analysis was run.');
  const tail = b('unknown', 'Physical effectiveness: requires engineering design and modelling.');
  if (/drain|catch ?basin|inlet|outfall|pipe|clog|tide gate/.test(question.toLowerCase()))
    return [
      head,
      b(
        'caveat',
        'Fixing a drain is recorded as an unquantified hydraulic_or_drainage proposal. It does not mark this road or nearby properties safe, and does not change exposure or ranking, until validated before/after flood analysis is supplied.',
      ),
      b(
        'hypothesis',
        'Confirm the cause first (inspect inlets, trace the outfall and owner), then record the proposal; attach hazard_update_evidence once a before/after analysis exists.',
      ),
      tail,
    ];
  return [
    head,
    b(
      'hypothesis',
      'You can record a hypothetical access_only proposal; the network model then assumes the corridor is passable in the scenarios you pick and reranks other corridors. That shows the value IF it worked.',
    ),
    tail,
  ];
}

const overview = (inv: InvestigationResult): AnswerBlock[] => [
  ...network(inv).slice(0, 1),
  ...flood(inv).slice(0, 1),
  ...(inv.cause_assessment ? [b('caveat', inv.cause_assessment.finding)] : []),
  b('hypothesis', `Candidate methods: ${inv.candidate_methods.map((m) => m.name).join(', ')}.`),
  b('unknown', `${inv.missing_site_information.length} site facts are missing; ask 'what is missing?'.`),
];

export function answerDeterministic(inv: InvestigationResult, question: string): AssistantAnswer {
  const intent = classify(question);
  const handlers: Record<string, () => AnswerBlock[]> = {
    network: () => network(inv),
    flood: () => flood(inv),
    road: () => road(inv),
    candidates: () => candidates(inv),
    method: () => method(inv, question),
    cost: () => cost(inv, question),
    missing: () => missing(inv),
    precedent: () => precedent(inv),
    sources: () => sources(inv),
    guarantee: () => guarantee(question),
    cause: () => cause(inv),
    inspect: () => inspect(inv),
    overview: () => overview(inv),
  };
  const parts = mockParts(inv);
  const mockCaveat = parts.length
    ? [b('caveat', `Mock inputs for this corridor: ${parts.join(', ')}; treat those numbers as placeholders.`)]
    : [];
  return {
    question,
    intent,
    mode: 'deterministic',
    blocks: [...mockCaveat, ...handlers[intent]()],
    suggested_followups: SUGGESTED_QUESTIONS.filter((f) => classify(f) !== intent).slice(0, 3),
  };
}

/** Reject remote answers that cite unknown sources or make uncited "sourced" claims. */
export function isGroundedAnswer(ans: AssistantAnswer, inv: InvestigationResult): boolean {
  const allowed = new Set([...inv.citations.map((c) => c.citation_id), 'network_impact']);
  const kinds = new Set(['sourced', 'hypothesis', 'unknown', 'caveat']);
  return (
    Array.isArray(ans.blocks) &&
    ans.blocks.length > 0 &&
    ans.blocks.every(
      (blk) =>
        kinds.has(blk.kind) &&
        Array.isArray(blk.citation_ids) &&
        blk.citation_ids.every((c) => allowed.has(c)) &&
        (blk.kind !== 'sourced' || blk.citation_ids.length > 0),
    )
  );
}
