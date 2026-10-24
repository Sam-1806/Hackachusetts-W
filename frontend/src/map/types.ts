import type { Feature, FeatureCollection, Geometry, Position as GeoJsonPosition } from 'geojson';

export type Position2D = [longitude: number, latitude: number];
export type Position3D = [longitude: number, latitude: number, heightMeters: number];
export type Position = GeoJsonPosition;
export type MapGeometry = Geometry;
export type MapFeature = Feature<Geometry>;
export type MapFeatureCollection = FeatureCollection<Geometry>;

export type EvidenceStatus =
  | 'observed'
  | 'published_model'
  | 'computed'
  | 'assumed'
  | 'mock';

export interface FloodMapLayer {
  scenarioId: string;
  label: string;
  data: MapFeatureCollection;
  status: 'observed' | 'published_model' | 'mock';
  sourceUrl?: string;
  sourceLabel?: string;
  limitations?: string[];
}

export interface RoadMapLayer {
  graphVersion: string;
  data: MapFeatureCollection;
  roadIdProperty?: string;
  exposedRoadIds?: string[];
  selectedRoadId?: string | null;
  /** All canonical road IDs of the selected corridor (highlighted together). */
  selectedRoadIds?: string[];
  /** Fly the camera to the selected corridor whenever the selection changes. */
  focusSelected?: boolean;
}

export interface BuildingMapLayer {
  data: MapFeatureCollection;
  status: 'official' | 'mock';
  heightProperty?: string;
  heightUnits?: 'feet' | 'meters';
  sourceUrl?: string;
}

export interface SceneObject {
  id: string;
  label: string;
  position: Position3D;
  kind: 'fire_station' | 'gauge' | 'vehicle' | 'site_marker';
  provenance: 'official' | 'illustrative';
  sourceUrl?: string;
}

export interface RouteMapLine {
  routeId: string;
  label: string;
  coordinates: Position[];
  kind: 'baseline' | 'disrupted' | 'counterfactual';
  provenance: 'computed' | 'assumed' | 'mock';
}

export type GeometryStatus =
  | 'sourced_design_alignment'
  | 'sourced_asset_location'
  | 'schematic'
  | 'none';

export interface ConceptIntervention {
  intervention_id: string;
  linked_investigation_id?: string;
  corridor_id?: string;
  graph_version: string;
  intervention_type:
    | 'raised_roadway'
    | 'floodwall'
    | 'berm'
    | 'deployable_barrier'
    | 'drainage_upgrade'
    | 'alternate_access';
  target_asset_type:
    | 'road'
    | 'shoreline'
    | 'catch_basin'
    | 'outfall'
    | 'pipe'
    | 'catchment'
    | 'opening'
    | 'other';
  geometry?: MapGeometry;
  geometry_status: GeometryStatus;
  geometry_source_ids: string[];
  visual_parameters?: {
    conceptual_height_m?: number;
    absolute_crest_elevation_m?: number;
    vertical_datum?: string;
    footprint_width_m?: number;
  };
  related_road_ids: string[];
  evidence_source_ids: string[];
  missing_engineering_inputs: string[];
  status: 'conceptual' | 'engineer_reviewed' | 'implemented' | 'verified';
  provenance: 'published_option' | 'derived_concept' | 'illustrative';
  label?: string;
};

export interface MapLayerVisibility {
  flood: boolean;
  roads: boolean;
  routes: boolean;
  interventions: boolean;
  buildings: boolean;
}

export interface MapSelection {
  kind: 'road' | 'intervention';
  id: string;
}
