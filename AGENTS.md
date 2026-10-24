# FloodRoute / ResilienceOS — Coding-agent instructions

**Version:** 2026-10-24, team-build scope (supersedes original mock-only P0 instructions).

Read `PROJECT_CONTEXT.md` and `FloodRoute_Team_Worksplit.md` before making substantive changes. Also read the **role-specific addendum(s)**: Person 1 reads `FloodRoute_Ranking_Impact_Addendum.md`; Person 2 reads `FloodRoute_Simulation_Intervention_Addendum.md`; Person 3 reads **both** `FloodRoute_Engineering_Causal_Diagnosis_Addendum.md` and `FloodRoute_Engineering_Intervention_Visualization_Addendum.md`. Addenda extend the shared spec but never supersede the scientific/safety boundaries. `PROJECT_CONTEXT.md` defines product truth and data/scientific boundaries; `FloodRoute_Team_Worksplit.md` defines responsibility and interface handoffs. If a file is absent, proceed using this document and flag the missing input. **Do not interpret the old instruction 'no backend / no routing / no LLM' as current:** the work now includes a real network-ranking prototype, real flood-data integration where feasible, and an evidence-grounded engineering investigation. Existing mocks stay as fallbacks.

Do not commit or push to git without permission. Never add an AI tool as a co-author. Never expose credentials or tokens.

## Goal and central demo

Build an interactive Boston flood-resilience **planning** application:

1. Show a historical flood-evidence layer or an official future modeled scenario in 3D, with status and provenance plainly labeled.
2. Analyze disruptions to representative essential-service journeys (e.g., neighborhood to emergency department, fire station to representative incident) in a directed road graph.
3. Rank affected **roads/corridors by marginal network-accessibility consequences**, factoring in alternate routes and relevant demand—not by wetness alone.
4. Select a road/corridor, review known road and hazard facts, and inspect evidence-grounded engineering measures and published cost *examples*.
5. Diagnose potential causes of a hotspot (which may involve drainage or shoreline assets *rather than the road*), and preview a **conceptual physical intervention** whose geometry can differ from the affected roads.
6. Test an **idealized, scenario-scoped counterfactual** ('assume these road links remain passable'); recompute all rankings. Record whether an intervention is hypothetical, implemented, or verified. Do not imply a proposed fix physically prevents flooding.

A real quantitative core is more important than a polished invented number. Reuse the existing Cesium/React frontend; do not rebuild working components merely to implement the new scope.

## Three owners — strictly separated workspaces

- **Person 1: network and reranking.** Owns `analysis/network/`, `data/normalized/roads/`, and a **versioned canonical road manifest** / stable `road_id` mappings. Builds graph, journeys, accessibility loss, rankings, and before/after counterfactuals. Creates the initial shared contract with the team.
- **Person 2: flood evidence, geospatial processing, visualization, overall UI integration.** Owns `analysis/hazard/`, the shared Cesium scene, `frontend/` composition, and display of road overlays/routes. Produces scenario-specific exposure for the canonical IDs. Integrates others' JSON outputs via adapters. Do not edit Person 3's investigation components concurrently.
- **Person 3: engineering investigations and assistant.** Owns `engineering/` and `frontend/src/investigation/` (or equivalent existing location). Gathers actual road fields and published engineering sources; produces cited options, caveated **historical** costs, a road-specific diagnosis/investigation panel, cited intervention proposals with optional physical concept geometry, an intervention form, and optionally a grounded live LLM, with a deterministic fallback.

If the repo already uses a different layout, *map ownership to existing directories instead of moving the entire app.* No two agents should edit the same file at the same time. Person 2 integrates `App.tsx` and shared styling. Person 1 coordinates contract changes; freeze a first schema version before parallel implementation.

## Shared interface and independent progress

Stable identifiers: `road_id`, `corridor_id`, `graph_version`, `scenario_id`, `journey_id`, `facility_id`, `intervention_id`. Road IDs must be traceable to a versioned manifest; CSV row position is not a permanent identifier.

Use normalized JSON/GeoJSON between subsystems, with coordinates in **EPSG:4326 [longitude, latitude]**; preserve source CRS and elevation datums separately. Distances in meters, estimated times in seconds, depth in meters, dollar costs with price year and scope. All claims have provenance: `observed`, `published_model`, `computed`, `assumed`, or `mock`. An unknown depth is `null`, not 0.

Provisional exchange objects (refine jointly; do not silently make incompatible changes):

- `RoadManifest`: graph version, canonical features/geometry, source-to-ID map, graph metadata.
- `FloodExposureResult`: `scenario_id`, `graph_version`, source and type (historical observation / future published model / mock), extent, road exposure/depth where genuinely supported, passability assumptions, provenance.
- `RoadRankingResult`: scenario set, `graph_version`, corridor/road IDs, relative order, impact metric **with units**, affected journeys, alternatives/detours/disconnections, assumptions.
- `InvestigationResult`: corridor IDs, known physical attributes, flood evidence, network impact, possible engineering methods, actual source citations, cost precedents, unknown site constraints.
- `InterventionProposal`: scenario-specific assumed passability, candidate measure, `hypothetical` / `implemented` / `verified` status, supporting evidence and review notes.
- `CounterfactualResult`: before/after network-impact measures and full reranking, graph/scenario version, limitations.

**Intervention proposal handshake:** Person 3 supplies a source-linked or **clearly schematic** intervention footprint/alignment and engineering evidence. Person 2 renders it as a **separate Cesium layer**, leaving original flood extents unchanged. Person 1 receives **only explicitly selected, scenario-scoped passability assumptions**, not the geometry or a claimed flood reduction. Identified cause, candidate physical measure, visual preview and graph counterfactual are four different types of evidence. See role-specific addenda.

**Avoid waiting:** Person 1 builds on fixture closures, Person 2 on fixture road IDs, Person 3 on a fixture investigation. Fixtures and computed/official records must be plainly distinguished, including in the UI. A small offline Python CLI that outputs these JSON records is fine; a continuously hosted backend is **not required**. API integration is optional if it helps and is reliable.

## Provisional algorithms, not mandatory prescriptions

- A directed weighted street graph using inspected Boston-streets routing fields, with topology/units checked; fall back to MassGIS/OSMnx if needed.
- Representative origin-destination accessibility measured before/after flood-road assumptions. Account for unreachable trips explicitly and test multiple essential destinations. Population/service weighting is optional where defensible data is available.
- For candidate corridor `e`, examine the **marginal reduction in accessibility loss if e remains open while other scenario closures are unchanged**. Use observed event counts and published scenario probabilities **separately**, not as interchangeable flood frequencies. Corridors may require reopening multiple adjacent links as a bundle.
- Recompute on changes to the intervention set. Rankings can rise, fall, or stay the same due to network interactions; never hardcode a decrease for neighboring corridors.
- Avoid premature commitments to any precise formula, hard closure-depth threshold, or universal weights. Document methods and test toy-network counterexamples first.

## Non-negotiable credibility and safety

- Future 2030/2050/2070 MC-FRM hazards are **not historical events** or live forecasts. Historical event footprints do not imply a measured minute-by-minute flood-water velocity field.
- Flood-polygon overlap does **not** establish road passability (bridges, tunnels, grade, local water levels). Mark `exposed` / `potentially_closed` and state assumptions. Never offer live emergency-driver navigation or assert a route is safe to drive.
- Visually animated water may be illustrative; never portray invented directions, depths, or timestamps as observed hydrodynamics.
- An idealized restored road edge is **not** evidence that a specific barrier/raised road works. Construction options require physical feasibility checks, site survey, hydraulics/drainage, utilities, permitting, and engineering review.
- Engineering LLM outputs are tied to actual source evidence and known fields. Unknown material, drainage, elevation, or structural condition stays unknown. Do not invent site-specific construction estimates. Label Boston's 2018 example berm (~$2.3M/2,000 ft) and raised road (~$13.6M/2,000 ft) as **2018 conceptual example costs**, not current local quotes.
- An 'implemented' fix is an asserted work record, not a verified flood-resilience guarantee. A scenario-dependent `verified` change requires sufficient engineering evidence; retain who/what verified it.
- Show source/provenance and a persistent statement: `Planning prototype — not for operational emergency routing or construction decisions.`

## Priorities and acceptance

1. Establish one real target area (Morrissey Blvd is candidate, contingent on actual flood overlap), a canonical graph, and one proven geospatial join. If missing, keep the mock fallback and flag the blockage.
2. Produce **real computed** baseline vs disrupted journeys and at least one meaningful corridor ranking using stated road-closure assumptions.
3. Let the UI inspect ranking evidence and demonstrate one genuine **re-ranking** after an idealized counterfactual.
4. Provide at least one source-grounded engineering investigation panel with candidate methods, real links, unknowns, and properly labeled conceptual cost references.
5. Keep the 3D view navigable, provenance visible, and local development/build/test commands working.

Run relevant tests/typecheck/build; inspect the UI if browser tooling exists. Do not claim verification without actually performing it. Include fallback data when official data is unavailable. Update the README with working setup, which outputs are computed, which are mocked, which sources were actually loaded, and the exact demo path.

Do not ask for approval on ordinary implementation choices, but do not fabricate missing facts. Do not spend the hackathon on real-time flood forecasting, full hydrodynamics, operational 911 routing, or definitive civil engineering design.
