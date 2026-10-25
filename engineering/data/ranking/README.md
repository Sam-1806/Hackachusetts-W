# Interim corridor ranking on real flood closures (Person 3, pending Person 1)

Produced by `engineering/scripts/rank_corridors.py` on Person 1's OSM graph `osm-2026-10-24-v0.1`. The inputs are:
- **Network:** rebuilt with Person 1's `build_osm_manifest.py` on 2026-10-24. All 63 Morrissey road IDs and all road IDs in their three runs match.
- **Journeys and method:** Person 1's 13 journeys, 5 emergency departments, demand weights and 3600 s unreachable penalty, from their `ranking_detail.json` (the mock runs in `results (2)`).
- **Closures:** network-wide real exposure in `engineering/data/hazard/osm_net/`. Roads whose centerline overlaps the extent are treated as closed (assumed).

**Validation:** the script first reruns Person 1's three mock scenarios. It matches them within 1.3% on every journey baseline, with the same disrupted journeys and the same corridor order. Corridor impacts differ by ≤ 4.3 demand-weighted seconds. The small differences come from origin/destination snapping and float rounding. Please replace these files with Person 1's own engine output when available.

## Results

| Scenario | Closed roads | Disrupted journeys | #1 candidate | Morrissey `cor_dceb13cd52` | Morrissey `cor_87278ad9ba` |
|:--|--:|:--|:--|:--|:--|
| MC-FRM 2050 1% | 354 | Columbia Point → ED **unreachable** | Bundle of the 10 closed roads on Columbia Point's baseline route (Bianculli Blvd, Columbia Rd, 3 Morrissey segments, Pulaski Skyway, 2 unnamed links): recovers 3,988.8 | rank 6 of 93, recovers 0 alone, standalone 42.9 | rank 93 of 93, 0 |
| USGS Jan 4, 2018 | 103 | Columbia Point → ED 321 s → 386 s (+21%) | Pulaski Skyway + 1 link: recovers 73.0 | rank 39 of 41, 0 | rank 40 of 41, 0 |
| USGS Mar 2, 2018 | 28 | Same as January | Same as January | rank 20 of 22, 0 | rank 21 of 22, 0 |

How to read the 2050 result:
- Columbia Point loses access because **several** flooded links on its route close together.
- Keeping Morrissey alone open recovers nothing, because the route stays cut elsewhere.
- Keeping the whole route bundle open restores the 321 s trip. That is the interaction effect the work split asked to capture.

**Candidates:** Person 1's 7 corridors, plus closures grouped by street name, closed unnamed links on disrupted routes, and one "restore baseline route" bundle per disrupted journey (ids `p3c_*`, `p3b_*`).

**Counterfactuals (2050):**
- `counterfactual_mcfrm-2050-1pct_ci-cor_dceb13cd52-raised_roadway.json`: Morrissey northbound kept passable. Loss avoided 0.
- `counterfactual_mcfrm-2050-1pct_whatif-columbia-point-access-bundle.json`: the 10-road bundle kept passable. Loss avoided 3,988.8, and Columbia Point is reachable again (321 s).

Both are idealized access assumptions only: no hydraulic effect or flood-extent change is implied.
