# FloodRoute / ResilienceOS — Project context and implementation contract

**Status:** Three-person hackathon build, superseding the original frontend-only mock specification.  
**Updated:** October 24, 2026.  
**Related:** `AGENTS.md`, `FloodRoute_Team_Worksplit.md`, `docs/FloodRoute_3D_Feasibility_and_Sources.pdf` (when present).

## CURRENT ADDENDUM — causal diagnosis and physical intervention preview (24 October 2026)

The shared baseline below remains valid. For the current three-person work, apply these **additive** updates before coding:

- A road may be a **symptom location**, not the broken asset. Investigate competing flooding causes (e.g. coastal inflow, tide-constrained outfall, catch basin, drainage capacity, surface ponding) before offering cause-matched interventions. The engineer may need to investigate a shoreline, outfall, catchment, drain or corridor. See `FloodRoute_Engineering_Causal_Diagnosis_Addendum.md`.
- The chosen intervention is a **physical asset concept**, with optional location/alignment/polygon/point distinct from affected `road_ids`. Person 3 provides engineering evidence, source provenance, and an explicitly sourced or schematic spatial concept; Person 2 visualizes it in Cesium; Person 1 separately computes any *user-authorized* hypothetical network-access effects. See `FloodRoute_Engineering_Intervention_Visualization_Addendum.md` and `FloodRoute_Simulation_Intervention_Addendum.md`.
- Previewing a berm, wall, drainage project or raised road **must not modify modeled floodwater**, mark a road drivable, reduce affected property counts, or claim benefits. Recomputed network results are allowed only with a separately and visibly specified set of **hypothetically preserved links per scenario**. Without validated before/after hydraulics, physical protection effectiveness remains **unknown**.
- All additions to the existing data contract should be optional/additive at first, validated, and versioned with Persons 1–3. Do not parallel-edit shared TypeScript contracts. Historical / future / conceptual distinctions and datum/units rules still apply.


## 1. Product at a glance

**Problem.** Public flood maps show where water is likely to reach, but they do not directly reveal which threatened transportation connections cause the largest disruption to essential-service access, how much network redundancy exists, and which corridors deserve engineering investigation first.

**Target users.** Municipal climate resilience, transportation, public works and emergency-preparedness analysts; licensed engineers reviewing candidate measures. **Not** a live emergency-dispatch navigation product.

**Full loop:** **Observed historical evidence and distinct published future flood scenarios → potentially disrupted road network → essential-service accessibility losses → dynamically ranked critical corridors → road-specific, cited engineering investigation → hypothetical/verified intervention → network-wide reranking.**

**Central technical insight:** A road's importance depends on the **rest of the graph** and the availability of alternative routes to *multiple* important facilities. Preserving a road has limited marginal value if good alternatives exist; improvements elsewhere can change its priority. Correctly evaluating this effect can be more valuable than another flood animation.

### Demo sequence

1. Fly to a small Boston area in Cesium 3D. Select a labeled historical flood-evidence event *or* a modeled future hazard (e.g., 2050 1% annual-exceedance case).
2. Compare modeled normal and flood-affected access for a few representative journeys to/from real emergency departments and fire stations, using closure assumptions labeled as such.
3. Show the computed relative ranking of roads/corridors, why detours are or are not adequate, and the journeys affected.
4. Select the top corridor. Inspect known road geometry/attributes, available flood evidence, sources, uncertainties, and candidate protection/alternate-access measures.
5. Choose `Assume this corridor remains passable in [selected scenario(s)]` and **actually recompute** network access and all ranks. Show results. Label as a graph counterfactual—not a physically validated fix.

A camera animation or historical water replay is optional and **illustrative unless actual time-resolved, local hydrodynamic outputs are obtained**.

## 2. Current deliverables: who owns what

| Owner | Independent computation/output | Integration contract |
|---|---|---|
| **Person 1: Network/ranking** | Source-inspected routable directed graph, canonical IDs, representative OD journeys, real accessibility metrics, marginal/bundled corridor ranking, re-ranking under assumed passability | `RoadManifest`, `RoadRankingResult`, `CounterfactualResult` |
| **Person 2: Hazard/3D/UI** | Actual public flood extent for selected geographic area if accessible, road-exposure spatial join, distinguish observed/model/illustrative layers, Cesium UI, app integration | `FloodExposureResult`, Cesium presentation, data adapters |
| **Person 3: Engineering/citations** | Road facts, flood evidence and network context, candidate measures, sources + conceptual cost examples, source-grounded assistant or deterministic fallback, intervention record | `InvestigationResult`, `InterventionProposal` |

Start independently on a **shared synthetic fixture**, not each other's unfinished computation. The one shared technical dependency is the **versioned road-ID manifest**. Freeze it early and keep an explicit mapping to source geometries. No competing edits to app composition or shared types.

### Target architecture

```text
Official published GIS / starter ZIPs  ────> hazard ingestion + road join ──┐
Road centerlines / OSMnx / facilities ────> graph + accessibility/ranking ──┤
Published engineering guides + attributes -> investigation/evidence ───────┤
Small coherent fixtures (parallel fallback) ────────────────────────────────┤
                                             normalized JSON/GeoJSON v1   │
                                                       │                   │
                                                DataSource adapter <────────┘
                                                       │
                                            React + CesiumJS frontend
```

A Python CLI that precomputes normalized JSON is suitable for hackathon speed; a backend/API is **optional**, unlike the original file's blanket prohibition. The existing semi-clickable frontend and `MockDataSource` are useful assets. Reuse, not rewrite.

## 3. Source and data inventory (exact links)

These are published or identified sources, **not assertions that a working joined dataset is already loaded**. Check permissions, actual schema, coordinate/datum semantics, coverage, vintage, and completeness.

### Hackachusetts ZIP datasets

| Source | Contents/use | Caveats |
|---|---|---|
| `robotics.zip/boston-streets/data.csv` | 19,440 road centerline records, WKT, street and routing fields; basis for graph/geometry | Roughly 1,195 missing WKT geometries in audited snapshot; no guaranteed source-stable segment ID, directed cost/unit consistency and topology must be tested |
| `robotics.zip/boston-map/` | 256×256 navigation grid for algorithm tests | Not georeferenced to Boston, not a flood surface |
| `robotics.zip/bridges/data.csv` | 2022 Massachusetts bridge condition context | Snapshot lacks location links; must not attach conditions to a specific bridge without join |
| `civic.zip/neighborhoods/` | 24 neighborhood population summary records | No boundaries in snapshot; avoid representing as spatially precise demand without polygons |
| `civic.zip/vision-zero/` | 44,986 geolocated crash records | Optional transportation context, not flood or EMS travel-time ground truth |
| `healthcare.zip/hospitals/` | 103 hospital/facility records | No starter coordinates and may include non-emergency facilities; use current MassGIS hospital/ED points |
| `climate.zip/tides/` | 744 hourly 2024 water-level observations | One station/time window; not road inundation or 2018 event reenactment |

### Official external sources

**Hazards and geography**

- [Massachusetts Coast Flood Risk Model / coastal flooding viewer](https://www.mass.gov/info-details/massachusetts-sea-level-rise-and-coastal-flooding-viewer): future modeled horizons and annual-exceedance scenarios; inspect specific products for flood extent/depth and provenance.
- [Example 2050 1% flood extent ArcGIS service](https://services1.arcgis.com/7iJyYTjCtKsZS1LR/ArcGIS/rest/services/MA_2050_1Perc_v11/FeatureServer): machine-readable *published model* extent, subject to confirming reachability, layer selection, projection and usage terms.
- [MassGIS LiDAR terrain](https://www.mass.gov/info-details/massgis-data-lidar-terrain-data): terrain elevation context; terrain alone does not reconstruct street-level flow or road-deck height.
- [NOAA Boston water level station 8443970](https://tidesandcurrents.noaa.gov/stationhome.html?id=8443970): measured tidal water levels for dates within NOAA archive. One station does not provide exact local water movement through roads.
- [USGS 2018 Boston nor'easter observations](https://www.usgs.gov/): locate specific event flood maps/high-water marks; use only after selecting verified actual event products. Historical peak footprint ≠ measured dynamic flow field.

**Road graph and essential destinations**

- [MassGIS / MassDOT Roads](https://www.mass.gov/info-details/massgis-data-massgis-massdot-roads): enriched public road geometry/attributes if needed.
- [OSMnx documentation](https://osmnx.readthedocs.io/en/stable/getting-started.html): fallback graph creation, explicit source/date/version.
- [MassGIS Hospitals](https://www.mass.gov/info-details/massgis-data-hospitals): coordinates and emergency department indicator, with August 2026 data updates; filter suitable destinations.
- [Boston Fire Station ArcGIS layer](https://gisportal.boston.gov/arcgis/rest/services/PublicSafety/OpenData/MapServer/2): fire-station locations.
- [MassGIS Fire Stations](https://www.mass.gov/info-details/massgis-data-fire-stations): alternative statewide fire station layer.
- [MassGIS Emergency Service Zones](https://www.mass.gov/info-details/massgis-data-emergency-service-zones): planning-level responsibility areas; not a current dispatch feed.
- [Boston/MassDOT Road Inventory ArcGIS layer 14](https://gisportal.boston.gov/arcgis/rest/services/Infrastructure/OpenData/MapServer/14): candidate surface/width/lane/AADT attributes; **inspect record-level field availability**.

**Engineering evidence and existing plans**

- [Boston Climate Resilient Design Guidelines](https://www.boston.gov/departments/public-works/climate-resilient-design-guidelines): berms, coastal walls, roadway elevations, temporary barriers and constraints.
- [2018 vegetated berm example](https://content.boston.gov/sites/default/files/file/document_files/2018/10/section_4.0_sample_vegetated_berm_barrier.pdf): conceptual **~$2.3 million / 2,000 feet**.
- [2018 raised roadway example](https://content.boston.gov/sites/default/files/file/document_files/2018/10/section_6.0_sample_raised_roadway_barrier.pdf): conceptual **~$13.6 million / 2,000 feet**.
- [MassDOT Morrissey Boulevard Corridor Study](https://www.mass.gov/news/massdot-releases-the-morrissey-boulevard-corridor-study-final-report): site-specific published options and constraints; distinguish plans from completed work.
- [Boston Coastal Resilience Implementation](https://www.boston.gov/departments/climate-resilience/coastal-resilience-implementation): existing local projects and statuses; verify them when used.
- [Massachusetts Climate Resilience Design Standards Guidance](https://www.mass.gov/info-details/climate-resilience-design-standards-guidance): screening/design context; do not assume an API exists.

**3D:** [Cesium OSM Buildings](https://cesium.com/platform/cesium-ion/content/cesium-osm-buildings/), streaming assets subject to credentials/network/attribution. Use source-labeled fallback on failure.

**Historical cost figures are neither adjusted for inflation nor applicable as precise prices for an arbitrarily selected road.** Capture estimate year, example scope, excluded works and uncertainty.

## 4. Minimum data contracts (proposed, provisional)

The old P0 `FloodScenario`, `RoadFeature`, `RouteComparison`, `Vulnerability`, `EngineeringInvestigation` models remain useful starting structures. Do **not** silently change them in parallel. Extend them in a shared `v1` contract around these normalized exchange records:

```ts
interface RoadManifest {
  graph_version: string;
  roads: GeoJSON.FeatureCollection;
  source_id_mapping: Record<string, string>;
  metadata: Record<string, unknown>;
}

interface FloodExposureResult {
  scenario_id: string;
  graph_version: string;
  scenario_type: 'observed_historical'|'published_future_model'|'illustrative';
  extent_geojson?: GeoJSON.FeatureCollection;
  affected_roads: Array<{
    road_id: string;
    exposure: 'exposed'|'not_exposed'|'unknown';
    depth_m?: number|null;
    passability: 'potentially_closed'|'unknown'|'assumed_open';
    passability_basis: string;
    provenance: Provenance;
  }>;
  provenance: Provenance;
}

interface RoadRankingResult {
  scenario_set_id: string;
  graph_version: string;
  ranking: Array<{
    corridor_id: string;
    road_ids: string[];
    priority_rank: number;
    impact_value: number|null;
    impact_units: string;
    affected_journey_ids: string[];
    detour_or_disconnection_evidence: string[];
    assumptions: string[];
    provenance: Provenance;
  }>;
}

interface InterventionProposal {
  intervention_id: string;
  corridor_id: string;
  road_ids: string[];
  method: string;
  status: 'hypothetical'|'implemented'|'verified';
  assumed_passability_by_scenario: Record<string, string>;
  evidence_source_ids: string[];
  engineering_review_notes: string[];
}

interface CounterfactualResult {
  graph_version: string;
  intervention_id: string;
  scenario_set_id: string;
  before_ranking: RoadRankingResult;
  after_ranking: RoadRankingResult;
  accessibility_change: { value: number|null; units: string };
  assumptions: string[];
}

interface InvestigationResult {
  corridor_id: string;
  road_ids: string[];
  known_road_facts: unknown[];
  flood_evidence: unknown[];
  network_consequences: unknown[];
  candidate_methods: unknown[];
  published_cost_examples: unknown[];
  unknown_site_constraints: string[];
  source_ids: string[];
  caveats: string[];
}
```

Define `Provenance` with origin (`observed`, `published_model`, `computed`, `assumed`, `mock`), exact source reference, date/period and limitations. The interfaces above are **discussion-starting contracts**, not fixed formulas or final schema. Prefer Zod/JSON Schema validation and a tiny checked fixture. Road IDs persist only within `graph_version` and require explicit remapping on graph change.

## 5. Analytical approach (preliminary, not decided)

### Road network and accessibility

Construct a directed weighted graph using inspected source road geometry and routing attributes. Verify connectivity, units, one-way behavior and grade-separated crossings. Choose representative origins (communities and fire stations) and destinations (clinically appropriate emergency departments or representative incidents). A route is a proxy for **modeled access**, not actual ambulance response time. Represent unreachable OD pairs explicitly. Use cautious assumptions where official assignments, traffic speeds or population demand are missing.

### Flood effects and criticality

For each eligible published/observed scenario, spatially join road links to flood footprint/depth evidence. **Exposure is not confirmed closure.** For sensitivity analysis, one might hypothesize potentially impassable links and compare alternative closure assumptions. Then compare accessibility with a candidate edge or *corridor bundle* preserved while the rest of scenario closures remain. Candidates can receive higher relative priority when loss creates large detours, lost service access, or few alternatives.

One provisional conceptual quantity is the **scenario-weighted change in aggregate access loss** between a disrupted graph and the graph where a candidate connection is assumed available. Do not prematurely impose a specific loss function, population weight, disconnection penalty, or universal flood-frequency score. Use empirical test cases, expose components, and distinguish historical observation frequency from modeled future AEP.

### Intervention update and reranking

Re-run the candidate evaluations after each proposed/verified intervention. A particular road might become *more* critical after other changes; no monotonic decrease should be hardcoded. One idealized reopened edge sometimes provides zero benefit when neighboring links remain inundated, so allow multi-edge bundles and check interactions. A hypothetical fix changes **routing assumptions only**; it does not rewrite official flood extents or imply hydraulic effectiveness.

## 6. Engineering investigation and assistant

On selecting a vulnerable corridor, assemble an evidence packet with its stable road IDs, actual known geometry and attributes, flood evidence, network consequences, and genuine published engineering sources. Include unknown roadway structure, drainage, utilities, subsurface, access constraints, and flow direction rather than hallucinating them.

The investigator can compare plausible measures (raised roadway, berm, floodwall, temporary barrier, drainage and alternate access) according to site context *where documented*; each proposal identifies what would have to be surveyed or modeled to establish feasibility. A grounded LLM may help navigate references and produce an engineer review brief, but a citation-backed deterministic fallback should function without credentials. Cite the relevant documents; do not transform 2018 example cost into a quoted project bid.

Allow proposed improvements to be stored with `hypothetical`, `implemented`, `verified` status and scenario-specific assumptions. Only *verified evidence* should support a claimed real change to road resilience. A person marking something 'fixed' in the UI is not sufficient for scientific validation.

## 7. 3D interaction and visuals

Keep the existing React + TypeScript + Vite + CesiumJS + Tailwind/shadcn UI stack. Map dominates desktop layout; compact controls for scenarios, routes, exposure/criticality, and selected corridor. Show one source-linked historical/future flood evidence view, a visible **computed** accessibility/ranking comparison, and an investigation panel. A toggle for a hypothetical intervention should rerun rankings rather than swap hardcoded bars. Show provenance beside numerical outputs and mock badges only on genuinely illustrative records.

The 3D view may animate water **for communication only**. Do not claim exact speed, depth, travel direction or timestamps for an individual historical street without a verified corresponding time-resolved hydraulic dataset. Real basemap/3D tiles do not make mocked flood results real.

## 8. Feasibility gates / independently testable deliverables

- **P1 Network:** directed connected graph, verified source units; OD routes and alternative/disconnection test; actual computed ranking and change from hypothetical preserved corridor; JSON exports with canonical IDs. If road data lacks connectivity, test OSMnx fallback and report.
- **P2 Hazard/UI:** real official scenario extent clipped to a selected bounded geography where available; reproducible projection transformation; road exposure output joined to frozen IDs; navigable Cesium scene; end-to-end frontend consumes exported normalized results. If raster unavailable, show *extent only* and no invented depth.
- **P3 Engineering:** select a fixture or computed corridor; assemble source-backed known/unknown fields; present 2–4 candidates with applicable/unknown notes; show proper dated example costs; return typed intervention; works independently of live LLM.
- **Integrated demo:** actual flood exposure + computed road impact if feasible; one re-ranking after a hypothetical counterfactual; one grounded investigation. If any stage is mocked, label it clearly and state why.

## 9. High-priority risks

1. No stable road IDs / broken directed road topology → versioned manifest, topology checks, fallback OSMnx.
2. Flood polygons overlap bridges/tunnels but not roadway decks → explicit passability assumptions, sensitivity cases, no false certainty.
3. Published event data does not give exact minute-by-minute road water-flow or depth → avoid misrepresented animation.
4. Mixed observation frequency with future scenario probabilities → preserve scenario provenance and separate weighting.
5. No meaningful difference on chosen corridor → early spatial join and OD test; change geography/scenario rather than inventing detours.
6. Adjacent flooded edges make single-edge counterfactual meaningless → corridor-bundle support.
7. Incomplete road materials / widths / drainage / subsurface → unavailable data stays unknown.
8. LLM invents engineering conclusions or dollars → curated citations, explicit uncertainty, no site quote.
9. Proposed protection physically redirects water → idealized graph-only test, no inferred hydro result.
10. Cesium credentials/streaming fail → local fallback and prerecorded demo.
11. Agents collide on shared files → freeze contract; disjoint directories; one frontend integrator.
12. Mock metrics masquerade as computed → record-level provenance, clear visible status.

## 10. Definition of success

**The minimum compelling system is not a physics simulator.** It uses authoritative flood evidence, a real street graph and important destinations to calculate network-level accessibility effects. It explains *why* a road ranks highly (including how alternatives affect it), lets engineers explore cited investigation options, and recomputes priorities under clearly assumed fixes. Anything not backed by actual data/computation remains visibly illustrative. The app should run locally and be demonstrable without a production server.

**Footer:** `Planning prototype only — not for live emergency routing or construction decisions.`
