# FloodRoute — Engineering Intervention Geometry & Simulation Handoff (Addendum 2)

**Audience:** Person 3 (engineering recommendations / AI) and their coding agent  
**Date:** October 24, 2026  
**Status:** Additive, scoped requirements. Read **after** `AGENTS.md`, `PROJECT_CONTEXT.md`, `FloodRoute_Team_Worksplit.md`, and **Addendum 1** `FloodRoute_Engineering_Causal_Diagnosis_Addendum.md`. Preserve those documents; do not rewrite them or duplicate their source library.

## 1. Purpose

The existing workstream identifies a flooded hotspot, investigates competing causes, describes possible candidate responses, and cites real evidence. **This second addendum makes a recommended measure visualizable and testable without claiming that a proposed construction scheme actually changes flooding.**

**New handoff:** `diagnosed hotspot / affected asset → candidate physical intervention → traceable concept geometry + supporting evidence → Cesium preview (Person 2) → optional explicitly assumed network-access counterfactual (Person 1)`.

A floodwall may protect a shoreline pathway and a group of road links/buildings; the relevant physical work is not necessarily on the high-priority road itself. A blocked inlet, deficient outfall, or low point may call for maintenance or drainage engineering rather than road raising. Preserve this causal distinction from Addendum 1.

## 2. Person 3's exact additional responsibilities

1. **Propose cause-matched candidates, not arbitrary road fixes.** For each candidate, state *which hypothesized mechanism it addresses*, supporting and conflicting evidence, and missing site checks. If mechanism or asset owner is unknown, say so.
2. **Identify the asset / physical footprint.** The feature might be a shoreline barrier alignment, road elevation section, berm footprint, deployable gate location, pump/outfall, drainage catchment, or alternate connection. It may be different from the impacted `road_ids`.
3. **Generate a renderable concept record.** Provide a GeoJSON Point/LineString/Polygon (or optional feature collection) *only when location can be grounded*. If no verified alignment exists, supply an **illustrative sketch with `geometry_status: "schematic"`** and a strong visual badge; do not imply the sketch matches a published engineered design.
4. **Include visual parameters cautiously.** Optional height/crest/elevation/length/width/footprint can be stored only with explicit units and, for absolute elevation, a stated **vertical datum**. Do not invent terrain, structure heights, foundations, or utility clearance.
5. **Surface real engineering evidence.** Cite relevant sections/pages of Boston's 2018 Climate Resilient Design Guidelines, the MassDOT Morrissey Boulevard Study, and applicable BWSC flooding / drainage guidance from Addendum 1. Clearly distinguish a *published option*, *our illustrative concept*, and a *completed existing asset*.
6. **Cost:** attach a **published sample cost precedent** with location/scope, year, limitations; do not extrapolate the historic $2.3M berm / $13.6M raised-roadway examples into a made-up site quotation or pretend those numbers apply to a pump/blocked drain.
7. **Hand off two logically separate outputs:** (a) an engineering/visual concept for Person 2, and (b) an **optional proposed graph assumption** for Person 1 specifying scenarios and road IDs hypothetically preserved *if a planner explicitly chooses to test that assumption*. Mere geometry must not generate presumed benefit.
8. **Keep alternatives visible.** Return 2–4 candidates with suitability, trade-offs and missing evidence. For the hackathon, pick **one** plausible, source-grounded example to preview well; alternatives can remain cards without custom 3D geometry.

## 3. Intervention types and appropriate visualization

| Candidate | Asset targeted | Preferred preview | Reality check |
|---|---|---|---|
| Raised roadway | Road segment/corridor | Line or corridor footprint with schematic raised road mesh | Connecting grades, utilities, drainage and pavement rebuild matter |
| Floodwall/seawall | Coastal entry/pathway | Continuous alignment with vertical wall visual | Gaps, flanking, gates, foundations and behind-wall drainage may invalidate protection |
| Vegetated berm/levee | Shoreline/land strip | Footprint or line with a broad sloped 3D berm | Land ownership, footprint, soil, foundations and continuity |
| Deployable gate/barrier | Specific opening / entry point | Gate marker and short barrier alignment | Deployment operations, seals and emergency access requirements |
| Drainage/inlet/outfall upgrade | Catch basin, pipe, outfall or catchment | Point/symbol plus affected area or a *schematic* pipe layer | Subsurface network/ownership/capacity often not public; cannot invent it |
| Alternate access | Proposed/new connection | Conceptual route/line | Land, traffic, access and constructability must be assessed |

**Not all interventions make a blue flood polygon vanish.** A raised roadway may make a route higher while adjacent land still floods. A barrier may redirect water; a drainage improvement may address pluvial ponding rather than coastal overtopping. Physical consequences require appropriate engineering/hydraulic analysis.

## 4. Additive normalized contract (discussion starter — do not replace shared types)

Person 1 is the owner of canonical `road_id`, `corridor_id`, `graph_version` and the shared schema. Person 3 should implement this *as an optional extension or versioned sidecar* until the team freezes an agreed contract; use existing `InterventionProposal`/`InvestigationResult` where compatible.

```ts
import type { Geometry } from 'geojson';

type GeometryStatus =
  | 'sourced_design_alignment'  // only with a specific cited map/drawing
  | 'sourced_asset_location'   // e.g. verified existing outfall / road segment
  | 'schematic'                // invented for UI exploration, plainly labeled
  | 'none';                   // no spatial claim possible

type ConceptIntervention = {
  intervention_id: string;
  linked_investigation_id?: string;
  corridor_id?: string;
  graph_version: string;
  intervention_type: 'raised_roadway'|'floodwall'|'berm'|
    'deployable_barrier'|'drainage_upgrade'|'alternate_access';
  target_asset_type: 'road'|'shoreline'|'catch_basin'|'outfall'|
    'pipe'|'catchment'|'opening'|'other';
  target_asset_id?: string;       // only if established by a source
  geometry?: Geometry;            // EPSG:4326, [longitude,latitude]; optional
  geometry_status: GeometryStatus;
  geometry_source_ids: string[];
  visual_parameters?: {
    conceptual_height_m?: number; // display-only if sourced, otherwise omit
    absolute_crest_elevation_m?: number;
    vertical_datum?: string;      // required if absolute elevation provided
    footprint_width_m?: number;
  };
  addressed_mechanism_ids?: string[];  // link to cause assessment
  related_road_ids: string[];     // roads involved/affected, not necessarily protected
  evidence_source_ids: string[];
  missing_engineering_inputs: string[];
  published_cost_precedents: Array<{
    source_id: string;
    example_scope: string;
    price_year: number;
    amount_usd?: number;
    limitations: string[];
  }>;
  status: 'conceptual'|'engineer_reviewed'|'implemented'|'verified';
  provenance: 'published_option'|'derived_concept'|'illustrative';
  // No implied hydraulic or accessibility benefit in this object.
};

type NetworkAssumptionForReview = {
  intervention_id: string;
  graph_version: string;
  scenario_ids: string[];
  hypothetical_preserved_road_ids: string[];
  selection_status: 'draft'|'explicitly_selected_for_counterfactual';
  assumption_notes: string[];
  // This is a QUESTION to Person 1's network simulator, not a forecast of efficacy.
};
```

**Critical:** `related_road_ids` and `hypothetical_preserved_road_ids` are not equivalent. A physical barrier's schematic polyline cannot automatically decide which roads it protects. If the latter list has not been explicitly set for a *what-if*, do not request any rerank.

## 5. Exact source grounding for one Morrissey example

Use source links already in the team handoff and **Addendum 1**; don't scrape unnecessary new sources before checking them. Priority documents:

- [MassDOT Morrissey Boulevard Corridor Study (final report)](https://www.mass.gov/doc/morrissey-boulevard-corridor-study-final-report/download) — site-specific candidate designs and constraints, but **not proof a particular barrier alignment is engineered, funded, or built**. Read figure legends and page-specific context before copying a route or describing status.
- [Boston Climate Resilient Design Guidelines](https://www.boston.gov/departments/public-works/climate-resilient-design-guidelines) — methods, constraints and conceptual 2018 costs.
- [BWSC Boston Inundation Model](https://www.bwsc.org/boston-inundation-model) / [viewer limitations](https://www.bwscstormviewer.com/disclaimers) — possible combined coastal/drainage mechanisms, data constraints.
- [BWSC adaptation scenario descriptions](https://www.bwscstormviewer.com/flood-modeling) — precedent for shoreline + outfall action, not automatically downloadable hydraulic scenarios.

First choose a geographically **verified and visible** corridor. If no reliable proposed barrier alignment can be extracted today, render one clearly **schematic** conceptual segment and explicitly show what survey/alignment/design information is missing. It is better than inventing an official geometry.

## 6. Integration and ownership

- **Person 3 owns:** `engineering/` source documents/index, road/asset diagnosis, optional contract sidecar, `ConceptIntervention` fixture/provider, engineering panel, validity/provenance and cost checks.
- **Person 2 owns:** Cesium 3D representation, toggling alternatives, camera fly-to, layer key/legend, and frontend composition. Preview selection does not mutate underlying flood layers or travel results.
- **Person 1 owns:** network graph, ranking/reranking and consuming `NetworkAssumptionForReview` when explicitly selected; computes full effects *if* requested, including altered criticality of other roads.
- **No one** should independently alter shared canonical road IDs or shared contract fields without notifying Person 1. Add optional fields or sidecars first, then collectively freeze v0.2.

**Parallel development:** Person 3 produces 1 labeled example `ConceptIntervention` + 2–3 candidate options using a fixture corridor. Person 2 starts 3D intervention-layer rendering from an identically shaped fixture. Person 1 tests one predetermined `NetworkAssumptionForReview` independently. Replace fixtures through adapters, never rewrite the UI for the actual data.

## 7. Acceptance tests for Person 3's second addendum

- [ ] Selected investigation produces 2–4 source-grounded candidate types, **not a definite repair directive**.
- [ ] At least one candidate carries renderable (or intentionally absent) physical concept geometry with correct provenance and location validity.
- [ ] Previewing the intervention never marks a road as physically protected or changes flood polygons in the output.
- [ ] The site investigation includes which flooding mechanism the option addresses and which records would confirm/refute it.
- [ ] Costs remain historical sample benchmarks with price year, scope and limitations; no fabricated site quote.
- [ ] Person 2 can read the concept via fixture/provider without importing engineering internals.
- [ ] An explicit hypothetical passability selection can be sent to Person 1 and does not imply hydraulic validation.
- [ ] Engineering panel says what physical survey, ownership check, drainage assessment or permitting remains unresolved.

### Short kickoff prompt for Person 3

> Read `AGENTS.md`, `PROJECT_CONTEXT.md`, `FloodRoute_Team_Worksplit.md`, `FloodRoute_Engineering_Causal_Diagnosis_Addendum.md`, and **this second addendum**. Extend the existing engineering module; do not rewrite the network or Cesium simulator. Deliver a source-linked `ConceptIntervention` record for one real chosen corridor, cause-matched option cards with missing site facts and dated cost precedence, and an optional separate graph-only `NetworkAssumptionForReview` proposal. Keep geometry clearly classified as sourced or schematic and never change published floodwater or claim physical protection effectiveness.
