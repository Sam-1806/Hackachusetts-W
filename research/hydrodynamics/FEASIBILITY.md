# Boston time-resolved hydrodynamics feasibility

**Checked:** 2026-10-24  
**Target:** Morrissey Boulevard study bbox `[-71.065, 42.29, -71.035, 42.335]`  
**Conclusion:** NOAA STOFS-3D-Atlantic is the only examined source with immediately downloadable hourly fields. It supports a credible **archived model-guidance replay**, but not an observed or building-scale historical reconstruction. BWSC and public MC-FRM products expose scenario summaries, not raw time steps.

## Recommended near-term evidence stack

1. Use NOAA's observed Boston gauge record as the historical clock and observed point evidence.
2. If a moving spatial layer is useful, use the normalized STOFS subset delivered here and label it `archived operational forecast guidance` on every frame.
3. Do not show velocity arrows yet. The downloadable velocity files are native full-domain NetCDFs of about 13 GB per component/day; no public Boston subset endpoint was found.
4. Do not call the STOFS animation a reconstruction, observation, or street-level depth replay. Its audited local mesh is approximately 139–603 m per edge (median 280 m), so it cannot resolve buildings, lanes, drains, or local barriers.

## 1. NOAA STOFS-3D-Atlantic

### Working archive and selected event

NOAA's public data documentation and bucket:

- Documentation: <https://noaa-nos-stofs3d-pds.s3.amazonaws.com/README.html>
- Bucket prefix: `s3://noaa-nos-stofs3d-pds/STOFS-3D-Atl/`
- Selected run: `STOFS-3D-Atl/stofs_3d_atl.20240113/` initialized at 2024-01-13 12:00 UTC.
- Historical context: NOAA station 8443970 lists the January 13–14 East Coast winter storm among Boston's largest observed levels: <https://tidesandcurrents.noaa.gov/inundationdb/inundation.html?action=&bdate=20240111&datum=MHHW&edate=20240115&id=8443970&timezone=GMT&units=standard>
- Exact observed gauge API used for context: <https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_level&application=FloodRoute&begin_date=20240113%2012:00&end_date=20240113%2020:00&datum=NAVD&station=8443970&time_zone=gmt&units=metric&format=json>

The gauge query returned 81 verified six-minute values. In that query window the maximum is 2.713 m NAVD88 at 16:48 UTC. This is a point observation at station 8443970, not road depth.

### Exact objects and coverage

Hourly disturbance polygons are directly downloadable. Examples used for the delivered subset:

- `STOFS-3D-Atl/stofs_3d_atl.20240113/stofs_3d_atl.t12z.disturbance.f001.gpkg` — 68,124,672 bytes; valid 13:00 UTC
- `STOFS-3D-Atl/stofs_3d_atl.20240113/stofs_3d_atl.t12z.disturbance.f004.gpkg` — 77,078,528 bytes; valid 16:00 UTC
- `STOFS-3D-Atl/stofs_3d_atl.20240113/stofs_3d_atl.t12z.disturbance.f007.gpkg` — 68,452,352 bytes; valid 19:00 UTC

Direct URL pattern:

```text
https://noaa-nos-stofs3d-pds.s3.amazonaws.com/STOFS-3D-Atl/stofs_3d_atl.20240113/stofs_3d_atl.t12z.disturbance.fHHH.gpkg
```

For this 2024 run, the bucket contains 24 hourly nowcast files (`n023` through `n000`) and 48 forecast files (`f001` through `f048`). Current NOAA documentation describes up to 96 forecast hours; archive contents vary by model version/date.

The GeoPackage layer is `disturbance`, EPSG:4326 multipolygons with fields:

```text
id, minWaterLevel, maxWaterLevel, verticalDatum, units, rgba
```

For the inspected files the datum is `NAVD88`, units are meters, and output is distributed as 0.1 m water-level bands. NOAA defines disturbance as water above ground where topobathy is above the reference surface, and as water-surface elevation above xGEOID20B over water. Therefore it is not uniformly a land flood-depth field.

Native full-field objects for the selected run include:

- `stofs_3d_atl.t12z.f001_024.field2d.nc` — 5,719,268,177 bytes
- `stofs_3d_atl.t12z.fields.out2d_forecast_day1.nc` — 2,988,894,195 bytes
- `stofs_3d_atl.t12z.fields.horizontalVelX_forecast_day1.nc` — 12,995,055,529 bytes
- `stofs_3d_atl.t12z.fields.horizontalVelY_forecast_day1.nc` — 12,995,055,529 bytes
- `schout_adcirc_20240113.nc` — 1,719,069,804 bytes

These native files are the route to water-level and velocity vectors, but they require staged full-file or range-aware NetCDF/HDF5 processing plus mesh subsetting. NOAA documents no Boston-specific OPeNDAP or server-side spatial-subset service for this bucket.

### Actual Boston mesh audit

The January 2024 run uses STOFS v1.1. The public mesh is:

```text
s3://noaa-nos-stofs3d-pds/STOFS-3D-Atl/staticfiles/v1.1/stofs_3d_atl_hgrid.ll
```

The file declares 2,654,153 nodes and 5,137,229 elements. A direct connectivity audit of the Morrissey bbox found:

| Metric | Value |
|---|---:|
| Nodes inside bbox | 138 |
| Elements with at least one node in bbox | 301 |
| Unique audited edges | 475 |
| Minimum edge | 138.7 m |
| 10th percentile | 220.2 m |
| Median edge | 280.3 m |
| 90th percentile | 394.5 m |
| Maximum edge | 603.3 m |

This is suitable for harbor/neighborhood-scale guidance, not water moving around individual OSM buildings or along a particular lane.

The audit is reproducible with `research/hydrodynamics/audit_stofs_mesh.py` against the public `stofs_3d_atl_hgrid.ll` file.

### Delivered normalized subset

- Extractor: `research/hydrodynamics/extract_stofs_disturbance.py`
- Output: `results/hydrodynamics/stofs_20240113_boston_disturbance.json`
- Observed gauge normalizer: `research/hydrodynamics/normalize_noaa_gauge.py`
- Observed gauge output: `results/hydrodynamics/noaa_8443970_20240113_water_level.json`
- STOFS subset size: about 30 KB
- Frames: 13:00, 16:00, and 19:00 UTC
- Rendering: for each frame, replace a Cesium `GeoJsonDataSource` containing the provided water-level bands. Color/opacity may follow `max_water_level_m`, but the legend must state `archived STOFS forecast guidance; NAVD88; not observed road depth`.

The normalized subset is useful because it provides genuine time-varying model geometry. It is not sufficient for flow arrows because the GeoPackages contain no velocity field. The separate NOAA gauge sidecar contains 81 verified six-minute observations for a timestamped graph; it is deliberately not embedded as spatial flood depth.

Reproduction:

```bash
aws s3 cp s3://noaa-nos-stofs3d-pds/STOFS-3D-Atl/stofs_3d_atl.20240113/stofs_3d_atl.t12z.disturbance.f001.gpkg /tmp/f001.gpkg --no-sign-request
aws s3 cp s3://noaa-nos-stofs3d-pds/STOFS-3D-Atl/stofs_3d_atl.20240113/stofs_3d_atl.t12z.disturbance.f004.gpkg /tmp/f004.gpkg --no-sign-request
aws s3 cp s3://noaa-nos-stofs3d-pds/STOFS-3D-Atl/stofs_3d_atl.20240113/stofs_3d_atl.t12z.disturbance.f007.gpkg /tmp/f007.gpkg --no-sign-request

curl -fsSL 'https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_level&application=FloodRoute&begin_date=20240113%2012:00&end_date=20240113%2020:00&datum=NAVD&station=8443970&time_zone=gmt&units=metric&format=json' \
  --output /tmp/noaa-8443970.json

python3 research/hydrodynamics/extract_stofs_disturbance.py \
  /tmp/f001.gpkg /tmp/f004.gpkg /tmp/f007.gpkg \
  --output results/hydrodynamics/stofs_20240113_boston_disturbance.json

python3 research/hydrodynamics/normalize_noaa_gauge.py \
  /tmp/noaa-8443970.json \
  --output results/hydrodynamics/noaa_8443970_20240113_water_level.json
```

## 2. Boston Water and Sewer Commission

Primary pages:

- Model description: <https://www.bwsc.org/boston-inundation-model>
- Current viewer: <https://www.bwscstormviewer.com/stormapp>
- Limitations: <https://www.bwscstormviewer.com/disclaimers>
- Technical context: <https://www.bwsc.org/sites/default/files/2023-02/BWSC%20Coastal%20Stormwater%20Discharge%20Analysis%20-%20Final%20Report.pdf>

BWSC describes a 2D PCSWMM model capable of predicting flood extent/duration, but the public viewer does not expose the raw hydraulic time series or velocity output. It consumes public ArcGIS **cached tiled map services** for predefined future scenarios and separate 360-degree rendered images.

One exact public current-scenario example:

```text
Web map item: b58a4a735e874983a62d3e05f1edaf5a
https://www.arcgis.com/sharing/rest/content/items/b58a4a735e874983a62d3e05f1edaf5a

Map service:
https://tiles.arcgis.com/tiles/Pn95KPPz613AKHXi/arcgis/rest/services/Noreaster_50yrRP_100YrSS_2030SLR_2025/MapServer
```

Its advertised capabilities are `Map,TilesOnly,Tilemap`; it is a single fused PNG32 cache and reports `exportTilesAllowed: false`. No queryable depth values, time dimension, velocity layer, NetCDF, or raw PCSWMM result download is exposed. BWSC could potentially supply raw results by request, but the public viewer cannot currently support a physical replay.

## 3. Massachusetts MC-FRM

Primary sources:

- State viewer description: <https://www.mass.gov/info-details/massachusetts-sea-level-rise-and-coastal-flooding-viewer>
- Official FAQ: <https://www.mass.gov/doc/mc-frm-faq/download>
- Public download description: <https://www.woodsholegroup.com/innovation/massachusetts-coast-flood-risk-model/>

The underlying coupled model is dynamic and can calculate currents and flood duration. However, the public products listed for download are summary GIS layers:

- Level 1 annual exceedance probability, selected flood depths, and extents
- Level 2 water-surface elevation, maximum wave height, design/wave-action elevation, tidal benchmarks, and special-zone hatching

The inspected ArcGIS service similarly publishes summary scenario layers. No raw event time steps, velocity vectors, or historical-event hindcast series were found in the public product catalog. Underlying capability must not be presented as public data availability.

## 4. SFINCS fallback

SFINCS is a credible fallback for a small, explicitly modeled historical reconstruction, not a quick source of observed data.

- Official repository: <https://github.com/Deltares/SFINCS>
- Forcing documentation: <https://sfincs.readthedocs.io/en/latest/input_forcing.html>
- Output/parameter documentation: <https://sfincs.readthedocs.io/en/latest/parameters.html>

A defensible Morrissey setup would require:

1. A datum-consistent high-resolution DEM/topobathymetry and explicit building/road/barrier treatment.
2. Observed NOAA 8443970 boundary water levels and appropriate offshore/spatial boundary assumptions.
3. Rainfall, infiltration/roughness, initial conditions, and ideally drainage/outfall representation for compound flooding.
4. Calibration/validation against independent USGS high-water marks or observed flood extents.
5. Sensitivity tests for grid resolution, friction, structures, drainage omissions, and datum conversion.

SFINCS can output time-varying water levels/depths and velocity/flux fields suitable for Cesium raster tiles, contour polygons, or sampled vector arrows. Until calibrated, the UI may call it a `model reconstruction under stated inputs`; it may not call it observed historical flow.

## Scientifically supportable UI claims

Safe:

- “Observed Boston Harbor gauge level at this timestamp.”
- “Archived STOFS forecast guidance initialized during the January 13, 2024 event.”
- “Model water-level disturbance band, NAVD88, on an approximately 280 m median local mesh.”
- “The animation shows model evolution at hourly steps; it is not observed street-level water movement.”

Not supported:

- Measured water depth on Morrissey Boulevard from STOFS or the gauge.
- Water flowing around an individual building, vehicle, wall, or drain.
- Accurate street-level velocity/direction from the delivered GeoPackage subset.
- Calling BWSC/MC-FRM public summary maps a time-resolved historical replay.
- Claiming any physical intervention changes the archived flood fields.

