"""Real replacements for the illustrative DEMO_CONTEXT in sim+ranks `frontend/src/data/personOneRanking.ts`.

For each of the four corridors that UI ranks (fixture:morrissey-boulevard, fixture:day-boulevard,
fixture:mount-vernon, fixture:inland-control) this computes:

  access   - network accessibility loss if ONLY this corridor's flood-exposed roads close
             (Person 1's method via rank_corridors.Engine on the OSM graph; 13 journeys to EDs,
             demand weights, unreachable = +3600 s), plus seconds recovered by keeping it open
             when ALL exposed roads close.
  property - City of Boston building footprints within BUFFER_M of the corridor centerline, and
             how many of them intersect each flood extent (MC-FRM 2050 1%, USGS Jan/Mar 2018).
             Exposure counts only; no damage or value is implied.

Points use the UI's own weights (access 45, property 25) scaled to the maximum among the four
corridors, so the relative order is data-driven. Flood points (30) stay as the UI computes them.

Needs: pip install -r engineering/requirements-overlay.txt   (shapely, pyproj)
Usage (from engineering/):
  python scripts/sim_ranks_values.py --network <network.json> --p1-results "<results>" \
     --sim-ranks <worktree of origin/sim+ranks> --out ../handoff/person3_demo/sim_ranks_values.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, Point, box, shape
from shapely.ops import transform, unary_union
from shapely.strtree import STRtree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rank_corridors as R  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HAZ = ROOT / "engineering" / "data" / "hazard"
BUILDINGS = "https://gis.bostonplans.org/hosting/rest/services/Boston_Buildings/FeatureServer/9"
BUFFER_M = 100.0
MATCH_M = 40.0
SCENARIOS = [
    ("mcfrm-2050-1pct", HAZ / "mcfrm_2050_1pct_morrissey.geojson", HAZ / "osm_net/flood_exposure_mcfrm-2050-1pct.json",
     "MC-FRM 2050 1% (projected)"),
    ("usgs-2018-01-04", HAZ / "usgs_2018_01_04_morrissey.geojson", HAZ / "osm_net/flood_exposure_usgs-2018-01-04.json",
     "Jan 4, 2018 (observed)"),
    ("usgs-2018-03-02", HAZ / "usgs_2018_03_02_morrissey.geojson", HAZ / "osm_net/flood_exposure_usgs-2018-03-02.json",
     "Mar 2, 2018 (observed)"),
]
to_m = Transformer.from_crs("EPSG:4326", "EPSG:26986", always_xy=True).transform  # MA State Plane, metres


def get_json(url: str, params: dict) -> dict:
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "FloodRoute-P3"})
    with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 (fixed https host)
        return json.load(r)


def fetch_buildings(bbox: tuple[float, float, float, float]) -> list[dict]:
    """Page by OBJECTID chunks (offset paging on this service can stop early)."""
    geom = {"geometry": ",".join(map(str, bbox)), "geometryType": "esriGeometryEnvelope", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects"}
    ids = sorted(get_json(f"{BUILDINGS}/query", {"where": "1=1", **geom, "returnIdsOnly": "true", "f": "json"})
                 .get("objectIds") or [])
    feats = []
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        d = get_json(f"{BUILDINGS}/query", {"objectIds": ",".join(map(str, chunk)), "outFields": "OBJECTID,PART_USE,BRA_Land_Use",
                                            "outSR": "4326", "returnGeometry": "true", "f": "geojson"})
        feats += d.get("features", [])
    if len(feats) != len(ids):
        raise RuntimeError(f"building fetch incomplete: {len(feats)} of {len(ids)}")
    return feats


def roads_by_name_near(g: R.Graph, name: str, line_ll: list, radius_m: float) -> list[str]:
    """OSM roads with this name whose midpoint is within radius_m of the fixture line."""
    ref = transform(to_m, LineString(line_ll))
    out = []
    for rid, r in g.road.items():
        if name.lower() not in (r["name"] or "").lower():
            continue
        c = r["coords"]
        if ref.distance(Point(to_m(*c[len(c) // 2][:2]))) <= radius_m:
            out.append(rid)
    return sorted(out)


def dominant_street_near(g: R.Graph, line_ll: list, radius_m: float) -> str | None:
    """Name with the most OSM length within radius_m of the fixture line."""
    ref = transform(to_m, LineString(line_ll))
    acc: dict[str, float] = {}
    for r in g.road.values():
        if not r["name"]:
            continue
        c = r["coords"]
        if ref.distance(Point(to_m(*c[len(c) // 2][:2]))) <= radius_m:
            acc[r["name"]] = acc.get(r["name"], 0.0) + float(r["L"])
    return max(acc, key=acc.get) if acc else None


def match_roads(g: R.Graph, line_ll: list, name_hint: str | None) -> list[str]:
    """OSM roads whose every vertex lies within MATCH_M of the fixture line (optionally same name)."""
    ref = transform(to_m, LineString(line_ll))
    out = []
    for rid, r in g.road.items():
        if name_hint and name_hint.lower() not in (r["name"] or "").lower():
            continue
        c = r["coords"]
        if ref.distance(Point(to_m(*c[0][:2]))) > MATCH_M or ref.distance(Point(to_m(*c[-1][:2]))) > MATCH_M:
            continue
        if all(ref.distance(Point(to_m(*p[:2]))) <= MATCH_M for p in c):
            out.append(rid)
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--network", required=True)
    ap.add_argument("--p1-results", required=True)
    ap.add_argument("--sim-ranks", required=True, help="Checkout of origin/sim+ranks")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    net = R.load(a.network)
    scc_path = Path(a.network).with_name("main_scc_node_ids.json")
    g = R.Graph(net, set(R.load(scc_path)) if scc_path.exists() else None)
    detail, ends, p1_corridors, _ = R.load_p1(Path(a.p1_results))
    eng = R.Engine(g, detail, ends)

    # --- Map sim+ranks fixture corridors to OSM roads ---
    sim = Path(a.sim_ranks) / "frontend" / "public" / "data"
    fixture = {f["properties"]["road_id"]: f for f in R.load(sim / "app-dataset.json")["exposure"]["roads_geojson"]["features"]}
    mroads = R.load(sim / "morrissey_roads.geojson")["features"]
    inland_line = next(f for f in mroads if f["properties"]["corridor_id"] == "fixture:inland-control")["geometry"]["coordinates"]
    corridors = {
        "fixture:morrissey-boulevard": {"label": "Morrissey Boulevard", "road_ids": p1_corridors["cor_6dece7a926"]["road_ids"],
                                        "osm_corridor": "cor_6dece7a926 (Person 1 whole-road bundle, both carriageways)"},
        "fixture:day-boulevard": {"label": "Day Boulevard", "road_ids": p1_corridors["cor_5a83bdd655"]["road_ids"],
                                  "osm_corridor": "cor_5a83bdd655 (Person 1 William J. Day Boulevard)"},
        "fixture:mount-vernon": {"label": "Mount Vernon Street",
                                 "road_ids": roads_by_name_near(g, "Mount Vernon Street",
                                                                fixture["fixture-road-mount-vernon"]["geometry"]["coordinates"], 250),
                                 "osm_corridor": "OSM 'Mount Vernon Street' segments within 250 m of the fixture line "
                                                 "(fixture is a hand-drawn approximation)"},
    }
    inland_name = dominant_street_near(g, inland_line, 120)
    corridors["fixture:inland-control"] = {
        "label": f"Inland control corridor ({inland_name})",
        "road_ids": roads_by_name_near(g, inland_name, inland_line, 150) if inland_name else [],
        "osm_corridor": f"OSM '{inland_name}' segments within 150 m of the fixture line (dominant street along it)"}
    for cid, c in corridors.items():
        c["road_names"] = sorted({g.road[r]["name"] or "(unnamed)" for r in c["road_ids"]})
        c["length_km"] = round(sum(float(g.road[r]["L"]) for r in c["road_ids"]) / 1000, 2)
        print(f"{cid}: {len(c['road_ids'])} OSM roads, {c['length_km']} km, names {c['road_names'][:4]}")

    # --- Access: standalone loss and marginal recovery per scenario ---
    base = eng.run(frozenset(), {})
    for sid, _, exp_path, _ in SCENARIOS:
        fe = R.load(exp_path)
        closed = frozenset(r["road_id"] for r in fe["affected_roads"] if r["exposure"] == "exposed")
        full = eng.run(closed, base)
        total = eng.loss(full, base)
        for cid, c in corridors.items():
            mine = frozenset(r for r in c["road_ids"] if r in closed)
            if mine:
                only = {j["journey_id"]: eng.time(j["journey_id"], mine) for j in eng.journeys}
                standalone = eng.loss(only, base)
                reopened = {j["journey_id"]: eng.time(j["journey_id"], closed - mine) for j in eng.journeys}
                recovered = total - eng.loss(reopened, base)
                hit = [j["journey_id"] for j in eng.journeys if only[j["journey_id"]][0] != base[j["journey_id"]][0]]
                ev = []
                for jid in hit:
                    b0, t1 = base[jid][0], only[jid][0]
                    lab = next(j["label"] for j in eng.journeys if j["journey_id"] == jid)
                    ev.append(f"{lab}: {b0:.0f} s -> " + ("unreachable" if t1 == R.INF else f"{t1:.0f} s (+{(t1 - b0) / b0 * 100:.0f}%)"))
            else:
                standalone, recovered, hit, ev = 0.0, 0.0, [], []
            c.setdefault("access", {})[sid] = {"exposed_roads": len(mine), "standalone_loss_s": round(standalone, 1),
                                               "recovered_if_kept_open_s": round(recovered, 1),
                                               "journeys_affected_alone": hit, "evidence": ev}
        print(f"access {sid}: done ({len(closed)} closed network-wide)")

    # --- Property: buildings near each corridor, and in each extent ---
    lines_m = {cid: unary_union([transform(to_m, LineString(g.road[r]["coords"])) for r in c["road_ids"]])
               for cid, c in corridors.items() if c["road_ids"]}
    allb = unary_union(list(lines_m.values())).buffer(BUFFER_M + 50)
    to_ll = Transformer.from_crs("EPSG:26986", "EPSG:4326", always_xy=True).transform
    bbox = transform(to_ll, allb).bounds
    bfeats = fetch_buildings(bbox)
    bgeom = [transform(to_m, shape(f["geometry"])) for f in bfeats if f.get("geometry")]
    bgeom = [b if b.is_valid else b.buffer(0) for b in bgeom]
    tree = STRtree(bgeom)
    extents = {sid: transform(to_m, unary_union([shape(f["geometry"]) for f in R.load(p)["features"]]))
               for sid, p, _, _ in SCENARIOS}
    ext_window = {sid: transform(to_m, box(*R.load(p)["bbox"])) for sid, p, _, _ in SCENARIOS}
    print(f"buildings fetched: {len(bgeom)}")
    for cid, c in corridors.items():
        if cid not in lines_m:
            c["property"] = {"buildings_within_buffer": 0}
            continue
        zone = lines_m[cid].buffer(BUFFER_M)
        near = [bgeom[i] for i in tree.query(zone, predicate="intersects")]
        c["property"] = {"buildings_within_buffer": len(near), "buffer_m": BUFFER_M, "by_scenario": {}}
        for sid, _, _, lab in SCENARIOS:
            inside_window = zone.within(ext_window[sid]) or zone.intersection(ext_window[sid]).area / zone.area > 0.99
            n = sum(1 for b in near if b.intersects(extents[sid]))
            c["property"]["by_scenario"][sid] = {"buildings_in_extent": n, "label": lab,
                                                 "zone_fully_inside_extent_window": bool(inside_window)}
        print(f"property {cid}: {len(near)} buildings within {BUFFER_M:.0f} m; "
              f"in extent: {[c['property']['by_scenario'][s]['buildings_in_extent'] for s, *_ in SCENARIOS]}")

    # --- Points with the UI's weights, scaled to the max among the four corridors ---
    def scaled(values: dict, weight: float) -> dict:
        m = max(values.values()) if values else 0
        return {k: (round(weight * v / m) if m > 0 else 0) for k, v in values.items()}

    acc_raw = {cid: c["access"]["mcfrm-2050-1pct"]["standalone_loss_s"] for cid, c in corridors.items()}
    prop_raw = {cid: c["property"].get("by_scenario", {}).get("mcfrm-2050-1pct", {}).get("buildings_in_extent", 0)
                for cid, c in corridors.items()}
    acc_pts, prop_pts = scaled(acc_raw, 45), scaled(prop_raw, 25)

    demo_context = {}
    for cid, c in corridors.items():
        a50, aj = c["access"]["mcfrm-2050-1pct"], c["access"]["usgs-2018-01-04"]
        p = c["property"]
        pb = p.get("by_scenario", {})
        evidence = "; ".join(e.replace(" (UMass Boston area)", "").replace(" -> nearest emergency department: ", " → nearest ED goes from ")
                             .replace(" s -> ", " to ") for e in a50["evidence"])
        access_note = (
            f"2050 1% flood (MC-FRM): {a50['exposed_roads']} of {len(c['road_ids'])} segments flooded; closing them adds "
            f"{a50['standalone_loss_s']:.0f} demand-weighted seconds to neighborhood-to-ED trips"
            + (f"; {evidence}" if evidence else "")
            + f". Jan 2018: {aj['exposed_roads']} segments, {aj['standalone_loss_s']:.0f} s. Assumes flooded = closed."
        )
        property_note = (
            f"{p.get('buildings_within_buffer', 0)} buildings within {BUFFER_M:.0f} m: "
            f"{pb.get('mcfrm-2050-1pct', {}).get('buildings_in_extent', 0)} in the 2050 1% extent, "
            f"{pb.get('usgs-2018-01-04', {}).get('buildings_in_extent', 0)} in the Jan 2018 footprint, "
            f"{pb.get('usgs-2018-03-02', {}).get('buildings_in_extent', 0)} in Mar 2018. Overlap only, not damage."
        )
        demo_context[cid] = {"accessPoints": acc_pts[cid], "propertyPoints": prop_pts[cid],
                             "accessNote": access_note, "propertyNote": property_note}

    out = {
        "purpose": "Drop-in replacement for DEMO_CONTEXT in sim+ranks frontend/src/data/personOneRanking.ts",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "graph_version": g.version,
        "points_method": {
            "accessPoints": "45 x (MC-FRM 2050 standalone accessibility loss / max among the four corridors)",
            "propertyPoints": "25 x (buildings within 100 m intersecting the MC-FRM 2050 extent / max among the four)",
            "floodPoints": "unchanged: the UI computes 0-30 from USGS 2018 footprint overlap",
            "weights": "flood 30 / access 45 / property 25, as already used by the UI",
        },
        "DEMO_CONTEXT": demo_context,
        "raw": corridors,
        "sources": {
            "network": f"Person 1 OSM graph {g.version} (build_osm_manifest.py), 13 journeys from Person 1 ranking_detail.json",
            "flood": "Person 2 extents on simulations: MC-FRM 2050 1% (Woods Hole Group / MA ArcGIS), USGS Jan & Mar 2018",
            "buildings": BUILDINGS + " (City of Boston / BPDA 'Boston Buildings', public)",
            "method": "engineering/scripts/rank_corridors.py (validated against Person 1's 3 mock runs) + this script",
        },
        "limitations": [
            "Access uses assumed journeys/weights and treats extent overlap as closure; not verified impassability.",
            "Building counts are exposure proximity, not damage or loss.",
            "Points are scaled relative to these four corridors only.",
            "Interim computation by Person 3; replace with Person 1's engine output when available.",
        ],
        "flag_for_ui": "The Morrissey flood explanation in personOneRanking.ts cites '167 days since 2006 ... 12 more severe "
                       "high-water events'. No source for that figure is in the repo; cite it or remove it before the demo.",
    }
    Path(a.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nDEMO_CONTEXT points:")
    for cid, v in demo_context.items():
        print(f"  {cid:30} access {v['accessPoints']:>2}  property {v['propertyPoints']:>2}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
