# MC-FRM hazard ingestion

This small standard-library pipeline queries the official `MA_2050_1Perc_v11`
ArcGIS feature layer, asks the service to transform it from EPSG:26986 to
EPSG:4326, clips the statewide feature to a bounded Morrissey Boulevard study
area, and computes line/polygon overlap against a road manifest.

Run from the repository root:

```bash
python3 analysis/hazard/fetch_mcfrm.py
python3 -m unittest discover -s analysis/hazard/tests -v
```

To replace the labeled road fixture with Person 1's manifest:

```bash
python3 analysis/hazard/fetch_mcfrm.py \
  --road-manifest data/normalized/roads/road_manifest.geojson
```

For deterministic/offline regeneration after saving an ArcGIS GeoJSON query:

```bash
python3 analysis/hazard/fetch_mcfrm.py \
  --offline-feature /path/to/arcgis-query.geojson
```

The overlap output deliberately keeps `depth_m: null` and `passability:
"unknown"`. The published future extent is not an observed event, live
forecast, measured road depth, or proof that a road is impassable.
