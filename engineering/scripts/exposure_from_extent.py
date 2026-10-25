"""Road exposure from an already-clipped EPSG:4326 flood extent GeoJSON (Person 2's artifacts).

Takes Person 2's extents from the `simulations` branch (results/hazard/*.geojson,
results/historical/*.geojson) and Person 1's RoadManifest, and writes a FloodExposureResult
keyed to the manifest road ids. Fields follow Person 2's `flood-exposure-result/v1` plus
`provenance.data_status` (used by engineering/).

Rule: a road is "exposed" if its centerline intersects the extent; "not_exposed" otherwise.
Only roads fully inside the extent's bbox are evaluated. depth_m = null; passability = "unknown".

Needs: pip install -r engineering/requirements-overlay.txt
Usage (from engineering/):
  python scripts/exposure_from_extent.py --extent data/hazard/mcfrm_2050_1pct_morrissey.geojson \
     --manifest <road_manifest.json> --scenario mcfrm-2050-1pct --scenario-type published_future_model \
     --label "MC-FRM 2050, 1% annual exceedance (projected)" --source-id S06 \
     --out data/hazard/flood_exposure_mcfrm-2050-1pct.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shapely.geometry import LineString, box, mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

DATA_STATUS = {"published_future_model": "published_model", "observed_historical": "observed", "illustrative": "mock"}
LIMITS = {
    "published_future_model": "Modeled future condition (annual exceedance), not a historical date or live forecast.",
    "observed_historical": "Estimated event peak footprint from high-water marks/sensors; not time-resolved.",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--extent", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--scenario-type", required=True, choices=sorted(DATA_STATUS))
    ap.add_argument("--label", required=True)
    ap.add_argument("--source-id", required=True, help="engineering/evidence source id (S06 MC-FRM, S07 USGS)")
    ap.add_argument("--source-ref", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--all-roads", action="store_true",
                    help="Also list roads outside the extent window, with exposure 'unknown'")
    a = ap.parse_args()

    ext = json.loads(Path(a.extent).read_text(encoding="utf-8"))
    polys = [shape(f["geometry"]) for f in ext["features"] if f.get("geometry")]
    polys = [p if p.is_valid else p.buffer(0) for p in polys]
    foot = unary_union(polys)
    bbox = ext.get("bbox") or list(foot.bounds)
    win = box(*bbox)

    mf = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    feats = mf["roads"]["features"] if "roads" in mf else mf["roads_geojson"]["features"]
    lines = [LineString(f["geometry"]["coordinates"]) for f in feats]
    inside = [i for i, ln in enumerate(lines) if win.contains(ln)]
    # With --all-roads, roads not fully inside the extent window are kept as "unknown" (not evaluated).
    partial = [i for i, ln in enumerate(lines) if a.all_roads and i not in set(inside) and win.intersects(ln)]
    outside = [i for i in range(len(lines)) if a.all_roads and i not in set(inside)]
    roads = [feats[i] for i in inside]
    tree = STRtree([lines[i] for i in inside])
    hit = set(tree.query(foot, predicate="intersects").tolist())

    basis = "official_extent" if a.scenario_type == "published_future_model" else "historical_footprint"
    pbasis = ("Extent geometry overlap only; road-deck elevation, local water depth, and drivability "
              "were not established.")
    result = {
        "schema_version": "flood-exposure-result/v1",
        "scenario_id": a.scenario,
        "scenario_label": a.label,
        "graph_version": mf["graph_version"],
        "scenario_type": a.scenario_type,
        "affected_roads": [{"road_id": f["properties"]["road_id"],
                            "exposure": "exposed" if i in hit else "not_exposed",
                            "depth_m": None, "passability": "unknown", "passability_basis": pbasis,
                            "basis": basis, "source_id": a.source_id} for i, f in enumerate(roads)]
                          + [{"road_id": feats[i]["properties"]["road_id"], "exposure": "unknown",
                              "depth_m": None, "passability": "unknown",
                              "passability_basis": ("Road extends beyond the flood-extent study window; not evaluated."
                                                    + (" Partly inside the window." if i in set(partial) else "")),
                              "basis": basis, "source_id": a.source_id} for i in outside],
        "extent_geojson": {"type": "Feature", "geometry": mapping(foot.simplify(0.00001)),
                           "properties": {"scenario_id": a.scenario, "source_id": a.source_id, "bbox": bbox}},
        "provenance": {
            "data_status": DATA_STATUS[a.scenario_type],
            "source_id": a.source_id,
            "extent_file": Path(a.extent).name,
            "source_ref": a.source_ref or ext.get("metadata", {}).get("source_url") or "",
            "road_source": f"Person 1 manifest {mf['graph_version']}",
            "method": "Centerline intersects extent -> exposed (shapely). Roads fully inside the extent bbox only.",
            "limitations": [
                LIMITS.get(a.scenario_type, ""),
                "Overlap is exposure evidence, not confirmed inundation or impassability; passability 'unknown'.",
                "No depth in the extent; depth_m is null.",
            ],
        },
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result), encoding="utf-8")
    print(f"{a.scenario}: {len(roads)} roads evaluated, {len(hit)} exposed, {len(outside)} unknown "
          f"(outside window) -> {out}")


if __name__ == "__main__":
    main()
