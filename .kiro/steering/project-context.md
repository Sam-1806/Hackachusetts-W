---
inclusion: always
---

# FloodRoute project context

FloodRoute is a network-aware flood resilience investigation tool for Boston (Morrissey Boulevard demo area). It ranks flood-exposed road corridors by how much they matter for access to emergency departments, investigates possible flooding causes, and previews candidate interventions. It is not a flood-physics engine, a dispatch navigator, or a construction cost estimator.

## Team ownership (do not edit another stream's files without telling them)

| Stream | Owner | Folders |
|:--|:--|:--|
| Road graph, ranking, counterfactual reranking | Person 1 | `analysis/network/`, `frontend/src/data/personOneRanking.ts` |
| Flood evidence, hazard mapping, 3D scene, app composition | Person 2 | `analysis/hazard/`, `analysis/historical/`, `analysis/scene/`, `frontend/` (except below) |
| Road facts, engineering evidence, cause diagnosis, concepts, investigation UI | Person 3 | `engineering/`, `frontend/src/investigation/`, `handoff/person3_demo/` |

Planning documents live in `docs/` (work split and addenda).

## Shared identifiers

- Road IDs and `graph_version` come from Person 1's OSM manifest (`osm-2026-10-24-v0.1`). Never invent road IDs.
- Demo corridors: `cor_dceb13cd52` and `cor_87278ad9ba` (Morrissey carriageways), `cor_6dece7a926` (whole road).
- Scenario IDs: `mcfrm-2050-1pct` (projected, `published_model`), `usgs-2018-01-04` and `usgs-2018-03-02` (observed).
- Geometry for the UI is EPSG:4326 `[lon, lat]`. Distances in metres, times in seconds.

## How to run and verify

- Python tests (stdlib only): `cd engineering; python -m unittest discover -s tests`
- Frontend: `npm install`, `npm run dev`, and `npm run build` (runs `tsc -b` then `vite build`).
- Spatial scripts (`exposure_from_extent.py`, `sim_ranks_values.py`) need `pip install -r engineering/requirements-overlay.txt`.
- After changing Person 3 data, regenerate in order: `build_corridor_context.py` → `cli investigate` → `cli concepts` → `cli brief` → `export_demo_bundle.py`.
