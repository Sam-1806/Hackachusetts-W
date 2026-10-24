import booleanIntersects from '@turf/boolean-intersects';
import type { FeatureCollection, LineString, Polygon } from 'geojson';
import type {
  AppDataset,
  HistoricalExperienceDataset,
  HistoricalGaugeSeries,
  HistoricalRoadEvent,
  RoadProperties,
} from '../domain/contracts';

const getJson = async <T,>(path: string): Promise<T> => {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Could not load ${path} (${response.status})`);
  return response.json() as Promise<T>;
};

export async function loadHistoricalExperience(): Promise<HistoricalExperienceDataset> {
  const [fixtures, roadSource, january, march, gaugeSource, buildings] = await Promise.all([
    getJson<AppDataset>('/data/app-dataset.json'),
    getJson<FeatureCollection<LineString, { road_id: string; corridor_id: string; name: string; data_status: 'mock' }> & { graph_version: string }>('/data/morrissey_roads.geojson'),
    getJson<FeatureCollection<Polygon>>('/data/usgs_2018_01_04_morrissey.geojson'),
    getJson<FeatureCollection<Polygon>>('/data/usgs_2018_03_02_morrissey.geojson'),
    getJson<{ series: HistoricalGaugeSeries[] }>('/data/noaa_boston_2018_hourly.json'),
    getJson<FeatureCollection<Polygon>>('/data/boston_buildings_morrissey.geojson'),
  ]);

  const eventInputs = [
    {
      event_id: 'usgs-2018-01-04',
      label: 'January 2018 nor’easter',
      date_label: 'January 4, 2018',
      summary: 'USGS estimated peak inundation from high-water marks and storm sensors. NOAA Boston recorded its highest observed water level on this date.',
      footprint: january,
    },
    {
      event_id: 'usgs-2018-03-02',
      label: 'March 2018 nor’easter',
      date_label: 'March 2–4, 2018',
      summary: 'USGS estimated peak inundation for the long-duration March nor’easter using high-water marks and storm-sensor evidence.',
      footprint: march,
    },
  ];

  const roads: HistoricalExperienceDataset['roads'] = {
    type: 'FeatureCollection',
    features: roadSource.features.map((feature) => ({
      ...feature,
      properties: {
        ...feature.properties,
        exposure: 'unknown',
        passability: 'unknown',
        depth_m: null,
      } satisfies RoadProperties,
    })),
  };

  const events: HistoricalRoadEvent[] = eventInputs.map((input) => {
    const gauge = gaugeSource.series.find((series) => series.event_id === input.event_id);
    if (!gauge) throw new Error(`Missing NOAA gauge series for ${input.event_id}`);
    return {
      ...input,
      affected_road_ids: roads.features
        .filter((road) => input.footprint.features.some((polygon) => booleanIntersects(road, polygon)))
        .map((road) => road.properties.road_id),
      gauge,
      source_url: 'https://data.usgs.gov/datacatalog/data/USGS:60100f99d34e162231fecfa8',
      status: 'observed_peak_evidence',
      limitations: [
        'The footprint is an estimated event peak, not a time-resolved hydraulic result.',
        'NOAA gauge levels describe Boston Harbor, not water depth on this road.',
        'Road passability, local velocity, and flow direction remain unknown.',
      ],
    };
  });

  const morrisseyRoadIds = roads.features.filter((road) => road.properties.corridor_id === 'fixture:morrissey-boulevard').map((road) => road.properties.road_id);
  const inlandRoadIds = roads.features.filter((road) => road.properties.corridor_id === 'fixture:inland-control').map((road) => road.properties.road_id);
  const ranking = {
    ...fixtures.ranking,
    scenario_set_id: 'historical-events-through-2018',
    graph_version: roadSource.graph_version,
    ranking: [
      {
        ...fixtures.ranking.ranking[0],
        corridor_id: 'fixture:morrissey-boulevard',
        road_ids: morrisseyRoadIds,
        label: 'Morrissey Boulevard',
        assumptions: ['Mock priority supplied only until Person 1 connects the network-ranking output.'],
      },
      {
        ...fixtures.ranking.ranking[1],
        corridor_id: 'fixture:inland-control',
        road_ids: inlandRoadIds,
        label: 'Inland control corridor',
        assumptions: ['Mock comparison corridor; no historical footprint overlap in this bounded test.'],
      },
    ],
  };

  return {
    graph_version: roadSource.graph_version,
    roads,
    buildings,
    ranking,
    concept: {
      ...fixtures.concept,
      graph_version: roadSource.graph_version,
      corridor_id: 'fixture:morrissey-boulevard',
      related_road_ids: morrisseyRoadIds,
    },
    investigation: {
      ...fixtures.investigation,
      corridor_id: 'fixture:morrissey-boulevard',
      road_ids: morrisseyRoadIds,
    },
    events,
  };
}
