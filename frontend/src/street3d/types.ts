import type { ConceptIntervention, FloodMapLayer, MapSelection, RoadMapLayer, SceneObject } from '../map/types';

/** Shape of `frontend/public/scene/<id>/manifest.json` (see analysis/scene/build_bpda_scene.py). */
export interface StreetSceneManifest {
  scene_id: string;
  title: string;
  frame: {
    description: string;
    origin_boston3d_ft: [number, number];
    origin_epsg2249_ft: [number, number];
    source_crs: string;
    vertical_datum: 'NAVD88';
    units: 'metres';
    bounds_xz: [number, number, number, number];
    geo: {
      lonlat_to_xz: { x: [number, number, number]; z: [number, number, number] };
      xz_to_lonlat: { lon: [number, number, number]; lat: [number, number, number] };
      max_residual_m: number;
      note: string;
    };
  };
  heightfield: {
    file: string;
    encoding: string;
    width: number;
    height: number;
    resolution_m: number;
    origin_xz: [number, number];
    source: string;
  };
  layers: {
    terrain: { file: string; textures: Record<string, string>; status: 'official' };
    buildings: { file: string; records: string; count: number; status: 'official' };
    streets: { file: string; status: 'official'; display_offsets_m: Record<string, number> } | null;
    props: { file: string; status: 'illustrative' } | null;
  };
  tiles: string[];
  sources: Array<{ id: string; name: string; url: string; license?: string }>;
  limitations: string[];
}

export interface BuildingRecord {
  feature_id: number;
  model_id: string;
  name: string | null;
  struct_type: string;
  status: string;
  lod: string;
  model_credit: string | null;
  survey_source: string | null;
  survey_date: string | null;
  ground_elevation_ft_navd88: number | null;
  height_ft: number | null;
  tile_id: string;
  parcel_id: string | null;
  centroid: [number, number];
  base_m: number;
  top_m: number;
}

export interface StreetPropsFile {
  provenance: 'illustrative';
  note: string;
  /** [x, y, z, heading] */
  streetlights: Array<[number, number, number, number]>;
  /** [x, y, z, scale] */
  street_trees: Array<[number, number, number, number]>;
  park_trees: Array<[number, number, number, number]>;
  /** [x, y, z, heading, colourIndex] */
  parked_cars: Array<[number, number, number, number, number]>;
}

/** Water presentation for the 3D street scene. Levels are metres NAVD88. */
export interface StreetWater {
  /** Sourced footprint (e.g. USGS estimated peak extent). */
  flood: FloodMapLayer | null;
  /** Peak water-surface elevation reported with the footprint, if any. */
  peakSurfaceM: number | null;
  /** Level actually drawn this frame (gauge-driven during replay, otherwise the peak). */
  displayedLevelM: number | null;
  /** Harbour level drawn outside the footprint. */
  harbourLevelM: number;
  mode: 'none' | 'peak' | 'gauge_replay';
}

export type CameraPreset = 'aerial' | 'corridor' | 'street' | 'concept';

export interface StreetSceneProps {
  manifestUrl: string;
  roads: RoadMapLayer;
  selectedRoadIds: string[];
  corridorLabel: string;
  water: StreetWater;
  interventions: ConceptIntervention[];
  selectedInterventionId?: string | null;
  sceneObjects?: SceneObject[];
  /** Changing this asks the camera to move; the value itself selects the framing. */
  cameraRequest?: { preset: CameraPreset; nonce: number };
  onSelection?: (selection: MapSelection) => void;
  /** Called when the user asks to leave the 3D scene because the corridor is outside the loaded tiles. */
  onOutsideCoverage?: () => void;
  /** When false the scene stays mounted but stops rendering (e.g. while the city overview is shown). */
  active?: boolean;
  className?: string;
}
