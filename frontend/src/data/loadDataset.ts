import type { FeatureCollection, LineString, Polygon } from 'geojson';
import type { AppDataset, FloodExposureResult, Provenance, RoadProperties, RoadRankingResult } from '../domain/contracts';

const assert: (condition: unknown, message: string) => asserts condition = (condition, message) => {
  if (!condition) throw new Error(`Dataset validation failed: ${message}`);
};

export async function loadAppDataset(): Promise<AppDataset> {
  const [appResponse, extentResponse, exposureResponse, roadsResponse] = await Promise.all([
    fetch('/data/app-dataset.json'),
    fetch('/data/mcfrm_2050_1pct_morrissey.geojson'),
    fetch('/data/flood_exposure_mcfrm_2050_1pct.json'),
    fetch('/data/morrissey_roads.geojson'),
  ]);
  for (const response of [appResponse, extentResponse, exposureResponse, roadsResponse]) {
    if (!response.ok) throw new Error(`Could not load ${response.url} (${response.status})`);
  }

  const value = (await appResponse.json()) as AppDataset;
  const extent = (await extentResponse.json()) as FeatureCollection<Polygon>;
  const officialExposure = (await exposureResponse.json()) as {
    scenario_id: string;
    graph_version: string;
    affected_roads: Array<{
      road_id: string;
      corridor_id: string;
      exposure: RoadProperties['exposure'];
      depth_m: number | null;
      passability: RoadProperties['passability'];
      passability_basis: string;
      source_id: string;
    }>;
    provenance: {
      origin: 'published_model';
      source_id: string;
      source_url: string;
      publisher_attribution: string;
      limitations: string[];
    };
  };
  const fixtureRoads = (await roadsResponse.json()) as FeatureCollection<LineString, { road_id: string; corridor_id: string; name: string; data_status: 'mock' }>;
  const exposureByRoad = new Map(officialExposure.affected_roads.map((road) => [road.road_id, road]));
  const officialProvenance: Provenance = {
    origin: 'published_model',
    source_id: officialExposure.provenance.source_id,
    source_name: 'Massachusetts Coast Flood Risk Model · Woods Hole Group',
    source_url: officialExposure.provenance.source_url,
    retrieved_at: '2026-10-24',
    period: '2050 planning horizon · 1% annual exceedance probability',
    limitations: officialExposure.provenance.limitations,
  };

  value.scenario = {
    scenario_id: officialExposure.scenario_id,
    label: 'MC-FRM 2050 · 1% annual exceedance',
    scenario_type: 'published_future_model',
    horizon_year: 2050,
    annual_exceedance_probability: 0.01,
    depth_status: 'unknown',
    status_note: 'Official published model extent, bounded to the Morrissey study area. This is a future planning scenario—not a historical event or live forecast.',
    provenance: officialProvenance,
  };

  const roads: FloodExposureResult['roads_geojson'] = {
    type: 'FeatureCollection',
    features: fixtureRoads.features.map((feature) => {
      const joined = exposureByRoad.get(feature.properties.road_id);
      return {
        ...feature,
        properties: {
          ...feature.properties,
          exposure: joined?.exposure ?? 'unknown',
          passability: joined?.passability ?? 'unknown',
          depth_m: joined?.depth_m ?? null,
        },
      };
    }),
  };

  value.exposure = {
    scenario_id: officialExposure.scenario_id,
    graph_version: officialExposure.graph_version,
    scenario_type: 'published_future_model',
    extent_geojson: extent,
    roads_geojson: roads,
    affected_roads: officialExposure.affected_roads.map((road) => ({
      road_id: road.road_id,
      exposure: road.exposure,
      depth_m: road.depth_m,
      passability: road.passability,
      passability_basis: road.passability_basis,
      provenance: { ...officialProvenance, origin: 'computed' },
    })),
    provenance: officialProvenance,
    processing_notes: [
      'ArcGIS envelope query transformed to EPSG:4326 and clipped locally to the study bbox.',
      'Road geometry is a labeled fixture pending Person 1 canonical manifest.',
      'Depth remains null; polygon overlap does not establish passability.',
    ],
  };

  const morrisseyRoadIds = officialExposure.affected_roads.filter((road) => road.corridor_id === 'fixture:morrissey-boulevard').map((road) => road.road_id);
  const inlandRoadIds = officialExposure.affected_roads.filter((road) => road.corridor_id === 'fixture:inland-control').map((road) => road.road_id);
  const remapRanking = (ranking: RoadRankingResult, after = false): RoadRankingResult => {
    const sourceRows = ranking.ranking;
    const morrissey = { ...sourceRows[after ? 1 : 0], corridor_id: 'fixture:morrissey-boulevard', road_ids: morrisseyRoadIds, label: 'Morrissey Boulevard fixture corridor', priority_rank: after ? 2 : 1 };
    const inland = { ...sourceRows[after ? 0 : 1], corridor_id: 'fixture:inland-control', road_ids: inlandRoadIds, label: 'Inland control fixture', priority_rank: after ? 1 : 2 };
    return { ...ranking, scenario_set_id: officialExposure.scenario_id, graph_version: officialExposure.graph_version, ranking: after ? [inland, morrissey] : [morrissey, inland] };
  };

  value.ranking = remapRanking(value.ranking);
  value.counterfactual = {
    ...value.counterfactual,
    graph_version: officialExposure.graph_version,
    scenario_set_id: officialExposure.scenario_id,
    before_ranking: remapRanking(value.counterfactual.before_ranking),
    after_ranking: remapRanking(value.counterfactual.after_ranking, true),
  };
  value.concept = {
    ...value.concept,
    graph_version: officialExposure.graph_version,
    corridor_id: 'fixture:morrissey-boulevard',
    related_road_ids: morrisseyRoadIds,
  };
  value.investigation = {
    ...value.investigation,
    corridor_id: 'fixture:morrissey-boulevard',
    road_ids: morrisseyRoadIds,
  };

  assert(value.scenario?.scenario_id, 'scenario_id is required');
  assert(value.exposure?.scenario_id === value.scenario.scenario_id, 'scenario IDs must match');
  assert(value.exposure?.graph_version === value.ranking?.graph_version, 'exposure and ranking graph_version must match');
  assert(value.concept?.graph_version === value.ranking?.graph_version, 'concept and ranking graph_version must match');
  assert(value.counterfactual?.graph_version === value.ranking?.graph_version, 'counterfactual and ranking graph_version must match');
  assert(value.exposure.extent_geojson?.type === 'FeatureCollection', 'extent must be GeoJSON');
  assert(value.exposure.roads_geojson?.type === 'FeatureCollection', 'roads must be GeoJSON');
  assert(value.ranking.ranking.every((row) => row.road_ids.length > 0), 'rank rows need road IDs');
  assert(value.ranking.ranking.every((row) => row.road_ids.every((roadId) => roads.features.some((road) => road.properties.road_id === roadId))), 'ranking uses road IDs absent from the loaded manifest');
  assert(value.exposure.affected_roads.every((road) => road.depth_m !== undefined), 'unknown depth must be null, never omitted');
  return value;
}
