# FloodRoute / ResilienceOS

FloodRoute is a historical-first Boston flood-road investigation prototype:

**mock road ranking → documented past flood events → evidence replay → focused 3D road investigation.**

The app opens in a **3D street scene** (React Three Fiber) built from the City's official BPDA 3D model around Morrissey Boulevard / Columbia Point. A **City overview** (CesiumJS) is one click away in the header for citywide context.

> Planning prototype only — not for live emergency routing or construction decisions.

## Run locally

Requirements: Node 20+ and Python 3.10+.

```bash
npm install
npm run dev
```

Open the URL printed by Vite. If port 5173 is occupied:

```bash
npm run dev -- --port 4317 --strictPort
```

A Cesium ion token is optional. Without one, the investigation uses locally loaded City of Boston building footprints and a token-free map fallback. With a token, Cesium terrain and OSM Buildings are available:

```bash
cp .env.example .env
# Set VITE_CESIUM_ION_TOKEN in .env, then restart the server.
```

## Manual demo

1. Open the app. It lands in the **3D street scene** and flies to **#1 Morrissey Boulevard** (highlighted with an amber chevron ribbon).
2. Explore: drag to orbit, right-drag to pan, scroll to zoom, **W/A/S/D** to move, **Q/E** for height. Camera presets: **Aerial · Corridor · Street level**. Click any building for its official BPDA record.
3. Select the **January 2018 nor’easter** (or March 2018) under Past floods. The USGS estimated peak footprint is drawn as water at the USGS reported peak water-surface elevation (9.2 ft / 2.80 m NAVD88); footprint-overlap road segments turn orange.
4. Click **Replay flood evidence**. The water level follows the observed NOAA Boston gauge, capped at that peak and clipped to the footprint. Use play/pause, the slider, or **Peak**. Click **Street-level view** to stand on the inundated boulevard.
5. Click **Continue to road investigation → Preview 3D concept** to fly to the schematic shoreline berm (volumetric mesh with a violet “concept” hologram). The water is unchanged.
6. Switch to **City overview** in the header to see the selected corridor highlighted and framed in Cesium. Selecting a road in the ranking highlights and flies to it in either view. **#2 Inland control corridor** is outside the loaded 3D tiles, so the 3D view offers the city overview instead.

For direct replay inspection:

```text
http://localhost:5173/?replay=usgs-2018-01-04
```

## Evidence status

| Element | Status | Meaning |
|---|---|---|
| January 4 and March 2–4, 2018 footprints | **USGS event evidence** | Estimated peak inundation polygons derived from high-water marks and storm sensors, clipped around Morrissey Boulevard. They are not time-resolved water fields. |
| Boston tide timeline | **Observed NOAA data** | Verified hourly heights at station 8443970 in meters NAVD88. A harbor gauge is not road water depth. |
| 3D terrain, buildings, streets | **Official BPDA 3D Smart Model** | Tiles BOS_I_7 and BOS_I_8 (PDDL): 2011 terrain TIN + 2011 planimetric groundplan texture, 4,929 current building/wall/dock models (CyberCity3D / pbcGIS, LOD 1–3), and groundplan road, sidewalk, parking and pavement-marking polygons draped on the terrain. |
| Facade windows, curb height, road display offsets | **Stylised** | Shader-derived windows and a 0.17 m curb are visual conventions, not surveyed. |
| Trees, streetlights, parked and moving cars | **Illustrative** | Placed along official sidewalk/parking/open-space polygons; no inventory was loaded. Moving cars hold position rather than drive into displayed water — not a passability claim. |
| 3D water surface | **USGS footprint + reported WSE** | Drawn only inside the USGS footprint or official hydrography, at the USGS peak WSE (or, during replay, the observed NOAA gauge level capped at that WSE). Water colour = displayed level minus 2011 terrain: a visual cue, not measured depth. The 2011 terrain has no bathymetry (open water is a flat ~0.4 m fill), so the harbour surface is never drawn below that fill; only the footprint-on-land water rises and recedes with the gauge. |
| Local buildings (city overview) | **Official City of Boston geometry** | 419 footprint records with published height attributes, extruded in the Cesium overview. |
| Fire station | **Official Boston point** | Engine 17 / Ladder 7 from the Boston fire-station GIS layer. |
| Response vehicle and investigation marker | **Illustrative props** | Georeferenced scene objects for orientation, clearly labeled illustrative. |
| Gauge-driven water level | **Illustrative animation** | Hourly NOAA gauge heights (linearly interpolated for display, default 1 h = 4 s), capped at the USGS peak WSE. Inside the footprint, water spreads from the harbour only through terrain below the displayed level (a priority-flood “connected bathtub” over the 2011 terrain); pockets not connected below the peak appear when the reported peak is reached. It does not claim measured flood progression, flow direction, velocity, drainage pathways or timing on the street. |
| Road ranking and road geometry | **Mock fixtures** | Person 1’s canonical manifest and computed ranking are not present yet. The Morrissey fixture centreline (`hazard-fixture-morrissey-v2`) follows the median of OpenStreetMap’s primary carriageways (ODbL); road IDs are unchanged from v1. |
| Engineering concept | **Mock / schematic fixture** | A source-grounded intervention type on an unverified alignment, rendered as a volumetric berm 1.8 m above local grade (schematic display height, not a design crest). It has no claimed physical effectiveness. |

Road depth, local velocity, flow direction, and passability remain unknown.

## Verify

```bash
npm test
python3 -m unittest discover -s analysis/hazard/tests -v
python3 research/hydrodynamics/validate_subset.py
python3 -m py_compile \
  analysis/historical/convert_usgs_2018.py \
  analysis/historical/normalize_noaa_gauge.py \
  analysis/scene/build_bpda_scene.py \
  analysis/scene/validate_scene.py \
  analysis/hazard/refine_fixture_centerline.py
npm run build
```

Cesium is code-split into its own chunk and only loads when the city overview is opened; Vite still reports a chunk-size warning without failing the build.

## 3D street scene data (BPDA 3D Smart Model)

`analysis/scene/build_bpda_scene.py` downloads the official BPDA tiles (terrain OBJ, building OBJ collection, groundplan DXF; ~58 MB, cached in `analysis/scene/.cache/`, git-ignored) and writes browser assets to `frontend/public/scene/morrissey/`:

| File | Content |
|---|---|
| `terrain.glb` + `groundplan_*.jpg` | Official 2011 terrain TIN with the official 2011 groundplan texture |
| `buildings.glb` + `buildings.json` | Merged current building models with per-model BPDA attributes |
| `streets.glb` | Road, sidewalk (+ curbs), parking, driveway, marking and hydrography meshes |
| `heightfield.bin` | 2 m terrain grid (metres NAVD88) for draping, water depth cues and camera collision |
| `props.json` | Illustrative tree / streetlight / parked-car anchors |
| `manifest.json` | Frame definition, lon/lat ↔ local affine, sources, licence and limitations |

Coordinates: BPDA local feet = EPSG:2249 (ftUS) minus the documented origin (731,100 ; 2,902,900); heights NAVD88 feet. The scene uses local metres (x east, y up, z = −north). The lon/lat transform is an affine fit to pyproj with a 0.17 m maximum residual over the scene.

```bash
python3 -m venv .venv && .venv/bin/pip install -r analysis/scene/requirements.txt
.venv/bin/python analysis/scene/build_bpda_scene.py            # ~1 min after download
.venv/bin/python analysis/scene/validate_scene.py              # alignment checks
python3 analysis/hazard/refine_fixture_centerline.py            # Morrissey fixture from the saved OSM extract
```

Add coverage with `--tiles BOS_H_7,BOS_H_8,BOS_I_7,BOS_I_8` (tile IDs from the BPDA tile-grid service). Validation results for the shipped scene: City of Boston footprints land a median 1.6 m from BPDA model centroids, and 99%+ of land samples inside each USGS 2018 footprint lie at or below its reported peak WSE (+0.3 m).

## Historical data preparation

The USGS conversion script clips the official Albers-projected shapefiles and transforms them to EPSG:4326:

```bash
python3 -m pip install -r analysis/historical/requirements.txt
python3 analysis/historical/convert_usgs_2018.py EVENT.zip OUTPUT.geojson \
  --event-id EVENT_ID \
  --event-label "Event label" \
  --event-date YYYY-MM-DD \
  --source-url SOURCE_URL
```

Browser-ready artifacts are in `frontend/public/data/`; analysis outputs are preserved under `results/historical/`.

## Hydrodynamic-data finding

The research report at `research/hydrodynamics/FEASIBILITY.md` found one downloadable time-varying source: archived NOAA STOFS-3D-Atlantic operational forecast guidance. A validated three-frame Boston subset is preserved under `results/hydrodynamics/`, but it is not used as an observed 2018 replay:

- It is archived forecast guidance, not observation or hindcast.
- The audited local mesh has a median edge length of about 280 m.
- The downloaded disturbance polygons have no velocity vectors.
- They cannot support water flowing around individual buildings, vehicles, barriers, or road lanes.

BWSC’s public viewer and public MC-FRM products expose scenario summaries rather than downloadable hydraulic time steps. A calibrated local reconstruction would require a separate modeling effort.

## Sources

- [USGS January and March 2018 flood documentation](https://www.usgs.gov/centers/new-england-water-science-center/science/flood-documentation-and-inundation-mapping-january)
- [USGS inundation shapefiles](https://data.usgs.gov/datacatalog/data/USGS:60100f99d34e162231fecfa8)
- [NOAA Boston station 8443970](https://tidesandcurrents.noaa.gov/stationhome.html?id=8443970)
- [City of Boston building layer](https://gisportal.boston.gov/arcgis/rest/services/Assessing/DOIT_buildings/MapServer/2)
- [BPDA 3D Smart Model downloads](https://www.bostonplans.org/3d-data-maps/3d-smart-model/3d-data-download) and [documentation](https://maps.bostonplans.org/3d/3D_Data_Documentation.pdf) (PDDL)
- [OpenStreetMap](https://www.openstreetmap.org/copyright) Morrissey Boulevard ways (ODbL), used only to place the road fixture centreline
- [Boston fire-station layer](https://gisportal.boston.gov/arcgis/rest/services/PublicSafety/OpenData/MapServer/2)
- [NOAA STOFS-3D-Atlantic archive documentation](https://noaa-nos-stofs3d-pds.s3.amazonaws.com/README.html)
