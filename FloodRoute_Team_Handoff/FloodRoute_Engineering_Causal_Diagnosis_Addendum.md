# FloodRoute — Engineering Cause Diagnosis Addendum

**Audience:** Person 3, Engineering Recommendations & AI / their coding agent  
**Date:** October 24, 2026  
**Status:** Additive requirements; **do not replace or rewrite** `AGENTS.md`, `PROJECT_CONTEXT.md`, or `FloodRoute_Team_Worksplit.md`.

## 1. What changes, and why

The existing engineering workstream already covers a selected corridor, sourced road facts, flood evidence, candidate interventions, historical example costs, and an engineer-facing investigation brief. **Keep all of that.** This addendum adds **one missing stage before choosing an intervention: investigate the *cause* of the flooding and identify the actual asset or system that might need work.**

A flooded roadway is an **observed impact location**, not necessarily the failing infrastructure. Water on a road and damage to adjacent homes may both result from a blocked catch basin, overwhelmed drainage network, tide-constrained outfall, low ground elevation, coastal overtopping, or several interacting causes. The correct action might target a **drain, outfall, entire catchment, shorefront pathway, or alternate access**, not the pavement itself.

**New principle:** `flooded road / hotspot → competing cause hypotheses → evidence and missing checks → cause-matched options → engineer review`. Never jump from road rank or map color to a specific construction recommendation.

Person 1 still ranks transportation and area impacts; Person 2 (simulation) still owns hazard surfaces and visualization. **Person 3 owns diagnosis hypotheses, relevant asset evidence, intervention suitability, and explanation.** This avoids moving GIS processing or the routing engine into Person 3's scope.

## 2. Distinguish mechanisms (do not collapse them)

| Possible mechanism | What might support it | Relevant candidate responses **to investigate** | What does **not** prove it |
|---|---|---|---|
| **Coastal overtopping / overland inflow** | Modeled coastal flood pathway, nearby shore elevation, historical high-water evidence | Continuous berm / barrier, shoreline protection, localized elevation, alternate access | A blue flood polygon alone does not prove the entry pathway at road scale |
| **High tide blocking stormwater discharge / backflow** | Outfall elevation and ownership, tide levels, rain timing, BWSC coastal stormwater modeling | Tide gate/backflow control, controlled pumping, storage, revised outfall configuration **with downstream checks** | High tide alone does not demonstrate a specific outfall is failing |
| **Localized inlet obstruction / debris** | Repeated, geographically specific catch-basin reports, maintenance records or **field inspection** | Cleaning, inspection, targeted maintenance, repair of damaged inlet or connecting pipe | A 311 report is an allegation, not a confirmed blockage; BWSC model does not resolve individual clogged basins |
| **Insufficient storm-drain or inlet capacity** | Rainfall intensity, inlet spacing/condition, verified pipe sizes, hydraulic calculations, repeated pluvial ponding | Added/relocated inlets, pipe/storage capacity assessment, surface detention/green infrastructure, pumping where appropriate | Road width or a flood footprint does not reveal underground capacity |
| **Unfavorable street grading / ponding** | LiDAR/topographic low points, surface grades and flow paths, field survey | Regrading, gutter/inlet relocation, redesigned overflow path | A low point alone does not establish deficient drainage or whether modifications displace water elsewhere |
| **Multiple simultaneous causes / unresolved** | Co-occurring rain, tides, shoreline pathways and unresolved utility records | Further data collection, site survey, hydraulic modeling and owner coordination | Never force one causal label just to populate an answer |

The table suggests possible mechanisms and investigations, **not a completed hydraulic diagnosis**. Drainage interventions may reduce flooding on neighboring properties and roads, but those benefits must not be claimed without suitable before/after hazard analysis.

### Important ownership check

Do **not** assume every catch basin, outfall or drainage pipe is BWSC-owned. State agencies (including MassDOT/DCR), private parties, and other operators can control nearby assets. The responsible asset owner must be established before the brief recommends a maintenance request or capital project to a named agency.

## 3. Additional public data and exact sources to investigate

These supplement the existing team's road, terrain, coastal MC-FRM, intervention-guideline and cost sources. **Do not duplicate the old source library.** Record retrieval date, URL, spatial coverage, update date, evidence type, original units/CRS, and whether a machine-readable export was actually obtained.

| Source | Exact link | What Person 3 can derive or research | Availability / limitation |
|---|---|---|---|
| **BWSC Inundation Model and limitations** | https://www.bwsc.org/boston-inundation-model and https://www.bwscstormviewer.com/disclaimers | Distinguish coastal overland flooding and tide-constrained outfalls from localized rainfall and clogged-inlet scenarios | Public viewer and documentation. **Do not treat model absence as proof of no flood**. Does not model local catch-basin obstruction; only certain owned outfalls included. |
| **BWSC modeled adaptation comparisons** | https://www.bwscstormviewer.com/flood-modeling | Published *No Action*, *Shoreline Protection*, and *Shoreline + Outfall Adaptation* comparisons; precedent for evaluating combinations, not just barriers | Scenarios are for a specified **2070 100-year tropical-storm setup**. Machine-readable before/after layers **not verified**. Do not invent local quantitative benefits. |
| **BWSC catch basin locator** | https://www.bwsc.org/environment-education/maproom/catch-basins-map | Look up mapped inlet locations around a selected hotspot | Public interactive map. Raw GIS feature export/API **not yet verified**; mapped location ≠ functional condition or ownership guarantee. |
| **BWSC maintenance documentation** | https://www.bwsc.org/projects/preventative-maintenance | Evidence that cleaning, inspection and CCTV pipe review are legitimate first-line actions | Describes practices, not public street-by-street inspection/cleaning history. Request site-specific records if needed. |
| **BWSC stormwater system description** | https://www.bwsc.org/environment-education/water-sewer-and-stormwater/stormwater-system | Stormwater system elements, catch basins, pipes, outfalls; upstream/downstream reasoning | Citywide system description, **not** a complete public georeferenced pipe network with diameter/capacity. |
| **Boston 311 open dataset** | https://data.boston.gov/dataset/311-service-requests | Time/location/category/description of reported flooded streets and blocked drains, when available | Official portal; check current yearly resource, geolocation access and request categories. Reporting bias, duplicates and inconsistent case descriptions; complaints are **not** confirmed failure causes. |
| **Boston Open311 API** | https://311.boston.gov/open311 | Potential service-request access and service classifications | Official documentation says an API key application is required; **do not assume keyless automated access**. Open CSV resources may be simpler for hackathon use. |
| **MassDOT Project Development & Design Guide, Ch. 8** | https://www.mass.gov/info-details/pddg-chapter-8-drainage-and-erosion-control | How practitioners investigate surface runoff, inlet capacity, grade, drainage systems, design checks and documentation | Guidance for engineering review, **not** proof a specific Boston asset is deficient. Includes field verification and consideration of impacts away from the site. |
| **Massachusetts Climate Resilience Design Standards** | https://www.mass.gov/info-details/climate-resilience-design-standards-guidance | Concept-stage screening of precipitation/coastal hazards and relevant design horizons | Public documentation; tool may require registration; no public machine API assumed. |
| **NOAA Atlas 14 precipitation frequency** | https://hdsc.nws.noaa.gov/pfds/ | Context for historical/intensity-frequency rainfall scenarios when comparing an event to drainage design assumptions | A location's precipitation-frequency estimate **does not** establish pipe capacity or a blocked drain. |
| **MassGIS LiDAR** *(already in project sources)* | https://www.mass.gov/info-details/massgis-data-lidar-terrain-data | If Person 2 provides validated elevations/terrain samples, investigate surface low points and plausible overland flow routes | Do not implement a second LiDAR ingestion pipeline under Person 3; surface drainage direction is a hypothesis until verified. |

**Especially useful existing model comparison:** BWSC's published scenario set explicitly separates shoreline protection from the *additional* effect of coastal outfall adaptations. It is a strong example of why a barrier alone may not resolve ponding behind a protected shoreline. The viewer is not proof that installing a particular tide gate would fix a selected road.

**Data access gate:** Before planning automated retrieval of catch basins, outfall topology, pipes or maintenance logs, actually test for downloadable data and allowed usage. A web map or a statement that infrastructure exists is **not** equivalent to a public API. If unavailable, use a human-reviewed fixture and mark these fields `not_available`.

## 4. Additional recommendation workflow for a clicked road or hotspot

1. **Locate the affected system.** Accept `road_id` and/or `hotspot_id`, evidence footprint and scenario IDs; identify which exposed buildings/roads are spatially associated. **Do not infer a road causes adjacent property damage.**
2. **Classify the evidence, not just the flood.** Distinguish `observed_report`, `observed_measurement`, `published_model`, `GIS_derived`, `engineering_record`, `hypothesis`, and `unknown`. Historical flood footprints, model depths, 311 complaints and hypothetical animations are not interchangeable.
3. **Generate multiple cause hypotheses.** Prefer `possibly coastal inflow`, `possibly tide-constrained drainage`, `possibly inlet blockage`, `possibly drainage capacity`, `possibly local grading`, or `undetermined` over a forced root cause. List both supporting **and contradictory/absent** evidence for each.
4. **Identify the responsible physical asset(s) to inspect.** A road section might be a *symptom* while an inlet, outfall, shoreline opening or upstream drainage subsystem is the actual investigation target. Asset existence, current condition and owner are different facts.
5. **Propose cause-matched investigative actions and candidate remedies.** Start with inspection, cleaning or maintenance *when evidence suggests those are plausible*, and only then discuss construction choices where justified. For each option state conditions for applicability, ways it can fail, affected assets, possible downstream consequences and required engineer checks.
6. **Keep cost evidence scoped to the right type of work.** Published 2018 flood-barrier/raised-road examples already in the team's evidence library are not estimates for drainage cleaning, new catch basins, pipe replacement, pumps or a selected site. For unsupported cost types write `cost_estimate_unavailable` and specify inputs needed for a quote. If presenting costs at all, show scope, date, inclusion/exclusions and source.
7. **Output an investigation brief, not a diagnosis certificate.** Include priority context, suggested causes, supporting links, what to survey, asset ownership questions, candidate measures, missing engineering facts, and concrete *next investigation steps*. State what cannot presently be claimed.

### Suggested example response (illustrative, not Boston field findings)

> **Finding:** Recurrent street ponding and nearby property exposure are documented or reported in the selected area. The cause is **not established**. Possible explanations include obstructed inlets, insufficient drainage capacity, local grading, or tide-constrained outfalls.  
> **Next investigation:** Locate and inspect catch basins, verify outfall ownership and downstream tide conditions, compare rainfall and flood timing, and obtain a drainage survey/maintenance record.  
> **Candidates only after checks:** Cleaning if blockage is confirmed; inlet/grading alterations if runoff collection is deficient; outfall/tide-gate or storage review if high tailwater is implicated; coastal protection if overland tidal entry is demonstrated.  
> **No cost or claimed avoided property damage** until site-specific engineering or credible before/after modeling supports it.

## 5. Minimal additive contract — do not break existing interfaces

**Proposal for Person 3's *own* investigation output**, not a mandate for Person 1/2 to rewrite their schemas. Add an optional `cause_assessment` field to the existing investigation result or a separate keyed sidecar. Reuse project-defined provenance types when available.

```ts
type HypothesizedMechanism =
  | 'coastal_overland' | 'tidal_outfall_backwater'
  | 'inlet_blockage' | 'storm_drain_capacity'
  | 'surface_grading' | 'multiple_or_unknown';

type EvidenceItem = {
  source_id: string;
  url?: string;
  evidence_type: 'observed_report' | 'observed_measurement'
    | 'published_model' | 'gis_derived' | 'engineering_record'
    | 'hypothesis' | 'unknown';
  summary: string;
  observed_at?: string;   // Only if actually available
  limitations: string[];
};

type CauseHypothesis = {
  mechanism: HypothesizedMechanism;
  supporting_evidence_ids: string[];
  counter_evidence_ids: string[];
  unknowns: string[];
  status: 'possible' | 'evidence_supported' | 'unresolved';
  // No fabricated numerical likelihoods.
};

type AssetToInvestigate = {
  asset_type: 'road' | 'catch_basin' | 'pipe' | 'outfall'
    | 'shoreline' | 'pump' | 'catchment' | 'other';
  asset_id?: string;
  owner?: string;           // only when sourced
  location_ref?: string;
  evidence_ids: string[];
};

type DiagnosticAddendum = {
  road_ids: string[];      // Canonical, versioned road IDs already agreed
  hotspot_id?: string;
  scenario_ids: string[];
  evidence: EvidenceItem[];
  possible_causes: CauseHypothesis[];
  assets_to_investigate: AssetToInvestigate[];
  recommended_next_checks: string[];
  intervention_caveats: string[];
  limitations: string[];
  engineer_review_required: true;
};
```

**Boundary with the other teammates:** Person 2 provides `FloodExposureResult` or an optional hazard/hotspot summary and depth/flow information *only if genuinely sourced*. Person 1 provides `RoadRankingResult` and optional property-exposure context; neither is required to implement an asset diagnosis. Person 3 must accept a small representative fixture immediately. Do not require their real pipelines or actual ArcGIS availability before producing a useful diagnosis UI.

**Intervention and reranking rule:** The existing `InterventionProposal` should carry an **explicit mechanism and conditional effect claim**:
- `access_only`: Idealized travel/passability assumption for Person 1's graph counterfactual. **No automatic reduction in flooding or property losses.**
- `hydraulic_or_drainage`: Requires validated before/after flood surfaces or engineered calculations before changing road exposure, property-loss projections, or network ranking. Otherwise record an *unquantified proposal*, not a successful fix.

## 6. MVP acceptance checks for this addendum only

- [ ] The assistant does **not** conclude “road needs elevation” solely from flood exposure or high network priority.
- [ ] It can distinguish at least **three plausible mechanisms** (e.g. coastal inflow, blocked inlet, tide-constrained outfall) in one source-linked demonstration, without making unsupported claims of certainty.
- [ ] It cites actual relevant records/guidelines and clearly separates **published fact, report, model output, inference and missing data**.
- [ ] It identifies **what should be inspected** and the *potential asset owner*, with `unknown` where ownership or exact location isn't verified.
- [ ] The brief explains why the road might only be an impacted location while another drainage/coastal asset is the intervention target.
- [ ] It never assigns the 2018 roadway/berm construction estimate to a catch-basin cleaning or drainage retrofit.
- [ ] If the user selects “fix the drain,” the tool does **not** automatically mark all surrounding properties or roads safe; it requires a justified hazard update before predicted flood impacts change.
- [ ] The new fields remain optional/additive and existing contracts, UI, ranking and simulation demos still run unchanged.

### Coding-agent kickoff (scoped)

> Read this addendum **after** the existing team handoff and engineering context. Extend only the recommendations/engineering workstream with source-linked, alternative flood-cause hypotheses and cause-specific investigation options. Reuse existing sources and contracts rather than reimplementing ranking, flood mapping, or the current recommendation UI. Start from one labeled corridor fixture and implement evidence, uncertainty, asset ownership, candidate actions, and missing checks. Keep the new fields additive and test that a modeled flood polygon alone never triggers a definite drainage diagnosis or exact cost claim.
