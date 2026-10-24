import type { Feature, FeatureCollection, Geometry, LineString, Polygon } from 'geojson';

export type EvidenceOrigin = 'observed' | 'published_model' | 'computed' | 'assumed' | 'mock';

export interface Provenance {
  origin: EvidenceOrigin;
  source_id: string;
  source_name: string;
  source_url: string;
  retrieved_at?: string;
  period?: string;
  limitations: string[];
}

export interface FloodScenario {
  scenario_id: string;
  label: string;
  scenario_type: 'observed_historical' | 'published_future_model' | 'illustrative';
  horizon_year: number | null;
  annual_exceedance_probability: number | null;
  depth_status: 'available' | 'unknown';
  status_note: string;
  provenance: Provenance;
}

export interface RoadProperties {
  road_id: string;
  corridor_id: string;
  name: string;
  exposure: 'exposed' | 'not_exposed' | 'unknown';
  passability: 'potentially_closed' | 'unknown' | 'assumed_open';
  depth_m: number | null;
  data_status: EvidenceOrigin;
}

export type RoadFeature = Feature<LineString, RoadProperties>;

export interface FloodExposureResult {
  scenario_id: string;
  graph_version: string;
  scenario_type: FloodScenario['scenario_type'];
  extent_geojson: FeatureCollection<Polygon>;
  roads_geojson: FeatureCollection<LineString, RoadProperties>;
  affected_roads: Array<{
    road_id: string;
    exposure: RoadProperties['exposure'];
    depth_m: number | null;
    passability: RoadProperties['passability'];
    passability_basis: string;
    provenance: Provenance;
  }>;
  provenance: Provenance;
  processing_notes: string[];
}

export interface RankingRow {
  corridor_id: string;
  road_ids: string[];
  label: string;
  priority_rank: number;
  impact_value: number | null;
  impact_units: string;
  affected_journey_ids: string[];
  detour_or_disconnection_evidence: string[];
  assumptions: string[];
  provenance: Provenance;
}

export interface RoadRankingResult {
  scenario_set_id: string;
  graph_version: string;
  ranking: RankingRow[];
}

export interface NetworkAssumptionForReview {
  intervention_id: string;
  graph_version: string;
  scenario_ids: string[];
  hypothetical_preserved_road_ids: string[];
  selection_status: 'draft' | 'explicitly_selected_for_counterfactual';
  assumption_notes: string[];
}

export interface CounterfactualResult {
  graph_version: string;
  intervention_id: string;
  scenario_set_id: string;
  before_ranking: RoadRankingResult;
  after_ranking: RoadRankingResult;
  accessibility_change: { value: number | null; units: string };
  assumptions: string[];
  provenance: Provenance;
}

export interface ConceptIntervention {
  intervention_id: string;
  linked_investigation_id?: string;
  corridor_id?: string;
  graph_version: string;
  intervention_type: 'raised_roadway' | 'floodwall' | 'berm' | 'deployable_barrier' | 'drainage_upgrade' | 'alternate_access';
  target_asset_type: 'road' | 'shoreline' | 'catch_basin' | 'outfall' | 'pipe' | 'catchment' | 'opening' | 'other';
  geometry?: Geometry;
  geometry_status: 'sourced_design_alignment' | 'sourced_asset_location' | 'schematic' | 'none';
  geometry_source_ids: string[];
  visual_parameters?: { conceptual_height_m?: number; absolute_crest_elevation_m?: number; vertical_datum?: string; footprint_width_m?: number };
  related_road_ids: string[];
  evidence_source_ids: string[];
  missing_engineering_inputs: string[];
  status: 'conceptual' | 'engineer_reviewed' | 'implemented' | 'verified';
  provenance: 'published_option' | 'derived_concept' | 'illustrative';
  label: string;
  description: string;
  source_url: string;
}

export interface InvestigationResult {
  investigation_id: string;
  corridor_id: string;
  road_ids: string[];
  summary: string;
  possible_mechanisms: string[];
  candidate_methods: Array<{ method: string; evidence: string; source_url: string }>;
  unknown_site_constraints: string[];
  caveats: string[];
  provenance: EvidenceOrigin;
}

export interface JourneyFeatureProperties {
  journey_id: string;
  label: string;
  state: 'baseline' | 'disrupted';
  status: 'available' | 'detour' | 'unreachable';
  provenance: EvidenceOrigin;
}

export type JourneyFeature = Feature<LineString, JourneyFeatureProperties>;

export interface AppDataset {
  scenario: FloodScenario;
  exposure: FloodExposureResult;
  ranking: RoadRankingResult;
  counterfactual: CounterfactualResult;
  concept: ConceptIntervention;
  investigation: InvestigationResult;
  journeys: FeatureCollection<LineString, JourneyFeatureProperties>;
}

export interface HistoricalGaugeSeries {
  event_id: string;
  station_id: string;
  station_name: string;
  longitude: number;
  latitude: number;
  parameter: string;
  unit: string;
  datum: string;
  time_zone: string;
  source_url: string;
  observations: Array<{ timestamp: string; value: number; quality: 'verified' | 'unknown' }>;
  limitations: string[];
}

export interface HistoricalRoadEvent {
  event_id: string;
  label: string;
  date_label: string;
  summary: string;
  footprint: FeatureCollection<Polygon>;
  affected_road_ids: string[];
  gauge: HistoricalGaugeSeries;
  source_url: string;
  status: 'observed_peak_evidence';
  limitations: string[];
}

export interface HistoricalExperienceDataset {
  graph_version: string;
  roads: FeatureCollection<LineString, RoadProperties>;
  buildings: FeatureCollection<Polygon>;
  ranking: RoadRankingResult;
  concept: ConceptIntervention;
  investigation: InvestigationResult;
  events: HistoricalRoadEvent[];
}
