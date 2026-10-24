// Types for the Person 3 investigation module.
// Mirrors engineering/floodroute_eng/investigation.py (schema_version "investigation-v0.1")
// and the InterventionProposal contract. When Person 1 publishes contracts/, re-export from there.

export type DataStatus = 'observed' | 'published_model' | 'derived' | 'mock' | 'assumed' | string;
export type FactStatus = 'observed' | 'not_available';
export type BlockKind = 'sourced' | 'hypothesis' | 'unknown' | 'caveat';

export interface PageRef {
  printed_page: number | null;
  pdf_page: number | null;
}

export interface Citation {
  citation_id: string;
  source_id: string;
  title: string;
  url: string | null;
  page: PageRef | null;
  published?: string | null;
}

export interface RoadFactSummary {
  label: string;
  status: FactStatus;
  value: string | number | null;
  unit?: string | null;
  range?: [number, number];
  distinct_values?: string[];
  segments_total?: number;
  segments_missing?: number;
  note?: string;
  unit_note?: string;
  source_id?: string;
  source_field?: string;
}

export interface RoadFacts {
  summary: Record<string, RoadFactSummary>;
  matched_inventory_segment_ids: string[];
  per_road_match: Record<string, { matched_count: number; best_mean_distance_m: number | null; method: string }>;
  unmatched_road_ids: string[];
  citation_ids: string[];
  snapshot: Record<string, unknown>;
}

export interface FloodEvidence {
  scenario_id: string;
  label: string;
  kind: 'future_model' | 'historical_observed' | 'unknown';
  data_status: DataStatus;
  roads_exposed: string[];
  roads_not_exposed: string[];
  roads_unknown: string[];
  passability: Record<'potentially_closed' | 'unknown' | 'assumed_open', number>;
  depth_m: { min: number | null; max: number | null; status: string };
  basis: string[];
  citation_ids: string[];
  caveat: string;
}

export interface Journey {
  journey_id: string;
  label: string;
  baseline_s: number;
  flooded_s: number | null;
  reachable: boolean;
}

export interface NetworkImpact {
  status: 'available' | 'not_available';
  data_status?: DataStatus;
  priority_rank?: number;
  impact_metric?: number;
  metric_units?: string;
  journeys_total?: number;
  journeys_unreachable?: string[];
  affected_journeys?: Journey[];
  detour_or_disconnect_evidence?: {
    detour_available_for?: string[];
    disconnected?: string[];
    detour_road_names?: string[];
    detour_flood_exposure?: string;
  };
  assumptions?: string[];
  note?: string;
}

export interface ScreeningCheck {
  check: string;
  fact: string;
  status: 'supports' | 'against' | 'unknown';
  value: unknown;
  note: string;
}

export interface CandidateMethod {
  method_id: string;
  name: string;
  category: string;
  summary: string;
  relevance: 'candidate' | 'screened_out';
  screened_out_reason: string | null;
  screening: ScreeningCheck[];
  sourced_points: { text: string; citation_ids: string[] }[];
  hypotheses: string[];
  failure_modes: string[];
  required_data: string[];
  cost_precedent_ids: string[];
  status: 'to_investigate';
  // Causal Diagnosis Addendum (optional, additive)
  addresses_mechanisms?: HypothesizedMechanism[];
  cause_gate?: string;
  cause_relevance?: 'access_only' | 'cause_supported' | 'cause_possible' | 'cause_unresolved';
}

// ---------------------------------------------------------------- Causal Diagnosis Addendum

export type HypothesizedMechanism =
  | 'coastal_overland'
  | 'tidal_outfall_backwater'
  | 'inlet_blockage'
  | 'storm_drain_capacity'
  | 'surface_grading'
  | 'multiple_or_unknown';

export type EvidenceType =
  | 'observed_report'
  | 'observed_measurement'
  | 'published_model'
  | 'gis_derived'
  | 'engineering_record'
  | 'hypothesis'
  | 'unknown';

export interface EvidenceItem {
  evidence_id: string;
  source_id: string;
  url?: string | null;
  evidence_type: EvidenceType;
  summary: string;
  observed_at?: string;
  limitations: string[];
  data_status?: DataStatus;
  distance_to_corridor_m?: number;
  pdf_page?: number;
  [extra: string]: unknown;
}

export interface CauseHypothesis {
  mechanism: HypothesizedMechanism;
  label: string;
  description: string;
  supporting_evidence_ids: string[];
  counter_evidence_ids: string[];
  context_evidence_ids: string[];
  unknowns: string[];
  status: 'possible' | 'evidence_supported' | 'unresolved';
  status_basis: string;
  does_not_prove: string;
}

export interface AssetToInvestigate {
  asset_type: 'road' | 'catch_basin' | 'pipe' | 'outfall' | 'shoreline' | 'pump' | 'catchment' | 'other';
  asset_id?: string | null;
  role: 'impacted_location' | 'possible_cause_asset';
  owner?: string | null;
  owner_status: 'as_mapped_unverified' | 'unknown' | string;
  location_ref?: string;
  evidence_ids: string[];
}

export interface CauseMatchedAction {
  action_id: string;
  name: string;
  kind: 'investigation' | 'maintenance' | 'capital';
  mechanism: HypothesizedMechanism;
  mechanism_status: CauseHypothesis['status'];
  applicable_if: string;
  could_fail: string;
  downstream_checks: string[];
  asset_types: string[];
  source_ids: string[];
  related_method_ids?: string[];
  cost_status: 'cost_estimate_unavailable' | 'published_example_available';
  precedent_ids?: string[];
  quote_inputs?: string[];
  gate: string;
}

export interface DiagnosticAddendum {
  schema_version: string;
  road_ids: string[];
  hotspot_id?: string | null;
  scenario_ids: string[];
  finding: string;
  impacted_location_note: string;
  evidence: EvidenceItem[];
  possible_causes: CauseHypothesis[];
  assets_to_investigate: AssetToInvestigate[];
  assets_note?: string;
  owner_note: string;
  cause_matched_actions: CauseMatchedAction[];
  recommended_next_checks: string[];
  intervention_caveats: string[];
  limitations: string[];
  engineer_review_required: true;
  data_access: Record<string, string | null>;
}

export interface CostExample {
  precedent_id: string;
  method_id: string;
  title: string;
  source_id: string;
  price_basis: string;
  sample_dimensions: { length_ft: number;[k: string]: unknown };
  total_usd: number;
  unit_cost: { usd: number; per: string };
  contingency: string;
  excluded: string[];
  annual_om_usd_range?: [number, number];
  citation_ids: string[];
  transferable: false;
  label: string;
}

export interface InvestigationResult {
  schema_version: string;
  corridor_id: string;
  corridor_name: string;
  road_ids: string[];
  graph_version: string | null;
  road_facts: RoadFacts;
  flood_evidence: FloodEvidence[];
  network_impact: NetworkImpact;
  candidate_methods: CandidateMethod[];
  other_methods_considered: {
    method_id: string;
    name: string;
    relevance: string;
    reason: string;
    details?: CandidateMethod;
  }[];
  published_cost_examples: {
    examples: CostExample[];
    methods_without_cost_precedent: string[];
    caveats: string[];
    estimating_method_guidance: string[];
    site_specific_estimate: { value: null; status: string; note: string };
  };
  local_precedents: { precedent_id: string; status: string; text: string; citation_ids: string[] }[];
  missing_site_information: { item: string; status: string; why_needed: string }[];
  citations: Citation[];
  limitations: string[];
  provenance: {
    generated_at: string;
    evidence_library_version: string;
    input_data_status: Record<string, unknown>;
    generator: string;
  };
  /** Optional cause diagnosis (Causal Diagnosis Addendum). Absent in v0.1 results. */
  cause_assessment?: DiagnosticAddendum;
}

export type InterventionStatus = 'hypothetical' | 'implemented' | 'verified';
export type AssumedPassability = 'assumed_open' | 'unchanged';

export interface InterventionProposal {
  intervention_id: string;
  corridor_id: string;
  road_ids: string[];
  graph_version: string | null;
  proposed_method: { method_id: string; name: string; category: string };
  status: InterventionStatus;
  assumed_passability_by_scenario: Record<string, AssumedPassability>;
  review_notes: string;
  source_ids: string[];
  created_at: string;
  status_evidence?: { source_ids: string[]; reviewer: string };
  // Causal Diagnosis Addendum (optional, additive). Missing effect_claim means 'access_only'.
  effect_claim?: EffectClaim;
  mechanism?: HypothesizedMechanism | null;
  effect_status?: 'idealized_access_assumption' | 'unquantified_proposal' | 'hazard_update_supplied';
  rerank_eligible?: boolean;
  requested_scenarios?: string[];
  hazard_update_evidence?: { source_ids: string[]; description: string };
}

export type EffectClaim = 'access_only' | 'hydraulic_or_drainage';

export interface AnswerBlock {
  kind: BlockKind;
  text: string;
  citation_ids: string[];
}

export interface AssistantAnswer {
  question: string;
  intent: string;
  mode: string;
  blocks: AnswerBlock[];
  suggested_followups: string[];
}

/** Optional remote assistant (e.g. a backend wrapping engineering/floodroute_eng/assistant.py).
 *  Must return citation_ids that exist in the investigation; the UI re-validates and falls back. */
export type RemoteAsk = (question: string, investigation: InvestigationResult) => Promise<AssistantAnswer>;

// ---------------------------------------------------------------- Addendum 2: concept geometry (output 1 of 2)
// Mirrors engineering/floodroute_eng/concepts.py (schema_version "concept-intervention-v0.1").
// Concepts carry NO passability, flood, or ranking effect.

export type GeometryStatus = 'sourced_design_alignment' | 'sourced_asset_location' | 'schematic' | 'none';

export type ConceptGeometry =
  | { type: 'Point'; coordinates: number[] }
  | { type: 'MultiPoint'; coordinates: number[][] }
  | { type: 'LineString'; coordinates: number[][] }
  | { type: 'MultiLineString'; coordinates: number[][][] }
  | { type: 'Polygon'; coordinates: number[][][] };

export interface ConceptIntervention {
  intervention_id: string;
  name: string;
  linked_investigation_id?: string;
  corridor_id?: string;
  graph_version: string | null;
  intervention_type: 'raised_roadway' | 'floodwall' | 'berm' | 'deployable_barrier' | 'drainage_upgrade' | 'alternate_access';
  target_asset_type: 'road' | 'shoreline' | 'catch_basin' | 'outfall' | 'pipe' | 'catchment' | 'opening' | 'other';
  target_asset_id?: string | null;
  target_asset_refs?: { facility_id: string | null; owner_as_mapped: string | null; owner_status: string }[];
  candidate_ref: string;
  geometry: ConceptGeometry | null;
  geometry_status: GeometryStatus;
  geometry_source_ids: string[];
  geometry_note: string;
  display_badge: string;
  visual_parameters?: {
    conceptual_height_m?: number;
    absolute_crest_elevation_m?: number;
    vertical_datum?: string;
    footprint_width_m?: number;
    basis?: string;
    source_id?: string;
  } | null;
  addressed_mechanism_ids: HypothesizedMechanism[];
  mechanism_status: Partial<Record<HypothesizedMechanism, CauseHypothesis['status']>>;
  supporting_evidence_ids: string[];
  conflicting_evidence_ids: string[];
  confirm_with: string[];
  refute_if: string[];
  unresolved_checks: Record<'physical_survey' | 'ownership_check' | 'drainage_assessment' | 'permitting', string>;
  related_road_ids: string[];
  related_road_ids_note: string;
  evidence_source_ids: string[];
  evidence_distinction: { kind: 'published_option' | 'illustrative_concept' | 'existing_asset'; text: string; source_id: string | null }[];
  suitability: string;
  trade_offs: string[];
  missing_engineering_inputs: string[];
  published_cost_precedents: {
    precedent_id: string;
    source_id: string;
    example_scope: string;
    price_year: number;
    price_year_note?: string;
    amount_usd?: number;
    limitations: string[];
  }[];
  cost_status: 'cost_estimate_unavailable' | 'published_example_available';
  status: 'conceptual' | 'engineer_reviewed' | 'implemented' | 'verified';
  provenance: 'published_option' | 'derived_concept' | 'illustrative';
  implied_benefit: 'none';
  display_caveats: string[];
}

export interface ConceptSet {
  schema_version: string;
  corridor_id: string;
  graph_version: string | null;
  generated_at: string;
  featured_intervention_id: string | null;
  featured_reason: string;
  concepts: ConceptIntervention[];
  alternatives_not_rendered: { candidate_ref: string; name: string; intervention_type: string; reason: string }[];
  notes: string[];
}

// ---------------------------------------------------------------- Addendum 2: network what-if (output 2 of 2)
// Mirrors engineering/floodroute_eng/network_assumption.py. A QUESTION to Person 1, not a forecast.

export interface NetworkAssumptionForReview {
  schema_version: string;
  intervention_id: string;
  intervention_type: ConceptIntervention['intervention_type'];
  graph_version: string | null;
  scenario_ids: string[];
  hypothetical_preserved_road_ids: string[];
  selection_status: 'draft' | 'explicitly_selected_for_counterfactual';
  assumption_notes: string[];
  created_at: string;
  rerank_requested: boolean;
  hazard_update_evidence?: { source_ids: string[]; description: string };
}
