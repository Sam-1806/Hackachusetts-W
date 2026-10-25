# Person 1 inputs used by the Person 3 pipeline

These are copies so the pipeline can be rerun from this branch:

- `results/`: Person 1's three engine runs (mock closures). `rank_corridors.py --validate` reproduces them. The journeys, demand weights and ED end points are read from here.
- `mock_flood_exposure_mock-morrissey-closure.json`: carries the road IDs and geometry of the 63 Morrissey OSM segments. It's used as `--manifest` for `build_corridor_context.py`; its mock exposure values are ignored.
- `build_osm_manifest.py`, `build_road_manifest.py`: Person 1's graph builders.

To rebuild the OSM network (not committed, ~40 MB), run from the repo root:

```
pip install osmnx==2.0.1
python engineering/data/p1_inputs/build_osm_manifest.py --place "Boston, Massachusetts, USA" --buffer 3000 --out <dir>
```

Then pass `<dir>/network.json` to `rank_corridors.py` and `sim_ranks_values.py`.

Some READMEs and commands elsewhere refer to `FloodRoute_Team_Handoff/...`. On this branch, those files live here.
