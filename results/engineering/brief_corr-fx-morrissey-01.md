# Engineer review brief: William T Morrissey Boulevard (fixture stretch)

Corridor `corr-fx-morrissey-01` · roads fx-r-001, fx-r-002, fx-r-003, fx-r-004 · graph `fixture-v0.1` · generated 2026-10-24T20:31:49+00:00

> Preliminary investigation aid. Not a design, certification, or cost estimate.
> - ILLUSTRATIVE FIXTURE. Geometry comes from the MassDOT Road Inventory (S10). Road IDs, flood exposure, and ranking numbers are mock placeholders, not analysis results.
> - Some inputs are MOCK fixture data (see provenance.input_data_status). Do not present network or flood numbers as results.
> - Candidate methods are options to investigate, not recommendations or designs. A licensed engineer must review.
> - No hydraulic modelling was performed; nothing here shows that a measure would keep the road passable.
> - Published costs are 2018 sample figures for different sites and are not estimates for this corridor.
> - Road Inventory code values are passed through undecoded; widths assumed to be in feet.
> - Candidate construction methods are gated on the cause assessment; the flooded road may be an impacted location rather than the asset that needs work.

## Why this corridor is a priority
Rank 1, impact 1840.0 weighted added travel seconds (mock) (data status: mock) [network_impact].
- Dorchester origin -> emergency department (fixture): 540 s normal, 780 s flooded
- Fire station -> Columbia Point incident point (fixture): 420 s normal, unreachable
- Savin Hill origin -> community center (fixture): 360 s normal, 410 s flooded

## Cause assessment (hypotheses, not a diagnosis)

**Finding:** Flooding on this corridor is documented or modelled, and drainage complaints are reported nearby. The cause is not established. Possible explanations: coastal overtopping / overland inflow, high tide blocking stormwater discharge / backflow, localized inlet obstruction / debris.

**Why the road may not be the asset to fix:** The road is where flooding is seen. The asset that needs work may be an inlet, pipe, outfall, or shoreline opening elsewhere in the system.

- **Coastal overtopping / overland inflow**: possible. Evidence is consistent with this cause but does not establish it.
  - Supports: [published_model] MC-FRM 2050, 1% annual exceedance (projected): 4 of 4 corridor roads exposed; depth not available / requires site survey. (mock) [S06]
  - Supports: [observed_measurement] January 2018 coastal flood (observed footprint): 1 of 4 corridor roads exposed; depth not available / requires site survey. (mock) [S07]
  - Supports: [published_model] Present-day flood pathways into the study area were identified at Tenean Beach/Conley Street, southeast of Kosciuszko Circle, Bianculli Boulevard, Pattens Cove, and Quincy Shore Drive/Neponset Trail; in a 2030 extreme event these expand and new pathways appear from Moakley Park and the I-93 underpass. [S12]
  - Does not prove it: A flood polygon over the road does not show where water enters at road scale.
  - Unknown: Shoreline / edge elevations along the pathway (survey, vertical datum); Which opening or low point admits the water; Whether the corridor floods before or after adjacent shoreline overtops
- **High tide blocking stormwater discharge / backflow**: possible. Evidence is consistent with this cause but does not establish it.
  - Supports: [published_model] Stormwater flooding may remain a significant problem in the Central section because of limited gravity discharge at high tide; one option assumes BWSC's proposed additional stormwater infrastructure for the Northern section. [S12]
  - Does not prove it: High tide alone does not show that a specific outfall is failing.
  - Unknown: Which outfall(s) serve the corridor inlets and who owns them; Outfall invert elevations vs tide levels (datum); Whether tide gates / check valves exist and work; Timing of past flooding vs tide and rainfall
- **Localized inlet obstruction / debris**: possible. Evidence is consistent with this cause but does not establish it.
  - Supports: [observed_report] 3 311 report(s) at INTERSECTION of Freeport St & William T Morrissey Blvd  Dorchester  MA (Catchbasin: 3), 2021-04-28 to 2021-04-29, 3 m from corridor. [BOS311]
  - Supports: [observed_report] 3 311 report(s) at INTERSECTION of Freeport St & Victory Rd  Dorchester  MA (Catchbasin: 3), 2021-05-04 to 2022-10-05, 73 m from corridor. [BOS311]
  - Supports: [observed_report] 1 311 report(s) at INTERSECTION of Blanche St & Victory Rd  Dorchester  MA (Catchbasin: 1), 2026-03-16 to 2026-03-16, 74 m from corridor. [BOS311]
  - Against: [engineering_record] Closure note at INTERSECTION of Freeport St & Victory Rd  Dorchester  MA: "BWSC states checked all catch basins and all are taking water. 10/06" [BOS311]
  - Against: [engineering_record] Closure note at 1 Worrell St  Dorchester  MA  02122: "BWSC reports no flood on arrival." [BOS311]
  - Does not prove it: A 311 report is an allegation, not a confirmed blockage; the BWSC model does not represent individual clogged basins.
  - Unknown: Current condition of the corridor catch basins; Cleaning history from the owner; Whether reported ponding cleared after cleaning; Not represented in the BWSC Inundation Model (see ev-bwsc-model-scope).
- **Insufficient storm-drain or inlet capacity**: unresolved. No discriminating evidence yet.
  - Does not prove it: Road width or a flood footprint does not reveal underground capacity.
  - Unknown: Pipe diameters, slopes and connectivity; Contributing catchment area; Design storm used for the existing system; Not represented in the BWSC Inundation Model (see ev-bwsc-model-scope).
- **Unfavorable street grading / ponding**: unresolved. No discriminating evidence yet.
  - Does not prove it: A low point alone does not prove deficient drainage, and regrading can push water elsewhere.
  - Unknown: Validated surface elevations along the corridor (from Person 2 / survey); Inlet positions relative to low points
- **Multiple simultaneous causes / unresolved**: possible. 3 mechanisms have some supporting evidence; the evidence does not discriminate between them.

### Assets to inspect
Owner codes for nearby mapped catch basins: DCR 47, PRIV 10, BWSC 2. Send maintenance requests to the confirmed owner; do not assume BWSC. 10 nearest of 59 mapped catch basins listed.

| Type | Role | ID | Owner | Location |
|:--|:--|:--|:--|:--|
| road | impacted_location | fx-r-001 | unknown | William T Morrissey Boulevard (fixture stretch) |
| road | impacted_location | fx-r-002 | unknown | William T Morrissey Boulevard (fixture stretch) |
| road | impacted_location | fx-r-003 | unknown | William T Morrissey Boulevard (fixture stretch) |
| road | impacted_location | fx-r-004 | unknown | William T Morrissey Boulevard (fixture stretch) |
| catch_basin | possible_cause_asset | 13LCB106 | DCR (as_mapped_unverified) | 42.299373,-71.049603 (6 m from corridor) |
| catch_basin | possible_cause_asset | 13LCB105 | DCR (as_mapped_unverified) | 42.299527,-71.049416 (6 m from corridor) |
| catch_basin | possible_cause_asset | 13LCB114 | DCR (as_mapped_unverified) | 42.297644,-71.049067 (6 m from corridor) |
| catch_basin | possible_cause_asset | 13LCB123 | DCR (as_mapped_unverified) | 42.295980,-71.048198 (7 m from corridor) |
| catch_basin | possible_cause_asset | 13LCB128 | DCR (as_mapped_unverified) | 42.295674,-71.048008 (7 m from corridor) |
| catch_basin | possible_cause_asset | 14LCB43 | DCR (as_mapped_unverified) | 42.301749,-71.048572 (7 m from corridor) |
| catch_basin | possible_cause_asset | 14LCB45 | DCR (as_mapped_unverified) | 42.301782,-71.048679 (7 m from corridor) |
| catch_basin | possible_cause_asset | 14LCB25 | DCR (as_mapped_unverified) | 42.300433,-71.049553 (8 m from corridor) |
| catch_basin | possible_cause_asset | 13LCB111 | DCR (as_mapped_unverified) | 42.297331,-71.048915 (8 m from corridor) |
| catch_basin | possible_cause_asset | 13LCB103 | DCR (as_mapped_unverified) | 42.299834,-71.049381 (9 m from corridor) |
| pipe | possible_cause_asset | - | unknown | Pipes connecting corridor inlets to their outfall (not public) |
| outfall | possible_cause_asset | - | unknown | Outfall(s) serving the corridor inlets: not identified |
| shoreline | possible_cause_asset | - | unknown | Central section shoreline pathway, Bianculli Blvd to Freeport St (per S12) |

### Next investigation steps
1. Survey the shoreline edge and suspected entry pathway
2. Trace corridor inlets to their outfall(s) and confirm owner
3. Compare reported flooding dates against tide and rainfall records
4. Inspect and, if blocked, clean the corridor catch basins
5. CCTV the connecting pipe if cleaning does not restore drainage
6. Convene asset owners and collect drainage records before choosing a measure
7. Drainage capacity assessment (inlets and pipes) with the owner's records
8. Topographic survey of gutters, low points and inlet positions

### Cause-matched options (only after checks)
- **Inspect and, if blocked, clean the corridor catch basins** [maintenance, inlet_blockage: possible]. Gate: If inspection confirms blockage. Applicable if: Catch-basin reports or debris notes near the corridor. Could fail: Flooding persists after cleaning, pointing to capacity or tide causes instead. Downstream checks: Record whether ponding recurs after cleaning; Report to the asset owner, not by default to BWSC. Cost: cost_estimate_unavailable (inputs for a quote: Number of basins, Owner's maintenance contract rates).
- **Evaluate continuous coastal protection (berm, wall, raised road) only where overland entry is demonstrated** [capital, coastal_overland: possible]. Gate: Only after checks confirm this mechanism. Applicable if: Survey shows overland entry along a definable alignment that ties into high ground. Could fail: Water enters around the ends; outfalls behind the barrier still back up at high tide (see BWSC adaptation scenarios). Downstream checks: Check drainage behind the barrier at high tide; Check displaced water to neighbours. Cost: published_example_available.
- **Review tide gate / backflow control, storage or pumping at the outfall** [capital, tidal_outfall_backwater: possible]. Gate: Only after checks confirm this mechanism. Applicable if: Outfall is identified and tide-constrained discharge is shown by timing or modelling. Could fail: Storage or pumping undersized; gate closed during rain with no relief; power failure. Downstream checks: Upstream ponding when the gate is closed; Owner coordination (DCR/MassDOT/BWSC/private). Cost: cost_estimate_unavailable (inputs for a quote: Outfall diameter and invert, Design tide and storm, Required storage volume or pump rate).

### Cannot presently be claimed
- Do not choose road elevation from flood exposure or network priority alone; it addresses coastal overland inflow only.
- Drainage or maintenance actions have no published cost example here: cost_estimate_unavailable until quoted.
- 2018 barrier/raised-road sample costs apply only to coastal capital options, never to catch-basin cleaning or drainage retrofits.
- A drainage fix does not change road exposure, property-loss projections, or network ranking without validated before/after flood analysis.
- No avoided property damage is claimed.
- Hypotheses to investigate, not a hydraulic diagnosis.
- Statuses are evidence categories, not probabilities.
- 311 data are resident reports with closure notes; catch basin data are mapped attributes, not condition.
- Pipe network, outfall locations, inverts and maintenance logs were not publicly available as data.
- Engineer review required.

## Documented flood exposure
- **MC-FRM 2050, 1% annual exceedance (projected)** (future_model, mock): exposed 4, unknown 0; depth: not available / requires site survey. [S06] Projected annual-exceedance scenario; not a prediction of a dated storm. Extent overlap does not prove the road was impassable.
- **January 2018 coastal flood (observed footprint)** (historical_observed, mock): exposed 1, unknown 3; depth: not available / requires site survey. [S07] Observed footprint; does not show street-level depth, velocity, or timing. Extent overlap does not prove the road was impassable.

## Road facts (MassDOT Road Inventory)
- Street name: WILLIAM T MORRISSEY BOULEVARD
- From street: NEPONSET AVENUE
- To street: WILLIAM T MORRISSEY BOULEVARD
- Number of lanes: 3 lanes
- Surface width: 34 ft (assumed)
- Right-of-way width: 100 ft (assumed)
- Median width: 8 ft (assumed)
- Annual average daily traffic: 36537-44937 vehicles/day
- AADT year: 2014, 2015
- Surface type (code): 6
- State functional class (code): 3
- Jurisdiction (code): 3
- Structural condition (code): 2
- Curb (code): 3
- Median type (code): 1, 2
- Street operation (code): 2
- Pavement structure / layer thicknesses and materials: not available / requires site survey
- Surveyed road crown / edge-of-pavement elevation (with vertical datum): not available / requires site survey
- Storm drain inlet and pipe capacity, outfall locations and tide-gate status: not available / requires site survey
- Underground utilities (water, sewer, gas, electric, telecom) and depths: not available / requires site survey
- Soil / groundwater conditions and foundation suitability: not available / requires site survey
- Building setbacks and first-floor elevations adjacent to the right-of-way: not available / requires site survey

Matched inventory segments: 51287, 58285, 62774, 62908 [S10]

## Candidate measures to investigate
### Raise the roadway profile (raised roadway barrier)
Raise the road (and usually sidewalks) so the road itself acts as a flood barrier and/or stays above design flood elevation.
- The guideline sample considers raised roadways with a 4-ft grade change, and notes the approach may also apply to elevating emergency evacuation routes. [S11.sec6#p3]
- Option 1 (retaining walls and/or slopes) may be feasible where buildings are set back at least 14 ft from the back of sidewalk. [S11.sec6#p3]
- The guidelines do not recommend a raised roadway barrier where existing buildings sit at the back of sidewalk; raising only the roadway creates safety, drainage, ADA and access impacts. [S11.sec6#p3]
- Once a street is raised, a stormwater pump system (pumps, generators) adds ongoing O&M cost; the guideline expects stormwater costs to be significant, citing Miami Beach raised-road projects. [S11.sec6#p10]
- *Hypothesis:* Raising one corridor does not by itself block flood pathways that enter around its ends or through adjacent low ground.
- Failure modes: Flanking around the ends of the raised section; Ponding behind the raised road without pumped drainage; Utility relocation conflicts; Driveway / building access grade conflicts
- Data needed: Surveyed road and adjacent grade elevations with vertical datum; Building setbacks and first-floor elevations; Utility locations and depths; Drainage network and outfall/tide-gate details; Geotechnical borings
### Vegetated berm / landscaped embankment along the flood side
An earthen, planted embankment with crest and access paths placed between the water and the road.
- The guideline sample berm extends about 2,000 ft with an assumed grade change of about 2 ft for 2030 design flood elevation (DFE) conditions, with an incremental 2070 raise considered. [S11.sec4#p10]
- The sample design drawings tabulate crest, slope, and access-path widths by height, so a berm needs a horizontal footprint that grows with height. [S11]
- The Morrissey study's key findings say coastal resilience measures should focus on nature-based solutions. [S12#p174]
- *Hypothesis:* A berm only protects the road if it ties into high ground at both ends; otherwise water can route around it.
- Failure modes: Insufficient open space for slopes; Flanking at ends; Scour/erosion on flood-side slope; Seepage through or under the embankment
- Data needed: Available open space and ownership on the flood side; Topography (LiDAR is a start, survey needed); Geotechnical and groundwater conditions; Wetland / resource-area permitting constraints
### Strengthen alternate access routes
Rather than protecting this corridor, investigate whether improving a detour route preserves the same journeys.
- Whether a detour exists, and how long it is, comes from the network analysis for this corridor (see network impact). [network_impact]
- Network results report a detour for journeys j-fx-01, j-fx-03; disconnected: j-fx-02. [network_impact]
- *Hypothesis:* A detour is only useful if it is itself outside the flood scenario footprint and has capacity for diverted traffic.
- Failure modes: Detour floods in the same scenario; Detour lacks capacity or emergency-vehicle suitability
- Data needed: Flood exposure of the detour roads; Detour geometry and capacity
### Deployable (temporary) flood barrier
Barriers deployed before or during a flood and retracted afterward; may be an interim measure.
- The guideline defines deployable barriers as systems deployed before and/or during a flood event and retracted afterward, and lists types from pre-installed and passive systems to mobile units and water-filled tubes. [S11.sec7#p3]
- The guideline presents a comparison matrix rather than a sample site; product mentions are not endorsements. [S11.sec7#p3]
- *Hypothesis:* Deployment depends on forecast lead time, trained crews, storage, and access; a barrier placed across a road closes that road while deployed.
- Failure modes: Not deployed in time; Seepage at joints or under the base; Blocks the road it is meant to protect while deployed
- Data needed: Who deploys and stores it; Warning time available for the relevant flood type; Foundation / anchoring surface along alignment

Not offered: Drainage, backflow prevention, and stormwater storage (Passed screening but outside the top 4 offered.); Raise / extend an existing seawall or waterfront edge (No evidence of an existing seawall at this corridor's flood edge.)

## Local precedent
- [study_finding] Present-day flood pathways into the study area were identified at Tenean Beach/Conley Street, southeast of Kosciuszko Circle, Bianculli Boulevard, Pattens Cove, and Quincy Shore Drive/Neponset Trail; in a 2030 extreme event these expand and new pathways appear from Moakley Park and the I-93 underpass. [S12#p74]
- [study_finding] The study notes flood protection is being advanced outside the central section (Bianculli Boulevard to Freeport Street), leaving that area as a key storm-surge pathway into the study area. [S12#p182]
- [prior_design_intent] The study records that DCR's 2017 Morrissey Boulevard redesign planned to elevate the roadway for coastal resiliency, with a stated target of limiting tidal-flooding closures to fewer than 3 in 2065. [S12#p108]
- [study_finding] Stormwater flooding may remain a significant problem in the Central section because of limited gravity discharge at high tide; one option assumes BWSC's proposed additional stormwater infrastructure for the Northern section. [S12#p166]
- [study_finding] Key findings state flood mitigation could be implemented along the coastline and Dorchester Bay Basin, should focus on nature-based solutions, and that environmental permitting is expected to be complex. [S12#p174]
- [study_finding] Infrastructure in the area is owned by multiple jurisdictions (including MassDOT, DCR, MBTA, City of Boston, utilities, and private owners), so any project needs coordinated ownership and permitting. [S12#p174]

## Published cost context (2018 samples, not transferable)
- These are conceptual 'opinion of probable cost' figures for sample barriers at sample sites in the City of Boston guidelines published October 2018. They are not bids, not 2026 prices, and not transferable per-foot rates for another site.
- Escalation from the 2018 publication date to today is not applied here. Any escalation index and base year must be chosen by a cost estimator.
- The guidelines state each opinion reflects sample design considerations and does not reflect engineering analyses prepared for design.

| Sample | Length | Total | Unit | Key exclusions |
|:--|--:|--:|--:|:--|
| Sample raised roadway, Option 1 (retaining wall oceanside) [S11.sec6#p12] | 2,000 ft | $13,600,000 | $683,000/100 linear ft | Pumps and generators (guideline cites typical pump station cost variation of $500k to $20M), Private utility relocation (gas, electric, steam, telecom), Owner's costs |
| Sample raised roadway, Option 1.A (retaining walls both sides; no built property within 14 ft of ROW) [S11.sec6#p13] | 2,000 ft | $15,800,000 | $788,000/100 linear ft | Pumps and generators, Private utility relocation, Owner's costs |
| Sample raised roadway, Option 2 (roadway and sidewalks raised with new development) [S11.sec6#p13] | 2,000 ft | $15,100,000 | $757,000/100 linear ft | Option 2 exclusion notes were not extracted for this build; read S11.sec6 p.61 onward before citing; do not assume it includes pumps, utilities, or permitting |
| Sample vegetated berm barrier, 2030 DFE conditions [S11.sec4#p10] | 2,000 ft | $2,300,000 | $116,000/100 linear ft | Owner's costs, Design/permitting, Construction/logistical/insurance |
| Sample vegetated berm, 2070 DFE incremental increase [S11.sec4#p10] | 5,300 ft | $3,200,000 | $61,000/100 linear ft | Owner's costs, Design/permitting, Construction/logistical/insurance |

Site-specific estimate: Site cost estimation is a separate engineering task.

## Concept interventions for preview (not designs)

Previews show where a measure might sit. They do not mark roads protected or change flood layers.

### Inspect and, if blocked, clean the corridor catch basins (featured preview)
- Type / target: drainage_upgrade / catch_basin; geometry: **sourced_asset_location** (Existing asset location (cited). Not a design.). 10 nearest mapped catch basins (BWSC layer). Locations of existing assets, not new works.
- Addresses: inlet_blockage (possible)
- Would confirm: Field inspection finding debris/sediment in corridor basins; Owner cleaning log entries followed by ponding clearing
- Would refute: Basins found clear and taking water while ponding persists (e.g. 311 closure note 'all are taking water')
- Unresolved physical survey: Basin condition inspection; connecting pipe CCTV if needed.
- Unresolved ownership check: Mapped owner codes are unverified; confirm before sending a maintenance request.
- Unresolved drainage assessment: Outfall location, invert and tide-gate status; pipe sizes (not public).
- Unresolved permitting: Usually none for cleaning; capital drainage work needs owner approval and street-opening permits.
- Cost: cost_estimate_unavailable
### Raise the roadway profile (raised roadway barrier)
- Type / target: raised_roadway / road; geometry: **sourced_asset_location** (Existing asset location (cited). Not a design.). Centerlines of the existing corridor road segments (MassDOT Road Inventory). The extent of any raised section is not designed.
- Addresses: coastal_overland (possible)
- Would confirm: Surveyed shoreline/edge elevations below the event water level along a continuous path to the road; High-water marks or photos showing overland flow from the bay side (e.g. USGS 2018 records)
- Would refute: Surveyed edge is above the event water level with no opening; Road floods during rain at normal tide with no overland connection
- Unresolved physical survey: Road, sidewalk and adjacent grade elevations with vertical datum; building setbacks (>=14 ft rule).
- Unresolved ownership check: Roadway jurisdiction is a raw Road Inventory code (not decoded); adjacent property ownership unknown.
- Unresolved drainage assessment: Pumped drainage behind a raised road; outfall and tide conditions.
- Unresolved permitting: Coastal/environmental permitting expected to be complex per S12.
- Cost context (2018 samples, not quotes): Sample raised roadway, Option 1 (retaining wall oceanside); sample length 2,000 ft: $13,600,000; Sample raised roadway, Option 1.A (retaining walls both sides; no built property within 14 ft of ROW); sample length 2,000 ft: $15,800,000; Sample raised roadway, Option 2 (roadway and sidewalks raised with new development); sample length 2,000 ft: $15,100,000
### Vegetated berm / landscaped embankment along the flood side
- Type / target: berm / shoreline; geometry: **schematic** (SCHEMATIC - illustrative only, not an engineered or published alignment). Drawn 40 m east (bay side) of a corridor centerline for display only. Not a surveyed shoreline, not the Morrissey study's alignment (figures in S12 are images; no vector alignment extracted).
- Addresses: coastal_overland (possible)
- Would confirm: Surveyed shoreline/edge elevations below the event water level along a continuous path to the road; High-water marks or photos showing overland flow from the bay side (e.g. USGS 2018 records)
- Would refute: Surveyed edge is above the event water level with no opening; Road floods during rain at normal tide with no overland connection
- Unresolved physical survey: Shoreline position, open-space width and topography; tie-in to high ground at both ends.
- Unresolved ownership check: Owner of the flood-side land strip not established.
- Unresolved drainage assessment: Drainage of water trapped landward of the berm.
- Unresolved permitting: Wetland / resource-area permitting; nature-based design review.
- Cost context (2018 samples, not quotes): Sample vegetated berm barrier, 2030 DFE conditions; sample length 2,000 ft: $2,300,000; Sample vegetated berm, 2070 DFE incremental increase; sample length 5,300 ft: $3,200,000
### Deployable (temporary) flood barrier
- Type / target: deployable_barrier / opening; geometry: **none** (No location claimed). The opening that would need a gate has not been identified.
- Addresses: coastal_overland (possible)
- Would confirm: Surveyed shoreline/edge elevations below the event water level along a continuous path to the road; High-water marks or photos showing overland flow from the bay side (e.g. USGS 2018 records)
- Would refute: Surveyed edge is above the event water level with no opening; Road floods during rain at normal tide with no overland connection
- Unresolved physical survey: Which opening admits water; anchoring surface.
- Unresolved ownership check: Agency that stores and deploys it not identified.
- Unresolved drainage assessment: Seepage and ponding behind the barrier.
- Unresolved permitting: Emergency access and right-of-way use while deployed.
- Cost: cost_estimate_unavailable

Alternatives (cards only): Strengthen alternate access routes; Review tide gate / backflow control, storage or pumping at the outfall

## Site investigations needed
- Pavement structure / layer thicknesses and materials: not available / requires site survey
- Surveyed road crown / edge-of-pavement elevation (with vertical datum): not available / requires site survey
- Storm drain inlet and pipe capacity, outfall locations and tide-gate status: not available / requires site survey
- Underground utilities (water, sewer, gas, electric, telecom) and depths: not available / requires site survey
- Soil / groundwater conditions and foundation suitability: not available / requires site survey
- Building setbacks and first-floor elevations adjacent to the right-of-way: not available / requires site survey
- Flood depth at the road surface (with datum): not available / requires site survey
- Open space between road and water for a berm footprint: not available / requires site survey
- Flood exposure of the detour route: not available / requires site survey
- Forecast lead time for deployment: not available / requires site survey
- Agency that would store and deploy the barrier: not available / requires site survey
- Outfall(s) serving the corridor and their owner: not available / requires site survey
- Storm drain pipe sizes and connectivity: not available / requires site survey
- Catch basin condition and cleaning history from the owner: not available / requires site survey

## References
- [BOS311] Boston 311 Service Requests (data.boston.gov, yearly CKAN datastore resources). https://data.boston.gov/dataset/311-service-requests
- [BWSC.adapt] BWSC Storm Viewer - Flood Modeling (adaptation scenarios). https://www.bwscstormviewer.com/flood-modeling
- [BWSC.cb] BWSC Catch Basin layer (FeatureServer behind the public Catch Basin Locator map). https://services5.arcgis.com/ji3WHeqN0AysEK5g/arcgis/rest/services/Hydrant_Search_Map1/FeatureServer/0
- [BWSC.disc] BWSC Storm Viewer - Disclaimers. https://www.bwscstormviewer.com/disclaimers
- [BWSC.maint] BWSC Preventative Maintenance programs. https://www.bwsc.org/projects/preventative-maintenance
- [BWSC.sys] BWSC Stormwater System. https://www.bwsc.org/environment-education/water-sewer-and-stormwater/stormwater-system
- [NOAA.A14] NOAA Atlas 14 Precipitation Frequency Data Server. https://hdsc.nws.noaa.gov/pfds/
- [PDDG8] MassDOT Project Development & Design Guide, Chapter 8: Drainage and Erosion Control. https://www.mass.gov/info-details/pddg-chapter-8-drainage-and-erosion-control
- [S06] Massachusetts Coast Flood Risk Model (MC-FRM) / Sea Level Rise and Coastal Flooding Viewer. https://www.mass.gov/info-details/massachusetts-sea-level-rise-and-coastal-flooding-viewer
- [S07] USGS January & March 2018 coastal flood inundation data. https://data.usgs.gov/datacatalog/data/USGS%3A60100f99d34e162231fecfa8
- [S08] NOAA CO-OPS Boston tide gauge 8443970 (API). https://api.tidesandcurrents.noaa.gov/api/prod/
- [S09] MassGIS LiDAR Terrain Data. https://www.mass.gov/info-details/massgis-data-lidar-terrain-data
- [S10] MassDOT Road Inventory (City of Boston GIS portal, Infrastructure/OpenData layer 14). https://gisportal.boston.gov/arcgis/rest/services/Infrastructure/OpenData/MapServer/14
- [S11] Climate Resilient Design Standards & Guidelines for Protection of Public Rights-of-Way (overview page). https://www.boston.gov/sites/default/files/document-file-10-2018/climate_resilient_design_drawings.pdf
- [S11.sec4#p10] Section 4.0 Sample Vegetated Berm Barrier, PDF p.10. https://www.boston.gov/sites/default/files/file/document_files/2018/10/section_4.0_sample_vegetated_berm_barrier.pdf
- [S11.sec5] Section 5.0 Sample Harborwalk Seawall Barrier. https://www.boston.gov/sites/default/files/file/document_files/2018/10/section_5.0_sample_harborwalk_seawall_barrier.pdf
- [S11.sec5#p10] Section 5.0 Sample Harborwalk Seawall Barrier, PDF p.10. https://www.boston.gov/sites/default/files/file/document_files/2018/10/section_5.0_sample_harborwalk_seawall_barrier.pdf
- [S11.sec6#p10] Section 6.0 Sample Raised Roadway Barrier, PDF p.10. https://www.boston.gov/sites/default/files/file/document_files/2018/10/section_6.0_sample_raised_roadway_barrier.pdf
- [S11.sec6#p12] Section 6.0 Sample Raised Roadway Barrier, PDF p.12. https://www.boston.gov/sites/default/files/file/document_files/2018/10/section_6.0_sample_raised_roadway_barrier.pdf
- [S11.sec6#p13] Section 6.0 Sample Raised Roadway Barrier, PDF p.13. https://www.boston.gov/sites/default/files/file/document_files/2018/10/section_6.0_sample_raised_roadway_barrier.pdf
- [S11.sec6#p3] Section 6.0 Sample Raised Roadway Barrier, PDF p.3. https://www.boston.gov/sites/default/files/file/document_files/2018/10/section_6.0_sample_raised_roadway_barrier.pdf
- [S11.sec7#p3] Section 7.0 Deployable Flood Barrier Guidance, PDF p.3. https://d8-dev2.boston.gov/sites/default/files/file/document_files/2018/10/section_7.0_deployable_flood_barrier_guidance.pdf
- [S12] Morrissey Boulevard Corridor Study Final Report (June 2025). https://www.mass.gov/doc/morrissey-boulevard-corridor-study-final-report/download
- [S12#p108] Morrissey Boulevard Corridor Study Final Report (June 2025), PDF p.108. https://www.mass.gov/doc/morrissey-boulevard-corridor-study-final-report/download
- [S12#p166] Morrissey Boulevard Corridor Study Final Report (June 2025), PDF p.166. https://www.mass.gov/doc/morrissey-boulevard-corridor-study-final-report/download
- [S12#p167] Morrissey Boulevard Corridor Study Final Report (June 2025), PDF p.167. https://www.mass.gov/doc/morrissey-boulevard-corridor-study-final-report/download
- [S12#p174] Morrissey Boulevard Corridor Study Final Report (June 2025), PDF p.174. https://www.mass.gov/doc/morrissey-boulevard-corridor-study-final-report/download
- [S12#p182] Morrissey Boulevard Corridor Study Final Report (June 2025), PDF p.182. https://www.mass.gov/doc/morrissey-boulevard-corridor-study-final-report/download
- [S12#p74] Morrissey Boulevard Corridor Study Final Report (June 2025), PDF p.74. https://www.mass.gov/doc/morrissey-boulevard-corridor-study-final-report/download
- [network_impact] Network impact record for this corridor (ranking input). 
