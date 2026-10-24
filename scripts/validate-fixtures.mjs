import { readFile } from 'node:fs/promises';

const readJson = async (name) => JSON.parse(await readFile(new URL(`../frontend/public/data/${name}`, import.meta.url), 'utf8'));
const [data, officialExtent, officialExposure, roads, january, march, gauges, buildings] = await Promise.all([
  readJson('app-dataset.json'),
  readJson('mcfrm_2050_1pct_morrissey.geojson'),
  readJson('flood_exposure_mcfrm_2050_1pct.json'),
  readJson('morrissey_roads.geojson'),
  readJson('usgs_2018_01_04_morrissey.geojson'),
  readJson('usgs_2018_03_02_morrissey.geojson'),
  readJson('noaa_boston_2018_hourly.json'),
  readJson('boston_buildings_morrissey.geojson'),
]);
const errors = [];
const check = (condition, message) => { if (!condition) errors.push(message); };

check(data.scenario.scenario_id === data.exposure.scenario_id, 'scenario ID mismatch');
check(data.exposure.graph_version === data.ranking.graph_version, 'graph version mismatch');
check(data.concept.graph_version === data.ranking.graph_version, 'concept graph version mismatch');
check(data.counterfactual.graph_version === data.ranking.graph_version, 'counterfactual graph version mismatch');
check(data.exposure.extent_geojson.type === 'FeatureCollection', 'extent is not GeoJSON');
check(data.exposure.roads_geojson.features.every((feature) => feature.properties.depth_m !== undefined), 'all road depths must be null or numeric');
check(data.exposure.affected_roads.every((road) => road.depth_m !== undefined), 'all exposure depths must be null or numeric');
check(data.ranking.ranking.every((row) => row.provenance.origin), 'ranking provenance missing');
check(data.concept.geometry_status === 'schematic' || data.concept.geometry_source_ids.length > 0, 'sourced geometry needs a source');
check(data.concept.related_road_ids.every((id) => data.exposure.roads_geojson.features.some((road) => road.properties.road_id === id)), 'concept uses an unknown road ID');
check(officialExtent.type === 'FeatureCollection' && officialExtent.features.length > 0, 'official MC-FRM clip is empty');
check(officialExtent.features.every((feature) => feature.properties.scenario_id === 'mcfrm-2050-1pct'), 'official extent scenario mismatch');
check(officialExtent.features.every((feature) => feature.properties.data_status === 'published_model'), 'official extent status missing');
check(officialExposure.scenario_id === 'mcfrm-2050-1pct', 'official exposure scenario mismatch');
check(officialExposure.graph_version === roads.graph_version, 'hazard output and road fixture graph versions differ');
check(officialExposure.affected_roads.every((road) => road.depth_m === null), 'depth must remain null without an authoritative depth layer');
check(officialExposure.affected_roads.every((road) => road.passability === 'unknown'), 'extent overlap must not establish passability');
check(officialExposure.affected_roads.every((road) => roads.features.some((feature) => feature.properties.road_id === road.road_id)), 'hazard output includes an unknown road ID');
for (const event of [january, march]) {
  check(event.type === 'FeatureCollection' && event.features.length > 0, 'historical USGS footprint is empty');
  check(event.features.every((feature) => feature.properties.data_status === 'observed_event_estimated_peak_extent'), 'historical footprint status missing');
  check(event.features.every((feature) => feature.properties.peak_wse_ft_navd88 !== undefined), 'historical footprint WSE provenance missing');
}
check(gauges.series.length === 2, 'expected two historical NOAA gauge series');
check(gauges.series.every((series) => series.station_id === '8443970' && series.datum === 'NAVD88'), 'NOAA gauge station or datum mismatch');
check(gauges.series.every((series) => series.observations.length >= 72), 'NOAA hourly gauge series is incomplete');
check(buildings.type === 'FeatureCollection' && buildings.features.length > 300, 'Boston building subset is missing or unexpectedly small');

if (errors.length) {
  console.error(errors.map((error) => `- ${error}`).join('\n'));
  process.exit(1);
}
console.log(`Adapters valid: 2 USGS historical footprints, ${gauges.series.reduce((sum, series) => sum + series.observations.length, 0)} NOAA hourly observations, ${buildings.features.length} Boston buildings, and ${data.ranking.ranking.length} ranking-fixture rows.`);
