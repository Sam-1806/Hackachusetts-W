---
title: "FloodRoute / ResilienceOS — Three-Person Build Plan"
subtitle: "Work ownership, public data, provisional methods, interfaces, and handoff tests"
date: "24 October 2026"
---

# FloodRoute / ResilienceOS — Three-Person Build Plan

**Hackachusetts 2026 · Team handoff · 24 October 2026**  
**Status:** Implementation plan, not a completed or validated geographic model.  
**Companion documents:** `PROJECT_CONTEXT.md` (updated team-build product/context and contracts), `AGENTS.md` (updated coding-agent operating rules), and `FloodRoute_3D_Feasibility_and_Sources.pdf` (original source/risk audit when available). **This document specifies the three-person division of work**; it supersedes the earlier mock-only scope alongside the two updated companion files.

## 1. Product in one minute

**Problem.** Coastal flood maps tell Boston where water may reach, but do not directly tell planners which flooded roads most damage access to hospitals, fire stations, or communities; whether viable detours exist; or which roads deserve engineering investigation first.

**Proposed solution.** Analyze observed historical flood evidence alongside *separately labeled* future flood scenarios. Overlay potential road disruption on a routable street graph. Rank vulnerable **roads or corridors** by how much maintaining access would improve important journeys, including alternatives and demand. For a selected corridor, show the flood evidence and road characteristics; an evidence-grounded engineering copilot proposes options to *investigate*. Finally, allow a planner to **test an assumed protection**, rerun accessibility, and update all priorities. A proposed measure is not a verified physical fix.

**Five-beat live demo:**

1. Open an interactive **3D Boston** scene and choose a real historical-event footprint or published future flood scenario.
2. Show **normal vs flood-affected accessibility** for representative fire/hospital/community journeys.
3. Reveal the **highest-impact bottlenecks**, explaining why missing alternatives matter more than flood exposure alone.
4. Click a corridor to see evidence, road details, candidate measures, reference documents, conceptual cost context, and unknowns.
5. Choose **"assume this corridor remains passable"** and observe graph-based **reranking of the entire candidate set**. Explain that physical effectiveness has not been proven.

**Not the product:** a true real-time ambulance navigator; a live flood-physics engine; a validated road-level historical flow animation; an automated civil engineer; or a site-specific construction cost calculator.

### Ownership at a glance

| Owner | Workstream | Must deliver | Owns integration surface |
|:--|:--|:--|:--|
| **Person 1** | **Road graph, impact ranking, counterfactual reranking** | Connected graph, representative journeys, real computed comparison/ranking, re-ranking under assumed repair | `road_id`, `RoadRankingResult`, `CounterfactualResult` |
| **Person 2** | **Flood evidence, hazard mapping, 3D application and final UI integration** | At least one geographically grounded flood overlay, affected road mapping, responsive 3D UI and clickable story | `FloodExposureResult`, map scene, app composition |
| **Person 3** | **Road facts, engineering evidence, assistant, and investigation UX** | Source-backed corridor investigation with candidate options, caveated cost examples, intervention form | `InvestigationResult`, `InterventionProposal` |

**Coordination:** Person 1 freezes canonical road IDs; Person 2 is the **frontend/integration owner**; Person 3 owns engineering documents and the investigation panel. None needs another person's finished algorithm to begin: each starts from the agreed **fixture JSON** defined below.

---

### Latest scope refinement: diagnosis → physical concept → separate access counterfactual

- **Person 1:** No change in ownership. Receives explicit hypothetical preserved-road IDs per scenario to recompute graph rankings; does **not** infer hydraulic effectiveness from construction geometry. See `FloodRoute_Ranking_Impact_Addendum.md`.
- **Person 2:** In addition to flood surfaces and Cesium integration, owns 3D **visual preview of proposed physical interventions** as independent geometry layers; physical flood surfaces remain the published scenario unless replaced with a separately validated hydraulic result. See `FloodRoute_Simulation_Intervention_Addendum.md`.
- **Person 3:** First assess possible flooding causes and impacted assets (a flooded road is not necessarily the asset to fix). Then output **source-linked, conceptual engineering intervention(s)** with optional physical geometry, unknowns, and dated cost precedent for Person 2's 3D preview. See `FloodRoute_Engineering_Causal_Diagnosis_Addendum.md` (**first addendum**) and `FloodRoute_Engineering_Intervention_Visualization_Addendum.md` (**second addendum**).
- **Avoid shared-file collisions:** Person 1 alone coordinates `contracts/`; Person 2 owns Cesium/intervention map rendering and app composition; Person 3 owns engineering schemas/adapters in `engineering/` and investigation panel. Each builds fixture-compatible outputs independent of the other streams.


## 2. Common data contract — agree before parallel work

**Shared identifiers and conventions**

- `road_id`: stable within a **versioned canonical road manifest** (`graph_version`); never use an unrecorded CSV row number as a permanent ID. The starter Boston street CSV supplies WKT geometry and names but **no canonical unique street-segment ID**. Person 1 generates a manifest; everyone else uses those IDs. A future source remap must be explicit.
- `scenario_id`: for example `usgs-2018-jan-event` (historical evidence) versus `mcfrm-2050-1pct` (future annual-exceedance scenario). Never call a future scenario a past occurrence.
- `facility_id`, `journey_id`, `corridor_id` (one corridor may include multiple directed graph edges), `intervention_id`.
- UI geometry is **GeoJSON EPSG:4326 longitude/latitude**, not projected source geometry. Preserve each dataset's original coordinate reference system separately during analysis. Distances in meters, modeled travel time in seconds, elevations/depths with **explicit datum and units**.
- Every record carries `source_id`, `source_url` or `source_ref`, `data_status` (`observed`, `published_model`, `derived`, `mock`, `assumed`), and an explanation of limitations. Missing depth is `null`, never zero.

**Minimal exchange contracts** (names may be adjusted once, then frozen):

```ts
RoadManifest = { graph_version, roads: GeoJSONFeatureCollection, id_mapping, metadata }
FloodExposureResult = { scenario_id, graph_version, affected_roads: [
  { road_id, exposure: 'exposed'|'not_exposed'|'unknown',
    depth_m?: number|null, passability: 'potentially_closed'|'unknown'|'assumed_open',
    basis: 'official_extent'|'official_depth'|'historical_footprint'|'mock', source_id }
], extent_geojson, provenance }
RoadRankingResult = { scenario_set_id, graph_version, ranking: [
  { corridor_id, road_ids, priority_rank, impact_metric, metric_units,
    affected_journeys, detour_or_disconnect_evidence, assumptions, provenance }
] }
InvestigationResult = { corridor_id, road_ids, road_facts, flood_evidence,
  network_impact, candidate_methods, published_cost_examples,
  missing_site_information, citations, limitations }
InterventionProposal = { intervention_id, corridor_id, road_ids,
  proposed_method, status: 'hypothetical'|'implemented'|'verified',
  assumed_passability_by_scenario, review_notes, source_ids }
CounterfactualResult = { intervention_id, graph_version,
  before_ranking, after_ranking, accessibility_delta, assumptions }
```

**Critical boundary:** the ranking engine consumes **scenario-specific road exposure/passability assumptions**, not raw flood raster files or Cesium entities. The engineering assistant consumes **normalized facts and references**, not internal NetworkX graph objects. React never imports a backend script or raw CSV.

**Repository proposal — file ownership is non-overlapping:**

```text
contracts/                   # Frozen shared JSON schema/TS types — Person 1 creates first
fixtures/                    # Small jointly agreed example, then read-only
analysis/network/            # Person 1: graph, trips, ranking, reranking, CLI/tests
analysis/hazard/             # Person 2: MC-FRM/USGS loaders, CRS, road exposure mapping
frontend/                    # Person 2: Cesium, main panels, composition, deployment
frontend/src/investigation/  # Person 3 only: investigation drawer and chat UI
engineering/                 # Person 3: road facts, evidence index, cost precedents, prompts/tests
data/normalized/roads/       # Person 1: canonical road manifest and ID mapping
results/                     # Contract-compliant JSON outputs, owned by producing stream
```

**One-minute handshake fixture:** Before any external download, agree on **one area** (Morrissey Boulevard as candidate, subject to real flood overlap), **one scenario**, **two or three origin–destination pairs**, **one candidate corridor**, and a 20–50-segment fixture. This lets each stream implement and test independently. The fixture is illustrative and must say so.

---

## 3. Person 1 — Road-network analysis, ranking, reranking

### Mission

Produce a defensible **relative criticality ranking** for exposed roads/corridors based on **loss of access to important destinations and quality of alternatives**, then recompute priorities when an improvement is *assumed* or later verified. This person is accountable for the real quantitative core—not the LLM or 3D appearance.

### Datasets and exact sources

1. **Starter:** `robotics.zip/boston-streets/data.csv` — **19,440** Boston street centerlines; `street`, `speed_mph`, `oneway`, `cost_forward`, `cost_back`, WKT `geometry`. **No stable segment ID**, no guaranteed topology; build a versioned graph and validate directionality. Source: [Boston city SAM network via CKAN](https://data.boston.gov/api/3/action/datastore_search?resource_id=6fa7932b-7bc8-42bc-9250-168d5f5dc1ad&fields=ST_NAME,ST_TYPE,SPEEDLIMIT,ONEWAY,NBHD_L,ZIP_L,FT_COST,TF_COST,Shape_Length,shape_wkt&limit=100). This endpoint's example request returns 100 rows; the ZIP has the larger saved snapshot.
2. **Fallback/richer network:** [MassGIS–MassDOT Roads](https://www.mass.gov/info-details/massgis-data-massgis-massdot-roads). Consider OSMnx/OpenStreetMap if graph topology proves too difficult; log source and version. Do **not** silently mix inconsistent road IDs.
3. **Destination facilities:** [MassGIS Hospitals (August 2026)](https://www.mass.gov/info-details/massgis-data-hospitals) — point coordinates with `EMERGENCY_DEPT` flag and trauma attributes. The starter `healthcare.zip/hospitals/data.csv` has 103 rows but **no coordinates / ED flag**, so is insufficient by itself. [MassGIS Fire Stations](https://www.mass.gov/info-details/massgis-data-fire-stations), [Boston Public Safety GIS, fire departments layer 2](https://gisportal.boston.gov/arcgis/rest/services/PublicSafety/OpenData/MapServer/2).
4. **Service assignments (optional):** [MassGIS Emergency Service Zones](https://www.mass.gov/info-details/massgis-data-emergency-service-zones) — jurisdiction/service areas, **not an ambulance movement feed**.
5. **Demand/context:** `civic.zip/neighborhoods/data.csv` — 24 rows of 2025 neighborhood estimates. **No geographic boundaries in this CSV.** To weight origin points, obtain matching neighborhood polygons or more granular [Census data](https://data.census.gov/) and document how origin demand was assigned.
6. **Scenario closures:** Person 2's `FloodExposureResult`. Work immediately with a mock closure fixture rather than waiting for hazard GIS processing.

### Suggested implementation steps

- Parse streets/WKT; establish directed topology and weight interpretation (`cost_forward`, `cost_back` might already encode routing costs). Audit disconnected components, snap tolerances, bridge/tunnel behavior, and at least a few plausible local trips.
- Select **representative planning journeys** (e.g., a population-weighted neighborhood origin to an emergency department; fire station to a representative incident point). Avoid presenting arbitrary nearest-hospital journeys as clinically appropriate ambulance dispatch.
- Compute baseline accessibility; remove or heavily penalize **potentially impassable edges under explicit scenario assumptions**; recompute routes. Track detour time, distance, and **unreachable** separately. Unreachable must not be silently dropped from the score.
- Evaluate the marginal benefit of preserving **one road/corridor**, where feasible, conditional on all other scenario closures. Check alternate routes and serving multiple facilities automatically. Evaluate **corridor bundles**, since reopening one edge may be useless if adjacent edges remain flooded.
- Rank candidate **investigations**, not declare construction priorities or definitive fixes. Store which journeys and assumptions produced each ranking.
- Accept `InterventionProposal` from Person 3 (or fixture), update the assumed scenario-specific passability in a **sandbox copy** of the graph, and recompute *all* candidate rankings. A saved implemented/verified record requires actual evidence, not just a button click.

### Candidate methods (intentionally provisional)

The first usable metric **could** be population/service-weighted **change in modeled travel time** from baseline to a flood scenario, with an explicit penalty or separate count for inaccessible journeys. For each candidate corridor, **consider** comparing total accessibility loss before and after hypothetically preserving that corridor across relevant scenarios. Scenario weights **might** reflect a curated set of cases or defensible annual probabilities; historical counts and future exceedance probabilities **must not** be combined as if they were the same thing.

A simple prototype can use Dijkstra or A* on a directed NetworkX graph. If runtime allows, test **redundancy** via second-best routes / alternate paths rather than manually giving every road an arbitrary "importance" score. These are proposals to validate, **not a locked formula**. There may be interaction effects: protecting A and B together can have a benefit that neither alone delivers.

### Acceptance criteria

- Real graph builds from a documented input snapshot; ≥3 plausible selected trips produce inspectable baseline paths.
- Under one explicit mock or official flood-closure set, impacted journeys and a **computed**, explainable ranking change.
- A hypothetical intervention changes graph passability and recomputes rankings, **including effects on other corridors**.
- CLI or test harness produces valid `RoadRankingResult` and `CounterfactualResult` JSON using the shared IDs; runs without UI or engineering assistant.
- Unit tests cover an alternate-route example, an isolated neighborhood, and a multi-edge corridor case.

**Defer:** real traffic and signal timing; live dispatch; citywide origin sampling; calibrated monetary loss or mortality forecasts; sophisticated network portfolio optimization.

---

## 4. Person 2 — Flood scenarios, geospatial mapping, 3D demo, integration

### Mission

Ground the scenario in **actual flood geography** and create the central 3D interaction. Produce road exposure records for Person 1, **without implying exact road drivability or historical water-flow vectors**. Own the stitched user experience and final working local app.

### Datasets and exact sources

1. **Published future hazard:** [Massachusetts Sea Level Rise and Coastal Flooding Viewer / MC-FRM](https://www.mass.gov/info-details/massachusetts-sea-level-rise-and-coastal-flooding-viewer). Extents and depths for **2030, 2050, 2070** with specified annual exceedance probability; scenario probability is not a predicted storm date. [MC-FRM technical overview](https://www.mass.gov/doc/climate-resilience-design-standards/download). **Actual depth raster availability/download and licensing must be checked** before claiming precision.
2. **Observed historical event data:** [USGS January & March 2018 inundation shapefiles](https://data.usgs.gov/datacatalog/data/USGS%3A60100f99d34e162231fecfa8), and [USGS 2018 flood documentation](https://www.usgs.gov/centers/new-england-water-science-center/science/flood-documentation-and-inundation-mapping-january). Footprints and high-water marks are **not a continuous high-resolution 3D flow recording**.
3. **Time series for contextual replay:** `climate.zip/tides/data.csv` — **744 hourly readings** in August 2024 at NOAA Boston station 8443970, **meters relative to MLLW**. To replay January 2018, fetch the historical interval from [NOAA CO-OPS API](https://api.tidesandcurrents.noaa.gov/api/prod/) instead of substituting the ZIP's August 2024 values. Gauge water level is **not street-level water depth**.
4. **Terrain:** [MassGIS LiDAR Terrain Data](https://www.mass.gov/info-details/massgis-data-lidar-terrain-data). Road-grade estimates from terrain must handle underpasses, bridges, datum, and survey limitations.
5. **Road geometry:** Person 1's versioned canonical manifest from `robotics.zip/boston-streets`. In parallel, begin 3D work using a small fixture in the same agreed shape.
6. **Renderer:** [CesiumJS](https://cesium.com/platform/cesiumjs/) and streamed OSM/terrain assets when permitted. Cesium ion may need a token and internet; build graceful fallback if absent.

### Suggested implementation steps

- Pick one **demonstrably affected** Boston corridor using public hazard/event geometry, not one selected only because it looks cinematic. Morrissey Boulevard is a plausible candidate, but verify overlap and resulting journeys first.
- Fetch one official flood **extent** and align CRS. Optionally add verified depth data; preserve flood datum metadata. Intersect it with the canonical street graph and return `FloodExposureResult`, including **unknown** passability when depth/road elevation is not enough.
- Build a Cesium scene with buildings, 3D terrain, scenario overlay, road colors, normal-vs-flood route polylines, camera fly-to and selected corridor detail.
- Implement a clearly labeled **visual replay**: for historic events, show observed footprint and measured water-level time series; only animate inferred spatial progression as **illustrative**, never as the exact historical fluid flow, direction, or velocity.
- Compose the ranking table from Person 1 and the engineering drawer from Person 3, initially using fixtures. Ensure clicking a row selects the same `corridor_id` in map and investigation panel.
- Own local run/build, browser smoke test, video/screen-record fallback, and one concise demo script.

### Acceptance criteria

- Runs with `npm install && npm run dev` (or documented equivalent) on a teammate's laptop; map is navigable when Cesium assets load.
- At least one official flood footprint or extent renders in the **correct geographic location**. Mock overlays clearly say mock.
- Exports `FloodExposureResult` keyed to manifest road IDs, or an honest documented blocker; does not claim an extent intersection proves road closure.
- Selecting scenario, road/corridor, rank row, and intervention produces consistent panels; fallback mode works without an external token.
- Historical vs projected events are unmistakably distinguished and source metadata is visible.

**Defer:** GPU fluid dynamics, exact flow direction/time at road level, citywide seamless depth animation, live hazard detections, automatic passability guarantee.

---

## 5. Person 3 — Evidence-grounded engineering recommendations

### Mission

Answer **"what could a civil engineer reasonably investigate at this location, why, and what evidence is missing?"** The assistant supports preliminary investigation, not design certification or site-specific bidding.

### Datasets and exact sources

1. **Physical road attributes:** [Boston MassDOT Road Inventory GIS, layer 14](https://gisportal.boston.gov/arcgis/rest/services/Infrastructure/OpenData/MapServer/14) and [MassGIS–MassDOT Roads](https://www.mass.gov/info-details/massgis-data-massgis-massdot-roads) — available width/surface/class/volume fields should be checked **per record**; do not promise every field is populated. Use Person 1's road IDs and spatial join to source attributes. `robotics.zip/boston-streets` already supplies road names, one-way, speed, costs and WKT.
2. **Ground/structure context:** [MassGIS LiDAR terrain](https://www.mass.gov/info-details/massgis-data-lidar-terrain-data). `robotics.zip/bridges/data.csv` gives **2022** bridge condition summary **without coordinates**; use full FHWA/MassDOT inventory before attaching bridge condition to a particular site.
3. **Intervention methods/cost precedent:** [Boston Climate Resilient Design Guidelines](https://content.boston.gov/departments/public-works/climate-resilient-design-guidelines). They cover vegetated berms, raised seawalls, raised roadways and deployable barriers, including design considerations, operations/maintenance, and **2018 conceptual example costs**. The previously verified examples are roughly **$2.3m for a 2,000-ft sample berm** and **$13.6m for a 2,000-ft sample raised roadway**, not 2026 bids and not universal per-foot prices.
4. **Real local precedent:** [MassDOT Morrissey Boulevard corridor study (June 2025 report)](https://www.mass.gov/doc/morrissey-boulevard-corridor-study-final-report/download), [MassDOT 2025 report announcement](https://www.mass.gov/news/massdot-releases-the-morrissey-boulevard-corridor-study-final-report), [Boston coastal resilience implementation](https://www.boston.gov/departments/climate-resilience/coastal-resilience-implementation). Site plans must be represented accurately; do not claim proposals are approved or built without verification.
5. **Inputs from team:** Person 1's vulnerability record (detours, affected journeys, alternative connectivity) and Person 2's flood/event record (source, extent/depth where available, uncertainty). Start with one fabricated but labeled corridor fixture.

### Suggested implementation steps

- Normalize the source information into a small **cited engineering evidence library**: measure, when potentially applicable, why it might fail, required data, cost-example scope/year, and URL/page if possible.
- Build the **Road Investigation** context object from authoritative road attributes + flood evidence + ranked-network consequences. Keep each field's provenance; omit unavailable facts rather than hallucinating material, water direction, drainage capacity or underground utilities.
- Design an assistant prompt (optionally backed by a live model) that **uses only retrieved/source-linked evidence for factual claims**, separates sourced observations from hypotheses, and always states missing engineering data. A deterministic reference-backed answer is a valid fallback if live LLM integration fails.
- Offer 2–4 candidate **methods to evaluate**, not one guaranteed fix: e.g. road elevation, continuous barrier, deployable measure, drainage/site works, alternate access. Discuss applicability and constraints, avoiding promises that a barrier only at the road protects the network.
- Display **published example cost context** with price year, dimensions, excluded costs, and caveats. Cost estimation for the specific selected road is a separate engineering task. The model may suggest a **preliminary estimating method** but must not invent defensible local numbers.
- Let a planner record an **InterventionProposal** (method, corridor, which scenarios it is *assumed* to withstand, and status). Hand this to Person 1 for **idealized passability counterfactual**; do not modify flood extents or automatically label a road verified/fixed.
- Present a short exportable **engineer review brief**: reason for priority, documented flood exposure, road facts, candidate measures, precedent links, cost caveats, and site investigations needed.

### Acceptance criteria

- One selected corridor returns a useful `InvestigationResult` using actual named official documents, with accessible links and known/unknown separation.
- Missing road materials or depth become **"not available / requires site survey"**, not invented facts.
- Historical construction-price examples identify **2018**, sample dimensions, and non-transferability.
- Assistant or scripted fallback answers questions about the selected corridor, offers candidates, and produces a typed `InterventionProposal`.
- Investigation module runs against **fixture** ranking/flood contexts even if Persons 1–2 aren't finished.

**Defer:** engineering stamping/certification, custom hydraulics, exact site cost bids, open-ended ungrounded agent browsing, claiming physical benefit without a validated model.

---

## 6. Integration plan — minimize cross-team waiting

**Start together (15–25 minutes):** Agree on demo region, 1–2 scenario IDs, 2–3 journeys, one corridor fixture, normalized geometry and units. **Person 1** checks in `contracts/` and initial `road_manifest.geojson`; **Person 2** checks in a standalone 3D scene shell; **Person 3** prepares source-backed engineering fixtures. Freeze contract **v0.1** and record `graph_version`.

| Milestone | Person 1 | Person 2 | Person 3 | Integration test |
|:--|:--|:--|:--|:--|
| **Parallel start** | Build network using synthetic road closures | Load Cesium scene + official extent independently | Curate guidelines + one corridor brief | All 3 render/read the same fixture IDs |
| **First vertical slice** | Computed baseline vs impacted trips | Selected flood footprint and road overlay | Investigation panel with evidence | Select corridor -> matching rank, map, brief |
| **Counterfactual slice** | Recompute rankings after assumed passability change | Animate before/after network state | Emit typed hypothetical intervention | Changing selected measure updates affected rankings |
| **Final check** | Test disconnected journeys / reranking | Run app, screenshots, fallback & demo | Audit citations, costs, unknowns | No unlabeled mock numbers or claims of exact physics |

**Do not wait for a teammate:**

- Ranking works against `fixtures/mock_flood_exposure.json` from minute one.
- Hazard mapping tests can intersect against the frozen `road_manifest.geojson` without any ranking output.
- Engineering research uses `fixtures/sample_corridor_context.json` without running Cesium/NetworkX.
- The frontend consumes source-agnostic adapters; it initially imports validated JSON results, not Python APIs.
- Once official data arrives, replace the fixture producer, not the consuming UI.

**Single integrator:** Person 2 owns app composition and last-mile polish; Person 1 owns data contract changes (must notify everyone); Person 3 owns investigation and source validation. No parallel edits to `App.tsx` or the same CSS/config files.

**Suggested final demo scope:** **one** real area + **one** published future scenario + optionally **one** historical event + **three** representative journeys + **one** reranking counterfactual + **one** sourced investigation. More geographic coverage is a stretch goal, not a prerequisite.

---

## 7. Risks, validation, and what we must not overclaim

| Risk | Severity | Mitigation / owner |
|:--|:--|:--|
| Road source contains WKT but no stable ID; topological gaps | **High** | P1 creates versioned manifest and connectivity tests; consider OSMnx fallback |
| Published flood extent intersects a bridge/tunnel but does not show road drivability | **High** | P2 labels road status *potentially affected*; P1 does sensitivity runs on closures |
| Historical footprints do not show minute-by-minute street flow/depth | **High** | P2 uses honest evidence view + illustrative animation only; do not claim observed velocity vectors |
| 2030/2050/2070 modeled scenarios mistaken for historical flood frequency | **High** | Both scenarios have explicit `data_status`, horizon, annual probability / chosen weight |
| No meaningful emergency detour in selected corridor | **High** | P1 & P2 jointly test actual flood/network overlap before locking demo geography |
| Near-neighbor edges all flood; repairing one road yields no benefit | **Medium** | P1 supports multi-edge **corridor bundles** and checks network interaction effects |
| Road properties (material/width/drainage) absent or dated | **High** | P3 marks missing; joins official layers only when verified |
| LLM invents engineering recommendations or exact costs | **High** | P3 evidence library, links, structured unknowns, safe fallback; human-review framing |
| Simulated project incorrectly treated as physically effective | **High** | `hypothetical` state and scenario-scoped assumed passability; never alter hydrology without model |
| Large depth rasters, CRS and vertical datum mismatches | **High** | P2 begin with vector extents; record datum; optional small clipped raster later |
| Cesium assets/token/network unavailable during pitch | **Medium** | P2 offline graceful fallback + screen recording of golden path |
| Scoring ignores population, alternative routes, or unreachable journeys | **High** | P1 test small counterexamples; show component explanations and limitations |

### Definition of done (minimum defensible end-to-end product)

- [ ] Publicly sourced flood **extent** positioned correctly on real Boston map, **or** transparent fallback labeled mock.
- [ ] Road graph has consistent IDs and at least three validated representative journeys.
- [ ] Rank list is generated by code from scenario-specific graph changes; explains alternate routes, important destinations, and unreachable cases.
- [ ] A hypothetical intervention **changes the graph and produces a new computed ranking**.
- [ ] Engineer sees actual cited design precedents, missing site facts and cost **examples**, not invented construction estimates.
- [ ] Scenarios clearly distinguish historical observed footprints, future models, and visual illustration.
- [ ] UI has a complete clickable route: scenario -> rank -> road detail -> investigation -> assumed intervention -> reranking.
- [ ] Each stream can run and test independently; documented `README` explains real vs mocked elements.

### Two questions to resolve early, not silently assume

1. Does the chosen official flood extent overlap enough routable links to produce a **meaningful accessibility change**? If not, pick a different neighborhood; don't stage a false real-world result.
2. Can the team acquire useful **historical event footprints** for the chosen corridor? If not, focus the actual analysis on MC-FRM scenarios and show 2018 only as regional context.

---

## 8. Source directory — verified documentation, integration not guaranteed

The following public pages/services were checked for **existence and described content** on October 24, 2026. This is **not** proof that every service endpoint has been downloaded, decoded or joined successfully.

| ID | Authority / source | Purpose | URL |
|:--|:--|:--|:--|
| S01 | Starter Robotics / City of Boston SAM | WKT roads, direction/speed/cost | [Boston data API](https://data.boston.gov/api/3/action/datastore_search?resource_id=6fa7932b-7bc8-42bc-9250-168d5f5dc1ad&fields=ST_NAME,ST_TYPE,SPEEDLIMIT,ONEWAY,NBHD_L,ZIP_L,FT_COST,TF_COST,Shape_Length,shape_wkt&limit=100) |
| S02 | MassGIS–MassDOT Roads | Full public roadway network | [MassGIS roads](https://www.mass.gov/info-details/massgis-data-massgis-massdot-roads) |
| S03 | MassGIS Hospitals, updated Aug 2026 | Hospital coordinates, ED and trauma attributes | [MassGIS hospitals](https://www.mass.gov/info-details/massgis-data-hospitals) |
| S04 | MassGIS Fire Stations / Boston Public Safety | Fire response origins | [MassGIS fire stations](https://www.mass.gov/info-details/massgis-data-fire-stations) · [Boston GIS layer](https://gisportal.boston.gov/arcgis/rest/services/PublicSafety/OpenData/MapServer/2) |
| S05 | MassGIS Emergency Service Zones | Service agency assignment geography | [MassGIS ESZ](https://www.mass.gov/info-details/massgis-data-emergency-service-zones) |
| S06 | Massachusetts MC-FRM | Published future flood extents and depths | [Flooding viewer](https://www.mass.gov/info-details/massachusetts-sea-level-rise-and-coastal-flooding-viewer) · [technical overview](https://www.mass.gov/doc/climate-resilience-design-standards/download) |
| S07 | USGS coastal 2018 flooding | Historical footprints and high-water evidence | [USGS map data](https://data.usgs.gov/datacatalog/data/USGS%3A60100f99d34e162231fecfa8) · [study](https://www.usgs.gov/centers/new-england-water-science-center/science/flood-documentation-and-inundation-mapping-january) |
| S08 | NOAA Boston tide gauge (8443970) | Water levels at station, time context | [CO-OPS API](https://api.tidesandcurrents.noaa.gov/api/prod/) |
| S09 | MassGIS LiDAR terrain | Bare-earth elevations, slope context | [LiDAR](https://www.mass.gov/info-details/massgis-data-lidar-terrain-data) |
| S10 | City of Boston road inventory GIS | Road characteristics; verify completeness | [Boston road inventory](https://gisportal.boston.gov/arcgis/rest/services/Infrastructure/OpenData/MapServer/14) |
| S11 | Boston climate-resilient design guidelines | Engineering options and 2018 sample costs | [Design guidelines](https://content.boston.gov/departments/public-works/climate-resilient-design-guidelines) |
| S12 | MassDOT Morrissey Boulevard study | Local flood/transport constraints and proposals | [Final report](https://www.mass.gov/doc/morrissey-boulevard-corridor-study-final-report/download) |
| S13 | City of Boston | Coastal resilience implementation status | [Project tracker](https://www.boston.gov/departments/climate-resilience/coastal-resilience-implementation) |
| S14 | Census & starter Civic ZIP | Representative population/demand | [Census portal](https://data.census.gov/) |

**Final interpretation:** The team can build a compelling **network-aware resilience investigation tool**, not an autonomous flood-engineering system. The strongest defensible output is a transparent priority queue and engineering review brief that updates when a hypothesized intervention changes connectivity.
