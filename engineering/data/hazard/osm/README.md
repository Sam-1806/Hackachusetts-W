# Real flood exposure on Person 1's OSM graph (`osm-2026-10-24-v0.1`)

These replace `mock_flood_exposure_mock-morrissey-closure.json` (roads selected by street name).

- **Same roads:** the 63 Morrissey Blvd road IDs and geometries from that mock file (corridors `cor_87278ad9ba`, `cor_dceb13cd52`).
- **Extents:** Person 2's clipped extents from the `simulations` branch (`results/hazard`, `results/historical`).
- **Rule:** a road is `exposed` if its centerline intersects the extent and `not_exposed` otherwise.
- **Unknown roads:** 14 roads at the south end extend past the extents' study window (lat < 42.29), so they are `unknown` (not evaluated).

| File | Scenario | `cor_87278ad9ba` exposed / not / unknown | `cor_dceb13cd52` exposed / not / unknown |
|:--|:--|:--|:--|
| `flood_exposure_mcfrm-2050-1pct.json` | MC-FRM 2050 1% (projected, `published_model`) | 25 / 1 / 6 | 23 / 0 / 8 |
| `flood_exposure_usgs-2018-01-04.json` | Jan 4, 2018 (observed) | 12 / 14 / 6 | 10 / 13 / 8 |
| `flood_exposure_usgs-2018-03-02.json` | Mar 2, 2018 (observed) | 1 / 25 / 6 | 2 / 21 / 8 |

Notes for routing:
- `passability` is `unknown` everywhere: an extent overlap doesn't prove a closure, and there's no depth. If the router closes `exposed` roads, record that as a scenario assumption in `RoadRankingResult.assumptions`, e.g. "exposed roads treated as closed".
- Only Morrissey roads are covered. For realistic detours, run the same overlay on the **full** manifest, so that flooded side streets close too:
  ```
  python engineering/scripts/exposure_from_extent.py --all-roads --manifest <road_manifest.json> \
     --extent engineering/data/hazard/mcfrm_2050_1pct_morrissey.geojson --scenario mcfrm-2050-1pct \
     --scenario-type published_future_model --label "MC-FRM 2050 1%" --source-id S06 --out <file>.json
  ```
  It needs `pip install -r engineering/requirements-overlay.txt`. Person 2's `analysis/hazard/fetch_mcfrm.py --road-manifest` does the same for MC-FRM.

**Network-wide version:** `engineering/data/hazard/osm_net/` covers all 1,582 roads of the full OSM manifest inside the extents' window: MC-FRM 2050 has 354 exposed, January 2018 has 103, March 2018 has 28. Use these for routing so that flooded side streets close too.

**Interim ranking:** `engineering/data/ranking/` holds a ranking computed from those closures by re-implementing your documented method. It is validated against your three mock runs; see its README. Please rerun your engine on `osm_net/` and send back the `RoadRankingResult` and `CounterfactualResult`, so the interim files can be replaced.
