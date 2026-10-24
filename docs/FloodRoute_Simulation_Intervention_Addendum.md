# FloodRoute — Person 2 Addendum: Visualize Physical Intervention Concepts

**Audience:** Person 2 / 3D flood scenario and UI integration lead; their Codex agents  
**Status:** Additive requirements to existing simulation responsibilities. Read `AGENTS.md`, `PROJECT_CONTEXT.md`, `FloodRoute_Team_Worksplit.md`, and this addendum. Read Person 3's second addendum **only for the shared physical-concept schema**, not to implement the engineering research.

## 1. Additional scope

The main Cesium scene must distinguish **(1) flood hazard**, **(2) disrupted roads and network impacts**, **(3) preliminary physical intervention concepts**, and **(4) assumed network counterfactuals**. Previously the demo merely highlighted a road and presumed it was fixed. The new visualization shows *what might physically be constructed* and how a planner can inspect it **without faking hydrodynamic effectiveness**.

Person 3 supplies a source-backed `ConceptIntervention` (geometry may be sourced, schematic, or absent). You render it. Person 1 supplies ranking/accessibility before/after output under user-selected passability assumptions. You display the output; do not compute it yourself.

## 2. Scene interactions and behaviors

- Add `Interventions` overlay toggle and an `Existing / Concept preview` visual comparison mode.
- Render at least **one** source-grounded *type* with labeled **schematic alignment if site geometry is not verified**. Prefer a shoreline berm + floodwall concept where a relevant Morrissey precedent is confirmed, but do not assert an exact alignment or dimensions without a matching source.
- Camera fly-to the concept and selected affected road; avoid placing it in the middle of water or buildings if the map/ground alignment is unverified.
- Use differentiated appearance: **published/verified asset** versus **conceptual/schematic proposal** (line style, transparency, badges and legend). Do not depict an unbuilt proposal as completed infrastructure.
- For roadway elevation, use a narrow segment/overlay or conceptual mesh; for berm/wall a line + volumetric schematic; for drainage a point symbol and possibly a labeled context polygon (not fake underground pipes).
- If absolute elevations are requested, validate the height source/datum. Use a safe schematic height where clearly labeled; no inferred crest relative to Cesium terrain from depth alone.
- Selecting `Preview intervention` **must not change** published flood extents, depths, or exposed roads.
- A distinct button `Test idealized access assumption` opens explicit affected road IDs and scenario IDs for confirmation, then invokes a teammate adapter returning `CounterfactualResult`; show before/after ranking as **network-only, assumption-conditional**, not physical flooding changes.
- Preserve the historical-versus-modeled-versus-illustrative statuses in all panels; historical water animations remain illustrative unless time-resolved local flood physics are actually available.

## 3. Contract boundary

Use Person 3's `ConceptIntervention` shape as **one versioned optional adapter / fixture**. Person 1 owns canonical `road_id` and shared contract changes; Person 3 controls the engineering proposal, not the Cesium render. Never change `App.tsx`, types or shared styling simultaneously with another agent; you are the final app integrator.

Existing `FloodRouteDataSource` can be extended additively, e.g. `getConceptInterventions(investigationId)` and `getCounterfactual(assumption)`, or use two separate typed adapters. **Do not force a backend** if validated JSON fixtures are enough for this demo; don't bake engineering prose into map components.

When Person 3 or Person 1 is not ready, use an internally consistent fixture with IDs matching the canonical manifest version (or a clearly temporary fixture graph version). Mocked counterfactual rankings must be marked mock, not computed.

## 4. First visual demonstration

1. Show actual official flood extent over a bounded Boston area, if data can be loaded reliably.
2. Click a road that Person 1 ranks highly. Show its associated scenarios and affected journeys.
3. Open Person 3's road/hotspot diagnosis; select a proposed measure.
4. Render an **illustrative** volumetric berm or floodwall with visible source and location uncertainty.
5. Confirm `Test idealized access assumption` and display the **real** Person 1 computed reranking (or a visibly marked fixture if integration is not ready).
6. The water/flood layer stays exactly the same, with a clear note: 'Protection outcome not hydraulically modeled'.

## 5. Acceptance criteria

- [ ] Working Cesium 3D scene + existing scenario, road and route interactions preserved.
- [ ] Physical intervention concept appears as a separate toggleable 3D scene layer with proper citation/provenance.
- [ ] Physical geometry is not conflated with a selected road or magically 'protected' road state.
- [ ] No automatic flood removal, no claimed hydrodynamic change and no invented protection costs.
- [ ] Screenshot-ready before/after conceptual visualization; no unsupported real-time water-flow claims.
- [ ] Clear handoff to Person 1's computed graph counterfactual and Person 3's option/evidence UI.
- [ ] Performance remains workable on a team laptop, with graceful no-token/offline fallback and local build checks.

## 6. Priorities

**First:** one real flood overlay correctly located; **second:** one coherent conceptual physical intervention from fixture; **third:** road exposure mapping and ranking integration; **fourth:** polish, extra structure types and historical replay. Do not let cosmetic hydrodynamics delay the real scenario or working road IDs.
