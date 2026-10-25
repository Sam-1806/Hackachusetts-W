# Person 3 → Person 2: hardcoded demo handoff

Two files, no Python, no imports from `engineering/`. Load them as static JSON. **Nothing in this bundle is mock** (`mock_banner` is `null`).

| File | What it is |
|:--|:--|
| `demo_data.json` | All panel text: why-priority (real ranking), flood evidence, road facts, possible causes, assets/owners, next checks, option cards, costs, scripted chat answers, what-if examples, citations, plus drop-in objects for your existing UI |
| `map_layers.geojson` | All map features in one EPSG:4326 collection; filter by `properties.layer` |

**Corridor:** Person 1's `cor_dceb13cd52` on their OSM graph `osm-2026-10-24-v0.1`. That's William T. Morrissey Blvd, 31 segments, the carriageway that carries Columbia Point traffic. It's the Morrissey corridor with network impact in the 2050 scenario (see below). Road IDs are Person 1's.

Regenerate (only if data changes), from `engineering/`:
`python scripts/export_demo_bundle.py --corridor cor_dceb13cd52 --context data\corridor_context_cor_dceb13cd52.json`.
The other carriageway, `cor_87278ad9ba`, has the same outputs in `results/engineering/*cor_87278ad9ba*`.

## Values for the merged `sim+ranks` UI

`sim+ranks` ranks four corridors with `flood (30) + access (45) + property (25)` points, and the access and property inputs were hand-set (`DEMO_CONTEXT` in `frontend/src/data/personOneRanking.ts`). These files replace them with computed values:

| File | What it is |
|:--|:--|
| `demoContext.real.ts` | Drop-in `REAL_CONTEXT` (same shape as `DEMO_CONTEXT`). Copy it to `frontend/src/data/` and use `REAL_CONTEXT[id] ?? DEMO_CONTEXT[id]` |
| `sim_ranks_values.json` | Raw numbers, OSM road matches, method, sources, limitations |

How the inputs are computed:
- **Access:** Person 1's network on the OSM graph (13 journeys to EDs). It's the accessibility loss when only the corridor's roads that overlap MC-FRM 2050 are closed.
- **Property:** City of Boston building footprints within 100 m of the corridor that intersect the MC-FRM 2050 extent.
- **Scaling:** both are scaled to the maximum among the four corridors.

| Corridor (UI id) | OSM roads | 2050 exposed segments | Access loss (2050) | Buildings ≤100 m / in 2050 extent / Jan 2018 / Mar 2018 | Points (flood + access + property) |
|:--|--:|--:|--:|:--|:--|
| Morrissey Blvd | 63 (both carriageways) | 48 | 42.9 s (Columbia Point → ED) | 411 / 163 / 63 / 15 | 30 + 45 + 25 = **100** |
| Day Blvd | 30 | 11 | 0 | 398 / 55 / 2 / 1 | 30 + 0 + 8 = **38** |
| Mount Vernon St | 11 | 11 | 0 | 46 / 40 / 1 / 0 | 0 + 0 + 6 = **6** |
| Inland control (Stoughton St) | 7 | 0 | 0 | 220 / 0 / 0 / 0 | 0 + 0 + 0 = **0** |

Already applied and built in a local checkout of `sim+ranks` (`tsc -b` and `vite build` pass):
1. Added `frontend/src/data/demoContext.real.ts`, and `personOneRanking.ts` now prefers it. Its assumption text says so.
2. Ran `engineering/scripts/apply_to_app_dataset.py` to replace `concept` and `investigation` in `app-dataset.json` with Person 3's objects.
3. In `App.tsx`, the "Concept fixture" badge now shows the geometry status.

**Flag before the demo:** the Morrissey flood explanation in `personOneRanking.ts` says "Since 2006 ... 167 days ... including 12 more severe high-water events". No source for those numbers is in the repo. Cite it (e.g. a NOAA gauge threshold analysis) or remove it.

## Map (Cesium or 2D)

Camera: `corridor.center_lonlat` (`[-71.04751, 42.30444]`), zoom ~15. The corridor is ~5 km, and your 3D street scene covers its central ~70%.

| `layer` | Count | Draw as | Popup / label |
|:--|--:|:--|:--|
| `flood_extent` | 3 | Translucent fill, drawn first. Show one at a time with a scenario toggle: `mcfrm-2050-1pct` (projected), `usgs-2018-01-04`, `usgs-2018-03-02` (observed) | `label` ("... footprint only, no depth") |
| `corridor` | 31 | Line 6 px, coloured by `exposure_by_scenario[<selected scenario>]`: dark blue `exposed`, light blue `not_exposed`, grey `unknown` (south end, outside the extents' window) | `label` (Person 1 road id) |
| `catch_basin` | 230 | Small dot; `style_hint` colour = mapped owner (DCR purple 168, PRIV gold 44, BWSC blue 11, DOT 7) | `label` (owner is "mapped, unverified") |
| `report_311` | 78 | Red ring | `type`, `opened`, `location`, `closure_note`; always add "report, not a confirmed cause" |
| `concept` | 3 | Shown only when its option card is clicked | `name` + `badge` |

Concept rendering rules:
- `geometry_status: "sourced_asset_location"` → solid green: the catch-basin MultiPoint (featured) and the corridor MultiLineString (raised roadway). Badge: "Existing asset location (cited). Not a design."
- `geometry_status: "schematic"` → **red dashed + visible "SCHEMATIC" label** (berm). It is drawn by us, not a published alignment.
- Optional 3D extrusion uses `display_height_m` (1.22 m raised road, 0.61 m berm) **above terrain**, labelled with `height_basis` ("guideline SAMPLE ... not a design height").
- Deployable barrier has no geometry: card only, disable "Preview".
- Previewing never changes flood polygons, road colours, or rankings.

## Dropping objects into your existing UI

`demo_data.json` holds drop-ins in the **exact shapes** of `frontend/src/domain/contracts.ts` on `simulations`. All of them typecheck against that file.

| Key | Contract | Replaces in `app-dataset.json` |
|:--|:--|:--|
| `person2_concepts[]` (use `person2_recommended_concept_id` = `ci-cor_dceb13cd52-raised_roadway`) | `ConceptIntervention` | `concept` |
| `person2_investigation` | `InvestigationResult` | `investigation` |
| `person2_ranking` (top 10 of 93 candidates, MC-FRM 2050) | `RoadRankingResult` | `ranking` |
| `person2_counterfactuals[]` (2 what-ifs, see below) | `CounterfactualResult` | `counterfactual` (pick one) |

Then, in `App.tsx`, change the hardcoded `<Badge tone="mock">Concept fixture</Badge>` to show the geometry status: "Existing road location · not a design" (or "SCHEMATIC" for the berm). Your `loadDataset.ts` remaps IDs to its fixture; once you load Person 1's OSM roads, these IDs match as-is.

| Concept | Geometry | In your 3D scene | Renders as |
|:--|:--|:--|:--|
| Raised roadway (**recommended**) | 31 real corridor segments, `sourced_asset_location` | 223 of 331 vertices | Street scene: raised slab, 1.22 m (guideline sample) × 15.2 m (MassDOT surface width). Cesium: volume |
| Vegetated berm | ~4.4 km smoothed line, 40 m bay-side, `schematic` | 42 of 61 points | Your berm profile at 0.61 m (sample), dashed, SCHEMATIC label |
| Inspect/clean inlets (featured) | 10 nearest real catch basins (MultiPoint) | 8 of 10 | Labelled points (height 0) |
| Deployable barrier | none | — | Card only |

## Panel (in this order; keys in `demo_data.json`)

1. **Banner** `mock_banner`: `null`, so hide it. Keep the "interim ranking" note from `why_priority.assumptions`.
2. **Why this corridor** `why_priority`:
   - Show `rank` of `rank_of`, `impact`, `standalone_loss`, `evidence`, and `top_of_ranking` (5 rows).
   - The current values are rank 6 of 93 in MC-FRM 2050. It recovers 0 s on its own, but its standalone loss is 42.9.
   - The #1 candidate is the 10-road Columbia Point access bundle (3,988.8 recovered).
3. **Flood evidence** `flood_evidence`: one row per scenario, with projected and observed kept visibly separate. Show each row's `caveat`; depth is not available.
   - MC-FRM 2050 1% (projected): **23 of 31** segments exposed, 8 unknown.
   - January 4, 2018 (observed): **10** exposed.
   - March 2, 2018 (observed): **2** exposed.
4. **Possible causes (not a diagnosis)** `cause_assessment`:
   - `finding` bold, `impacted_location_note` as a callout.
   - One card per `causes[]` with a status pill (`possible` yellow, `unresolved` grey, `evidence_supported` green), `supporting` / `against` lines tagged by `type`, `does_not_prove`, `unknowns`.
   - Current statuses:
     - Blocked inlets: **evidence supported**.
     - Coastal overtopping and tide-blocked drains: possible.
     - Drain capacity and grading: unresolved.
5. **Assets to inspect**: `owner_note`, `assets_note`, plus "Pipes / outfalls: owner unknown, not public".
6. **Next investigation steps** `next_checks` (numbered).
7. **Options to evaluate** `options[]` cards with "Preview on map". Below: `alternatives_cards_only`.
8. **Road facts** `road_facts` (MassDOT; units marked "(assumed)"; missing ones say "not available / requires site survey").
9. **Local precedent** `local_precedent` + "Study findings ≠ approved or built."
10. **Ask the assistant**: buttons for each `chat_script[].question`; show `blocks` with a tag per `kind` and `cites`.
11. **Network what-if**:
    - `whatif_examples.draft_default` has rerank_requested **false**.
    - After the explicit checkbox, `explicitly_selected` has rerank_requested **true**.
    - Then show the matching `person2_counterfactuals` result, as in beat 6 of the demo script.
    - Selecting the drain option shows `drainage_selected_rejected_message`.
12. **Sources** `citations` and `limitations`.

## 90-second demo script (Person 3 beat)

1. *Click Morrissey Boulevard.* "The state's 2050 1%-chance projection covers 23 of this carriageway's 31 segments. USGS footprints covered 10 in the January 2018 nor'easter. Our tool doesn't jump from that to 'raise the road'. It first asks **why** it floods."
2. *Why this corridor.* "On the network, the 2050 flood closes 354 road segments. Columbia Point loses access to an emergency department entirely. Keeping Morrissey alone open doesn't fix that, because the route is also cut on Bianculli Blvd, Columbia Rd and the Pulaski Skyway. Keeping those 10 links open together restores the 5-minute trip. So Morrissey ranks 6th of 93, and the real priority is the bundle."
3. *Possible causes.* "Three causes are in play: coastal overtopping, high tide blocking drains, and blocked inlets. Blocked inlets has a site record: a 311 catch-basin case at Morrissey and Mount Vernon St was closed in October 2025 with 'removed leaves and debris'. But a 2022 BWSC note near Freeport St says the basins there were taking water. That's evidence at the site, not proof of cause."
4. *Assets to inspect.* "The road is where the water shows up. Of the 230 mapped catch basins along it, 168 are DCR's and 11 are BWSC's, so maintenance requests have to go to the right owner."
5. *Options → Preview.* Click the inlet points, the raised-road slab, and the SCHEMATIC berm. "Real asset locations versus our sketch. Previewing changes nothing about the flood or the ranking."
6. *What-if.* Tick roads + scenario + explicit checkbox. "Assume only Morrissey stays passable: accessibility loss avoided is 0. Assume the 10-link access bundle stays passable: Columbia Point is reachable again. These are access assumptions, not proof any construction works, and a drain fix can't be sent without real flood analysis."
7. *Costs.* "Only published 2018 Boston samples, for example $13.6M for a 2,000 ft sample raised road, and never applied to drain cleaning."

## Say / don't say

| Say | Don't say |
|:--|:--|
| "possible causes", "evidence supported at the site" | "the cause is…", "X% likely", "proven" |
| "options to investigate", "concept preview" | "our recommendation", "the fix", "design" |
| "2018 sample cost for a different site" | "it would cost $X here" |
| "mapped owner, unverified" | "BWSC is responsible" |
| "in our model, these roads are treated as closed where the extent overlaps them" | "these roads will be / were closed" |
| "keeping these links open would restore access, in the network model" | "this protects the road / homes" |

## Likely judge questions

- **Is this real data?** Yes, all retrieved 2026-10-24:
  - **Roads:** Person 1's OSM graph and corridors.
  - **Road facts:** MassDOT.
  - **Flood:** your MC-FRM 2050 1% and USGS 2018 extents.
  - **Drainage evidence:** BWSC catch basins and Boston 311.
  - **Citations:** the guidelines and study.
  - **Journeys and demand weights:** Person 1's assumed planning proxies (neighborhood → nearest ED).
- **Who computed the ranking?** Person 3 re-implemented Person 1's documented method (`engineering/scripts/rank_corridors.py`). It reproduces Person 1's three mock runs within 1.3% and gives the same corridor order. It's interim until Person 1 reruns their engine on the real closures.
- **Why is Morrissey not #1?** Because no single road restores Columbia Point's access in 2050; several flooded links have to stay open together. That's the point of ranking by network effect, not flood exposure.
- **Why is "blocked inlets" green?** It has a maintenance record at the corridor itself. That doesn't mean the inlet caused the flooding; flood polygons and complaints alone can never turn a cause green.
- **Is the AI making this up?** The demo answers are deterministic and built only from cited fields; missing data is shown as missing.
- **Where's the berm from?** It's our schematic. The Morrissey study's figures are images, so no official alignment could be extracted.
