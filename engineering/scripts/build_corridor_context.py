"""Assemble a corridor context (same shape as fixtures/sample_corridor_context.json) from teammates' outputs.

Inputs
  --manifest   Person 1 RoadManifest JSON (road_manifest.json)
  --flood      one or more FloodExposureResult JSON files (Person 2, or a documented interim overlay)
  --ranking    optional Person 1 RoadRankingResult JSON
  --mock-ranking  carry the fixture's placeholder ranking (remapped to the new road ids, labelled mock)

Corridor selection: manifest roads whose name contains --street and whose mean latitude lies in
[--lat-min, --lat-max]. Writes only the corridor's roads and exposure rows.

Usage (from engineering/):
  python scripts/build_corridor_context.py --manifest <road_manifest.json> --flood <exposure.json> \
     --street morrissey --lat-min 42.2945 --lat-max 42.3036 --corridor-id corr-morrissey-central-01 \
     --name "William T Morrissey Boulevard (Freeport St stretch)" --mock-ranking --out ../fixtures/<file>.json
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO_META = {
    "usgs-2018-jan-event": {"label": "January 2018 coastal flood (observed footprint)", "kind": "historical_observed",
                            "source_id": "S07"},
    "usgs-2018-mar-event": {"label": "March 2018 coastal flood (observed footprint)", "kind": "historical_observed",
                            "source_id": "S07"},
    "mcfrm-2050-1pct": {"label": "MC-FRM 2050, 1% annual exceedance (projected)", "kind": "future_model",
                        "source_id": "S06"},
    "mcfrm-2070-1pct": {"label": "MC-FRM 2070, 1% annual exceedance (projected)", "kind": "future_model",
                        "source_id": "S06"},
}


def load(p: str | Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--flood", action="append", default=[])
    ap.add_argument("--ranking")
    ap.add_argument("--mock-ranking", action="store_true")
    ap.add_argument("--street", help="Select roads whose name contains this (with --lat-min/--lat-max)")
    ap.add_argument("--lat-min", type=float)
    ap.add_argument("--lat-max", type=float)
    ap.add_argument("--manifest-corridor", help="Select roads whose properties.corridor_id equals this "
                                                 "(Person 1's corridor); also used as --corridor-id by default")
    ap.add_argument("--corridor-id")
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if not a.manifest_corridor and not (a.street and a.lat_min is not None and a.lat_max is not None):
        ap.error("give --manifest-corridor, or --street with --lat-min and --lat-max")
    a.corridor_id = a.corridor_id or a.manifest_corridor
    if not a.corridor_id:
        ap.error("--corridor-id is required with --street selection")

    mf = load(a.manifest)
    gv = mf["graph_version"]
    # Accept a RoadManifest ({roads: FC}) or a FloodExposureResult-style file ({roads_geojson: FC}).
    features = (mf.get("roads") or mf.get("roads_geojson") or {}).get("features", [])
    roads = []
    for f in features:
        p = f["properties"]
        if a.manifest_corridor:
            if p.get("corridor_id") == a.manifest_corridor:
                g = copy.deepcopy(f)
                # Keep identity only; drop any exposure/passability carried by the source file (may be mock).
                g["properties"] = {k: p[k] for k in ("road_id", "corridor_id", "name", "oneway", "length_m",
                                                     "speed_mph") if k in p}
                roads.append(g)
            continue
        if a.street.lower() not in (p.get("name") or "").lower():
            continue
        ys = [c[1] for c in f["geometry"]["coordinates"]]
        if a.lat_min <= sum(ys) / len(ys) <= a.lat_max:
            roads.append(f)
    if not roads:
        raise SystemExit("No manifest roads matched the corridor selection")
    roads.sort(key=lambda f: f["geometry"]["coordinates"][0][1])
    road_ids = [f["properties"]["road_id"] for f in roads]
    ids = set(road_ids)

    flood, scenarios = [], []
    for path in a.flood:
        fe = load(path)
        if fe.get("graph_version") != gv:
            raise SystemExit(f"{path}: graph_version {fe.get('graph_version')} != manifest {gv}")
        fe = copy.deepcopy(fe)
        fe["affected_roads"] = [r for r in fe["affected_roads"] if r["road_id"] in ids]
        flood.append(fe)
        kind_from_type = {"published_future_model": "future_model", "observed_historical": "historical_observed"}
        meta = dict(SCENARIO_META.get(fe["scenario_id"], {}))
        meta.setdefault("label", fe.get("scenario_label", fe["scenario_id"]))
        meta.setdefault("kind", kind_from_type.get(fe.get("scenario_type"), "unknown"))
        meta.setdefault("source_id", fe["provenance"].get("source_id"))
        scenarios.append({"scenario_id": fe["scenario_id"], **meta, "data_status": fe["provenance"]["data_status"]})

    if a.ranking:
        ranking = load(a.ranking)
        if ranking.get("graph_version") != gv:
            raise SystemExit(f"ranking graph_version {ranking.get('graph_version')} != manifest {gv}")
    elif a.mock_ranking:
        fx = load(ROOT / "fixtures" / "sample_corridor_context.json")["ranking"]
        ranking = copy.deepcopy(fx)
        ranking["graph_version"] = gv
        for r in ranking["ranking"]:
            r["corridor_id"], r["road_ids"] = a.corridor_id, road_ids
            r["provenance"] = {"data_status": "mock",
                               "note": "PLACEHOLDER ranking carried from the fixture until Person 1's routing results arrive."}
            r["assumptions"] = ["Placeholder values; not computed on this graph."]
            r["detour_or_disconnect_evidence"]["detour_road_names"] = ["Dorchester Avenue (placeholder)"]
    else:
        ranking = {"scenario_set_id": None, "graph_version": gv, "ranking": []}

    for f in roads:
        f["properties"]["graph_version"] = gv
    statuses = sorted({s["data_status"] for s in scenarios} | {"mock" if a.mock_ranking and not a.ranking else "derived"})
    ctx = {
        "data_status": "mixed" if "mock" in statuses else "derived",
        "context_notice": (f"Roads: Person 1 manifest {gv}. Flood: {', '.join(s['scenario_id'] for s in scenarios) or 'none'}. "
                           f"Ranking: {'placeholder (mock)' if a.mock_ranking and not a.ranking else 'Person 1' if a.ranking else 'not available'}."),
        "graph_version": gv,
        "corridor": {"corridor_id": a.corridor_id, "name": a.name, "road_ids": road_ids},
        "roads": {"type": "FeatureCollection", "features": roads},
        "scenarios": scenarios,
        "flood_exposure": flood,
        "ranking": ranking,
        "sources": {"manifest": str(Path(a.manifest).name),
                    "manifest_provenance": (mf.get("metadata") or {}).get("provenance") or {
                        "note": "Road geometry and IDs taken from this file; its exposure/passability values are ignored."},
                    "flood": [Path(p).name for p in a.flood], "ranking": Path(a.ranking).name if a.ranking else None},
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ctx, indent=1), encoding="utf-8")
    print(f"wrote {out}: {len(road_ids)} roads, scenarios {[s['scenario_id'] for s in scenarios]}, "
          f"exposed {[sum(r['exposure'] == 'exposed' for r in fe['affected_roads']) for fe in flood]}")


if __name__ == "__main__":
    main()
