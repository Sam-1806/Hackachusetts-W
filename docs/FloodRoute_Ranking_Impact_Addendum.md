# FloodRoute — Impact Ranking Addendum (Person 1)

**October 24, 2026 · Additional context only**  
**Read alongside:** `FloodRoute_Team_Worksplit.md`, `PROJECT_CONTEXT.md`, and `AGENTS.md`.  
**Scope:** This document adds the newly agreed **property-loss, community-impact, and objective-setting requirements**. It does **not** replace the existing road-graph, emergency-access, alternative-route, scenario, or reranking instructions. Keep those implementations and shared interfaces unless a coordinated extension is needed.

## 1. What changed in the product idea

The previous ranking focused on **transportation accessibility**: a flooded connection matters if its loss causes significant detours or disconnects important journeys, considering all available alternatives.

We now want to assess the **broader harm of flooding**, including:

- **Direct economic loss:** Potential damage to buildings, contents, vehicles, businesses, and public infrastructure, valued in dollars **without discounting losses because the owner is wealthy**. A destroyed expensive asset still represents substantial financial damage.
- **Community hardship:** Displacement, disruption to livelihoods, and difficulty recovering from losses. Income, renter status, and access to resources can help describe *recovery capacity*, not determine whether someone's property is worth counting.
- **Transportation/access loss:** The existing modeled detours, isolation, and access to essential services. Keep this analysis intact.
- **Public-sector consequences (when supported):** Public infrastructure repair, response expenditures, and other municipal exposure, separately from total private economic damage.

These represent **different objectives**, not four interchangeable numerical scores. The system should show their components and let planners understand tradeoffs. There is **no agreed final universal ranking formula**.

> **Essential causal distinction:** A road that floods and a nearby property that floods may share the *same underlying water hazard*. The road itself is not necessarily responsible for the property's damage. A road-passability improvement does not automatically prevent nearby buildings from flooding.

## 2. Change the ranking *object* when necessary

We should retain road/corridor rankings for **transportation criticality**, but not force all property losses onto a specific road.

A useful extension is a **geographic flood-impact hotspot** (block, catchment, corridor-adjacent area, or other defined polygon), containing exposed properties, residents, and infrastructure. A hotspot can reference roads and drainage assets without claiming that repairing any one of them will solve all its problems.

Consider displaying **two linked views** before attempting a global score:

1. **Critical road corridors:** Ranked from graph-based accessibility loss and redundancy, as already planned.
2. **Flood-impact hotspots:** Characterized by property exposure/loss, affected households, hardship indicators, and any overlapping transportation disruption.

A later combined decision queue *could* use adjustable stakeholder priorities, a Pareto comparison, or transparent constraints; treat these as candidate designs, not a decided algorithm. Do not sum unrelated raw units such as dollars, detour minutes, and a social-vulnerability percentile without transparent normalization and policy choices.

## 3. What to measure, and what NOT to infer

| New dimension | Practical first-pass measurement | More ambitious measurement | Important caveat |
|---|---|---|---|
| Property exposure | Number of intersected parcels/buildings, exposed assessed value **where available** | Expected physical repair/contents loss using depth-damage functions and replacement-cost inputs | **Assessment value ≠ replacement cost ≠ actual damage.** An intersected parcel is not necessarily damaged. |
| Community hardship | Affected housing units/people plus separately reported area-level recovery indicators | Modeled displacement, recovery duration or out-of-pocket burden | Area-level statistics do not establish any individual owner's income or insurance coverage. |
| Public fiscal impact | Identified public facilities/assets exposed | Modeled public repair or emergency-response expenditures | Private insured losses are not automatically government expenditures. |
| Transport access | **Use the existing ranking engine** | Broader service demand and user-defined travel priorities | Do not recalculate or duplicate the established network work here. |

**Avoid double-counting:** An insurer's payout is a financing/transfer consequence of damage, not an additional destroyed asset. Likewise, a property-loss estimate should not automatically include its full market value *and* full repair cost. Vehicle damage or business interruption must not be presented as measured simply because a parcel was exposed.

### Equity without erasing expensive damage

Two areas might have (hypothetically) **$12M** versus **$3M** in physical losses. Under a *minimize total monetary damage* objective, the first area can rank higher. The second may experience more displacement and weaker ability to recover. Represent **both facts**, rather than reducing the first area's dollar losses or silently overriding them with income weights.

For a transparent first version, prefer **separate economic, accessibility, and hardship panels**, with optional user-configured priorities only after the components are trustworthy. Government, insurers, and community planners may legitimately use different decision objectives; do not pretend one score is universally correct.

## 4. Additional public data to investigate

These are **identified source systems**, not confirmation that relevant layers are downloaded, joinable, complete, or suitable for the selected block. Test availability, fields, CRS, coverage, dates, and licensing before using them.

| Source | URL | Potential contribution | Ownership / caution |
|---|---|---|---|
| Boston parcels, current | https://gis.boston.gov/arcgis/rest/services/Parcels/Parcels_current/FeatureServer | Parcel polygons and geographic IDs | **P2** can produce spatial exposure; parcel boundaries aren't building footprints. |
| Boston property assessment GIS | https://gis.boston.gov/arcgis/rest/services/Assessing/properties_boston_gov/FeatureServer | Assessed values and some property characteristics (inspect exact layer fields) | **P1** can assess economic proxy; FY26 assessment is not replacement value. |
| BWSC citywide inundation model | https://www.bwsc.org/boston-inundation-model | Rainfall/stormwater and coastal-related inundation scenarios | **P2** hazard provider; machine-readable download of needed layers not yet confirmed. |
| BWSC adaptation model scenarios | https://www.bwscstormviewer.com/flood-modeling | *No action*, *shoreline protection*, *shoreline plus outfall adaptation* comparisons | A promising **actual modeled intervention comparison**; verify spatial data access before computing gains. |
| MAPC climate vulnerability analysis | https://climate-vulnerability.mapc.org/ | Tract/area-level sensitivity and adaptive-capacity indicators | **P1** social-context layer; check data vintage, geography and download access. |
| FEMA Hazus Flood Technical Manual | https://www.fema.gov/sites/default/files/documents/fema_rsl_hazus-7-fltm_06272025_0.pdf | Flood depth-damage methodology for buildings/contents and uncertainty context | Not a ready-to-use Boston property damage table; calibration required. |
| Boston 311 (optional) | https://data.boston.gov/ | Drainage complaints, blocked catch basins, recurrent localized issues | Corroboration only; complaint frequency reflects reporting behavior, not true flood frequency or proven causation. |
| Census ACS (optional) | https://data.census.gov/ | Household, housing, income and mobility indicators | Aggregate carefully; do not infer an individual's financial status. |

Retain the existing official coastal flood, road, hospital, fire station and Census sources already defined in the team plan; they are intentionally **not repeated here**.

## 5. Minimal additive data contract (proposal, not a rewrite)

Do not break `RoadRankingResult`, `FloodExposureResult`, `InterventionProposal`, or the canonical `road_id` mapping. Consider extending outputs with a **separate** record keyed by `scenario_id` and `area_id` (and spatial polygon where available):

```ts
// Illustrative new shapes; coordinate with Person 2 before freezing them.
interface AreaImpact {
  scenario_id: string;
  area_id: string;
  area_geometry_ref?: string;  // ID or URI to a validated polygon
  exposed_parcels?: number | null;
  exposed_assessed_value_usd?: number | null;
  estimated_physical_loss_usd?: number | null; // only with defensible damage model
  estimated_loss_method?: string;
  affected_people_estimate?: number | null;
  recovery_indicators?: Record<string, number | null>;
  associated_road_ids?: string[]; // spatial association; NOT causal attribution
  provenance: unknown; // Reuse the project's existing provenance contract
  limitations: string[];
}

interface ImpactProfile {
  scenario_set_id: string;
  graph_version: string;
  transport_impact_ref?: string; // Existing computed RoadRankingResult
  area_impacts: AreaImpact[];
  objective_mode?: 'economic' | 'accessibility' | 'hardship' | 'multi_objective';
  notes: string[];
}
```

**Integration boundaries:** Person 2 may deliver normalized parcel/building exposure alongside road exposure; Person 1 computes and presents impact components; Person 3 supplies candidate intervention assumptions/evidence. None of these additions requires another person's *completed* subsystem to start: use a small tagged fixture first.

## 6. Reranking after an intervention: the new rule

Keep the already planned **network-wide graph reranking**. Add a strict distinction between two intervention effects:

- **Access-only counterfactual** (e.g. assume a roadway remains passable): recalculate transportation access and road rankings. **Do not decrease property-damage estimates** or floodwater extent on that basis.
- **Hydraulic/drainage intervention** (e.g. a floodwall system, outfall adaptation, or catchment improvement): property exposure/loss and other affected roads may change **only if a defensible updated flood surface or officially modeled before/after scenario is provided**. Otherwise show a proposed intervention, with its benefit *unknown*.

A completed project should be recorded with method, date, location, documented design limit, and evidence before assumptions change in the verified planning baseline. Hypothetical outcomes stay in sandbox scenarios. A project may protect one road while leaving surrounding properties flooded, and prioritization elsewhere may go **up or down** after reranking.

## 7. Practical priority for Person 1 (avoid expanding the sprint uncontrollably)

**Must retain:** Working computed transportation criticality, alternatives, and network-wide reranking from the original assignment.

**Add now, if source availability allows:** A compact *area-impact* module showing (a) exposed parcel count and, where actually joined, assessed value; (b) **one** socioeconomic recovery-context measure at tract/block-group level; and (c) the transport impact **side by side**. Keep missing values as `null`, not zero, and never label a parcel's full assessed value as flood damage.

**Stretch:** Depth-based monetary loss modeling using calibrated building/contents inputs; a multi-objective comparison across candidate areas; validated modeled hydraulic intervention scenarios. These should not block the transportation ranking MVP.

**Acceptance checks to add:**

- A high-value exposed property is **not discounted** in the economic dimension because its neighborhood is wealthy.
- An economically vulnerable area can have greater hardship **without altering the same dollar-value loss**.
- A road made passable in a graph counterfactual changes transport metrics **but not property-loss metrics**.
- A hotspot may overlap several roads without claiming any one road caused building flooding.
- If exposure geometry exists but no depth/damage model does, display **exposure**, not invented repair losses.
- Scenario provenance and time horizon stay attached to every output; no misuse of 311 complaint count as actual recurrence frequency.

**Success criterion:** The ranking system can explain *why* a location matters across different perspectives **without conflating flood exposure, economic damage, social hardship, and the causal benefit of a specific road intervention**.
