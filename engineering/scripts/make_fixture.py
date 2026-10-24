"""Build fixtures/sample_corridor_context.json for the engineering workstream.

Road geometry is copied from the real S10 Road Inventory snapshot so the
spatial join can be exercised, but road IDs, flood exposure and ranking values
are MOCK placeholders until Person 1 (manifest/ranking) and Person 2 (flood
exposure) publish real results. Every mock block says so.

Usage (from engineering/):
    python scripts/make_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "engineering" / "data" / "road_inventory_morrissey.geojson"
OUT = ROOT / "fixtures" / "sample_corridor_context.json"

# Inventory segments forming a ~0.5 mile stretch (both carriageways), lat ~42.298-42.303.
SEGMENTS = ["51287", "58285", "62908", "62774"]
GRAPH_VERSION = "fixture-v0.1"
CORRIDOR_ID = "corr-fx-morrissey-01"
NOTICE = ("ILLUSTRATIVE FIXTURE. Geometry comes from the MassDOT Road Inventory (S10). "
          "Road IDs, flood exposure, and ranking numbers are mock placeholders, not analysis results.")


def main() -> None:
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    picked: dict[str, dict] = {}
    for f in snap["features"]:
        sid = f["properties"].get("Rd_Seg_ID", "").strip()
        if sid in SEGMENTS and sid not in picked:
            picked[sid] = f

    roads = []
    for i, sid in enumerate(SEGMENTS, start=1):
        f = picked[sid]
        roads.append({
            "type": "Feature",
            "geometry": f["geometry"],
            "properties": {
                "road_id": f"fx-r-{i:03d}",
                "name": f["properties"]["St_Name"],
                "graph_version": GRAPH_VERSION,
                "geometry_source_id": "S10",
                "data_status": "mock",
                "note": "Fixture road_id; replace with Person 1 manifest IDs.",
            },
        })
    road_ids = [r["properties"]["road_id"] for r in roads]

    scenarios = [
        {"scenario_id": "mcfrm-2050-1pct", "label": "MC-FRM 2050, 1% annual exceedance (projected)",
         "kind": "future_model", "source_id": "S06", "data_status": "mock"},
        {"scenario_id": "usgs-2018-jan-event", "label": "January 2018 coastal flood (observed footprint)",
         "kind": "historical_observed", "source_id": "S07", "data_status": "mock"},
    ]

    flood_exposure = [
        {
            "scenario_id": "mcfrm-2050-1pct",
            "graph_version": GRAPH_VERSION,
            "affected_roads": [
                {"road_id": rid, "exposure": "exposed", "depth_m": None,
                 "passability": "potentially_closed", "basis": "mock", "source_id": "S06"}
                for rid in road_ids
            ],
            "extent_geojson": None,
            "provenance": {"data_status": "mock", "note": NOTICE},
        },
        {
            "scenario_id": "usgs-2018-jan-event",
            "graph_version": GRAPH_VERSION,
            "affected_roads": [
                {"road_id": road_ids[0], "exposure": "exposed", "depth_m": None,
                 "passability": "unknown", "basis": "mock", "source_id": "S07"},
                {"road_id": road_ids[1], "exposure": "unknown", "depth_m": None,
                 "passability": "unknown", "basis": "mock", "source_id": "S07"},
            ],
            "extent_geojson": None,
            "provenance": {"data_status": "mock", "note": NOTICE},
        },
    ]

    ranking = {
        "scenario_set_id": "fx-set-01",
        "graph_version": GRAPH_VERSION,
        "ranking": [{
            "corridor_id": CORRIDOR_ID,
            "road_ids": road_ids,
            "priority_rank": 1,
            "impact_metric": 1840.0,
            "metric_units": "weighted added travel seconds (mock)",
            "affected_journeys": [
                {"journey_id": "j-fx-01", "label": "Dorchester origin -> emergency department (fixture)",
                 "baseline_s": 540, "flooded_s": 780, "reachable": True},
                {"journey_id": "j-fx-02", "label": "Fire station -> Columbia Point incident point (fixture)",
                 "baseline_s": 420, "flooded_s": None, "reachable": False},
                {"journey_id": "j-fx-03", "label": "Savin Hill origin -> community center (fixture)",
                 "baseline_s": 360, "flooded_s": 410, "reachable": True},
            ],
            "detour_or_disconnect_evidence": {
                "detour_available_for": ["j-fx-01", "j-fx-03"],
                "disconnected": ["j-fx-02"],
                "detour_road_names": ["Dorchester Avenue (fixture)"],
                "detour_flood_exposure": "unknown",
            },
            "assumptions": ["Mock closure set: all corridor roads potentially closed in mcfrm-2050-1pct"],
            "provenance": {"data_status": "mock", "note": NOTICE},
        }],
    }

    fixture = {
        "fixture_notice": NOTICE,
        "data_status": "mock",
        "graph_version": GRAPH_VERSION,
        "corridor": {"corridor_id": CORRIDOR_ID,
                     "name": "William T Morrissey Boulevard (fixture stretch)",
                     "road_ids": road_ids},
        "roads": {"type": "FeatureCollection", "features": roads},
        "scenarios": scenarios,
        "flood_exposure": flood_exposure,
        "ranking": ranking,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
